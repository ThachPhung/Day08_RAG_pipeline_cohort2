"""Task 8 - PageIndex vectorless fallback.

If no PageIndex API key is configured, this module provides a vectorless local
fallback over markdown document structure. Results are marked source='pageindex'
to make fallback behavior explicit to the pipeline.
"""

try:
    from .local_rag_utils import lexical_rank
    from .task4_chunking_indexing import chunk_documents, load_documents
except ImportError:
    from local_rag_utils import lexical_rank
    from task4_chunking_indexing import chunk_documents, load_documents


def upload_documents() -> bool:
    """Placeholder upload hook for real PageIndex integration."""
    return True


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Vectorless fallback search over local markdown chunks."""
    chunks = chunk_documents(load_documents())
    results = lexical_rank(query, chunks, top_k=top_k)
    if not results:
        results = chunks[:top_k]
    return [
        {
            "content": item["content"],
            "score": float(item.get("score", 0.0)),
            "metadata": item.get("metadata", {}),
            "source": "pageindex",
        }
        for item in results[:top_k]
    ]


if __name__ == "__main__":
    print(pageindex_search("ma tuy", top_k=3))
