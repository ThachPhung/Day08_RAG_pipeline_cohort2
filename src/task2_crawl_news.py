"""
Task 2 - Crawl news articles about artists related to drug cases.

The script saves one JSON file per article into data/landing/news/.
It tries Crawl4AI first, then falls back to a lightweight urllib HTML fetcher.
"""

import asyncio
import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://vnexpress.net/dien-vien-hai-bi-tam-giu-vi-lien-quan-ma-tuy-4475240.html",
    "https://vnexpress.net/nguoi-mau-nhikolai-dinh-bi-bat-vi-tang-tru-ma-tuy-4762598.html",
    "https://vietnamnet.vn/tp-hcm-khoi-to-71-doi-tuong-trong-duong-day-ma-tuy-lon-co-ca-si-long-nhat-2517560.html",
    "https://thanhnien.vn/ca-si-son-ngoc-minh-vua-bi-bat-vi-lien-quan-den-ma-tuy-la-ai-18526052012481811.htm",
    "https://thanhnien.vn/nghe-si-tu-nguyen-xet-nghiem-ma-tuy-showbiz-dang-bat-an-den-muc-nao-185260526105918638.htm",
]


def setup_directory() -> None:
    """Create data/landing/news/ if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _clean_html(raw_html: str) -> str:
    """Convert raw HTML to plain markdown-like text without extra dependencies."""
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw_html)
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_html)
    title = html.unescape(title_match.group(1)).strip() if title_match else "Unknown"

    text = re.sub(r"(?i)</(p|div|h1|h2|h3|li)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return title, text.strip()


def _fetch_with_urllib(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        raw_html = response.read().decode("utf-8", errors="ignore")

    title, content = _clean_html(raw_html)
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content,
    }


async def crawl_article(url: str) -> dict:
    """
    Crawl one article and return metadata + content.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str,
            "content_markdown": str
        }
    """
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            title = result.metadata.get("title", "Unknown") if result.metadata else "Unknown"
            return {
                "url": url,
                "title": title,
                "date_crawled": datetime.now().isoformat(),
                "content_markdown": result.markdown or "",
            }
    except Exception:
        return _fetch_with_urllib(url)


async def crawl_all() -> list[Path]:
    """Crawl all URLs in ARTICLE_URLS and save each article as JSON."""
    setup_directory()
    saved_files = []

    for index, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{index}/{len(ARTICLE_URLS)}] Crawling: {url}")
        article = await crawl_article(url)

        filename = f"article_{index:02d}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        saved_files.append(filepath)
        print(f"Saved: {filepath}")

    return saved_files


if __name__ == "__main__":
    asyncio.run(crawl_all())
