"""RAGAS evaluation harness.

Runs a fixed question set with known-correct answers through the full RAG
pipeline (retrieval + generation), then scores the results with RAGAS on
three axes:
  - faithfulness: does the answer avoid claims unsupported by the retrieved
    context? (measures hallucination)
  - answer_relevancy: does the answer actually address the question asked?
  - context_precision: are the retrieved chunks relevant to the question,
    ranked appropriately? (measures retrieval quality, not just generation)

A separate, small set of intentionally unanswerable questions is checked
qualitatively (not scored by RAGAS) to confirm the pipeline's refusal
behavior — RAGAS's ground-truth-based metrics aren't a good fit for "I
don't know" as a correct answer.
"""
import json
import logging
import os
import time

from datasets import Dataset
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import answer_relevancy, context_precision, faithfulness
from ragas.run_config import RunConfig

from src import config
from src.generate import answer_question

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("evaluate")

# Groq's free tier still has rate limits (well above Gemini's, but not
# unlimited). A small pacing gap between our own generation calls avoids
# bursting into them; RAGAS's own judge calls are serialized below instead.
REQUEST_PACING_SECONDS = 2

# The evaluation harness uses GROQ_JUDGE_MODEL (a lighter model, e.g.
# llama-3.1-8b-instant) for BOTH generating the answers being scored and
# for the RAGAS judge itself — deliberately different from GROQ_MODEL (the
# 70B model the live app/API default to). This keeps the whole evaluation
# run self-contained on its own Groq daily token quota, isolated from
# whatever the live demo has already spent on the 70B model's quota, and
# a lighter model comfortably fits a full 14-question, 3-metric run within
# free-tier limits.
_EVAL_MODEL = config.GROQ_JUDGE_MODEL

QUESTIONS = [
    {
        "question": "What is the minimum password length required by Nimbus Analytics' security policy?",
        "ground_truth": "Passwords must be a minimum of 14 characters, with at least one uppercase letter, one lowercase letter, one number, and one special character.",
    },
    {
        "question": "How much is the home office stipend for approved remote employees?",
        "ground_truth": "Approved remote employees receive a one-time home office stipend of $750.",
    },
    {
        "question": "How many dedicated sick days do employees receive per year, and do they roll over?",
        "ground_truth": "Employees receive 8 dedicated sick days per year, and they do not roll over.",
    },
    {
        "question": "What was Nimbus Analytics' revenue in Q1 2026?",
        "ground_truth": "Q1 2026 revenue was $18.4M, up 22% year-over-year.",
    },
    {
        "question": "What was the operating margin in Q2 2026?",
        "ground_truth": "Q2 2026 operating margin was 25%, with operating income of $4.9M.",
    },
    {
        "question": "Within how many hours must system access be revoked after an employee's termination?",
        "ground_truth": "All system access must be revoked within 24 hours of an employee's termination date, or immediately for involuntary terminations.",
    },
    {
        "question": "What caused the billing discrepancy in support ticket 4522?",
        "ground_truth": "The batch-import endpoint used for a historical data migration didn't carry historical billing timestamps, so events were counted as May-cycle usage instead of being pro-rated across their original dates.",
    },
    {
        "question": "Why couldn't the customer in ticket 4521 log in after resetting their password?",
        "ground_truth": "Their account had MFA enabled via an authenticator app that had recently been replaced, which triggered a security hold requiring MFA re-confirmation during the password reset flow.",
    },
    {
        "question": "How long does Nimbus Analytics retain security and access logs?",
        "ground_truth": "Security logs and access logs are retained for 13 months.",
    },
    {
        "question": "Within how many hours must Nimbus Analytics notify a supervisory authority after a confirmed GDPR data breach?",
        "ground_truth": "The relevant supervisory authority must be notified within 72 hours of becoming aware of the breach.",
    },
    {
        "question": "What is the API rate limit for Enterprise tier customers?",
        "ground_truth": "Enterprise tier customers have a rate limit of 10,000 requests per minute per project token.",
    },
    {
        "question": "What opinion did the auditor issue in the SOC 2 Type II report?",
        "ground_truth": "The auditor issued an unqualified (clean) opinion, with two minor exceptions noted.",
    },
    {
        "question": "What is the maximum number of PTO days that can carry over into the next calendar year?",
        "ground_truth": "Unused PTO carries over up to a maximum of 10 days into the following calendar year.",
    },
    {
        "question": "What percentage of the FY2026 budget was allocated to Engineering?",
        "ground_truth": "Engineering was allocated $27.5M, representing 34% of the total FY2026 budget.",
    },
]

