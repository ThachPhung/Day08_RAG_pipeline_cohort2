# Conversation Memory — chat history + follow-up

Phần việc: **Trương Hải Quân**. Thêm tầng hội thoại cho RAG Chatbot của nhóm,
đúng spec lead giao: **chat history, follow-up question, truyền history vào pipeline**.

## File trong folder này
| File | Vai trò |
|------|---------|
| `conversation.py` | Lõi memory. Hàm public `build_contextual_query(user_question, messages, max_turns=3)` — biến câu follow-up + lịch sử thành 1 câu hỏi đầy đủ ngữ cảnh. Không phụ thuộc Streamlit. |
| `chat_app.py` | UI Streamlit có memory (session_state.messages + hiển thị hội thoại + nút Clear chat). |
| `test_conversation.py` | Unit test phần logic (chạy offline, không cần API key). |

## Luồng hoạt động
```
user gõ follow-up ("còn dưới 18 tuổi thì sao?")
   → build_contextual_query(question, messages)        # dùng lịch sử chat
        → LLM condense thành câu standalone đầy đủ ngữ cảnh   (nếu có OPENAI_API_KEY)
        → fallback: nối lịch sử + câu hỏi                     (nếu không có key)
   → generate_with_citation(contextual_query)           # pipeline RAG có sẵn (Task 10)
   → lưu {user, assistant+sources} vào st.session_state.messages
   → render lại toàn bộ hội thoại
```

## Cách "truyền history vào pipeline"
Lịch sử được nén thành **một câu hỏi standalone** rồi mới đưa vào `generate_with_citation`.
→ retrieval chính xác hơn cho câu follow-up, **không phải sửa pipeline** của ai.
`build_contextual_query` dùng LLM viết lại (chất lượng cao); tự degrade về nối-chuỗi khi
không có API key nên vẫn chạy được offline.

## Format message (theo lead)
```python
{"role": "user", "content": "...", "contextual_query": "..."}   # contextual_query: để debug
{"role": "assistant", "content": "...", "sources": [...]}
```

## Boundaries (cho người merge)
- **Sở hữu:** toàn bộ folder `group_project/memory/`.
- **Tái sử dụng (không sửa):** `src/task10_generation.generate_with_citation` (pipeline nhóm).
- **Không đụng:** các file task của teammate, `group_project/app.py`.
- Tích hợp vào `group_project/app.py`: chỉ cần `from group_project.memory.conversation import build_contextual_query`
  rồi thay `generate_with_citation(question)` bằng `generate_with_citation(build_contextual_query(question, messages))`,
  thêm `st.session_state.messages` + nút Clear chat (xem `chat_app.py` làm mẫu đầy đủ).

## Chạy & test
```bash
# Unit test (offline, không cần key/index)
python -m pytest group_project/memory/test_conversation.py -v

# Smoke logic (in ra câu follow-up đã được viết lại)
python group_project/memory/conversation.py

# Chạy app (cần OPENAI_API_KEY + index Task 4 đã build)
streamlit run group_project/memory/chat_app.py
```

> Windows: nếu gặp `UnicodeEncodeError` khi chạy script in `✓`/`→`, đặt biến môi trường `PYTHONUTF8=1`.
