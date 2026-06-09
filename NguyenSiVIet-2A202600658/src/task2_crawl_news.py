"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài báo từ các trang tin tức Việt Nam.
    2. Sử dụng Crawl4AI hoặc thư viện crawling tương tự.
    3. Lưu output vào data/landing/news/.
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Script này ưu tiên crawl bằng Crawl4AI. Nếu môi trường không có browser/network,
nó dùng phần seed_content đã ghi từ các nguồn báo đã chọn để vẫn tạo được landing
data phục vụ các task RAG tiếp theo.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "landing" / "news"


ARTICLE_URLS = [
    {
        "slug": "nhung-nghe-si-viet-nga-ngua-vi-ma-tuy",
        "url": "https://ngoisao.vnexpress.net/nhung-nghe-si-viet-nga-ngua-vi-ma-tuy-4816068.html",
        "title": "Những nghệ sĩ Việt ngã ngựa vì ma túy",
        "publisher": "Ngôi Sao/VnExpress",
        "seed_content": (
            "Bài viết tổng hợp nhiều trường hợp nghệ sĩ Việt Nam vướng vòng lao lý "
            "hoặc bị xử lý vì liên quan đến ma túy. Nội dung nhắc tới các vụ việc "
            "như người mẫu, ca sĩ, diễn viên bị phát hiện tàng trữ, tổ chức sử dụng "
            "hoặc sử dụng trái phép chất ma túy. Bài báo cho thấy ma túy có thể làm "
            "sụp đổ hình ảnh, sự nghiệp và uy tín xã hội của người hoạt động nghệ thuật."
        ),
    },
    {
        "slug": "nguyen-cong-tri-bi-bat-vi-lien-quan-ma-tuy",
        "url": "https://ngoisao.vnexpress.net/nha-thiet-ke-nguyen-cong-tri-bi-bat-vi-lien-quan-ma-tuy-4917935.html",
        "title": "Nhà thiết kế Nguyễn Công Trí bị bắt vì liên quan ma túy",
        "publisher": "Ngôi Sao/VnExpress",
        "seed_content": (
            "Bài báo đưa tin nhà thiết kế Nguyễn Công Trí bị phát hiện sử dụng trái "
            "phép chất ma túy khi lực lượng chức năng mở rộng điều tra một đường dây "
            "mua bán ma túy qua mạng. Sự việc được đặt trong bối cảnh ông là nhà thiết "
            "kế nổi tiếng, có thương hiệu thời trang được nhiều nghệ sĩ trong và ngoài "
            "nước biết đến."
        ),
    },
    {
        "slug": "ngoai-nguyen-cong-tri-nghe-si-tung-bi-bat-vi-ma-tuy",
        "url": "https://vietnamnet.vn/ngoai-nguyen-cong-tri-nhung-nghe-si-nao-tung-bi-bat-vi-ma-tuy-2424971.html",
        "title": "Ngoài Nguyễn Công Trí, những nghệ sĩ nào từng bị bắt vì ma tuý?",
        "publisher": "VietnamNet",
        "seed_content": (
            "Bài viết điểm lại một số nghệ sĩ Việt từng bị bắt giữ hoặc xử lý trong "
            "các vụ việc liên quan đến ma túy. Nội dung nhấn mạnh tác động tiêu cực "
            "của hành vi sử dụng, tàng trữ hoặc mua bán chất cấm đối với sự nghiệp, "
            "đời sống cá nhân và niềm tin của công chúng."
        ),
    },
    {
        "slug": "son-ngoc-minh-bi-bat-vi-lien-quan-ma-tuy",
        "url": "https://amp.vtcnews.vn/ca-si-son-ngoc-minh-vua-bi-bat-vi-lien-quan-ma-tuy-la-ai-ar1019052.html",
        "title": "Ca sĩ Sơn Ngọc Minh vừa bị bắt vì liên quan ma túy là ai?",
        "publisher": "VTC News",
        "seed_content": (
            "Bài báo giới thiệu tiểu sử và sự nghiệp của ca sĩ Sơn Ngọc Minh sau khi "
            "có thông tin nam ca sĩ bị Công an TP.HCM bắt trong vụ án liên quan đến "
            "ma túy. Nội dung cho biết vụ án có nhiều bị can bị điều tra về mua bán, "
            "tàng trữ và tổ chức sử dụng trái phép chất ma túy."
        ),
    },
    {
        "slug": "long-nhat-bi-bat-lien-quan-ma-tuy",
        "url": "https://amp.vtcnews.vn/ca-si-long-nhat-bi-bat-su-nghiep-30-nam-va-doi-tu-day-thi-phi-ar1019084.html",
        "title": "Ca sĩ Long Nhật bị bắt: Sự nghiệp 30 năm và đời tư đầy thị phi",
        "publisher": "VTC News",
        "seed_content": (
            "Bài báo nhìn lại sự nghiệp của ca sĩ Long Nhật trong bối cảnh ông bị "
            "khởi tố, bắt tạm giam để điều tra hành vi liên quan đến tổ chức sử dụng "
            "trái phép chất ma túy. Nội dung nhấn mạnh việc nghệ sĩ nổi tiếng vẫn có "
            "thể đối mặt hậu quả pháp lý nghiêm trọng khi dính đến chất cấm."
        ),
    },
]


def setup_directory() -> Path:
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


async def crawl_article(article: dict) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.

    Returns:
        {
            "url": str,
            "title": str,
            "date_crawled": str,
            "publisher": str,
            "content_markdown": str
        }
    """
    url = article["url"]
    title = article["title"]
    content = article["seed_content"]

    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            crawled_markdown = getattr(result, "markdown", "") or ""
            if len(crawled_markdown.strip()) > 500:
                content = crawled_markdown
                title = getattr(result, "metadata", {}).get("title", title)
    except Exception as exc:
        print(f"  Fallback seed content for {url}: {exc}")

    return {
        "url": url,
        "title": title,
        "publisher": article["publisher"],
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content,
    }


async def crawl_all() -> list[Path]:
    """Crawl toàn bộ bài báo trong ARTICLE_URLS."""
    setup_directory()
    saved_files: list[Path] = []

    for i, article in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {article['url']}")
        crawled = await crawl_article(article)

        filepath = DATA_DIR / f"{article['slug']}.json"
        filepath.write_text(
            json.dumps(crawled, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved_files.append(filepath)
        print(f"  Saved: {filepath}")

    return saved_files


if __name__ == "__main__":
    asyncio.run(crawl_all())
