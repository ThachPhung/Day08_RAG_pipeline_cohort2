"""
<<<<<<< HEAD
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (Weaviate khuyến cáo)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho tiếng Việt)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - Weaviate (khuyến cáo: hỗ trợ hybrid search built-in)
    - ChromaDB (đơn giản, local)
    - FAISS (chỉ dense search)

Cài đặt:
    pip install langchain-text-splitters sentence-transformers weaviate-client
=======
Task 4 — Chunking & Indexing vào Vector Store (local pickle index).
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
"""

from pathlib import Path

<<<<<<< HEAD
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# TODO: Chọn chunking strategy và giải thích vì sao
CHUNK_SIZE = 500        # Vì sao chọn 500? ...
CHUNK_OVERLAP = 50      # Vì sao chọn 50? ...
CHUNKING_METHOD = "recursive"  # "recursive" | "markdown_header" | "semantic"

# TODO: Chọn embedding model và giải thích
EMBEDDING_MODEL = "BAAI/bge-m3"  # Vì sao? Multilingual, tốt cho tiếng Việt
EMBEDDING_DIM = 1024

# TODO: Chọn vector store
VECTOR_STORE = "weaviate"  # "weaviate" | "chromadb" | "faiss"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    # TODO: Iterate qua STANDARDIZED_DIR, đọc .md files
    # documents = []
    # for md_file in STANDARDIZED_DIR.rglob("*.md"):
    #     content = md_file.read_text(encoding="utf-8")
    #     doc_type = "legal" if "legal" in str(md_file) else "news"
    #     documents.append({
    #         "content": content,
    #         "metadata": {"source": md_file.name, "type": doc_type}
    #     })
    # return documents
    raise NotImplementedError("Implement load_documents")


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    # TODO: Implement chunking
    #
    # Ví dụ với RecursiveCharacterTextSplitter:
    # from langchain_text_splitters import RecursiveCharacterTextSplitter
    #
    # splitter = RecursiveCharacterTextSplitter(
    #     chunk_size=CHUNK_SIZE,
    #     chunk_overlap=CHUNK_OVERLAP,
    #     separators=["\n\n", "\n", ". ", " ", ""]
    # )
    # chunks = []
    # for doc in documents:
    #     splits = splitter.split_text(doc["content"])
    #     for i, chunk_text in enumerate(splits):
    #         chunks.append({
    #             "content": chunk_text,
    #             "metadata": {**doc["metadata"], "chunk_index": i}
    #         })
    # return chunks
    raise NotImplementedError("Implement chunk_documents")


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    # TODO: Implement embedding
    #
    # Ví dụ với sentence-transformers:
    # from sentence_transformers import SentenceTransformer
    #
    # model = SentenceTransformer(EMBEDDING_MODEL)
    # texts = [c["content"] for c in chunks]
    # embeddings = model.encode(texts, show_progress_bar=True)
    # for chunk, emb in zip(chunks, embeddings):
    #     chunk["embedding"] = emb.tolist()
    # return chunks
    raise NotImplementedError("Implement embed_chunks")


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    # TODO: Implement indexing
    #
    # Ví dụ với Weaviate:
    # import weaviate
    # from weaviate.classes.config import Configure, Property, DataType
    #
    # client = weaviate.connect_to_local()  # hoặc connect_to_weaviate_cloud()
    #
    # # Tạo collection
    # collection = client.collections.create(
    #     name="DrugLawDocs",
    #     vectorizer_config=Configure.Vectorizer.none(),
    #     properties=[
    #         Property(name="content", data_type=DataType.TEXT),
    #         Property(name="source", data_type=DataType.TEXT),
    #         Property(name="doc_type", data_type=DataType.TEXT),
    #     ]
    # )
    #
    # # Insert chunks
    # with collection.batch.dynamic() as batch:
    #     for chunk in chunks:
    #         batch.add_object(
    #             properties={"content": chunk["content"], ...},
    #             vector=chunk["embedding"]
    #         )
    raise NotImplementedError("Implement index_to_vectorstore")


def run_pipeline():
=======
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src._index_store import embed_texts, save_chunks

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# RecursiveCharacterTextSplitter: phù hợp markdown/PDF đã convert, tách theo đoạn/nghỉ dòng.
# CHUNK_SIZE=800: đủ ngữ cảnh cho điều luật; OVERLAP=100: giữ liên kết giữa các điều khoản.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "recursive"

# Multilingual MiniLM: nhẹ, hỗ trợ tiếng Việt tốt hơn all-MiniLM monolingual.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384

VECTOR_STORE = "local_pickle"


def load_documents() -> list[dict]:
    """Đọc toàn bộ markdown files từ data/standardized/."""
    documents: list[dict] = []
    if not STANDARDIZED_DIR.exists():
        return documents

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        rel = md_file.relative_to(STANDARDIZED_DIR)
        doc_type = rel.parts[0] if len(rel.parts) > 1 else "unknown"
        documents.append(
            {
                "content": content,
                "metadata": {
                    "source": md_file.name,
                    "type": doc_type,
                    "path": str(rel),
                },
            }
        )
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chunk documents theo RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict] = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            if not chunk_text.strip():
                continue
            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": {**doc["metadata"], "chunk_index": i},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed toàn bộ chunks bằng sentence-transformers."""
    texts = [c["content"] for c in chunks]
    embeddings = embed_texts(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Lưu chunks + embeddings vào data/index/chunks.pkl."""
    save_chunks(chunks)


def run_pipeline() -> None:
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
