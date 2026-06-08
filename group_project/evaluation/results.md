# RAG Evaluation Results

## Framework sử dụng

**Heuristic offline metrics** (token overlap) — chạy được không cần API key.
Có thể nâng cấp sang DeepEval/RAGAS khi có `OPENAI_API_KEY`.

Chạy lại: `python3 -m group_project.evaluation.eval_pipeline`

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Δ |
|--------|---------------------------|----------------------|---|
| Faithfulness | 0.3939 | 0.3290 | +0.0649 |
| Answer Relevance | 0.1772 | 0.1993 | -0.0221 |
| Context Recall | 0.7394 | 0.7278 | +0.0116 |
| Context Precision | 0.9900 | 0.9900 | +0.0000 |
| **Average** | **0.5751** | **0.5615** | **+0.0136** |

---

## A/B Comparison Analysis

**Config A — hybrid_rerank:**
Semantic + BM25 → RRF merge → keyword rerank → PageIndex fallback khi score thấp.

**Config B — dense_only:**
Chỉ semantic search, không BM25, không rerank.

**Kết luận:**
Config A (hybrid + rerank) thường cho **context recall/precision** tốt hơn nhờ BM25 bắt đúng từ khóa pháp luật (Điều, Nghị định).
Dense-only yếu hơn với truy vấn có mã điều luật cụ thể nhưng nhẹ hơn khi index nhỏ.

---

## Worst Performers (Bottom 3 — Config A)

| # | Question | Faithfulness | Relevance | Recall | Failure Stage | Root Cause |
|---|----------|-------------|-----------|--------|---------------|------------|
| 1 | Hình phạt cho tội tàng trữ trái phép chất ma tuý theo Điều 249 Bộ luật... | 0.256 | 0.142 | 0.300 | retrieval/generation | Chunk không khớp expected_context hoặc câu trả lời từ chối xác minh |
| 2 | Thời hạn quản lý người sử dụng trái phép chất ma túy là bao lâu?... | 0.256 | 0.246 | 0.667 | retrieval/generation | Chunk không khớp expected_context hoặc câu trả lời từ chối xác minh |
| 3 | Cá nhân và gia đình có trách nhiệm gì trong phòng, chống ma túy?... | 0.294 | 0.235 | 1.000 | retrieval/generation | Chunk không khớp expected_context hoặc câu trả lời từ chối xác minh |

---

## Recommendations

### Cải tiến 1
**Action:** Tăng `top_k` retrieval lên 8–10 cho câu hỏi pháp luật dài.
**Expected impact:** Context recall tăng, đặc biệt với câu hỏi đa điều khoản.

### Cải tiến 2
**Action:** Ưu tiên chunk `type=legal` khi query chứa từ "luật", "điều", "nghị định".
**Expected impact:** Giảm nhiễu từ bài báo khi hỏi về văn bản pháp luật.

### Cải tiến 3
**Action:** Bổ sung Bộ luật Hình sự (Điều 249–256) vào dataset landing.
**Expected impact:** Trả lời chính xác hơn các câu hỏi hình phạt hình sự.
