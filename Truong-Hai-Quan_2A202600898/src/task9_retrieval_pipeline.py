"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Gộp semantic (Task 5) + lexical (Task 6) + rerank (Task 7) + fallback PageIndex
(Task 8) thành 1 hàm retrieve() thống nhất:

    Query
      ├→ Semantic Search ─┐
      │                    ├→ RRF merge → Rerank → kết quả 'hybrid'
      ├→ Lexical Search ──┘
      │
      └→ Nếu rỗng hoặc best_score < threshold → fallback PageIndex ('pageindex')

Lưu ý độ bền: Task 6 có fallback rank-bm25 cục bộ nên pipeline vẫn cho kết quả
'hybrid' kể cả khi Weaviate chưa cấu hình.
"""

from src.rag_common import _force_utf8_stdout
from src.task5_semantic_search import semantic_search
from src.task6_lexical_search import lexical_search
from src.task7_reranking import rerank, rerank_rrf
from src.task8_pageindex_vectorless import pageindex_search

_force_utf8_stdout()

# =============================================================================
# CONFIGURATION
# =============================================================================
SCORE_THRESHOLD = 0.3   # best score (sau rerank) < ngưỡng → fallback PageIndex
DEFAULT_TOP_K = 5
RERANK_METHOD = "cross_encoder"


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Retrieval pipeline hoàn chỉnh với fallback.

    Returns:
        List of {'content', 'score', 'metadata', 'source'} với
        source ∈ {'hybrid', 'pageindex'}. Cắt tối đa top_k.
    """
    pool = max(top_k * 2, top_k)

    # 1) Hai nhánh dense + sparse
    dense = semantic_search(query, top_k=pool)
    sparse = lexical_search(query, top_k=pool)

    # 2) Merge bằng Reciprocal Rank Fusion
    merged = rerank_rrf([dense, sparse], top_k=pool) if (dense or sparse) else []
    for item in merged:
        item["source"] = "hybrid"

    # 3) Rerank (cross-encoder) để chấm lại độ liên quan thực
    if use_reranking and merged:
        final = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        for item in final:
            item.setdefault("source", "hybrid")
    else:
        final = merged[:top_k]

    # 4) Fallback PageIndex nếu hybrid yếu/rỗng
    best = final[0]["score"] if final else 0.0
    if not final or best < score_threshold:
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            print(
                f"  ⚠ Hybrid yếu (best={best:.3f} < {score_threshold}) → fallback PageIndex"
            )
            return fallback[:top_k]

    return final[:top_k]


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý",
        "Nghệ sĩ nào bị bắt vì sử dụng ma tuý",
        "Luật phòng chống ma tuý 2021 quy định gì về cai nghiện",
    ]
    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        for i, r in enumerate(retrieve(q, top_k=3), 1):
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] {r['content'][:80]}...")
