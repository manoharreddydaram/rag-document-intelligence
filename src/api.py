"""FastAPI layer exposing the RAG pipeline as endpoints.

POST /ingest    - upload one or more files, runs the full ingest pipeline
POST /query     - ask a question, get a grounded answer + cited sources
GET  /documents - list ingested documents with their tagged category
"""
import logging
import os
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src import config
from src.generate import answer_question
from src.ingest import ingest_file, list_documents
from src.retrieval import get_index

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

app = FastAPI(
    title="Enterprise Document Intelligence API",
    description="RAG pipeline over mixed enterprise documents with hybrid retrieval and citation-grounded generation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str
    top_n: int = None


class SourceOut(BaseModel):
    filename: str
    category: str
    rerank_score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceOut]


class IngestFileResult(BaseModel):
    filename: str
    status: str
    num_chunks: int
    category: str | None = None
    error: str | None = None


class IngestResponse(BaseModel):
    results: list[IngestFileResult]


class DocumentOut(BaseModel):
    filename: str
    category: str
    confidence: float
    num_chunks: int


@app.get("/")
def root():
    return {"status": "ok", "service": "Enterprise Document Intelligence API"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(files: list[UploadFile] = File(...)):
    results = []
    tmp_dir = tempfile.mkdtemp(prefix="rag_ingest_")
    try:
        for upload in files:
            dest_path = os.path.join(tmp_dir, upload.filename)
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(upload.file, f)
            result = ingest_file(dest_path)
            results.append(
                IngestFileResult(
                    filename=result.filename,
                    status=result.status,
                    num_chunks=result.num_chunks,
                    category=result.category,
                    error=result.error,
                )
            )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if any(r.status == "ok" for r in results):
        get_index().refresh()

    return IngestResponse(results=results)


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    result = answer_question(request.question, rerank_top_n=request.top_n)
    return QueryResponse(
        answer=result.answer,
        sources=[SourceOut(**s) for s in result.sources],
    )


@app.get("/documents", response_model=list[DocumentOut])
def documents():
    return [DocumentOut(**d) for d in list_documents()]
