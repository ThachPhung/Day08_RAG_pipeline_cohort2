"""Task 6 - Lexical search using a small BM25 implementation."""

try:
    from .local_rag_utils import lexical_rank
    from .task4_chunking_indexing import chunk_documents, load_documents
except ImportError:
    from local_rag_utils import lexical_rank
    from task4_chunking_indexing import chunk_documents, load_documents


def build_bm25_index(corpus: list[dict]) -> list[dict]:
    """For this lightweight implementation, the corpus itself is the index."""
    return corpus


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Return top_k chunks sorted by BM25-style keyword score."""
    docs = load_documents()
    chunks = chunk_documents(docs)
    results = lexical_rank(query, chunks, top_k=top_k)
    return [
        {"content": item["content"], "score": item["score"], "metadata": item.get("metadata", {})}
        for item in results
    ]


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for result in lexical_search("ma tuy", top_k=5):
        print(f"[{result['score']:.3f}] {result['content'][:100]}...")
