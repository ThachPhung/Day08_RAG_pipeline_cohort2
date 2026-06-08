# Bài Tập Nhóm — RAG Chatbot + Evaluation

Nhóm 7 thành viên | Chủ đề: **Pháp luật ma tuý & tin tức liên quan**

---

## Kiến Trúc Hệ Thống

```
User (Streamlit UI)
        │
        ▼
┌───────────────────────────────────────┐
│  group_project/app.py                 │  ← UI + follow-up đơn giản
│  group_project/src/app.py             │  ← UI + SQLite ConversationMemory
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│  group_project/pipeline.py            │  ← Interface chung (Lead)
│    rag_query() / rag_retrieve()       │
│    chat_turn() + ConversationMemory   │
└───────────────────────────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
Task 9      Task 10 (group)
retrieve    answer_question + citation
(hybrid)    anti-hallucination policy
   │
   ├─ Semantic (dense)
   ├─ Lexical (BM25)
   ├─ RRF + Rerank
   └─ PageIndex fallback
        │
        ▼
group_project/index/chunks.pkl
data/standardized/*.md
```

---

## Phân Công Công Việc

| Thứ tự | Vai trò | Thành viên | Nhiệm vụ | Trạng thái |
|--------|---------|------------|----------|------------|
| 1 | **Lead** | Thạch Phùng | Chốt interface `pipeline.py`, integration, README, demo | ✅ |
| 2 | Dataset Owner | Hoàng Phương Thảo | `evaluation/golden_dataset.json` (51 câu Q&A) | ✅ |
| 3 | Retrieval Owner | Lương Quốc Đoàn | `group_project/src/task5–9` hybrid retrieval | ✅ |
| 4 | Generation Owner | Bùi Minh Hiếu | `group_project/src/task10_generation.py` citation + policy | ✅ |
| 5 | UI Owner | Anh Tuấn | `group_project/app.py` Streamlit chatbot | ✅ |
| 6 | Memory Owner | Trương Hải Quân | `conversation_memory.py` + `src/app.py` follow-up | ✅ |
| 7 | Evaluation Owner | Nguyễn Sĩ Việt | `evaluation/eval_pipeline.py` + `results.md` A/B | ✅ |
| 8 | **Lead** | Thạch Phùng | `demo.sh`, test tích hợp, tài liệu chạy demo | ✅ |

---

## Pipeline Interface (Contract chung)

Mọi module UI / Memory / Eval **import từ một chỗ**:

```python
from group_project.pipeline import rag_query, rag_retrieve, chat_turn, ConversationMemory

# Một lượt hỏi đáp (không memory)
result = rag_query("Hình phạt tàng trữ ma tuý?")
answer = result["answer"]
sources = result["sources"]          # list dict cho UI
retrieval_source = result["retrieval_source"]  # hybrid | pageindex

# Follow-up có memory
memory = ConversationMemory()
session_id = memory.new_session()
turn = chat_turn(memory, session_id, "Còn mức cao nhất thì sao?")
```

**Format `sources` (UI):**

```python
{
    "label": "luat-phong-chong-ma-tuy.md | legal | chunk 12",
    "source": "luat-phong-chong-ma-tuy.md",
    "type": "legal",
    "chunk_index": 12,
    "score": 0.8421,
    "preview": "Điều 5. Các hành vi bị nghiêm cấm..."
}
```

---

## Hướng Dẫn Chạy

### 1. Cài đặt

```bash
pip install -r requirements.txt
cp .env.example .env   # điền OPENAI_API_KEY (tuỳ chọn)
```

### 2. Chuẩn bị dữ liệu (bài cá nhân)

```bash
python3 -m src.task3_convert_markdown
```

Index nhóm tự build lần đầu khi query (lưu tại `group_project/index/`).

### 3. Chạy Chatbot

**UI cơ bản + follow-up đơn giản:**

```bash
streamlit run group_project/app.py
```

**UI + Conversation Memory (SQLite, condense follow-up):**

```bash
streamlit run group_project/src/app.py
```

### 4. Chạy Evaluation

```bash
python3 -m group_project.evaluation.eval_pipeline
```

Kết quả: `group_project/evaluation/results.md`

### 5. Demo tích hợp (Lead)

```bash
bash group_project/demo.sh
```

---

## Deliverables

| File | Mô tả |
|------|-------|
| `pipeline.py` | Interface chung cho toàn nhóm |
| `app.py` | Chatbot UI (Người 5) |
| `src/conversation_memory.py` | Memory + follow-up (Người 6) |
| `src/app.py` | Chatbot có SQLite memory |
| `evaluation/golden_dataset.json` | 51 cặp Q&A |
| `evaluation/eval_pipeline.py` | Eval + A/B hybrid vs dense-only |
| `evaluation/results.md` | Báo cáo điểm số |
| `demo.sh` | Script demo buổi trình bày |

---

## A/B Evaluation

| Config | Mô tả |
|--------|-------|
| **A — hybrid_rerank** | Semantic + BM25 + RRF + rerank + fallback |
| **B — dense_only** | Chỉ semantic, không BM25/rerank |

Metrics: Faithfulness, Answer Relevance, Context Recall, Context Precision (heuristic offline).

---

## Lưu ý

- **Không sửa** `src/` (bài cá nhân) — nhóm import và wrap trong `group_project/src/`.
- `.env` và `group_project/index/` không commit (đã có `.gitignore`).
- Thiếu `OPENAI_API_KEY`: pipeline vẫn chạy với trả lời extractive + citation từ context.
