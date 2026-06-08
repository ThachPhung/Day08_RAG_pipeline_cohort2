"""
Task 5 — Semantic Search Module (dense retrieval).

Embed query bằng cùng model ở Task 4 (OpenAI), rồi near_vector trên Weaviate.
Distance Weaviate là cosine distance ∈ [0, 2]; quy đổi similarity = 1 - distance.

    semantic_search(query, top_k) -> list[{content, score, metadata}]  (sorted desc)
"""

from src.rag_common import embed_query, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa bằng vector similarity (Weaviate near_vector).

    Returns:
        List of {'content': str, 'score': float, 'metadata': dict}, sorted desc.
        Trả [] nếu chưa index / chưa kết nối được Weaviate.
    """
    from weaviate.classes.query import MetadataQuery

    col = get_collection()
    if col is None:
        return []

    qvec = embed_query(query)
    res = col.query.near_vector(
        near_vector=qvec,
        limit=top_k,
        return_metadata=MetadataQuery(distance=True),
    )

    results: list[dict] = []
    for obj in res.objects:
        props = obj.properties
        distance = obj.metadata.distance
        score = 1.0 - distance if distance is not None else 0.0
        results.append(
            {
                "content": props.get("content", ""),
                "score": float(score),
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
    for r in semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5):
        print(f"[{r['score']:.3f}] ({r['metadata']['doc_type']}) {r['content'][:90]}...")