REFUSAL_TEST_QUESTIONS = [
    "What is Nimbus Analytics' stock ticker symbol?",
    "Who is the current CEO of Nimbus Analytics?",
]

# Groq's free-tier daily token budget is tight enough that a single
# evaluation pass can run out mid-way. Cache each question's answer to disk
# as soon as it's generated so a retry after a rate-limit wait resumes from
# where it left off instead of re-spending tokens on already-answered
# questions.
_CACHE_PATH = os.path.join(config.BASE_DIR, ".eval_cache.json")


def _load_cache() -> dict:
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def build_dataset() -> Dataset:
    cache = _load_cache()
    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    made_a_call = False
    for item in QUESTIONS:
        question = item["question"]
        cached = cache.get(question)
        if cached is None:
            if made_a_call:
                time.sleep(REQUEST_PACING_SECONDS)
            result = answer_question(question, model=_EVAL_MODEL)
            cached = {"answer": result.answer, "contexts": [c.text for c in result.retrieved_chunks]}
            cache[question] = cached
            _save_cache(cache)
            made_a_call = True
            logger.info("Answered: %s", question)
        else:
            logger.info("Using cached answer: %s", question)
        rows["question"].append(question)
        rows["answer"].append(cached["answer"])
        rows["contexts"].append(cached["contexts"])
        rows["ground_truth"].append(item["ground_truth"])
    return Dataset.from_dict(rows)


def check_refusal_behavior() -> list:
    cache = _load_cache()
    checks = []
    made_a_call = False
    for question in REFUSAL_TEST_QUESTIONS:
        cache_key = f"refusal::{question}"
        cached = cache.get(cache_key)
        if cached is None:
            if made_a_call:
                time.sleep(REQUEST_PACING_SECONDS)
            result = answer_question(question, model=_EVAL_MODEL)
            cached = {"answer": result.answer}
            cache[cache_key] = cached
            _save_cache(cache)
            made_a_call = True
            logger.info("Refusal check [%s]: answered", question)
        else:
            logger.info("Using cached refusal answer: %s", question)
        refused = "don't have enough information" in cached["answer"].lower()
        checks.append({"question": question, "answer": cached["answer"], "correctly_refused": refused})
    return checks


def run_evaluation(output_path: str = None) -> dict:
    output_path = output_path or os.path.join(config.BASE_DIR, "evaluation_results.json")

    dataset = build_dataset()

    # Same lighter model used for generation above (see _EVAL_MODEL) also
    # serves as the RAGAS judge here, for the same reason: an independent
    # Groq quota that doesn't compete with the live app's 70B-model budget,
    # and comfortably enough headroom for the 42 judge calls this needs
    # (3 metrics x 14 questions).
    llm = ChatOpenAI(
        model=_EVAL_MODEL,
        api_key=config.GROQ_API_KEY,
        base_url=config.GROQ_BASE_URL,
        temperature=0,
    )
    # Groq has no embeddings endpoint, so RAGAS's answer_relevancy metric
    # (the only one needing embeddings) uses the same local sentence-
    # transformers model the retrieval pipeline already runs — free, no
    # extra API calls or quota. ragas's own HuggingfaceEmbeddings dataclass
    # doesn't implement the required async methods in this ragas version,
    # so wrap langchain's HuggingFace embeddings instead.
    embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL))

    # max_workers=1 serializes RAGAS's internal LLM-judge calls so they
    # respect Groq's rate limit; generous timeout/max_wait let its built-in
    # retry absorb transient 429s.
    run_config = RunConfig(max_workers=1, max_retries=10, max_wait=60, timeout=600)

    ragas_result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
        embeddings=embeddings,
        run_config=run_config,
    )
    df = ragas_result.to_pandas()

    refusal_checks = check_refusal_behavior()

    metric_names = ["faithfulness", "answer_relevancy", "context_precision"]
    overall = {name: float(df[name].mean()) for name in metric_names if name in df.columns}

    summary = {
        "num_questions": len(QUESTIONS),
        "overall": overall,
        "per_question": df.to_dict(orient="records"),
        "refusal_behavior_checks": refusal_checks,
    }

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("Saved evaluation results to %s", output_path)
    return summary


if __name__ == "__main__":
    result = run_evaluation()
    print(json.dumps(result["overall"], indent=2))
    print(f"\nRefusal behavior: {sum(c['correctly_refused'] for c in result['refusal_behavior_checks'])}/{len(result['refusal_behavior_checks'])} correct")
