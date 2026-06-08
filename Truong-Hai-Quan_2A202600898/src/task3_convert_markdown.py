"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Dùng MarkItDown của Microsoft (https://github.com/microsoft/markitdown) cho
PDF/DOCX/TXT. Bài báo đã crawl ở Task 2 lưu dạng JSON → ghép metadata header
rồi xuất .md.

Output: data/standardized/{legal,news}/*.md

Chạy:
    python -m src.task3_convert_markdown
"""

import json
from pathlib import Path

from markitdown import MarkItDown

from src.rag_common import _force_utf8_stdout

_force_utf8_stdout()  # tránh lỗi cp1252 khi in ✓/✗ trên Windows console

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Loại file MarkItDown xử lý tốt cho văn bản pháp luật
DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".html", ".htm"}


def convert_legal_docs() -> int:
    """Convert file trong data/landing/legal/ sang markdown. Trả về số file."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()
    count = 0
    for filepath in sorted(legal_dir.iterdir()):
        if not filepath.is_file() or filepath.suffix.lower() not in DOC_EXTS:
            continue
        print(f"Converting: {filepath.name}")
        try:
            result = md.convert(str(filepath))
            text = result.text_content or ""
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ Lỗi convert: {e}")
            continue

        if len(text.strip()) < 50:
            print(f"  ✗ Nội dung rỗng/quá ngắn, bỏ qua")
            continue

        header = f"# {filepath.stem}\n\n**Nguồn:** {filepath.name} (legal)\n\n---\n\n"
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text(header + text, encoding="utf-8")
        count += 1
        print(f"  ✓ Saved: {output_path.name} ({len(text)} chars)")
    return count


def convert_news_articles() -> int:
    """Convert JSON bài báo trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for filepath in sorted(news_dir.iterdir()):
        if filepath.suffix.lower() != ".json":
            continue
        print(f"Converting: {filepath.name}")
        data = json.loads(filepath.read_text(encoding="utf-8"))

        title = data.get("title", "Unknown")
        header = (
            f"# {title}\n\n"
            f"**Nguồn:** {data.get('url', 'N/A')}\n"
            f"**Ngày crawl:** {data.get('date_crawled', 'N/A')}\n\n---\n\n"
        )
        content = header + data.get("content_markdown", "")
        output_path = output_dir / f"{filepath.stem}.md"
        output_path.write_text(content, encoding="utf-8")
        count += 1
        print(f"  ✓ Saved: {output_path.name} ({len(content)} chars)")
    return count


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    n_legal = convert_legal_docs()

    print("\n--- News Articles ---")
    n_news = convert_news_articles()

    print(f"\n✓ Done! {n_legal} legal + {n_news} news → {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
