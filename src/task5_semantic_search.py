"""
Task 5 — Semantic Search Module.

Viết module tìm kiếm ngữ nghĩa (dense retrieval) trên vector store.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Phải tương thích với embedding model và vector store ở Task 4
"""


import json
from pathlib import Path
import numpy as np

VECTOR_STORE_FILE = Path(__file__).parent.parent / "data" / "vector_store.json"

_MODEL = None


def get_embedding_model():
    """Cache the embedding model globally to avoid loading it on every query."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        # Trực tiếp dùng model name cấu hình
        _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _MODEL


def cosine_similarity(v1, v2):
    """Tính cosine similarity giữa hai vectors sử dụng numpy."""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return float(dot_product / (norm_v1 * norm_v2))


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity trên file vector store JSON cục bộ.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    if not VECTOR_STORE_FILE.exists():
        print(f"⚠ Vector store {VECTOR_STORE_FILE} không tồn tại. Hãy chạy Task 4 trước.")
        return []

    # Load vector store
    with open(VECTOR_STORE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "chunks" in data:
        chunks = data["chunks"]
        vocabulary = data.get("tfidf_vocabulary")
    else:
        chunks = data
        vocabulary = None

    if not chunks:
        return []

    # Embed query
    try:
        model = get_embedding_model()
        query_vector = model.encode(query).tolist()
    except Exception as e:
        print(f"[WARN] get_embedding_model or encode failed ({e}). Using sklearn TfidfVectorizer fallback...")
        from sklearn.feature_extraction.text import TfidfVectorizer
        if vocabulary is not None:
            vectorizer = TfidfVectorizer(vocabulary=vocabulary)
            corpus_texts = [c["content"] for c in chunks]
            vectorizer.fit(corpus_texts)
            query_vector = vectorizer.transform([query]).toarray()[0].tolist()
        else:
            vectorizer = TfidfVectorizer()
            query_vector = vectorizer.fit_transform([query]).toarray()[0].tolist()


    # Calculate similarity
    results = []
    for chunk in chunks:
        score = cosine_similarity(query_vector, chunk["embedding"])
        results.append({
            "content": chunk["content"],
            "score": score,
            "metadata": chunk["metadata"]
        })


    # Sắp xếp giảm dần theo score
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:top_k]


if __name__ == "__main__":
    # Test
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")

