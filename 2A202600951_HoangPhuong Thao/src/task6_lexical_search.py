"""
Task 6 — Lexical Search Module (BM25).

Mặc định sử dụng BM25. Nếu dùng phương pháp khác (TF-IDF, Elasticsearch,
Weaviate BM25 built-in), hãy giải thích cơ chế trong buổi demo → +5 bonus.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)
"""

from pathlib import Path

import json
from pathlib import Path
from rank_bm25 import BM25Okapi

VECTOR_STORE_FILE = Path(__file__).parent.parent / "data" / "vector_store.json"

_BM25 = None
_CORPUS = None


def get_bm25_index():
    """Lấy hoặc xây dựng BM25 index từ file vector store hoặc standardized docs."""
    global _BM25, _CORPUS
    if _BM25 is None:
        if not VECTOR_STORE_FILE.exists():
            # Nếu chưa chạy indexing, tự động load và chunk tạm thời để test không bị lỗi
            try:
                from .task4_chunking_indexing import load_documents, chunk_documents
                docs = load_documents()
                _CORPUS = chunk_documents(docs)
            except Exception as e:
                print(f"⚠ Không thể load corpus tạm thời: {e}")
                _CORPUS = []
        else:
            with open(VECTOR_STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "chunks" in data:
                _CORPUS = data["chunks"]
            else:
                _CORPUS = data

        if not _CORPUS:
            return None, []

        # Tokenize tiếng Việt đơn giản bằng split()
        tokenized_corpus = [doc["content"].lower().split() for doc in _CORPUS]
        _BM25 = BM25Okapi(tokenized_corpus)
    return _BM25, _CORPUS


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus đầu vào (đáp ứng interface nếu cần gọi thủ công).
    """
    global _BM25, _CORPUS
    _CORPUS = corpus
    tokenized_corpus = [doc["content"].lower().split() for doc in _CORPUS]
    _BM25 = BM25Okapi(tokenized_corpus)
    return _BM25


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    bm25, corpus = get_bm25_index()
    if not bm25 or not corpus:
        return []

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    results = []
    for idx, score in enumerate(scores):
        results.append({
            "content": corpus[idx]["content"],
            "score": float(score),
            "metadata": corpus[idx]["metadata"]
        })

    # Sắp xếp giảm dần theo score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    # Test
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

