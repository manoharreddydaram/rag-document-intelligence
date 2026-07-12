"""Lightweight unit tests for chunking, parsing, and retrieval helpers.

Deliberately avoids loading the embedding/classification/cross-encoder
models so this suite runs fast and offline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import Chunk, chunk_text, parse_eml, parse_txt
from src.retrieval import _tokenize


def test_chunk_text_short_input_single_chunk():
    text = "This is a short document with only a handful of words."
    chunks = chunk_text(text, "short.txt")
    assert len(chunks) == 1
    assert chunks[0].filename == "short.txt"
    assert chunks[0].chunk_index == 0
    assert chunks[0].text.strip() == text


def test_chunk_text_long_input_produces_overlapping_chunks():
    # ~1500 words, well beyond the 500-word chunk size, so this must split.
    paragraph = " ".join(f"word{i}" for i in range(1500))
    chunks = chunk_text(paragraph, "long.txt")

    assert len(chunks) > 1
    # chunk_index must be sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # every chunk carries its filename and a default category before classification
    assert all(c.filename == "long.txt" for c in chunks)
    assert all(c.category == "uncategorized" for c in chunks)

    # consecutive chunks should overlap: the tail of chunk N should share
    # words with the head of chunk N+1
    first_words = set(chunks[0].text.split())
    second_words = set(chunks[1].text.split())
    assert first_words & second_words, "expected word overlap between consecutive chunks"


def test_chunk_text_produces_unique_ids():
    paragraph = " ".join(f"word{i}" for i in range(1500))
    chunks = chunk_text(paragraph, "long.txt")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_parse_txt_reads_file_content(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("Hello enterprise world.", encoding="utf-8")
    assert parse_txt(str(file_path)) == "Hello enterprise world."


def test_parse_eml_extracts_subject_and_body(tmp_path):
    eml_content = (
        "From: alice@example.com\n"
        "To: support@example.com\n"
        "Subject: Test Ticket\n"
        "Date: Mon, 1 Jan 2026 10:00:00 -0500\n"
        "Content-Type: text/plain\n\n"
        "This is the ticket body.\n"
    )
    file_path = tmp_path / "ticket.eml"
    file_path.write_bytes(eml_content.encode("utf-8"))

    text = parse_eml(str(file_path))
    assert "Test Ticket" in text
    assert "This is the ticket body." in text


def test_tokenize_lowercases_and_splits():
    tokens = _tokenize("Ticket #4521 Login Issue")
    assert tokens == ["ticket", "#4521", "login", "issue"]


def test_chunk_dataclass_defaults():
    chunk = Chunk(chunk_id="abc123", filename="doc.txt", chunk_index=0, text="hello")
    assert chunk.category == "uncategorized"
    assert chunk.confidence == 0.0
