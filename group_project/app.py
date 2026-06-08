from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from group_project.src.task10_generation import answer_question

APP_TITLE = "RAG Chatbot - Pháp luật ma túy"
APP_DESCRIPTION = (
    "Chatbot truy vấn văn bản pháp luật, trả lời có citation và lưu lịch sử hội thoại để hỗ trợ follow-up questions."
)

DEFAULT_TOP_K = 5
MAX_MEMORY_ITEMS = 5


def compose_query(question: str, history: list[dict]) -> str:
    if not history:
        return question

    history_segments = []
    for entry in history[-MAX_MEMORY_ITEMS:]:
        history_segments.append(f"Previous question: {entry['question']}\nAnswer: {entry['answer']}")

    return "\n\n".join(history_segments) + f"\n\nFollow-up question: {question}"


def render_source_document(source: dict, index: int) -> None:
    metadata = source.get("type", "unknown")
    source_name = source.get("source", "unknown")
    chunk_index = source.get("chunk_index", "?")
    score = source.get("score", 0.0)
    preview = source.get("preview", "")
    label = source.get("label", f"source_{index}")

    with st.expander(f"{index}. {label} (score={score})", expanded=False):
        st.markdown(f"**Source:** {source_name}  \n")
        st.markdown(f"**Type:** {metadata}  \n")
        st.markdown(f"**Chunk index:** {chunk_index}  \n")
        st.markdown(f"**Preview:** {preview}")


def initialize_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "last_answer" not in st.session_state:
        st.session_state.last_answer = None
    if "submit_chat" not in st.session_state:
        st.session_state.submit_chat = False


def clear_chat() -> None:
    st.session_state.history = []
    st.session_state.last_answer = None
    st.session_state.query = ""
    st.session_state.chat_input = ""
    st.session_state.submit_chat = False


def submit_chat() -> None:
    st.session_state.submit_chat = True


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="💬", layout="wide")
    initialize_state()

    st.title(APP_TITLE)
    st.write(APP_DESCRIPTION)

    with st.sidebar:
        st.header("Cài đặt")
        top_k = st.slider("Số nguồn hiển thị", min_value=1, max_value=10, value=DEFAULT_TOP_K)
        show_context = st.checkbox("Hiển thị context đầy đủ", value=False)
        st.markdown("---")
        st.button("Xóa lịch sử hội thoại", on_click=clear_chat)

    question = st.text_input(
        "Hỏi chatbot",
        value=st.session_state.query,
        placeholder="Nhập câu hỏi và nhấn Enter để gửi",
        key="chat_input",
        on_change=submit_chat,
    )
    submit_button = st.button("Gửi câu hỏi", on_click=submit_chat)
    submit = submit_button or st.session_state.submit_chat

    if submit and question.strip():
        st.session_state.submit_chat = False
        st.session_state.query = question.strip()
        query_text = compose_query(st.session_state.query, st.session_state.history)
        result = answer_question(query_text, top_k=top_k)

        entry = {
            "question": st.session_state.query,
            "answer": result["answer"],
            "sources": result["sources"],
            "context": result["context"],
            "retrieval_source": result["retrieval_source"],
            "policy": result["policy"],
        }
        st.session_state.history.append(entry)
        st.session_state.last_answer = result

    if st.session_state.history:
        st.subheader("Lịch sử hội thoại")
        for index, entry in enumerate(reversed(st.session_state.history), 1):
            container = st.container()
            with container:
                st.markdown(f"**Q{len(st.session_state.history) - index + 1}:** {entry['question']}")
                st.markdown(f"**A:** {entry['answer']}")
                st.markdown(f"_Nguồn truy xuất: {entry['retrieval_source']}_")
                if show_context:
                    with st.expander("Xem context truy xuất", expanded=False):
                        st.code(entry["context"], language="text")
                if entry["sources"]:
                    with st.expander("Xem các nguồn đã dùng", expanded=False):
                        for source_index, source in enumerate(entry["sources"], 1):
                            render_source_document(source, source_index)
                        st.markdown("---")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Chính sách chống ảo tưởng:**")
    st.sidebar.write(
        "Chatbot chỉ sử dụng nguồn truy xuất và từ chối trả lời khi bằng chứng yếu."
    )


if __name__ == "__main__":
    main()
