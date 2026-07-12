"""Hybrid retrieval: dense (ChromaDB embeddings) + sparse (BM25 keyword),
merged by chunk id and reranked with a cross-encoder.

Why hybrid: dense embeddings capture semantic similarity but can miss exact
identifiers that matter in enterprise search — ticket numbers, project IDs,
policy names, dollar figures. BM25 catches those exact/keyword matches that
embeddings sometimes blur past. Running both and merging recovers cases
either retriever alone would miss.

Why rerank: dense and sparse scores live on different, incomparable scales,
so a naive merge (e.g. weighted sum) is a rough heuristic. A cross-encoder
scores each (query, chunk) pair jointly, which is slower but far more
accurate at judging true relevance, so it's used only on the small merged
candidate set rather than the whole corpus.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import List

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from src import config
from src.ingest import embed_texts, get_collection

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("retrieval")


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    filename: str
    chunk_index: int
    category: str
    confidence: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rerank_score: float = 0.0


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


@lru_cache(maxsize=1)
def get_cross_encoder() -> CrossEncoder:
    logger.info("Loading cross-encoder: %s", config.CROSS_ENCODER_MODEL)
    return CrossEncoder(config.CROSS_ENCODER_MODEL)


class HybridIndex:
    """Builds a BM25 index over whatever is currently in the Chroma
    collection. Call refresh() after ingestion to pick up new documents."""

    def __init__(self):
        self._ids: List[str] = []
        self._texts: List[str] = []
        self._metadatas: List[dict] = []
        self._bm25: BM25Okapi = None
        self.refresh()

    def refresh(self) -> None:
        collection = get_collection()
        data = collection.get()
        self._ids = data["ids"]
        self._texts = data["documents"]
        self._metadatas = data["metadatas"]
        if self._texts:
            self._bm25 = BM25Okapi([_tokenize(t) for t in self._texts])
        else:
            self._bm25 = None
        logger.info("Hybrid index refreshed: %d chunks", len(self._ids))

    @property
    def size(self) -> int:
        return len(self._ids)

    def dense_search(self, query: str, top_k: int) -> List[RetrievedChunk]:
        if self.size == 0:
            return []
        collection = get_collection()
        query_embedding = embed_texts([query])[0].tolist()
        results = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, self.size))
        chunks = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            chunks.append(
                RetrievedChunk(
                    chunk_id=results["ids"][0][i],
                    text=results["documents"][0][i],
                    filename=metadata["filename"],
                    chunk_index=metadata["chunk_index"],
                    category=metadata["category"],
                    confidence=metadata["confidence"],
                    dense_score=1.0 - distance,  # cosine distance -> similarity
                )
            )
        return chunks

    def sparse_search(self, query: str, top_k: int) -> List[RetrievedChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        chunks = []
        for i in ranked:
            if scores[i] <= 0:
                continue
            metadata = self._metadatas[i]
            chunks.append(
                RetrievedChunk(
                    chunk_id=self._ids[i],
                    text=self._texts[i],
                    filename=metadata["filename"],
                    chunk_index=metadata["chunk_index"],
                    category=metadata["category"],
                    confidence=metadata["confidence"],
                    sparse_score=float(scores[i]),
                )
            )
        return chunks


_index: HybridIndex = None


def get_index() -> HybridIndex:
    global _index
    if _index is None:
        _index = HybridIndex()
    return _index


def hybrid_search(
    query: str,
    dense_top_k: int = None,
    sparse_top_k: int = None,
    rerank_top_n: int = None,
) -> List[RetrievedChunk]:
    dense_top_k = dense_top_k or config.DENSE_TOP_K
    sparse_top_k = sparse_top_k or config.SPARSE_TOP_K
    rerank_top_n = rerank_top_n or config.RERANK_TOP_N

    index = get_index()
    dense_results = index.dense_search(query, dense_top_k)
    sparse_results = index.sparse_search(query, sparse_top_k)

    merged: dict = {}
    for chunk in dense_results:
        merged[chunk.chunk_id] = chunk
    for chunk in sparse_results:
        if chunk.chunk_id in merged:
            merged[chunk.chunk_id].sparse_score = chunk.sparse_score
        else:
            merged[chunk.chunk_id] = chunk

    candidates = list(merged.values())
    if not candidates:
        return []

    cross_encoder = get_cross_encoder()
    pairs = [[query, c.text] for c in candidates]
    scores = cross_encoder.predict(pairs)
    for chunk, score in zip(candidates, scores):
        chunk.rerank_score = float(score)

    candidates.sort(key=lambda c: c.rerank_score, reverse=True)
    return candidates[:rerank_top_n]
