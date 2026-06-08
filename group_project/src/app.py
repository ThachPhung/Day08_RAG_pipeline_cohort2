"""
RAG Chatbot — Demo tích hợp Conversation Memory (Streamlit).

Chạy từ repo root:
    streamlit run group_project/src/app.py

⚠ Đây là app DEMO để verify tầng memory end-to-end và làm mồi cho bạn phụ trách UI.
   UI cuối (giao diện đẹp, branding...) do teammate UI hoàn thiện. App này chỉ minh hoạ
   cách gọi đúng contract: ConversationMemory.chat(session_id, user_message).

Cần để chạy thật: OPENAI_API_KEY (trong .env) + đã build index Task 4
(`python -m src.task4_chunking_indexing`). Thiếu key/index vẫn chạy nhưng câu trả lời là
fallback extractive / rỗng.
"""

import sys
from pathlib import Path

import streamlit as st

# Cho phép import conversation_memory (cùng thư mục) + src.* (repo root)
SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parents[1]
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from conversation_memory import ConversationMemory

st.set_page_config(page_title="RAG Chatbot — Pháp luật ma tuý", page_icon="⚖️")


@st.cache_resource
def get_memory() -> ConversationMemory:
    """Một instance ConversationMemory dùng chung (giữ kết nối SQLite)."""
    return ConversationMemory()


memory = get_memory()

# --- Session hiện tại ------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = memory.new_session(title="Phiên chat")

# --- Sidebar: quản lý phiên ------------------------------------------------
with st.sidebar:
    st.header("⚙️ Phiên chat")

    if st.button("➕ Cuộc trò chuyện mới", use_container_width=True):
        st.session_state.session_id = memory.new_session(title="Phiên chat")
        st.rerun()

    sessions = memory.list_sessions()
    if sessions:
        labels = {
            s["session_id"]: f"{(s['title'] or 'Phiên')} · {s['message_count']} tin"
            for s in sessions
        }
        ids = list(labels.keys())
        current = st.session_state.session_id
        idx = ids.index(current) if current in ids else 0
        chosen = st.selectbox(
            "Chuyển phiên", ids, index=idx, format_func=lambda i: labels[i]
        )
        if chosen != st.session_state.session_id:
            st.session_state.session_id = chosen
            st.rerun()

    if st.button("🗑️ Xoá phiên này", use_container_width=True):
        memory.clear(st.session_state.session_id)
        st.session_state.session_id = memory.new_session(title="Phiên chat")
        st.rerun()

    show_debug = st.toggle("🔍 Debug (xem câu hỏi đã viết lại)", value=False)

# --- Khu vực chat ----------------------------------------------------------
st.title("⚖️ RAG Chatbot — Pháp luật ma tuý & tin tức")
st.caption("Hỏi đáp có citation · hỗ trợ câu hỏi nối tiếp (conversation memory)")


def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"📚 Nguồn ({len(sources)} đoạn)"):
        for i, chunk in enumerate(sources, 1):
            meta = chunk.get("metadata", {}) or {}
            src = meta.get("source", chunk.get("source", f"Nguồn {i}"))
            score = chunk.get("score")
            score_str = f" · score {score:.3f}" if isinstance(score, (int, float)) else ""
            st.markdown(f"**{i}. {src}**{score_str}")
            st.caption((chunk.get("content", "")[:400]) + "…")


# Render lại lịch sử từ SQLite
for msg in memory.get_history(st.session_state.session_id):
    with st.chat_message(msg["role"]):
        if show_debug and msg["role"] == "assistant" and msg.get("rewritten_query"):
            st.info(f"🔁 Câu hỏi đã viết lại: *{msg['rewritten_query']}*")
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _render_sources(msg.get("sources", []))

# Ô nhập câu hỏi mới
if prompt := st.chat_input("Nhập câu hỏi của bạn…"):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Đang truy hồi & trả lời…"):
            result = memory.chat(st.session_state.session_id, prompt)
        if show_debug and result["rewritten_query"] != result["original_query"]:
            st.info(f"🔁 Câu hỏi đã viết lại: *{result['rewritten_query']}*")
        st.markdown(result["answer"])
        _render_sources(result["sources"])
