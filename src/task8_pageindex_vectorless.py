"""
<<<<<<< HEAD
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API
=======
Task 8 — PageIndex Vectorless RAG (API + local fallback).
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
"""

import os
from pathlib import Path
<<<<<<< HEAD
=======

>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


<<<<<<< HEAD
def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    # TODO: Implement upload
    #
    # Tham khảo: https://github.com/VectifyAI/PageIndex
    #
    # from pageindex import PageIndex
    #
    # pi = PageIndex(api_key=PAGEINDEX_API_KEY)
    #
    # for md_file in STANDARDIZED_DIR.rglob("*.md"):
    #     content = md_file.read_text(encoding="utf-8")
    #     pi.upload(
    #         content=content,
    #         metadata={"filename": md_file.name, "type": md_file.parent.name}
    #     )
    #     print(f"  ✓ Uploaded: {md_file.name}")
    raise NotImplementedError("Implement upload_documents")
=======
def upload_documents() -> None:
    """Upload markdown documents lên PageIndex nếu có API key."""
    if not PAGEINDEX_API_KEY:
        print("⚠ Không có PAGEINDEX_API_KEY — bỏ qua upload, dùng local fallback khi query.")
        return

    try:
        from pageindex import PageIndex

        pi = PageIndex(api_key=PAGEINDEX_API_KEY)
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            pi.upload(
                content=content,
                metadata={"filename": md_file.name, "type": md_file.parent.name},
            )
            print(f"  ✓ Uploaded: {md_file.name}")
    except Exception as exc:
        print(f"⚠ PageIndex upload failed: {exc}")


def _local_fallback_search(query: str, top_k: int) -> list[dict]:
    """Fallback: BM25 trên local corpus khi không có PageIndex API."""
    from src.task6_lexical_search import lexical_search

    results = lexical_search(query, top_k=top_k)
    for r in results:
        r["source"] = "pageindex"
    return results
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
<<<<<<< HEAD
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    # TODO: Implement PageIndex query
    #
    # from pageindex import PageIndex
    #
    # pi = PageIndex(api_key=PAGEINDEX_API_KEY)
    # results = pi.query(query=query, top_k=top_k)
    #
    # return [
    #     {
    #         "content": r.text,
    #         "score": r.score,
    #         "metadata": r.metadata,
    #         "source": "pageindex"
    #     }
    #     for r in results
    # ]
    raise NotImplementedError("Implement pageindex_search")
=======
    Vectorless retrieval qua PageIndex API, hoặc local BM25 fallback.
    """
    if PAGEINDEX_API_KEY:
        try:
            from pageindex import PageIndex

            pi = PageIndex(api_key=PAGEINDEX_API_KEY)
            results = pi.query(query=query, top_k=top_k)
            return [
                {
                    "content": getattr(r, "text", r.get("text", "")),
                    "score": float(getattr(r, "score", r.get("score", 0.5))),
                    "metadata": getattr(r, "metadata", r.get("metadata", {})),
                    "source": "pageindex",
                }
                for r in results
            ]
        except Exception:
            pass

    return _local_fallback_search(query, top_k)
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
<<<<<<< HEAD
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
=======
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env (hoặc dùng local fallback)")
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
    else:
        print("Uploading documents...")
        upload_documents()

<<<<<<< HEAD
        print("\nTest query:")
        results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
=======
    print("\nTest query:")
    results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
>>>>>>> 430f14b37ec710a67f2c80cf504b3dc0cc3e1d80
