# RAG Evaluation Results

## Framework sử dụng

Offline heuristic evaluator trong `group_project/evaluation/eval_pipeline.py`.

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (dense-only) | Delta |
|--------|-----------------------------|------------------------|-------|
| Faithfulness | 0.946 | 0.949 | -0.003 |
| Answer Relevance | 0.645 | 0.591 | +0.054 |
| Context Recall | 0.778 | 0.742 | +0.036 |
| Context Precision | 0.960 | 0.840 | +0.120 |
| Average | 0.832 | 0.780 | +0.052 |

## A/B Comparison Analysis

**Config A:** Semantic + BM25 retrieval, RRF fusion, keyword-overlap reranking, PageIndex fallback.

**Config B:** Semantic retrieval only, no reranking; used as the baseline.

**Kết luận:** Config A có điểm trung bình tốt hơn trong bộ golden dataset hiện tại. Hybrid + rerank thường ổn hơn khi câu hỏi có từ khóa pháp lý cụ thể; dense-only là baseline đơn giản để kiểm tra độ phủ embedding.

## Worst Performers (Bottom 3)

| # | Question | Faithfulness | Relevance | Recall | Failure Stage | Root Cause |
|---|----------|--------------|-----------|--------|---------------|------------|
| 1 | Vì sao nhóm dùng BM25 trong lexical search? | 0.902 | 0.500 | 0.357 | answering | Expected evidence was weak or split across noisy chunks. |
| 2 | Khi nào pipeline dùng PageIndex hoặc fallback vectorless? | 0.932 | 0.375 | 0.211 | retrieval | Expected evidence was weak or split across noisy chunks. |
| 3 | Pipeline nhóm dùng các bước retrieval nào trước khi fallback? | 0.949 | 0.500 | 0.188 | retrieval | Expected evidence was weak or split across noisy chunks. |

## Recommendations

### Cải tiến 1
**Action:** Làm sạch markdown đã crawl, bỏ menu/navigation và ký tự lỗi trước khi index.
**Expected impact:** Tăng context precision và giảm nhiễu trong câu trả lời.

### Cải tiến 2
**Action:** Thêm metadata `law_article`, `publisher`, `published_date` khi chunking.
**Expected impact:** Citation rõ hơn và retrieval chính xác hơn cho câu hỏi theo điều/khoản.

### Cải tiến 3
**Action:** Thử reranker multilingual thật như Jina/Qwen khi có API hoặc GPU.
**Expected impact:** Tăng answer relevance cho câu hỏi tiếng Việt dài và nhiều thực thể.
