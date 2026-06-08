"""Task 8 - PageIndex vectorless retrieval with a local fallback."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")


def upload_documents() -> None:
    """Upload documents to PageIndex when credentials and SDK are available."""
    if not PAGEINDEX_API_KEY:
        print("PAGEINDEX_API_KEY is missing; using local fallback only.")
        return

    from group_project.src._index_store import STANDARDIZED_DIR

    try:
        from pageindex import PageIndex

        client = PageIndex(api_key=PAGEINDEX_API_KEY)
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            client.upload(
                content=md_file.read_text(encoding="utf-8", errors="ignore"),
                metadata={"source": md_file.name, "type": md_file.parent.name},
            )
            print(f"Uploaded {md_file.name}")
    except Exception as exc:
        print(f"PageIndex upload failed, local fallback remains available: {exc}")


def _local_fallback_search(query: str, top_k: int) -> list[dict]:
    from group_project.src.task6_lexical_search import lexical_search

    results = lexical_search(query, top_k=top_k)
    for item in results:
        item["source"] = "pageindex"
        item["retriever"] = "pageindex_local_bm25"
    return results


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query PageIndex; if unavailable, use local BM25 as vectorless fallback."""
    if PAGEINDEX_API_KEY:
        try:
            from pageindex import PageIndex

            client = PageIndex(api_key=PAGEINDEX_API_KEY)
            raw_results = client.query(query=query, top_k=top_k)
            results: list[dict] = []
            for item in raw_results:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    score = item.get("score", 0.5)
                    metadata = item.get("metadata", {})
                else:
                    text = getattr(item, "text", getattr(item, "content", ""))
                    score = getattr(item, "score", 0.5)
                    metadata = getattr(item, "metadata", {})
                results.append(
                    {
                        "content": text,
                        "score": float(score),
                        "metadata": metadata,
                        "source": "pageindex",
                        "retriever": "pageindex_api",
                    }
                )
            return results[:top_k]
        except Exception:
            pass

    return _local_fallback_search(query, top_k)


if __name__ == "__main__":
    for result in pageindex_search("ma túy", top_k=3):
        print(f"{result['score']:.3f} {result['metadata'].get('source')}")

