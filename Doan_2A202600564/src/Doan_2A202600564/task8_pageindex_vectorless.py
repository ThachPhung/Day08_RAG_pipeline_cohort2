"""
Task 8 — PageIndex Vectorless RAG (API + local fallback).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


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


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
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


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env (hoặc dùng local fallback)")
    else:
        print("Uploading documents...")
        upload_documents()

    print("\nTest query:")
    results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
