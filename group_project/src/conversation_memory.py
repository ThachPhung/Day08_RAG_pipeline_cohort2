"""
Conversation Memory — tầng hội thoại cho RAG Chatbot nhóm.

Triển khai pattern **conversational RAG** chuẩn (giống LangChain
``create_history_aware_retriever`` + ``create_retrieval_chain``), gồm 2 lần gọi LLM
và CẢ HAI đều thấy lịch sử hội thoại:

    1. condense_question()      — viết lại follow-up + history -> câu hỏi standalone (cho retrieval)
    2. generate_with_history()  — sinh câu trả lời với prompt = system + history + context + câu hỏi

Lưu lịch sử bằng SQLite (``ChatHistoryStore``). Điểm tích hợp duy nhất cho UI là
``ConversationMemory.chat(session_id, user_message)``.

Module này TÁI SỬ DỤNG (import, không copy) pipeline đã có:
    - src.task9_retrieval_pipeline.retrieve   (retrieval hybrid + rerank + fallback)
    - src.task10_generation.{SYSTEM_PROMPT, reorder_for_llm, format_context,
                             _generate_from_context, TEMPERATURE, TOP_P}

Không sửa Task 9 / Task 10 / eval pipeline. Xem group_project/MEMORY_MODULE.md.
"""

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# group_project/src/conversation_memory.py -> parents[2] = repo root (để import src.*)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Nạp .env sớm để condense (cần OPENAI_API_KEY) không phụ thuộc thứ tự import.
load_dotenv()

# LƯU Ý: pipeline Task 9/10 kéo theo ML stack nặng (sentence-transformers, pageindex...).
# Ta IMPORT LAZY bên trong hàm (retrieve_chunks / generate_with_history) để:
#   - tầng memory + SQLite tải nhẹ, không bắt buộc cả ML stack lúc import module
#   - test monkeypatch retrieve_chunks / generate_with_history mà không cần deps thật

__all__ = [
    "ChatHistoryStore",
    "ConversationMemory",
    "condense_question",
    "generate_with_history",
    "retrieve_chunks",
]

# Mặc định
DEFAULT_TOP_K = 5
# history_window = số LƯỢT (mỗi lượt = user + assistant) đưa vào prompt làm ngữ cảnh
DEFAULT_HISTORY_WINDOW = 4
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "chat_history.db"

CONDENSE_SYSTEM_PROMPT = """Bạn là trợ lý viết lại câu hỏi cho hệ thống tìm kiếm.
Cho lịch sử hội thoại và câu hỏi follow-up mới nhất, hãy viết lại câu hỏi follow-up
thành MỘT câu hỏi độc lập, đầy đủ ngữ cảnh, hiểu được mà không cần đọc lịch sử.

Quy tắc:
- Giữ nguyên tiếng Việt và ý định gốc của người hỏi.
- Thay các tham chiếu mơ hồ ("nó", "cái đó", "vấn đề này") bằng đối tượng cụ thể từ lịch sử.
- Nếu câu hỏi đã độc lập, trả lại Y NGUYÊN.
- CHỈ trả về câu hỏi đã viết lại, KHÔNG thêm lời giải thích hay tiền tố."""


def _now() -> str:
    """Timestamp ISO8601 (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def _get_openai_client():
    """Trả OpenAI client nếu có API key hợp lệ, ngược lại None (giống Task 10)."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and not api_key.startswith("sk-xxx"):
        from openai import OpenAI

        return OpenAI(api_key=api_key)
    return None


def _history_as_messages(history: list[dict]) -> list[dict]:
    """Lọc history thành messages OpenAI hợp lệ (chỉ role user/assistant có content)."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]


def retrieve_chunks(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Wrapper lazy-import quanh ``retrieve`` của Task 9 (decouple ML stack + cho phép mock)."""
    from src.task9_retrieval_pipeline import retrieve

    return retrieve(query, top_k=top_k)


# =============================================================================
# Bước 1 — Condense: viết lại follow-up thành câu hỏi standalone (history-aware)
# =============================================================================

def condense_question(history: list[dict], question: str, *, client=None) -> str:
    """
    Viết lại câu hỏi follow-up dựa trên lịch sử hội thoại thành câu hỏi standalone.

    Fallback an toàn: nếu history rỗng hoặc không có API key -> trả về ``question`` y nguyên
    (vẫn chạy được khi demo offline).
    """
    if not history:
        return question

    client = client or _get_openai_client()
    if client is None:
        return question

    convo = _history_as_messages(history)
    convo.append(
        {
            "role": "user",
            "content": f"Câu hỏi follow-up: {question}\n\nViết lại thành câu hỏi độc lập:",
        }
    )

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "system", "content": CONDENSE_SYSTEM_PROMPT}, *convo],
            temperature=0.0,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        return rewritten or question
    except Exception:
        # Lỗi mạng/API: không chặn luồng chat, dùng câu hỏi gốc
        return question


# =============================================================================
# Bước 2 — Generation có history (tái sử dụng helper của Task 10)
# =============================================================================

def generate_with_history(
    question: str, chunks: list[dict], history: list[dict], *, client=None
) -> str:
    """
    Sinh câu trả lời có citation, prompt gồm cả lịch sử hội thoại để trả lời mạch lạc.

    Context dựng bằng ``reorder_for_llm`` + ``format_context`` của Task 10.
    Fallback không có API key: dùng ``_generate_from_context`` (extractive) của Task 10.
    """
    from src.task10_generation import (
        SYSTEM_PROMPT,
        TEMPERATURE,
        TOP_P,
        _generate_from_context,
        format_context,
        reorder_for_llm,
    )

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)

    client = client or _get_openai_client()
    if client is None:
        return _generate_from_context(question, context)

    user_message = f"Context:\n{context}\n\n---\n\nQuestion: {question}"
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *_history_as_messages(history),
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return response.choices[0].message.content or ""
    except Exception:
        return _generate_from_context(question, context)


