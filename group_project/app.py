"""
RAG Chatbot UI — Người 5 (basic Streamlit).

Chạy từ thư mục gốc repo:
    streamlit run group_project/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.task10_generation import generate_with_citation

st.set_page_config(
    page_title="RAG — Pháp luật & Tin tức ma tuý",
    page_icon="⚖️",
    layout="wide",
)

st.title("RAG Chatbot — Pháp luật & Tin tức ma tuý")
st.caption("Hỏi đáp dựa trên văn bản pháp luật và bài báo đã index. Trả lời có citation.")

with st.form("question_form", clear_on_submit=False):
    user_question = st.text_area(
        "Câu hỏi của bạn",
        placeholder="Ví dụ: Hình phạt tàng trữ ma tuý theo luật Việt Nam là gì?",
        height=100,
    )
    submitted = st.form_submit_button("Gửi câu hỏi", type="primary")

if submitted:
    question = user_question.strip()
    if not question:
        st.warning("Vui lòng nhập câu hỏi.")
    else:
        with st.spinner("Đang tìm kiếm và tạo câu trả lời..."):
            try:
                result = generate_with_citation(question)
            except Exception as exc:
                st.error(f"Lỗi khi chạy pipeline: {exc}")
                st.stop()

        answer = result["answer"]
        sources = result.get("sources", [])
        retrieval_source = result.get("retrieval_source", "unknown")

        st.subheader("Câu trả lời")
        st.markdown(answer)

        st.subheader("Nguồn tham khảo")
        st.caption(f"Retrieval: **{retrieval_source}** · {len(sources)} chunk(s)")

        if not sources:
            st.info("Không tìm thấy nguồn liên quan.")
        else:
            for i, source in enumerate(sources, 1):
                metadata = source.get("metadata", {})
                source_name = metadata.get("source", f"Source {i}")
                doc_type = metadata.get("type", "unknown")
                score = source.get("score")
                score_label = f" · score: {score:.3f}" if isinstance(score, (int, float)) else ""

                with st.expander(f"[{i}] {source_name} ({doc_type}){score_label}"):
                    st.markdown(source.get("content", ""))
