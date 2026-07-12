# Deploying to Streamlit Community Cloud

This app is deploy-ready. The steps below require your own GitHub and Streamlit
Community Cloud accounts — they can't be done on your behalf.

## 1. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit: enterprise document intelligence RAG system"
git branch -M main
git remote add origin https://github.com/<your-username>/rag-document-intelligence.git
git push -u origin main
```

`.env` is already git-ignored (see `.gitignore`) — never commit your actual API key.
`chroma_store/` is also git-ignored; the deployed app builds its own index on first
run (see step 4).

## 2. Create the Streamlit Cloud app

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **New app**.
3. Select your `rag-document-intelligence` repo, branch `main`, and main file path
   `app.py`.
4. Under **Advanced settings**, set the Python version to 3.10 or later.

## 3. Add your Groq API key as a secret

In the app's **Settings → Secrets**, add:

```toml
GROQ_API_KEY = "your_actual_key_here"
```

`app.py` reads `st.secrets["GROQ_API_KEY"]` and sets it as an environment variable
at startup, so the rest of the pipeline (which reads `os.getenv`) picks it up
transparently. Never hardcode the key in source.

## 4. Ingest the corpus on first run

The deployed app ships with `data/sample_docs/` but starts with an empty vector
store (persistent storage isn't guaranteed across Streamlit Cloud redeploys). Click
**"Ingest sample corpus"** in the sidebar the first time the app loads — this runs
once and takes roughly 1-2 minutes (downloading and running the embedding and
classification models).

## 5. Verify end-to-end

- Confirm the sidebar shows ~24 documents and 6 categories after ingestion.
- Ask a question from the eval set, e.g. *"What was Nimbus Analytics' revenue in Q1
  2026?"* and confirm you get a cited, grounded answer.
- Ask an out-of-scope question, e.g. *"What is Nimbus Analytics' stock ticker
  symbol?"* and confirm it returns the "I don't have enough information" refusal
  rather than guessing.

## 6. Resource notes

- First load is slow because `sentence-transformers`, `transformers` (zero-shot
  classifier), and the cross-encoder all download their model weights on first use
  (a few hundred MB total). Streamlit Cloud's free tier has ~1GB RAM headroom on top
  of these models — if you hit memory limits, the zero-shot classifier
  (`facebook/bart-large-mnli`, ~1.6GB) is the heaviest component and the first
  candidate to swap for a smaller model (e.g. `valhalla/distilbart-mnli-12-3`).
- The FastAPI layer (`src/api.py`) is not deployed alongside the Streamlit app by
  default — Streamlit Community Cloud runs a single entrypoint. Run the API locally
  or deploy it separately (e.g. Hugging Face Spaces with a Docker SDK) if you want a
  live API endpoint too.
- Groq's free tier is generous but still rate-limited. If demo questions in the live
  app return a 429 error, wait a few seconds between questions — `src/generate.py`
  already retries automatically on 429/5xx using the server's suggested backoff.
  (This project originally targeted the Gemini API, but a fresh Gemini project's free
  tier turned out to be capped at a hard 20 requests/day, far too low for interactive
  use or the RAGAS evaluation — Groq was substituted for both generation and the
  RAGAS judge LLM for that reason.)
