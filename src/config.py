import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(BASE_DIR, "chroma_store"))
SAMPLE_DOCS_DIR = os.getenv("SAMPLE_DOCS_DIR", os.path.join(BASE_DIR, "data", "sample_docs"))
COLLECTION_NAME = "documents"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# RAGAS uses a separate, smaller/cheaper model as its LLM judge. It has its
# own independent Groq daily token budget, distinct from GROQ_MODEL's
# budget — using two models keeps evaluation from competing with generation
# for the same quota, and a smaller model is more than adequate for judging
# faithfulness/relevancy against a fixed rubric.
GROQ_JUDGE_MODEL = os.getenv("GROQ_JUDGE_MODEL", "llama-3.1-8b-instant")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ZERO_SHOT_MODEL = "facebook/bart-large-mnli"

CHUNK_SIZE_WORDS = 500
CHUNK_OVERLAP_WORDS = 90  # ~18% overlap

DENSE_TOP_K = int(os.getenv("DENSE_TOP_K", "10"))
SPARSE_TOP_K = int(os.getenv("SPARSE_TOP_K", "10"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "5"))

CATEGORIES = [
    "security policy",
    "financial report",
    "HR",
    "customer support",
    "legal and compliance",
    "engineering documentation",
]

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".eml", ".docx"}
