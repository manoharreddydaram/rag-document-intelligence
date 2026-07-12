"""Citation-grounded answer generation via the Groq API (OpenAI-compatible).

The prompt forces the model to answer only from the supplied context chunks,
cite the source filename for every claim, and explicitly say when the
context doesn't cover the question — this is the core anti-hallucination
mechanism and the key interview talking point for this project.
"""
import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import List

import openai

from src import config
from src.retrieval import RetrievedChunk, hybrid_search

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("generate")


@lru_cache(maxsize=1)
def _get_client() -> openai.OpenAI:
    if not config.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file "
            "(see .env.example) or Streamlit secrets."
        )
    return openai.OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)


SYSTEM_INSTRUCTIONS = """You are an enterprise document assistant. Answer the \
user's question using ONLY the information in the numbered context excerpts \
below. Follow these rules strictly:

1. Every factual claim in your answer must be traceable to a specific \
excerpt. Cite the source filename in square brackets after the claim, e.g. \
"Passwords must be at least 14 characters [security_password_policy.pdf]."
2. If the excerpts do not contain enough information to answer the \
question, respond exactly with: "I don't have enough information in the \
provided documents to answer that." Do not guess or use outside knowledge.
3. Do not fabricate filenames, numbers, or policy details that are not \
present in the excerpts.
4. Be concise and directly answer the question first, then support it with \
citations.
"""


@dataclass
class GeneratedAnswer:
    answer: str
    sources: List[dict]
    retrieved_chunks: List[RetrievedChunk]


def _build_prompt(question: str, chunks: List[RetrievedChunk]) -> str:
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] Source: {chunk.filename} (category: {chunk.category})\n{chunk.text}"
        )
    context = "\n\n".join(context_blocks)
    return f"CONTEXT EXCERPTS:\n{context}\n\nQUESTION: {question}\n\nANSWER:"


_RETRY_DELAY_RE = re.compile(r"try again in (\d+(?:\.\d+)?)s", re.IGNORECASE)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _generate_with_retry(client: openai.OpenAI, prompt: str, model: str, max_attempts: int = 4) -> str:
    """Retry on rate limiting (429) and transient server-side errors
    (5xx) using the server's suggested delay when available."""
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            return response.choices[0].message.content.strip()
        except openai.APIStatusError as exc:
            is_last = attempt == max_attempts
            if exc.status_code not in _RETRYABLE_STATUS_CODES or is_last:
                raise
            match = _RETRY_DELAY_RE.search(str(exc))
            delay = float(match.group(1)) + 1 if match else 15.0
            logger.warning(
                "Groq call failed (%s, attempt %d/%d), retrying in %.0fs",
                exc.status_code, attempt, max_attempts, delay,
            )
            time.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover


def answer_question(question: str, rerank_top_n: int = None, model: str = None) -> GeneratedAnswer:
    """model defaults to config.GROQ_MODEL (the live app/API default).
    The evaluation harness overrides it to isolate its token usage on a
    separate Groq quota from live traffic."""
    chunks = hybrid_search(question, rerank_top_n=rerank_top_n)

    if not chunks:
        return GeneratedAnswer(
            answer="I don't have enough information in the provided documents to answer that.",
            sources=[],
            retrieved_chunks=[],
        )

    client = _get_client()
    prompt = _build_prompt(question, chunks)

    try:
        answer_text = _generate_with_retry(client, prompt, model=model or config.GROQ_MODEL)
    except Exception as exc:  # noqa: BLE001
        logger.error("Groq generation failed: %s", exc)
        raise

    sources = []
    seen_filenames = set()
    for chunk in chunks:
        if chunk.filename not in seen_filenames:
            seen_filenames.add(chunk.filename)
            sources.append(
                {
                    "filename": chunk.filename,
                    "category": chunk.category,
                    "rerank_score": chunk.rerank_score,
                }
            )

    return GeneratedAnswer(answer=answer_text, sources=sources, retrieved_chunks=chunks)
