"""
Task 4 - Chunking & indexing.

Implementation choice:
- Chunking: recursive character splitting with paragraph/sentence boundaries.
- Embedding: lightweight hashed token embedding for offline classroom tests.
- Vector store: in-memory list, exposed through helper functions.
"""

from pathlib import Path

try:
    from .local_rag_utils import chunk_documents as _chunk_documents
    from .local_rag_utils import load_markdown_documents, simple_embedding
except ImportError:
    from local_rag_utils import chunk_documents as _chunk_documents
    from local_rag_utils import load_markdown_documents, simple_embedding

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "local-hashed-token-embedding"
EMBEDDING_DIM = 128
VECTOR_STORE = "in_memory"

VECTOR_INDEX: list[dict] = []


def load_documents() -> list[dict]:
    """Read all markdown files from data/standardized/."""
    return load_markdown_documents()


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split documents into bounded chunks."""
    return _chunk_documents(documents, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Attach local embeddings to each chunk."""
    embedded = []
    for chunk in chunks:
        embedded.append({**chunk, "embedding": simple_embedding(chunk["content"], dim=EMBEDDING_DIM)})
    return embedded


def index_to_vectorstore(chunks: list[dict]) -> list[dict]:
    """Store chunks in an in-memory vector index."""
    VECTOR_INDEX.clear()
    VECTOR_INDEX.extend(chunks)
    return VECTOR_INDEX


def run_pipeline() -> list[dict]:
    docs = load_documents()
    chunks = chunk_documents(docs)
    embedded = embed_chunks(chunks)
    return index_to_vectorstore(embedded)


if __name__ == "__main__":
    index = run_pipeline()
    print(f"Indexed {len(index)} chunks")
