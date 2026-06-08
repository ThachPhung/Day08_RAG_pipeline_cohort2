# RAG Evaluation Results

## 1. Mục tiêu đánh giá

File này ghi lại kết quả test/evaluation cho pipeline nhóm từ **Task 1 đến Task 10**. Mục tiêu là kiểm tra toàn bộ luồng RAG có chạy được không, bao gồm thu thập dữ liệu, chuẩn hoá, chunking, indexing, retrieval, reranking, generation có citation và đánh giá chất lượng câu trả lời.

Evaluation được chạy trên `golden_dataset.json` với **51 test cases**.

## 2. Framework sử dụng

Framework: **Local heuristic evaluator**.

Lý do chọn: môi trường hiện tại không có OpenAI API key, vì vậy không dùng trực tiếp DeepEval/RAGAS/TruLens dạng LLM-as-a-judge. Thay vào đó, evaluator local mô phỏng các nhóm metric phổ biến của RAGAS/DeepEval để có thể chạy offline, ổn định và phù hợp demo trên máy local.

| Metric | Ý nghĩa |
|---|---|
| Faithfulness | Câu trả lời có bám vào context được truy xuất hay không, có citation hay không. |
| Answer Relevance | Câu trả lời có liên quan đến câu hỏi và expected answer hay không. |
| Context Recall | Context truy xuất có bao phủ expected answer / expected context hay không. |
| Context Precision | Trong các context lấy về, bao nhiêu phần thật sự hữu ích cho câu hỏi. |

## 3. Đối chiếu yêu cầu README

| Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|
| Golden dataset tối thiểu 15 Q&A | Đạt | Có 51 test cases |
| Chạy 4 metrics RAG | Đạt | Faithfulness, Answer Relevance, Context Recall, Context Precision |
| So sánh A/B ít nhất 2 configs | Đạt | Config A có rerank, Config B không rerank |
| Báo cáo bảng điểm và phân tích | Đạt | Có overall scores, worst performers, hạn chế và cải tiến |

## 4. Phạm vi test Task 1 đến Task 10

| Thành phần | File | Kết quả |
|---|---|---|
| Task 1 | `task1_collect_legal_docs.py` | Compile/import pass |
| Task 2 | `task2_crawl_news.py` | Compile/import pass, không crawl thật do phụ thuộc mạng/crawl4ai |
| Task 3 | `task3_convert_markdown.py` | Compile/import pass |
| Task 4 | `task4_chunking_indexing.py` | Compile/import pass |
| Task 5 | `task5_semantic_search.py` | Compile/import pass |
| Task 6 | `task6_lexical_search.py` | Compile/import pass |
| Task 7 | `task7_reranking.py` | Compile/import pass |
| Task 8 | `task8_pageindex_vectorless.py` | Compile/import pass |
| Task 9 | `task9_retrieval_pipeline.py` | Retrieval smoke test pass |
| Task 10 | `task10_generation.py` | Generation smoke test pass |
| Evaluation | `eval_pipeline.py` | Chạy đủ golden dataset và xuất report |

## 5. Cấu hình A/B comparison

| Config | Mô tả |
|---|---|
| Config A | Hybrid retrieval gồm semantic search + lexical BM25, merge bằng RRF, sau đó reranking local. |
| Config B | Hybrid retrieval giống Config A nhưng bỏ bước reranking. |

## 6. Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (hybrid no rerank) | Delta |
|--------|-----------------------------|------------------------------|-------|
| Faithfulness | 0.812 | 0.924 | -0.112 |
| Answer Relevance | 0.426 | 0.332 | +0.094 |
| Context Recall | 0.629 | 0.638 | -0.009 |
| Context Precision | 0.361 | 0.922 | -0.561 |
| **Average** | **0.557** | **0.704** | **-0.147** |

## 7. Phân tích kết quả

Config thắng trong lần chạy hiện tại: **Config B**.

- Config A overall: **0.557**
- Config B overall: **0.704**
- Config A kiểm tra tác động của reranker local sau hybrid retrieval.
- Config B phản ánh chất lượng hybrid retrieval sau RRF khi không rerank.
- Nếu Config B cao hơn, reranker local hiện tại chưa đủ tốt hoặc đang đẩy một số chunk hữu ích xuống thấp.

## 8. Worst Performers - Config A

| # | Question | Faithfulness | Answer Relevance | Context Recall | Context Precision | Root Cause |
|---|----------|--------------|------------------|----------------|-------------------|------------|
| 1 | Nếu câu hỏi yêu cầu thông tin không có trong tài liệu đã index thì chatbot phải trả lời thế nào? | 0.802 | 0.337 | 0.208 | 0.000 | Retriever chưa lấy đủ expected context hoặc dữ liệu chuẩn hóa còn thiếu chi tiết. |
| 2 | Dataset có đủ bằng chứng để tư vấn một người cụ thể sẽ bị phạt bao nhiêu năm tù không? | 0.802 | 0.243 | 0.468 | 0.000 | Retriever chưa lấy đủ expected context hoặc dữ liệu chuẩn hóa còn thiếu chi tiết. |
| 3 | Thời hạn cai nghiện ma túy tự nguyện tại cơ sở cai nghiện là bao lâu? | 0.796 | 0.241 | 0.540 | 0.000 | Answer extractive còn ngắn, chưa bao phủ đủ expected answer. |

## 9. Nhận xét về evaluator

`eval_pipeline.py` hỗ trợ nhiều schema source khác nhau để chấm đúng output từ retrieval và generation: `content`, `preview`, `text`, `page_content`, `context`.

Lý do: `task10_generation.py` format source cho UI bằng trường `preview`, trong khi retrieval raw thường dùng `content`. Nếu evaluator chỉ đọc `content`, điểm context của Config A có thể bị thấp giả.

## 10. Hạn chế

- Local heuristic evaluator không thay thế hoàn toàn DeepEval/RAGAS/TruLens vì không có LLM judge.
- Task 2 crawler chưa chạy crawl thật trong lần test này do phụ thuộc mạng và package `crawl4ai`.
- Reranker local còn đơn giản, chủ yếu dựa trên keyword overlap.
- Một số câu hỏi cần hiểu pháp lý sâu nên heuristic overlap có thể chấm chưa hoàn toàn giống con người.

## 11. Hướng cải thiện

| Cải tiến | Hành động | Expected impact |
|---|---|---|
| Cải thiện reranking | Dùng cross-encoder multilingual hoặc Jina Reranker khi có API key/model phù hợp. | Tăng context precision và giúp Config A tốt hơn. |
| Cải thiện parsing PDF | Dùng parser tốt hơn để giữ điều/khoản/mục rõ ràng. | Tăng context recall cho câu hỏi pháp luật. |
| Bổ sung framework thật | Khi có API key, chạy thêm RAGAS/DeepEval để so sánh với local heuristic. | Báo cáo thuyết phục hơn, bám sát yêu cầu framework. |
| Mở rộng golden dataset | Thêm câu hỏi phủ nhiều nhóm: luật, cai nghiện, danh mục chất, tin tức nghệ sĩ, câu hỏi ngoài dữ liệu. | Kết quả đánh giá ổn định hơn. |

## 12. Kết luận cuối

Pipeline nhóm từ Task 1 đến Task 10 đã chạy được ở mức local demo. Evaluation pipeline đọc được golden dataset, chạy A/B comparison và xuất báo cáo kết quả.

Trong lần chạy hiện tại, **Config B** đạt kết quả tốt hơn theo overall score.