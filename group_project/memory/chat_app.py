"""RAG Chatbot có conversation memory — chat history + follow-up question.

Phần memory cho bài nhóm (Trương Hải Quân). Triển khai đúng spec của lead:
    1. Lưu lịch sử chat trong st.session_state.messages
    2. Hiển thị lại toàn bộ hội thoại (kể cả sau refresh trong phiên)
    3. Hỗ trợ follow-up: dùng lịch sử để dựng câu hỏi đầy đủ ngữ cảnh trước khi gọi RAG
    4. Nút Clear chat để reset demo

Tái sử dụng pipeline có sẵn của nhóm: src.task10_generation.generate_with_citation.
KHÔNG sửa pipeline — chỉ thêm tầng hội thoại bọc ngoài.

Chạy từ thư mục gốc repo:
    streamlit run group_project/memory/chat_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# --- path setup: repo root cho `src`, script dir cho `conversation` ---
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path(__file__).resolve().parents[2]
for path in (str(ROOT_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.task10_generation import generate_with_citation  # pipeline nhóm (Task 10)
from conversation import build_contextual_query  # tầng memory (cùng folder)


def render_sources(sources: list[dict]) -> None:
    """Hiển thị danh sách nguồn (citation) dưới câu trả lời."""
    if not sources:
        return
    with st.expander(f"📚 Nguồn tham khảo ({len(sources)} chunk)"):
        for i, src in enumerate(sources, 1):
            meta = src.get("metadata", {})
            name = meta.get("source", f"Nguồn {i}")
            doc_type = meta.get("type", "unknown")
            score = src.get("score")
            score_txt = f" · score {score:.3f}" if isinstance(score, (int, float)) else ""
            st.markdown(f"**[{i}] {name}** ({doc_type}){score_txt}")
            st.caption(src.get("content", "")[:400])


st.set_page_config(page_title="RAG Chatbot — Memory", page_icon="💬", layout="wide")
st.title("💬 RAG Chatbot — Pháp luật & Tin tức ma tuý")
st.caption("Hỗ trợ hỏi nối tiếp (follow-up). Câu trả lời có citation từ tài liệu đã index.")

# (1) Lịch sử chat trong session_state — theo spec lead
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar: clear chat + debug toggle
with st.sidebar:
    st.header("⚙️ Tùy chọn")
    show_debug = st.toggle("🔍 Hiện câu hỏi đã viết lại (debug)", value=False)
    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.caption(f"{len(st.session_state.messages)} tin nhắn trong phiên")

# (2) Hiển thị lại toàn bộ hội thoại
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if show_debug and msg["role"] == "user":
            ctx = msg.get("contextual_query")
            if ctx and ctx != msg["content"]:
                st.caption(f"↳ tìm kiếm với: _{ctx}_")
        render_sources(msg.get("sources") or [])

# (3) Ô nhập câu hỏi mới
if prompt := st.chat_input("Nhập câu hỏi của bạn..."):
    # 3a. follow-up -> câu hỏi đầy đủ ngữ cảnh (dùng lịch sử trước khi append)
    contextual_query = build_contextual_query(prompt, st.session_state.messages)

    st.session_state.messages.append(
        {"role": "user", "content": prompt, "contextual_query": contextual_query}
    )
    with st.chat_message("user"):
        st.markdown(prompt)
        if show_debug and contextual_query != prompt:
            st.caption(f"↳ tìm kiếm với: _{contextual_query}_")

    # 3b. Gọi pipeline RAG với câu hỏi đã đủ ngữ cảnh
    with st.chat_message("assistant"):
        with st.spinner("Đang tìm kiếm và tạo câu trả lời..."):
            try:
                result = generate_with_citation(contextual_query)
            except Exception as exc:  # noqa: BLE001 - hiển thị lỗi cho người dùng demo
                st.error(f"Lỗi khi chạy pipeline: {exc}")
                st.stop()

        answer = result.get("answer", "")
        sources = result.get("sources", []) or []
        st.markdown(answer)
        render_sources(sources)

    # 3c. Lưu câu trả lời + sources (đúng format message lead quy định)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