# =============================================================================
# Lưu trữ lịch sử — SQLite
# =============================================================================

class ChatHistoryStore:
    """Lưu sessions + messages vào SQLite. Dùng ``:memory:`` cho test."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path) if db_path is not None else str(DEFAULT_DB_PATH)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: Streamlit có thể gọi từ thread khác
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title      TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                sources_json    TEXT,
                rewritten_query TEXT,
                created_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
            """
        )
        self._conn.commit()

    def create_session(self, title: str | None = None) -> str:
        session_id = uuid.uuid4().hex
        self._conn.execute(
            "INSERT INTO sessions (session_id, title, created_at) VALUES (?, ?, ?)",
            (session_id, title, _now()),
        )
        self._conn.commit()
        return session_id

    def _ensure_session(self, session_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, title, created_at) VALUES (?, ?, ?)",
            (session_id, None, _now()),
        )

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        sources: list[dict] | None = None,
        rewritten_query: str | None = None,
    ) -> int:
        self._ensure_session(session_id)
        sources_json = (
            json.dumps(sources, ensure_ascii=False) if sources is not None else None
        )
        cursor = self._conn.execute(
            """INSERT INTO messages
                 (session_id, role, content, sources_json, rewritten_query, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, sources_json, rewritten_query, _now()),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        """Trả messages theo thứ tự thời gian (cũ -> mới). ``limit`` = N message gần nhất."""
        if limit is not None:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [self._row_to_message(r) for r in rows]

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "sources": json.loads(row["sources_json"]) if row["sources_json"] else [],
            "rewritten_query": row["rewritten_query"],
            "created_at": row["created_at"],
        }

    def list_sessions(self) -> list[dict]:
        rows = self._conn.execute(
            """SELECT s.session_id, s.title, s.created_at, COUNT(m.id) AS message_count
               FROM sessions s
               LEFT JOIN messages m ON m.session_id = s.session_id
               GROUP BY s.session_id
               ORDER BY s.created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# =============================================================================
# Orchestrator — API public cho UI
# =============================================================================

class ConversationMemory:
    """
    Tầng hội thoại: nhớ lịch sử, condense follow-up, sinh trả lời có history, lưu lại.

    Cách dùng (UI chỉ cần thế này)::

        mem = ConversationMemory()
        sid = mem.new_session()
        result = mem.chat(sid, "Hình phạt tội tàng trữ ma tuý?")
        print(result["answer"])
    """

    def __init__(
        self,
        store: ChatHistoryStore | None = None,
        top_k: int = DEFAULT_TOP_K,
        history_window: int = DEFAULT_HISTORY_WINDOW,
    ):
        self.store = store if store is not None else ChatHistoryStore()
        self.top_k = top_k
        self.history_window = history_window

    def new_session(self, title: str | None = None) -> str:
        return self.store.create_session(title=title)

    def get_history(self, session_id: str, limit: int | None = None) -> list[dict]:
        return self.store.get_history(session_id, limit=limit)

    def list_sessions(self) -> list[dict]:
        return self.store.list_sessions()

    def clear(self, session_id: str) -> None:
        self.store.clear_session(session_id)

    def chat(self, session_id: str, user_message: str) -> dict:
        """
        Một lượt hội thoại đầy đủ. Trả về dict::

            {
              "answer": str,             # câu trả lời có citation
              "sources": list[dict],     # chunks dùng để trả lời (content/score/metadata)
              "rewritten_query": str,    # câu hỏi standalone sau condense
              "original_query": str,     # câu hỏi gốc của user
              "retrieval_source": str,   # "hybrid" | "pageindex" | "none"
              "session_id": str,
            }
        """
        # Lấy ngữ cảnh TRƯỚC khi ghi câu hỏi hiện tại (history không gồm lượt này)
        history = self.store.get_history(session_id, limit=self.history_window * 2)

        standalone = condense_question(history, user_message)
        chunks = retrieve_chunks(standalone, self.top_k)
        answer = generate_with_history(user_message, chunks, history)

        self.store.add_message(session_id, "user", user_message)
        self.store.add_message(
            session_id,
            "assistant",
            answer,
            sources=chunks,
            rewritten_query=standalone,
        )

        return {
            "answer": answer,
            "sources": chunks,
            "rewritten_query": standalone,
            "original_query": user_message,
            "retrieval_source": chunks[0].get("source", "none") if chunks else "none",
            "session_id": session_id,
        }


if __name__ == "__main__":
    # Console Windows mặc định cp1252 -> ép UTF-8 để in tiếng Việt không vỡ.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Smoke test: 1 câu hỏi + 1 follow-up. Dùng DB in-memory để không đụng DB thật.
    memory = ConversationMemory(store=ChatHistoryStore(db_path=":memory:"))
    sid = memory.new_session(title="smoke")

    turns = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý là gì?",
        "Còn mức cao nhất thì sao?",  # follow-up mơ hồ -> cần condense
    ]
    for turn in turns:
        print("\n" + "=" * 72)
        print(f"User: {turn}")
        result = memory.chat(sid, turn)
        print(f"  rewritten_query : {result['rewritten_query']}")
        print(
            f"  retrieval_source: {result['retrieval_source']} "
            f"({len(result['sources'])} chunks)"
        )
        print(f"  answer          : {result['answer'][:300]}")

    print("\n" + "=" * 72)
    print(f"History đã lưu: {len(memory.get_history(sid))} messages")
    memory.store.close()
