"""
Task 4 — Chunking & Indexing vào Vector Store (Weaviate Cloud).

LỰA CHỌN & LÝ DO
----------------
Chunking: RecursiveCharacterTextSplitter (langchain-text-splitters)
    - CHUNK_SIZE = 800 ký tự: văn bản pháp luật có cấu trúc "Điều/Khoản"; 800
      ký tự đủ gói trọn 1–2 khoản mà không cắt vụn ngữ nghĩa, vẫn nằm dưới giới
      hạn token của reranker/LLM.
    - CHUNK_OVERLAP = 120 (15%): giữ ngữ cảnh nối giữa 2 chunk liền kề, tránh
      mất câu bị cắt ngang ranh giới.
    - Recursive: tách ưu tiên theo đoạn → câu → từ, an toàn cho cả văn bản
      luật (có heading) lẫn bài báo (văn xuôi).

Embedding: OpenAI text-embedding-3-small (1536 dim)
    - Multilingual tốt cho tiếng Việt, rẻ, chất lượng cao, không cần tải model
      nặng về máy. Vector chuẩn hoá L2 → cosine = dot product.

Vector store: Weaviate Cloud (self-provided vectors)
    - Hỗ trợ hybrid search built-in (near_vector + BM25 + hybrid fusion).

Chạy:
    python -m src.task4_chunking_indexing
"""

from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag_common import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    STANDARDIZED_DIR,
    create_collection,
    embed_texts,
    index_count,
)

# =============================================================================
# CONFIGURATION
# =============================================================================
CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
CHUNKING_METHOD = "recursive"

VECTOR_STORE = "weaviate"  # xem rag_common để biết cách kết nối


# =============================================================================
# IMPLEMENTATION
# =============================================================================
def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        if not content.strip():
            continue
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append(
            {
                "content": content,
                "metadata": {"source": md_file.name, "type": doc_type},
            }
        )
    return documents


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
    )


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo RecursiveCharacterTextSplitter.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk.
    """
    splitter = _splitter()
    chunks: list[dict] = []
    for doc in documents:
        for i, piece in enumerate(splitter.split_text(doc["content"])):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(
                {
                    "content": piece,
                    "metadata": {**doc["metadata"], "chunk_index": i},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed toàn bộ chunks bằng OpenAI; thêm key 'embedding' vào mỗi chunk."""
    embeddings = embed_texts([c["content"] for c in chunks])
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Nạp chunks (đã có embedding) vào Weaviate collection."""
    col = create_collection(reset=True)

    with col.batch.dynamic() as batch:
        for ch in chunks:
            meta = ch["metadata"]
            batch.add_object(
                properties={
                    "content": ch["content"],
                    "source": meta.get("source", ""),
                    "doc_type": meta.get("type", ""),
                    "chunk_index": int(meta.get("chunk_index", 0)),
                },
                vector=ch["embedding"],
            )

    failed = col.batch.failed_objects
    if failed:
        print(f"⚠ {len(failed)} object lỗi khi insert. Ví dụ: {failed[0].message}")


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")
    if not docs:
        print("⚠ Chưa có markdown nào. Chạy Task 2 + Task 3 trước.")
        return

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print(f"✓ Indexed to Weaviate — collection hiện có {index_count()} objects")


if __name__ == "__main__":
    run_pipeline()
