"""
Task 4 — Chunking & Indexing vào Vector Store.
"""

import json
from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
VECTOR_STORE_FILE = Path(__file__).parent.parent / "data" / "vector_store.json"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
VECTOR_STORE = "local_json"

_TFIDF_VOCABULARY = None


def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.
    """
    documents = []
    if not STANDARDIZED_DIR.exists():
        print(f"[WARN] Standardized directory {STANDARDIZED_DIR} does not exist.")
        return documents

    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        if md_file.is_file():
            content = md_file.read_text(encoding="utf-8")
            doc_type = "legal" if "legal" in str(md_file.parent) or "legal" in str(md_file.name) else "news"
            documents.append({
                "content": content,
                "metadata": {"source": md_file.name, "type": doc_type}
            })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i}
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn hoặc TfidfVectorizer nếu sentence-transformers không có sẵn.
    """
    global _TFIDF_VOCABULARY
    try:
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        model = SentenceTransformer(EMBEDDING_MODEL)
        texts = [c["content"] for c in chunks]
        embeddings = model.encode(texts, show_progress_bar=True)
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb.tolist()
    except Exception as e:
        print(f"[WARN] sentence-transformers not available ({e}). Using sklearn TfidfVectorizer fallback...")
        from sklearn.feature_extraction.text import TfidfVectorizer
        texts = [c["content"] for c in chunks]
        vectorizer = TfidfVectorizer(max_features=EMBEDDING_DIM)
        tfidf_matrix = vectorizer.fit_transform(texts)
        embeddings = tfidf_matrix.toarray().tolist()
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb
        _TFIDF_VOCABULARY = {k: int(v) for k, v in vectorizer.vocabulary_.items()}
    return chunks



def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store dạng file JSON cục bộ kèm theo vocab của TF-IDF nếu có.
    """
    VECTOR_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    serialized_chunks = []
    for chunk in chunks:
        serialized_chunks.append({
            "content": chunk["content"],
            "embedding": chunk["embedding"],
            "metadata": chunk["metadata"]
        })
    data = {
        "chunks": serialized_chunks,
        "tfidf_vocabulary": _TFIDF_VOCABULARY
    }
    VECTOR_STORE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Saved {len(chunks)} chunks to vector store: {VECTOR_STORE_FILE}")


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"[OK] Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"[OK] Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"[OK] Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("[OK] Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
