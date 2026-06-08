#!/usr/bin/env bash
# Demo script — Lead integration test
# Chạy từ repo root: bash group_project/demo.sh

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 1. Kiểm tra dữ liệu ==="
python3 - <<'PY'
from pathlib import Path
legal = list(Path("data/landing/legal").glob("*.pdf"))
news = list(Path("data/landing/news").glob("*.html"))
std = list(Path("data/standardized").rglob("*.md"))
print(f"  Legal PDFs : {len(legal)}")
print(f"  News HTML  : {len(news)}")
print(f"  Markdown   : {len(std)}")
assert len(legal) >= 3, "Cần ≥3 PDF pháp luật"
assert len(news) >= 5, "Cần ≥5 bài báo"
assert len(std) >= 1, "Chạy: python3 -m src.task3_convert_markdown"
PY

echo ""
echo "=== 2. Test pipeline nhóm (1 câu hỏi) ==="
python3 - <<'PY'
from group_project.pipeline import rag_query
r = rag_query("Luật phòng chống ma tuý quy định cai nghiện?", top_k=3)
print("  Answer:", r["answer"][:120], "...")
print("  Sources:", len(r["sources"]), "| retrieval:", r["retrieval_source"])
PY

echo ""
echo "=== 3. Test memory (follow-up) ==="
python3 - <<'PY'
from group_project.src.conversation_memory import ConversationMemory, ChatHistoryStore
from unittest import mock

def fake_retrieve(q, top_k=5):
    return [{"content": f"Mock về: {q}", "score": 0.9, "metadata": {"source": "demo.md", "type": "legal"}, "source": "hybrid"}]

def fake_gen(q, chunks, history):
    return f"Trả lời mock cho: {q}"

with mock.patch("group_project.src.conversation_memory.retrieve_chunks", side_effect=fake_retrieve), \
     mock.patch("group_project.src.conversation_memory.generate_with_history", side_effect=fake_gen):
    mem = ConversationMemory(store=ChatHistoryStore(db_path=":memory:"))
    sid = mem.new_session()
    mem.chat(sid, "Hình phạt tàng trữ ma tuý?")
    r = mem.chat(sid, "Còn mức cao nhất thì sao?")
    print("  Follow-up rewritten:", r["rewritten_query"][:80])
    print("  History messages:", len(mem.get_history(sid)))
PY

echo ""
echo "=== 4. Chạy evaluation (sample 10 câu) ==="
python3 -m group_project.evaluation.eval_pipeline 2>&1 | tail -8

echo ""
echo "=== 5. Test bài cá nhân ==="
python3 -m pytest tests/test_individual.py -q --tb=no 2>&1 | tail -3

echo ""
echo "✓ Demo hoàn tất. Chạy UI:"
echo "  streamlit run group_project/app.py"
echo "  streamlit run group_project/src/app.py   # bản có SQLite memory"
