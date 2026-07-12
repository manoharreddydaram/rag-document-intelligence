"""Ingestion pipeline: load -> chunk -> classify -> embed -> store.

Supports mixed unstructured input (PDF, plain text, email .eml, .docx).
Each chunk is stored in a persistent ChromaDB collection with metadata
(source filename, chunk index, predicted category, classifier confidence)
needed for citation-grounded retrieval later in the pipeline.
"""
import email
import hashlib
import logging
import os
from dataclasses import dataclass, field
from email import policy
from functools import lru_cache
from typing import List, Optional

import chromadb
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from transformers import pipeline as hf_pipeline

from src import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest")


@dataclass
class Chunk:
    chunk_id: str
    filename: str
    chunk_index: int
    text: str
    category: str = "uncategorized"
    confidence: float = 0.0


@dataclass
class IngestResult:
    filename: str
    status: str  # "ok" | "skipped" | "failed"
    num_chunks: int = 0
    category: Optional[str] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------
# Parsing — one function per format. Each raises on failure; the caller is
# responsible for catching and logging so one bad file doesn't kill a batch.
# --------------------------------------------------------------------------

def parse_pdf(path: str) -> str:
    with fitz.open(path) as doc:
        return "\n".join(page.get_text() for page in doc)


def parse_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_eml(path: str) -> str:
    with open(path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    parts = [f"Subject: {msg.get('subject', '')}", f"From: {msg.get('from', '')}"]
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is not None:
        parts.append(body.get_content())
    else:
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                parts.append(part.get_content())
    return "\n".join(parts)


def parse_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)


_PARSERS = {
    ".pdf": parse_pdf,
    ".txt": parse_txt,
    ".eml": parse_eml,
    ".docx": parse_docx,
}


def parse_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext not in _PARSERS:
        raise ValueError(f"Unsupported file extension: {ext}")
    text = _PARSERS[ext](path)
    if not text or not text.strip():
        raise ValueError("Parsed document produced no extractable text")
    return text


def load_documents(dir_path: str) -> List[dict]:
    """Load every supported file in dir_path. Parsing failures are logged
    and skipped rather than raised, so one bad file doesn't crash a batch."""
    documents = []
    if not os.path.isdir(dir_path):
        logger.warning("Directory does not exist: %s", dir_path)
        return documents

    for filename in sorted(os.listdir(dir_path)):
        path = os.path.join(dir_path, filename)
        ext = os.path.splitext(filename)[1].lower()
        if not os.path.isfile(path) or ext not in config.SUPPORTED_EXTENSIONS:
            continue
        try:
            text = parse_document(path)
            documents.append({"filename": filename, "text": text})
        except Exception as exc:  # noqa: BLE001 - intentional catch-all per doc
            logger.warning("Skipping %s: failed to parse (%s)", filename, exc)
    return documents


# --------------------------------------------------------------------------
# Chunking
# --------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, filename: str) -> List[Chunk]:
    """Recursive character splitting sized in words (~500 words/chunk,
    ~18% overlap) as a token-count proxy, avoiding a tokenizer dependency
    just for chunk sizing."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE_WORDS,
        chunk_overlap=config.CHUNK_OVERLAP_WORDS,
        length_function=_word_count,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(text)
    chunks = []
    for i, piece in enumerate(pieces):
        chunk_id = hashlib.sha1(f"{filename}::{i}".encode()).hexdigest()[:16]
        chunks.append(Chunk(chunk_id=chunk_id, filename=filename, chunk_index=i, text=piece))
    return chunks


# --------------------------------------------------------------------------
# Classification (zero-shot) — run once per document (not per chunk) for
# speed; the predicted category + confidence is propagated to every chunk
# belonging to that document.
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_classifier():
    logger.info("Loading zero-shot classifier: %s", config.ZERO_SHOT_MODEL)
    return hf_pipeline("zero-shot-classification", model=config.ZERO_SHOT_MODEL)


def classify_document(text: str) -> tuple:
    classifier = _get_classifier()
    # Truncate to keep inference fast; the opening of a document is
    # normally sufficient signal for its overall category.
    excerpt = text[:2000]
    result = classifier(excerpt, candidate_labels=config.CATEGORIES, multi_label=False)
    return result["labels"][0], float(result["scores"][0])


# --------------------------------------------------------------------------
# Embedding
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    logger.info("Loading embedding model: %s", config.EMBEDDING_MODEL)
    return SentenceTransformer(config.EMBEDDING_MODEL)


def embed_texts(texts: List[str]):
    embedder = get_embedder()
    return embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)


# --------------------------------------------------------------------------
# Vector store
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_chroma_client():
    os.makedirs(config.CHROMA_PERSIST_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def delete_document_chunks(filename: str) -> None:
    """Remove any previously stored chunks for a filename, so re-ingesting
    the same file doesn't leave stale duplicates behind."""
    collection = get_collection()
    existing = collection.get(where={"filename": filename})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def ingest_file(path: str) -> IngestResult:
    filename = os.path.basename(path)
    try:
        text = parse_document(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping %s: failed to parse (%s)", filename, exc)
        return IngestResult(filename=filename, status="skipped", error=str(exc))

    try:
        chunks = chunk_text(text, filename)
        if not chunks:
            return IngestResult(filename=filename, status="skipped", error="no chunks produced")

        category, confidence = classify_document(text)
        for chunk in chunks:
            chunk.category = category
            chunk.confidence = confidence

        embeddings = embed_texts([c.text for c in chunks])

        delete_document_chunks(filename)
        collection = get_collection()
        collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=[e.tolist() for e in embeddings],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                    "category": c.category,
                    "confidence": c.confidence,
                }
                for c in chunks
            ],
        )
        return IngestResult(filename=filename, status="ok", num_chunks=len(chunks), category=category)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to ingest %s: %s", filename, exc)
        return IngestResult(filename=filename, status="failed", error=str(exc))


def ingest_directory(dir_path: str = None) -> List[IngestResult]:
    dir_path = dir_path or config.SAMPLE_DOCS_DIR
    results = []
    if not os.path.isdir(dir_path):
        logger.warning("Directory does not exist: %s", dir_path)
        return results

    for filename in sorted(os.listdir(dir_path)):
        path = os.path.join(dir_path, filename)
        ext = os.path.splitext(filename)[1].lower()
        if not os.path.isfile(path) or ext not in config.SUPPORTED_EXTENSIONS:
            continue
        results.append(ingest_file(path))
    return results


def list_documents() -> List[dict]:
    """Return one entry per unique ingested document with its tagged category."""
    collection = get_collection()
    data = collection.get()
    seen = {}
    for metadata in data["metadatas"]:
        filename = metadata["filename"]
        if filename not in seen:
            seen[filename] = {
                "filename": filename,
                "category": metadata["category"],
                "confidence": metadata["confidence"],
                "num_chunks": 0,
            }
        seen[filename]["num_chunks"] += 1
    return sorted(seen.values(), key=lambda d: d["filename"])


if __name__ == "__main__":
    results = ingest_directory()
    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status in ("skipped", "failed"))
    total_chunks = sum(r.num_chunks for r in results)
    logger.info("Ingestion complete: %d ok, %d skipped/failed, %d total chunks", ok, skipped, total_chunks)
    for r in results:
        if r.status != "ok":
            logger.warning("  %s: %s (%s)", r.filename, r.status, r.error)
