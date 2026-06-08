# Conversation Memory — Wrap-up cho người merge

> **Phần việc:** Conversation memory cho RAG Chatbot (follow-up questions, lưu chat history,
> rewrite câu hỏi). **Người làm:** Trương Hải Quân. **Nhánh:** `feature/memory_Quan`.
>
> Đọc 2 phút là rạp code được. Phần **Contract** và **Boundaries** là thứ bạn cần nhất khi merge.

---

## 1. Tóm tắt logic

Triển khai **conversational RAG** chuẩn (giống LangChain `create_history_aware_retriever` +
`create_retrieval_chain`) — **2 lần gọi LLM, cả hai đều thấy lịch sử hội thoại**:

```
user_message + session_id
        │
        ▼
[1] condense_question(history, user_message)      ← LLM #1: viết lại follow-up
        │                                            thành câu hỏi STANDALONE
        │   vd: "còn mức cao nhất?" ──► "Mức hình phạt cao nhất cho tội tàng trữ ma tuý là gì?"
        ▼
    retrieve_chunks(standalone, top_k)            ← Task 9 (hybrid + rerank + fallback)
        │
        ▼
[2] generate_with_history(user_message, chunks, history)  ← LLM #2: trả lời CÓ citation,
        │                                                    prompt gồm cả history → mạch lạc
        ▼
   lưu (user + assistant) vào SQLite  ──►  trả dict kết quả
```

Vì sao tách 2 bước: retriever cần câu **tự đủ nghĩa** (không search được "còn cái đó thì
sao?"), còn generation cần **history** để giữ mạch hội thoại và giải nghĩa tham chiếu.

**Fallback an toàn** (không chặn luồng): thiếu `OPENAI_API_KEY` → condense trả câu hỏi gốc,
generation dùng extractive (`_generate_from_context` của Task 10); lỗi API → cũng fallback.

---

## 2. Contract (API public — UI & eval chỉ cần cái này)

```python
from group_project.src.conversation_memory import ConversationMemory

memory = ConversationMemory()                 # tuỳ chọn: top_k=5, history_window=4
session_id = memory.new_session(title="...")  # tạo phiên mới, trả về str id

result = memory.chat(session_id, "Hình phạt tội tàng trữ ma tuý?")
```

`memory.chat(session_id, user_message)` trả về **dict**:

| key | kiểu | ý nghĩa |
|-----|------|---------|
| `answer` | `str` | câu trả lời có citation |
| `sources` | `list[dict]` | chunks đã dùng (mỗi chunk: `content`, `score`, `source`, `metadata`) |
| `rewritten_query` | `str` | câu hỏi standalone sau condense (để debug/hiển thị) |
| `original_query` | `str` | câu hỏi gốc của user |
| `retrieval_source` | `str` | `"hybrid"` \| `"pageindex"` \| `"none"` |
| `session_id` | `str` | phiên hiện tại |

Hàm phụ trợ: `memory.get_history(session_id)`, `memory.list_sessions()`, `memory.clear(session_id)`.

> **UI teammate:** chỉ cần gọi đúng 2 dòng `new_session()` + `chat()` ở trên. Xem
> `group_project/src/app.py` (Streamlit demo) làm mẫu — copy logic, thay giao diện tuỳ ý.

---

## 3. Boundaries (RANH GIỚI — đọc trước khi merge)

| | Phần memory SỞ HỮU (Quân) | KHÔNG đụng tới |
|---|---|---|
| **File** | `group_project/src/conversation_memory.py`, `group_project/src/app.py`, `group_project/src/test_memory.py`, `group_project/src/__init__.py`, `group_project/MEMORY_MODULE.md` | `src/task9_retrieval_pipeline.py`, `src/task10_generation.py`, `group_project/evaluation/*` |
| **Sửa file gốc** | chỉ thêm vài dòng vào `.gitignore` (mục *Conversation memory*) | — |
| **Trách nhiệm** | nhớ hội thoại, condense follow-up, generation có history, lưu/đọc SQLite, expose `chat()` | retrieval/ranking, citation rules, sinh câu trả lời gốc, metric eval |

**Tái sử dụng (import, KHÔNG copy, KHÔNG sửa):**
- `src.task9_retrieval_pipeline.retrieve`
- `src.task10_generation`: `SYSTEM_PROMPT`, `reorder_for_llm`, `format_context`, `_generate_from_context`, `TEMPERATURE`, `TOP_P`

→ Vì chỉ **thêm file mới** + import lại, **gần như không có merge conflict**. Conflict khả dĩ duy
nhất là `.gitignore` (rất dễ giải quyết).

> **Lưu ý kỹ thuật:** import Task 9/10 được **lazy** (bên trong hàm) vì pipeline kéo theo ML
> stack nặng. Nhờ vậy module memory + SQLite tải nhẹ và test mock được mà không cần ML stack.

---

## 4. Dependency & phối hợp

- **Không chờ ai:** Task 9/10 đã xong; app.py demo tự dựng. Test chạy độc lập (mock retrieval+gen).
- **Để chạy THẬT** (không block code): `OPENAI_API_KEY` trong `.env`; đã build index Task 4
  (`python -m src.task4_chunking_indexing`). Thiếu → vẫn chạy ở chế độ fallback.
- **Lưu trữ:** SQLite tại `data/chat_history.db` (đã gitignore). `sqlite3` là stdlib — **không
  thêm dependency mới**. `streamlit`/`openai` đã có sẵn trong `requirements.txt`.
- **Phối hợp 1 chiều:** UI teammate gọi `ConversationMemory.chat(...)` theo Contract ở trên.

---

## 5. Cách chạy & test

```bash
# Unit test (KHÔNG cần API key / index — mock sạch)
pytest group_project/src/test_memory.py -v          # 13 test

# Smoke nhanh module (1 câu + 1 follow-up, in ra rewritten_query)
python -m group_project.src.conversation_memory

# App demo end-to-end (cần OPENAI_API_KEY + index Task 4)
streamlit run group_project/src/app.py
```

Trong app, bật toggle **🔍 Debug** ở sidebar để thấy câu hỏi follow-up được viết lại thế nào.

---

## 6. Gợi ý điểm tích hợp khi merge

1. **App nhóm:** nếu nhóm dùng `app.py` ở repo root, chỉ cần import `ConversationMemory` và gọi
   `chat()` — không cần biết nội bộ condense/retrieve.
2. **Eval pipeline:** giữ nguyên (`generate_with_citation` không bị đụng). Nếu muốn eval *có
   memory*, gọi `ConversationMemory.chat()` thay cho `generate_with_citation()` và map
   `result["sources"]` → `retrieval_context`.
3. **Đổi backend lưu trữ:** chỉ cần thay `ChatHistoryStore` bằng class cùng interface
   (`create_session`/`add_message`/`get_history`/...) rồi truyền vào `ConversationMemory(store=...)`.
