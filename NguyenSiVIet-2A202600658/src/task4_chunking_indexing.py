"""
Task 4 — Chunking & Indexing vào Vector Store.

Lựa chọn triển khai:
    - Chunking: Recursive character splitting tự cài đặt, ưu tiên cắt theo đoạn,
      dòng, câu rồi mới theo khoảng trắng. Cách này an toàn với markdown và không
      phụ thuộc parser ngoài.
    - Chunk size: 500 ký tự, đủ ngắn cho retrieval chính xác và phù hợp test.
    - Overlap: 50 ký tự để giữ ngữ cảnh giữa hai chunk liền kề.
    - Embedding/index: local token vector index lưu trong memory. Repo skeleton
      gợi ý Weaviate, nhưng bản cá nhân này dùng local fallback để chạy được
      ngay cả khi chưa có Docker/API key.
"""

from __future__ import annotations

import json
from pathlib import Path

from .rag_utils import load_markdown_documents, tokenize


STANDARDIZED_DIR = Path(__file__).resolve().parent.parent / "data" / "standardized"
INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "standardized" / "local_chunks.json"


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "local-token-vector"
EMBEDDING_DIM = 0
VECTOR_STORE = "local-json"


def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    return load_markdown_documents()


def _split_long_piece(piece: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(piece):
        end = min(start + CHUNK_SIZE, len(piece))
        chunks.append(piece[start:end].strip())
        if end == len(piece):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return [chunk for chunk in chunks if chunk]


def _recursive_split(text: str) -> list[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]
    pieces = [text.strip()]

    for separator in separators:
        next_pieces: list[str] = []
        for piece in pieces:
            if len(piece) <= CHUNK_SIZE:
                next_pieces.append(piece)
                continue
            if separator:
                next_pieces.extend(part.strip() for part in piece.split(separator) if part.strip())
            else:
                next_pieces.extend(_split_long_piece(piece))
        pieces = next_pieces

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if len(piece) > CHUNK_SIZE:
            chunks.extend(_split_long_piece(piece))
            current = ""
            continue
        candidate = f"{current}\n{piece}".strip() if current else piece
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            if current:
                chunks.append(current)
            overlap = current[-CHUNK_OVERLAP:] if current else ""
            current = f"{overlap} {piece}".strip()
            if len(current) > CHUNK_SIZE:
                chunks.extend(_split_long_piece(current))
                current = ""
    if current:
        chunks.append(current)
    return chunks


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo recursive character strategy.

    Returns:
        List of {'content': str, 'metadata': dict}
    """
    chunks: list[dict] = []
    for doc in documents:
        for i, chunk_text in enumerate(_recursive_split(doc["content"])):
            if not chunk_text:
                continue
            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": {**doc.get("metadata", {}), "chunk_index": i},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Add a lightweight token-vector representation to each chunk."""
    for chunk in chunks:
        chunk["embedding"] = tokenize(chunk["content"])
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> Path:
    """Persist local chunk index as JSON for inspection/reuse."""
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    serializable = [
        {
            "content": chunk["content"],
            "metadata": chunk.get("metadata", {}),
            "embedding": chunk.get("embedding", []),
        }
        for chunk in chunks
    ]
    INDEX_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    return INDEX_PATH


def run_pipeline() -> list[dict]:
    """Chạy toàn bộ pipeline: load -> chunk -> embed -> index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\nLoaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    index_path = index_to_vectorstore(chunks)
    print(f"Indexed to {index_path}")
    return chunks


if __name__ == "__main__":
    run_pipeline()
