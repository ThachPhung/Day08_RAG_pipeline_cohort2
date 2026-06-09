"""Task 10 - Generation with citation."""

try:
    from .task9_retrieval_pipeline import retrieve
except ImportError:
    from task9_retrieval_pipeline import retrieve

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

SYSTEM_PROMPT = """Answer using only the provided context. Include citations in
square brackets with the source name. If evidence is insufficient, say that the
information cannot be verified from the available sources."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Keep the best chunk first and move strong chunks toward the end too."""
    if len(chunks) <= 2:
        return chunks
    front = chunks[::2]
    back = list(reversed(chunks[1::2]))
    return front + back


def format_context(chunks: list[dict]) -> str:
    """Format context chunks with source labels for citation."""
    parts = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", f"Source {index}")
        doc_type = metadata.get("type", "unknown")
        parts.append(
            f"[Document {index} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk.get('content', '')}"
        )
    return "\n\n---\n\n".join(parts)


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Generate a simple citation-style answer for the individual task."""
    chunks = retrieve(query, top_k=top_k)
    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)

    if not reordered:
        answer = "I cannot verify this information from the available sources."
        retrieval_source = "none"
    else:
        first = reordered[0]
        source = first.get("metadata", {}).get("source", "retrieved source")
        excerpt = " ".join(first.get("content", "").split())[:350]
        answer = (
            f"Based on the retrieved context, the most relevant evidence says: "
            f"{excerpt} [{source}]. "
            "If more precise legal interpretation is required, the original source "
            "document should be checked directly."
        )
        retrieval_source = first.get("source", "hybrid")

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source,
        "context": context,
    }


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(generate_with_citation("Hinh phat tang tru ma tuy?")["answer"])
