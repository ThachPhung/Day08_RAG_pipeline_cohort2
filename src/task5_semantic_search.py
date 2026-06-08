"""Task 5 - Semantic search module."""

try:
    from .local_rag_utils import semantic_rank
    from .task4_chunking_indexing import chunk_documents, load_documents
except ImportError:
    from local_rag_utils import semantic_rank
    from task4_chunking_indexing import chunk_documents, load_documents


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Return top_k chunks sorted by local vector cosine similarity."""
    docs = load_documents()
    chunks = chunk_documents(docs)
    results = semantic_rank(query, chunks, top_k=top_k)
    return [
        {"content": item["content"], "score": item["score"], "metadata": item.get("metadata", {})}
        for item in results
    ]


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for result in semantic_search("hinh phat ma tuy", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
