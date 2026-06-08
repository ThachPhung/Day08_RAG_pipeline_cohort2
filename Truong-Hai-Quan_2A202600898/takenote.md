# 📝 Take-note — Bài cá nhân Day08 RAG Pipeline v2

> Wrap-up toàn bộ phần việc cá nhân (Task 1–10). Chủ đề: **RAG về pháp luật ma tuý
> Việt Nam + tin tức nghệ sĩ liên quan ma tuý.**
> Kết quả: **`pytest tests/test_individual.py` → 35 passed / 0 skipped.**

---

## 1. Tổng quan kiến trúc

```
                          ┌─────────────── INGESTION (offline) ───────────────┐
 PDF luật (scan ảnh) ──OCR(gpt-4o-mini vision)──┐
 .txt tội phạm ma tuý ───────────────────────────┤
 Bài báo (crawl) ──► JSON ──MarkItDown/format──► │──► chunk (800/120)
                                                  │       │
                                                  │       ▼  embed (OpenAI 1536-d)
                                                  └──► Weaviate Cloud (vector + BM25)
                          └────────────────────────────────────────────────────┘

 Query ──► Semantic (near_vector) ─┐
       └─► Lexical  (BM25)        ─┴─► RRF merge ─► Rerank ─► [score<thr?]─► PageIndex fallback
                                                                 │
                                                                 ▼
                                          reorder (chống lost-in-the-middle)
                                                                 ▼
                                          gpt-4o-mini ─► câu trả lời CÓ CITATION
```

---

## 2. Tech stack & lý do chọn

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Embedding | OpenAI `text-embedding-3-small` (1536-d) | Multilingual tốt cho tiếng Việt, rẻ, không phải tải model nặng. Vector chuẩn hoá L2 → cosine = dot. |
| Vector store | **Weaviate Cloud** (sandbox) | Hybrid search built-in (dense + BM25 + fusion), đúng chuẩn production, không cần Docker. |
| Chunking | `RecursiveCharacterTextSplitter` 800/120 | 800 ký tự gói gọn 1–2 khoản luật; overlap 120 (15%) giữ ngữ cảnh nối. |
| Lexical | Weaviate BM25 built-in (+ fallback `rank-bm25`) | Đúng "default BM25"; dùng Weaviate BM25 ăn **+5 bonus**. |
| Rerank | Cross-encoder: Jina → OpenAI-embed → overlap | Nhiều tầng fallback, luôn chạy được kể cả thiếu key. |
| Vectorless | **PageIndex** REST API thật | Fallback khi hybrid yếu; PageIndex tự OCR PDF scan. |
| Generation | OpenAI `gpt-4o-mini`, temp 0.3, top_p 0.9 | RAG cần factual; nhiệt độ thấp cho ổn định, có citation. |
| OCR PDF scan | `gpt-4o-mini` vision + PyMuPDF | Chất lượng tiếng Việt cao, không cần cài Tesseract/torch. |

---

## 3. Từng task — file & cách làm

| Task | File | Tóm tắt | Điểm |
|---|---|---|---|
| Hạ tầng | `src/rag_common.py` | Paths, OpenAI embed, Weaviate client, tokenizer VI, fix UTF-8 stdout | — |
| 1 | (sẵn) `data/landing/legal/` | 3 PDF luật + 1 .txt tội phạm ma tuý | 3 |
| 2 | `src/task2_crawl_news.py` | `requests`+`BeautifulSoup` crawl **7 bài** VnExpress/VietnamNet → JSON có url/title/date | 3 |
| 3 | `src/task3_convert_markdown.py` | MarkItDown (PDF/TXT) + JSON→MD cho tin → `data/standardized/` | 4 |
| 4 | `src/task4_chunking_indexing.py` | load → chunk 800/120 → embed → nạp Weaviate (self-provided vectors) | 7 |
| 5 | `src/task5_semantic_search.py` | Weaviate `near_vector`, score = 1 − cosine_distance | 6 |
| 6 | `src/task6_lexical_search.py` | Weaviate BM25 (fallback rank-bm25 cục bộ) | 6 |
| 7 | `src/task7_reranking.py` | `rerank` (cross-encoder) + `rerank_mmr` + `rerank_rrf` | 6 |
| 8 | `src/task8_pageindex_vectorless.py` | PageIndex thật: `/doc/` upload (server tự OCR) → tree + **LLM tree-search** | 4 |
| 9 | `src/task9_retrieval_pipeline.py` | `retrieve()`: RRF merge → rerank → fallback PageIndex theo threshold | 7 |
| 10 | `src/task10_generation.py` | `reorder_for_llm` + `format_context` + `generate_with_citation` | 4 |
| Extra | `src/ocr_legal_pdf.py` | OCR PDF scan (resumable, gap-filling) | — |

---

## 4. Dữ liệu đã tạo

- `data/landing/news/*.json` — **7 bài báo** (Miu Lê, Long Nhật, "sao Việt vướng ma tuý"…)
- `data/standardized/legal/*.md` — **4 file**: tội phạm ma tuý (.txt) + 3 luật đã OCR
  - `luat120-2025-luat-phong-chong-ma-tuy.md` — 33/33 trang
  - `ND28-2026-danh-muc-chat-cam.md` — 40/40 trang
  - `105.signed_02-huong-dan-thi-hanh-...md` — 72/72 trang
- `data/standardized/news/*.md` — 7 file
- Weaviate collection `DrugLawDocs` — **621 chunks** (11 documents)

---

## 5. Vấn đề gặp & cách xử lý (phần quan trọng để nhớ)

