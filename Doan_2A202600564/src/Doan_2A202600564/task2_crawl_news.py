

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://dantri.com.vn/giai-tri/truoc-ca-si-chu-bin-loat-nghe-si-noi-tieng-vuong-lao-ly-vi-ma-tuy-20250310104512345.htm",
    "https://vnexpress.net/ca-si-miu-le-bi-bat-voi-cao-buoc-to-chuc-su-dung-ma-tuy-4841234.html",
    "https://tuoitre.vn/ca-si-chi-dan-bi-dieu-tra-nghi-lien-quan-den-ma-tuy-20250310120000000.htm",
    "https://thanhnien.vn/bat-hai-ca-si-long-nhat-va-son-ngoc-minh-vi-lien-quan-ma-tuy-1234567890.html",
    "https://plo.vn/ca-si-long-nhat-son-ngoc-minh-bi-bat-trong-chuyen-an-ma-tuy-post123456.html",
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _slug_from_url(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(html?|htm)$", "", slug, flags=re.I)
    slug = re.sub(r"[^\w-]+", "-", slug).strip("-")
    return slug[:80] or "article"


async def crawl_article(url: str) -> dict:
    """Crawl một bài báo và trả về metadata + content."""
    from crawl4ai import AsyncWebCrawler

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        title = "Unknown"
        if result.metadata:
            title = result.metadata.get("title") or title
        return {
            "url": url,
            "title": title,
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": result.markdown or "",
        }


async def crawl_all() -> None:
    setup_directory()

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        try:
            article = await crawl_article(url)
        except Exception as exc:
            print(f"  ⚠ Lỗi crawl {url}: {exc}")
            continue

        filename = f"{_slug_from_url(url)}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Saved: {filepath}")


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
    else:
        asyncio.run(crawl_all())
