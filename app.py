"""
app.py - web interface for the AI-Based Question Paper Generator.

Run with:
    streamlit run app.py
"""

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from src.assembly.paper_builder import build_paper
from src.assembly.question_bank import add_questions, connect, get_questions, summary, topics
from src.export.docx_export import docx_bytes
from src.generation.generator import generate_questions
from src.ingestion.pdf_reader import chunk_text, extract_text

load_dotenv(override=True)
SAMPLE_PDF = os.path.join("data", "sample", "photosynthesis_chapter.pdf")
provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

st.set_page_config(page_title="AI Question Paper Generator", layout="wide")
st.title("AI-Based Question Paper Generator")
st.caption("Upload a chapter, generate questions with an LLM, then build a ready-to-print paper with an answer key.")

conn = connect()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Status")
    st.write(f"**LLM provider:** {provider}")
    if provider == "ollama":
        st.write(f"**Model:** {os.getenv('OLLAMA_MODEL', 'llama3.2')}")
        st.caption("Make sure the Ollama app is running.")
    elif not os.getenv("ANTHROPIC_API_KEY"):
        st.error("No ANTHROPIC_API_KEY found in .env")
    total = sum(r[3] for r in summary(conn))
    st.write(f"**Questions in bank:** {total}")
    st.caption("Change the provider or model in your .env file, then restart the app.")

tab_gen, tab_paper, tab_bank = st.tabs(["1. Generate questions", "2. Build paper", "3. Question bank"])

# ------------------------------------------------------------------ tab 1
with tab_gen:
    st.subheader("Generate questions from a chapter")
    uploaded = st.file_uploader("Upload a chapter PDF (text-based, not a scan)", type="pdf")
    use_sample = st.checkbox("Use the sample chapter (photosynthesis) instead", key="use_sample")
    topic = st.text_input("Topic label (used to filter questions later)", value="general", key="topic")

    c1, c2, c3, c4 = st.columns(4)
    words = c1.number_input("Words per chunk", 100, 2000, 300, 50, key="words")
    per_mcq = c2.number_input("MCQs per chunk", 0, 10, 3, key="per_mcq")
    per_short = c3.number_input("Short answers per chunk", 0, 10, 2, key="per_short")
    max_chunks = c4.number_input("Max chunks to use", 1, 50, 3, key="max_chunks")
    st.caption("Smaller chunks and fewer questions per chunk work best with small local models.")

    if st.button("Generate questions", type="primary", key="btn_generate"):
        if not uploaded and not use_sample:
            st.warning("Upload a PDF or tick the sample chapter first.")
        elif per_mcq == 0 and per_short == 0:
            st.warning("Ask for at least one question per chunk.")
        elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEY is missing. Add it to .env, or set LLM_PROVIDER=ollama for the free option.")
        else:
            if uploaded:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded.getvalue())
                    pdf_path = tmp.name
            else:
                pdf_path = SAMPLE_PDF

            text = extract_text(pdf_path)
            if len(text.split()) < 100:
                st.error("Very little text found. The PDF may be scanned and needs OCR first.")
            else:
                chunks = chunk_text(text, int(words))[: int(max_chunks)]
                jobs = [(i, c, t, int(n)) for i, c in enumerate(chunks)
                        for t, n in (("mcq", per_mcq), ("short", per_short)) if n]
                bar = st.progress(0.0, text="Starting...")
                new_questions = []
                failed = False
                try:
                    for done, (i, chunk, qtype, n) in enumerate(jobs):
                        bar.progress(done / len(jobs), text=f"Chunk {i + 1} of {len(chunks)}: generating {n} {qtype}...")
                        new_questions += generate_questions(chunk, qtype, n)
                    bar.progress(1.0, text="Done")
                except Exception as e:  # show any provider error on the page instead of crashing
                    failed = True
                    st.error(f"{type(e).__name__}: {e}")

                if new_questions:
                    added = add_questions(conn, new_questions, topic=topic.strip() or "general")
                    st.success(f"Generated {len(new_questions)} questions: {added} added to the bank, "
                               f"{len(new_questions) - added} duplicates skipped.")
                    st.info("Go to the **2. Build paper** tab next.")
                elif not failed:
                    st.warning("No valid questions came back. Try again, or use fewer questions per chunk.")

# ------------------------------------------------------------------ tab 2
with tab_paper:
    st.subheader("Build a question paper from the bank")
    topic_options = ["All topics"] + topics(conn)
    topic_choice = st.selectbox("Use questions from", topic_options, key="paper_topic")

    c1, c2, c3 = st.columns(3)
    title = c1.text_input("Paper title", "Unit Test 1", key="p_title")
    subject = c2.text_input("Subject", "Science", key="p_subject")
    duration = c3.text_input("Duration", "1 Hour", key="p_duration")

    c1, c2, c3 = st.columns(3)
    n_mcq = c1.number_input("Number of MCQs (1 mark each)", 0, 50, 8, key="p_mcq")
    n_short = c2.number_input("Number of short answers", 0, 20, 3, key="p_short")
    seed = c3.number_input("Set number (same number = same paper)", 1, 999, 1, key="p_seed")

    if st.button("Build paper", type="primary", key="btn_build"):
        bank = get_questions(conn, topic=None if topic_choice == "All topics" else topic_choice)
        if not bank:
            st.warning("The question bank is empty. Generate questions in tab 1 first.")
        else:
            st.session_state["paper"] = build_paper(bank, int(n_mcq), int(n_short), seed=int(seed))
            st.session_state["meta"] = dict(title=title, subject=subject, duration=duration)

    paper = st.session_state.get("paper")
    if paper:
        for w in paper["warnings"]:
            st.warning(w)
        m1, m2, m3 = st.columns(3)
        m1.metric("MCQs", len(paper["mcq"]))
        m2.metric("Short answers", len(paper["short"]))
        m3.metric("Total marks", paper["total_marks"])

        meta = st.session_state["meta"]
        d1, d2 = st.columns(2)
        d1.download_button("Download question paper (.docx)", docx_bytes(paper, **meta),
                           file_name="question_paper.docx", key="dl_paper",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        d2.download_button("Download answer key (.docx)", docx_bytes(paper, include_answers=True, **meta),
                           file_name="answer_key.docx", key="dl_key",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        st.markdown("#### Preview")
        number = 1
        for q in paper["mcq"] + paper["short"]:
            with st.expander(f"Q{number}. [{q['type'].upper()} | {q['difficulty']} | {q['marks']} mark(s)] {q['question']}"):
                if q["type"] == "mcq":
                    for letter, option in zip("ABCD", q["options"]):
                        st.write(f"({letter}) {option}")
                    st.caption(f"Answer: {q['answer']}" + (f"  -  {q['explanation']}" if q.get("explanation") else ""))
                else:
                    st.caption(f"Model answer: {q['answer']}")
            number += 1

# ------------------------------------------------------------------ tab 3
with tab_bank:
    st.subheader("Question bank")
    rows = get_questions(conn)
    if not rows:
        st.info("The bank is empty. Generate questions in tab 1.")
    else:
        st.write("Counts by topic, type and difficulty:")
        st.dataframe(
            [dict(topic=t, type=ty, difficulty=d, count=c) for t, ty, d, c in summary(conn)],
            hide_index=True,
        )
        st.write("All questions:")
        st.dataframe(
            [dict(id=q["id"], topic=q["topic"], type=q["type"], difficulty=q["difficulty"],
                  marks=q["marks"], question=q["question"]) for q in rows],
            hide_index=True,
        )
