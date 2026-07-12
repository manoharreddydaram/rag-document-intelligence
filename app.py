"""Streamlit demo UI for the Enterprise Document Intelligence RAG pipeline."""
import os
import shutil
import tempfile

import streamlit as st

# Allow Streamlit Community Cloud secrets to populate env vars the rest of
# the pipeline reads via python-dotenv / os.getenv. Locally, no secrets.toml
# exists, and st.secrets raises rather than returning empty in that case.
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except st.errors.StreamlitSecretNotFoundError:
    pass

from src import config
from src.generate import answer_question
from src.ingest import ingest_directory, ingest_file, list_documents
from src.retrieval import get_index

st.set_page_config(page_title="Enterprise Document Intelligence", page_icon="📄", layout="wide")

st.title("📄 Enterprise Document Intelligence")
st.caption(
    "Ask questions over a corpus of mixed enterprise documents (policies, financial reports, "
    "HR docs, support tickets, legal/compliance, engineering docs). Answers are grounded in "
    "retrieved excerpts with source citations — hybrid dense + sparse retrieval, reranked."
)

with st.sidebar:
    st.header("Corpus")
    documents = list_documents()
    if not documents:
        st.warning("No documents ingested yet.")
        if st.button("Ingest sample corpus", type="primary"):
            with st.spinner("Parsing, classifying, embedding, and indexing sample_docs..."):
                results = ingest_directory()
                ok = sum(1 for r in results if r.status == "ok")
                st.success(f"Ingested {ok} documents.")
            st.rerun()
    else:
        st.metric("Documents indexed", len(documents))
        st.metric("Chunks indexed", sum(d["num_chunks"] for d in documents))

        category_counts = {}
        for d in documents:
            category_counts[d["category"]] = category_counts.get(d["category"], 0) + 1
        st.subheader("Category breakdown")
        for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            st.text(f"{category}: {count}")

        with st.expander("All documents"):
            for d in documents:
                st.text(f"{d['filename']} — {d['category']} ({d['confidence']:.0%} conf.)")

        if st.button("Re-ingest sample corpus"):
            with st.spinner("Re-ingesting..."):
                ingest_directory()
                get_index().refresh()
            st.rerun()

    st.divider()
    st.header("Upload your own documents")
    st.caption(
        "Add PDF, .txt, .eml, or .docx files to the corpus. They go through the same "
        "parse → chunk → classify → embed → store pipeline as the sample docs."
    )
    uploaded_files = st.file_uploader(
        "Choose files",
        type=[ext.lstrip(".") for ext in config.SUPPORTED_EXTENSIONS],
        accept_multiple_files=True,
    )
    if uploaded_files and st.button("Ingest uploaded files", type="primary"):
        tmp_dir = tempfile.mkdtemp(prefix="rag_upload_")
        try:
            results = []
            with st.spinner(f"Ingesting {len(uploaded_files)} file(s)..."):
                for uploaded in uploaded_files:
                    dest_path = os.path.join(tmp_dir, uploaded.name)
                    with open(dest_path, "wb") as f:
                        f.write(uploaded.getbuffer())
                    results.append(ingest_file(dest_path))
                get_index().refresh()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        for r in results:
            if r.status == "ok":
                st.success(f"{r.filename}: indexed as '{r.category}' ({r.num_chunks} chunk(s))")
            else:
                st.error(f"{r.filename}: {r.status} — {r.error}")
        st.rerun()

question = st.text_input(
    "Ask a question about the document corpus",
    placeholder="e.g. What was Nimbus Analytics' revenue in Q1 2026?",
)

if st.button("Ask", type="primary") and question:
    if not list_documents():
        st.error("No documents indexed yet. Use the sidebar to ingest the sample corpus first.")
    else:
        with st.spinner("Retrieving relevant chunks and generating a grounded answer..."):
            try:
                result = answer_question(question)
            except RuntimeError as exc:
                st.error(str(exc))
                result = None

        if result:
            st.subheader("Answer")
            st.markdown(result.answer)

            if result.sources:
                st.subheader("Cited sources")
                for source in result.sources:
                    st.markdown(f"- **{source['filename']}** _(category: {source['category']})_")

            if result.retrieved_chunks:
                with st.expander(f"Retrieved chunks ({len(result.retrieved_chunks)}) — hybrid retrieval + rerank detail"):
                    for chunk in result.retrieved_chunks:
                        st.markdown(
                            f"**{chunk.filename}** — chunk #{chunk.chunk_index} · "
                            f"category: `{chunk.category}` ({chunk.confidence:.0%} conf.) · "
                            f"rerank score: `{chunk.rerank_score:.3f}` · "
                            f"dense: `{chunk.dense_score:.3f}` · sparse: `{chunk.sparse_score:.3f}`"
                        )
                        st.text(chunk.text[:500] + ("..." if len(chunk.text) > 500 else ""))
                        st.divider()

st.divider()
st.caption(
    "Built as a portfolio project demonstrating unstructured data ingestion, zero-shot document "
    "classification, hybrid dense+sparse retrieval, cross-encoder reranking, and citation-grounded "
    "LLM generation with quantitative RAGAS evaluation."
)