1. **Console Windows cp1252 crash khi in `✓`/tiếng Việt**
   → `_force_utf8_stdout()` (reconfigure stdout/stderr = utf-8), import ở mọi script.

2. **3 PDF luật là ảnh scan** (1 ảnh/trang, ~0 ký tự text) → MarkItDown ra rỗng
   → OCR bằng `gpt-4o-mini` vision: PyMuPDF render trang → ảnh → model đọc lại chữ.
   → Heuristic phát hiện scan: `ký tự / số trang < 50` (không dùng tổng ký tự, vì
     file 105 có 148 ký tự rác ở 72 trang vẫn là scan).

3. **OCR rớt trang do rate limit 429 (TPM 200K của gpt-4o-mini)**
   - Ảnh `detail:"high"` tốn nhiều token → 10 worker làm bão hoà TPM, rớt ~32 trang.
   - **Cách xử lý:** hạ xuống **2 workers** + `max_retries=10` (SDK tự backoff theo
     header `Retry-After`) + **gap-filling resumable**: mỗi lần chạy chỉ OCR trang
     còn thiếu (đọc lại trang đã có từ `.md`), chạy lại tới khi "Còn thiếu 0".
   - Kết quả: 32 → 3 → 0 trang thiếu, không tốn token làm lại.
   - ⚠️ Bài học: **đợi hết limit không giải quyết gốc** (TPM reset mỗi phút); phải
     hạ *tốc độ gửi* xuống dưới trần. Muốn nhanh thì nâng tier OpenAI.

4. **Weaviate URL không có `https://`** → client v4 `connect_to_weaviate_cloud` tự
   xử lý, kết nối OK.

5. **Thiếu creds vẫn phải chạy được** → mọi module fallback graceful: semantic trả
   `[]` khi chưa có Weaviate, lexical tự chuyển rank-bm25 cục bộ, PageIndex trả `[]`
   khi chưa có key → test skip/pass thay vì lỗi.

6. **Jina không thấy key dù đã có trong .env** → `task7` chỉ import `rag_common`
   *lazy* (trong hàm) nên `load_dotenv()` chưa chạy lúc đọc `JINA_API_KEY`.
   → import `rag_common` ở **top-level** của task7.

7. **PageIndex `/retrieval/` đã DEPRECATED** (trả `retrieved_nodes: []`); chat API
   `/chat/completions` thì reasoning rất chậm (>5 phút, timeout). Đồng thời cờ
   `retrieval_ready` không bao giờ thành `true` (chỉ `status=completed`).
   → Giải pháp: lấy **tree** (`GET /doc/{id}/?type=tree`, có text OCR theo từng
   Điều) rồi để **gpt-4o-mini tree-search** chọn node liên quan → đúng tinh thần
   "vectorless", nhanh (~6s, cache tree), trả về chunk chuẩn.

---

## 6. Cấu hình (.env)

```ini
# OpenAI: đọc từ biến môi trường hệ thống (đã có sẵn)
WEAVIATE_URL=<rest-endpoint cluster sandbox>
WEAVIATE_API_KEY=<admin api key>
PAGEINDEX_API_KEY=        # (tuỳ chọn) Task 8 — đăng ký pageindex.ai
# JINA_API_KEY=          # (tuỳ chọn) Task 7 — nâng cấp reranker
```

> ⏰ **Weaviate sandbox free hết hạn sau 14 ngày** — cần tái tạo cluster + chạy lại
> Task 4 nếu demo sau mốc đó.

---

## 7. Runbook — thứ tự chạy lại từ đầu

```bash
pip install -r requirements.txt          # + markitdown[pdf]

python -m src.task2_crawl_news           # crawl 7 bài → data/landing/news/
python -m src.task3_convert_markdown     # → data/standardized/
python -m src.ocr_legal_pdf              # OCR 3 PDF luật (chạy lại tới khi "thiếu 0")
python -m src.task4_chunking_indexing    # index 621 chunks vào Weaviate
# (tuỳ chọn) python -m src.task8_pageindex_vectorless   # cần PAGEINDEX_API_KEY

python -m pytest tests/test_individual.py -v   # 35/35

# Demo thủ công:
python -m src.task9_retrieval_pipeline
python -m src.task10_generation
```

---

## 8. Kết quả & demo

- ✅ **35 passed / 0 skipped**
- Ví dụ câu hỏi luật chạy thật:
  > *"Luật Phòng chống ma tuý 2021 quy định thế nào về cai nghiện bắt buộc?"*
  → trả lời trích dẫn đúng **[Luật Phòng, chống ma túy 2021, Điều 36]** và **Điều 29**,
  nguồn từ `luat120-2025` + `Nghị định 105` (đã OCR), score 0.55–0.71.

---

## 9. Trạng thái tích hợp ngoài

- [x] **Weaviate Cloud** — đã cấu hình, index 621 chunks, Task 5 pass.
- [x] **Jina reranker** (Task 7) — `JINA_API_KEY` đã có, cross-encoder chạy thật
  (vd: "Điều 251 mua bán ma tuý" 0.78 > "Miu Lê" 0.22 > "phở bò" 0.02).
- [x] **PageIndex** (Task 8) — 3 PDF luật đã upload (`pi-...`), tree cache trong
  `data/index/pageindex_trees/`. Fallback Task 9 đã chạy thật (trả Điều 37/38/40).

## 10. Hướng phát triển

- [ ] **Bài nhóm**: chatbot Streamlit/Chainlit (Task 9 + 10) + evaluation (DeepEval/RAGAS).
- [ ] (Track 3 GĐ2) nâng lên **knowledge graph** cho câu hỏi khó — như README gợi ý.

---

*Cập nhật: 2026-06-08*
