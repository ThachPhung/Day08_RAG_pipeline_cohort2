"""Task 4 - Chunking and indexing for the group pipeline."""

from __future__ import annotations

from group_project.src._index_store import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    STANDARDIZED_DIR,
    embed_texts,
    save_chunks,
)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
CHUNKING_METHOD = "recursive_character"
VECTOR_STORE = "group_project/index local pickle"


def load_documents() -> list[dict]:
    """Read all standardized markdown files as group retrieval documents."""
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            continue
        rel = md_file.relative_to(STANDARDIZED_DIR)
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "path": str(rel).replace("\\", "/"),
                    "type": rel.parts[0] if len(rel.parts) > 1 else "unknown",
                },
            }
        )
    return documents


def _fallback_split(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        window = text[start:end]
        split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
        if split_at > CHUNK_SIZE * 0.45 and end < len(text):
            end = start + split_at + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Use RecursiveCharacterTextSplitter; fallback to an equivalent local splitter."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        split_text = splitter.split_text
    except Exception:
        split_text = _fallback_split

    chunks: list[dict] = []
    for doc in documents:
        for index, content in enumerate(split_text(doc["content"])):
            if not content.strip():
                continue
            chunks.append(
                {
                    "content": content,
                    "metadata": {**doc["metadata"], "chunk_index": index},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Attach dense vectors to chunks using MiniLM or deterministic fallback."""
    embeddings = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    save_chunks(chunks)


def run_pipeline() -> list[dict]:
    docs = load_documents()
    chunks = chunk_documents(docs)
    indexed = embed_chunks(chunks)
    index_to_vectorstore(indexed)
    print(f"Indexed {len(indexed)} chunks with {CHUNKING_METHOD}.")
    print(f"Embedding model: {EMBEDDING_MODEL}; dimension: {EMBEDDING_DIM}.")
    return indexed


if __name__ == "__main__":
    run_pipeline()

