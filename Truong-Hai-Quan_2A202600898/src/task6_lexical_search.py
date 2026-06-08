"""
Task 6 — Lexical Search Module (BM25).

Hai engine, ưu tiên Weaviate, có fallback offline:
    1. Weaviate BM25 built-in (col.query.bm25) — "chuẩn" production, +5 bonus.
    2. rank-bm25 (BM25Okapi) trên corpus đọc từ data/standardized/ — dùng khi
       chưa cấu hình/kết nối được Weaviate, để module vẫn chạy được độc lập.

Cơ chế BM25 (giải thích cho demo):
    BM25 = TF-IDF có bão hoà term-frequency + chuẩn hoá độ dài tài liệu.
    score(D,Q) = Σ_t IDF(t) · ( f(t,D)·(k1+1) ) / ( f(t,D) + k1·(1 - b + b·|D|/avgdl) )
        - f(t,D): tần suất term t trong doc D
        - IDF(t): term hiếm → trọng số cao
        - k1≈1.5: bão hoà TF (lặp nhiều không tăng tuyến tính)
        - b≈0.75: phạt doc dài
"""

from functools import lru_cache

from src.rag_common import get_collection, tokenize_vi


# ---------------------------------------------------------------------------
# Fallback engine: rank-bm25 trên corpus cục bộ
# ---------------------------------------------------------------------------
def _load_corpus() -> list[dict]:
    """Đọc + chunk markdown thành corpus {'content', 'metadata'} (cho rank-bm25)."""
    from src.task4_chunking_indexing import chunk_documents, load_documents

    return chunk_documents(load_documents())


def build_bm25_index(corpus: list[dict]):
    """Xây BM25 index (rank-bm25) từ corpus đã tokenize tiếng Việt."""
    from rank_bm25 import BM25Okapi

    tokenized = [tokenize_vi(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized)


@lru_cache(maxsize=1)
def _local_bm25():
    """(bm25, corpus) — cache để không build lại mỗi lần search."""
    corpus = _load_corpus()
    if not corpus:
        return None, []
    return build_bm25_index(corpus), corpus


def _lexical_search_local(query: str, top_k: int) -> list[dict]:
    bm25, corpus = _local_bm25()
    if bm25 is None:
        return []
    scores = bm25.get_scores(tokenize_vi(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for idx in ranked[:top_k]:
        if scores[idx] <= 0:
            continue
        results.append(
            {
                "content": corpus[idx]["content"],
                "score": float(scores[idx]),
                "metadata": corpus[idx]["metadata"],
            }
        )
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    BM25 lexical search. Ưu tiên Weaviate, fallback rank-bm25.

    Returns:
        List of {'content', 'score', 'metadata'}, sorted by score desc.
    """
    from weaviate.classes.query import MetadataQuery

    col = get_collection()
    if col is None:
        return _lexical_search_local(query, top_k)

    res = col.query.bm25(
        query=query,
        query_properties=["content"],
        limit=top_k,
        return_metadata=MetadataQuery(score=True),
    )

    results: list[dict] = []
    for obj in res.objects:
        props = obj.properties
        score = obj.metadata.score
        results.append(
            {
                "content": props.get("content", ""),
                "score": float(score) if score is not None else 0.0,
                "metadata": {
                    "source": props.get("source", ""),
                    "doc_type": props.get("doc_type", ""),
                    "chunk_index": props.get("chunk_index", 0),
                },
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


if __name__ == "__main__":
    for r in lexical_search("tàng trữ trái phép chất ma tuý", top_k=5):
        print(f"[{r['score']:.3f}] ({r['metadata'].get('doc_type')}) {r['content'][:90]}...")
