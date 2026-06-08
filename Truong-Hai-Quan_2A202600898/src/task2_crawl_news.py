"""
Task 2 — Crawl bài báo về nghệ sĩ Việt liên quan tới ma tuý.

Hướng dẫn gốc khuyến nghị Crawl4AI, nhưng cho phép "thư viện crawling tương tự".
Ở đây dùng requests + BeautifulSoup vì:
    - Nhẹ, không cần tải Playwright/headless browser (Crawl4AI khá nặng trên Windows).
    - Các trang báo VN (VnExpress, VietnamNet...) trả HTML tĩnh đọc được trực tiếp.

Mỗi bài lưu 1 file JSON trong data/landing/news/ gồm metadata:
    url, title, date_crawled, content_markdown.

Chạy:
    python -m src.task2_crawl_news
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.rag_common import _force_utf8_stdout

_force_utf8_stdout()  # tránh lỗi cp1252 khi in ✓/✗ trên Windows console

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "vi,en;q=0.9",
}

# Danh sách bài báo (nghệ sĩ Việt liên quan ma tuý). Để dư ra để nếu vài URL
# lỗi/đổi thì vẫn đủ tối thiểu 5 bài.
ARTICLE_URLS = [
    "https://vnexpress.net/ca-si-miu-le-bi-bat-voi-cao-buoc-to-chuc-su-dung-ma-tuy-5074769.html",
    "https://vnexpress.net/su-nghiep-long-nhat-truoc-khi-bi-bat-vi-lien-quan-ma-tuy-5076081.html",
    "https://ngoisao.vnexpress.net/nhung-nghe-si-viet-danh-mat-su-nghiep-vi-ma-tuy-4816068.html",
    "https://vnexpress.net/ca-si-miu-le-bi-bat-qua-tang-dung-ma-tuy-o-bai-bien-5072657.html",
    "https://vnexpress.net/miu-le-xin-loi-khan-gia-5074078.html",
    "https://vnexpress.net/su-nghiep-cua-miu-le-truoc-khi-bi-bat-qua-tang-dung-ma-tuy-5072762.html",
    "https://vietnamnet.vn/sao-viet-bi-bat-ngoi-tu-mat-danh-tieng-vi-chat-cam-2513746.html",
    "https://vietnamnet.vn/3-nu-nghe-si-viet-tu-huy-danh-tieng-vi-lien-quan-den-ma-tuy-2514737.html",
]

MIN_ARTICLES = 5


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(url: str) -> str:
    """Lấy phần slug cuối URL làm tên file."""
    tail = url.rstrip("/").split("/")[-1]
    tail = re.sub(r"\.html?$", "", tail)
    tail = re.sub(r"[^0-9a-zA-Z\-]+", "-", tail).strip("-")
    return tail[:80] or "article"


def _extract_article(html: str) -> tuple[str, str]:
    """
    Trích tiêu đề + nội dung chính từ HTML báo VN.
    Trả về (title, content_markdown).
    """
    soup = BeautifulSoup(html, "lxml")

    # Title: thử h1, rồi <title>
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Bỏ các thẻ không phải nội dung
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    # Lede (sapo) của VnExpress thường là <p class="description">
    parts: list[str] = []
    lede = soup.find(class_="description")
    if lede:
        txt = lede.get_text(" ", strip=True)
        if len(txt) > 40:
            parts.append(f"**{txt}**")

    # Đoạn nội dung: các <p>. Lọc đoạn quá ngắn/menu.
    seen = set()
    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if len(txt) < 40 or txt in seen:
            continue
        seen.add(txt)
        parts.append(txt)

    content = "\n\n".join(parts)
    return title or "Unknown", content


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài báo → dict {url, title, date_crawled, content_markdown}.

    Dùng requests (chạy trong thread để không block event loop). Nếu cài
    Crawl4AI, có thể thay block này bằng AsyncWebCrawler — interface trả về
    giống nhau.
    """

    def _fetch() -> dict:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        title, content = _extract_article(resp.text)
        return {
            "url": url,
            "title": title,
            "date_crawled": datetime.now().isoformat(timespec="seconds"),
            "content_markdown": content,
        }

    return await asyncio.to_thread(_fetch)


async def crawl_all():
    """Crawl toàn bộ ARTICLE_URLS, lưu mỗi bài 1 file JSON. Bỏ qua bài lỗi."""
    setup_directory()

    saved = 0
    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        try:
            article = await crawl_article(url)
        except Exception as e:  # noqa: BLE001 — crawl trang ngoài có thể lỗi đủ kiểu
            print(f"  ✗ Lỗi: {e}")
            continue

        if len(article["content_markdown"]) < 500:
            print(f"  ✗ Nội dung quá ngắn ({len(article['content_markdown'])} chars), bỏ qua")
            continue

        filename = f"{i:02d}_{_slugify(url)}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(
            json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        saved += 1
        print(f"  ✓ Saved: {filepath.name} ({len(article['content_markdown'])} chars)")

    print(f"\n✓ Đã lưu {saved}/{len(ARTICLE_URLS)} bài báo vào {DATA_DIR}")
    if saved < MIN_ARTICLES:
        print(f"⚠ Cảnh báo: chỉ có {saved} bài (<{MIN_ARTICLES}). Thêm URL vào ARTICLE_URLS.")
    return saved


if __name__ == "__main__":
    asyncio.run(crawl_all())
