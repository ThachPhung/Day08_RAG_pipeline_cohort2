# RAG Evaluation Results

## Framework sử dụng

Framework: **Local heuristic evaluator**.

Lý do chọn: chạy được offline, không cần OpenAI/DeepEval/RAGAS API key, phù hợp để demo nhanh pipeline nhóm. Các metric vẫn bám theo 4 nhóm đánh giá RAG phổ biến: faithfulness, answer relevance, context recall, context precision.

Số test cases hiện có: **51**.

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (hybrid no rerank) | Delta |
|--------|-----------------------------|------------------------------|-------|
| Faithfulness | 0.898 | 0.894 | +0.004 |
| Answer Relevance | 0.453 | 0.457 | -0.004 |
| Context Recall | 0.584 | 0.584 | +0.000 |
| Context Precision | 0.886 | 0.886 | +0.000 |
| **Average** | **0.705** | **0.705** | **+0.000** |

---

## A/B Comparison Analysis

**Config A:** Hybrid retrieval gồm semantic search + lexical BM25, merge bằng RRF, sau đó rerank local theo độ liên quan với query.

**Config B:** Hybrid retrieval giống Config A nhưng bỏ bước reranking để kiểm tra ảnh hưởng của reranker.

**Kết luận:** Config A có điểm trung bình cao hơn trong lần chạy hiện tại. Nếu Config A tốt hơn, reranking giúp đẩy chunk liên quan lên đầu. Nếu Config B tương đương hoặc tốt hơn, dataset/context hiện tại còn nhỏ nên lợi ích reranking chưa thể hiện rõ.

---

## Worst Performers (Bottom 3 - Config A)

| # | Question | Faithfulness | Relevance | Recall | Precision | Root Cause |
|---|----------|--------------|-----------|--------|-----------|------------|
| 1 | Nếu câu hỏi yêu cầu thông tin không có trong tài liệu đã index thì chatbot phải trả lời thế nào? | 0.940 | 0.183 | 0.170 | 0.000 | Retriever chưa lấy đủ expected context hoặc dữ liệu chuẩn hóa còn thiếu chi tiết. |
| 2 | Dataset có đủ bằng chứng để tư vấn một người cụ thể sẽ bị phạt bao nhiêu năm tù không? | 0.908 | 0.258 | 0.331 | 0.000 | Retriever chưa lấy đủ expected context hoặc dữ liệu chuẩn hóa còn thiếu chi tiết. |
| 3 | Thời hạn cai nghiện ma túy tự nguyện tại cơ sở cai nghiện là bao lâu? | 0.922 | 0.207 | 0.540 | 0.600 | Answer extractive còn ngắn, chưa bao phủ đủ expected answer. |

---

## Recommendations

### Cải tiến 1
**Action:** Bổ sung golden dataset lên tối thiểu 15 Q&A và phủ đều nhóm câu hỏi pháp luật, cai nghiện, danh mục chất ma tuý, tin tức nghệ sĩ.

**Expected impact:** Kết quả đánh giá ổn định hơn và đáp ứng đúng rubric bài nhóm.

### Cải tiến 2
**Action:** Convert PDF pháp luật bằng parser mạnh hơn để lấy được điều/khoản chi tiết thay vì chỉ dùng fallback summary.

**Expected impact:** Tăng context recall cho câu hỏi cần căn cứ điều luật cụ thể.

### Cải tiến 3
**Action:** Thay local heuristic reranker bằng cross-encoder multilingual hoặc Jina Reranker khi có API key.

**Expected impact:** Tăng answer relevance và context precision trên các câu hỏi dài hoặc nhiều thực thể.
