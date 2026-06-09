"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.
"""

import json
import re
from pathlib import Path

from markitdown import MarkItDown

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    slug = re.sub(r"[-\s]+", "-", slug).strip("-").lower()
    return slug[:120] or "document"


def convert_legal_docs() -> int:
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not legal_dir.exists():
        return 0

    md = MarkItDown()
    count = 0

    for filepath in sorted(legal_dir.iterdir()):
        if filepath.suffix.lower() not in (".pdf", ".docx", ".doc"):
            continue
        print(f"Converting: {filepath.name}")
        result = md.convert(str(filepath))
        output_path = output_dir / f"{_slugify(filepath.stem)}.md"
        output_path.write_text(result.text_content, encoding="utf-8")
        print(f"  ✓ Saved: {output_path}")
        count += 1

    return count


def convert_news_articles() -> int:
    """Convert news files (JSON/HTML) trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not news_dir.exists():
        return 0

    md = MarkItDown()
    count = 0

    for filepath in sorted(news_dir.iterdir()):
        if not filepath.is_file():
            continue

        suffix = filepath.suffix.lower()
        if suffix == ".json":
            print(f"Converting: {filepath.name}")
            data = json.loads(filepath.read_text(encoding="utf-8"))
            header = f"# {data.get('title', 'Unknown')}\n\n"
            header += f"**Source:** {data.get('url', 'N/A')}\n"
            header += f"**Crawled:** {data.get('date_crawled', 'N/A')}\n\n---\n\n"
            content = header + data.get("content_markdown", data.get("content", ""))
            output_path = output_dir / f"{filepath.stem}.md"
            output_path.write_text(content, encoding="utf-8")
            print(f"  ✓ Saved: {output_path}")
            count += 1
        elif suffix in (".html", ".htm"):
            print(f"Converting: {filepath.name}")
            result = md.convert(str(filepath))
            title = filepath.stem
            header = f"# {title}\n\n**Source:** {filepath.name}\n\n---\n\n"
            output_path = output_dir / f"{_slugify(filepath.stem)}.md"
            output_path.write_text(header + result.text_content, encoding="utf-8")
            print(f"  ✓ Saved: {output_path}")
            count += 1

    return count


def convert_all() -> None:
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    legal_count = convert_legal_docs()

    print("\n--- News Articles ---")
    news_count = convert_news_articles()

    print(f"\n✓ Done! Converted {legal_count} legal + {news_count} news files")
    print("Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
