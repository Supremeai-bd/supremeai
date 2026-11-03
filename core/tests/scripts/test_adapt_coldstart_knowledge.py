"""M23 P-C tests — coldstart→importer adapter বই-কনভয় গেট।

বাংলা: এই টেস্টগুলোই CI-এর 'validate-only' প্রতি-রান প্রমাণ — প্রতিবার
আমদানি-চুক্তি ও বই-উৎস এক থাকে কি না যাচাই হয় (drift হলে CI লাল)।
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
ADAPTER_PATH = BACKEND_DIR / "scripts" / "adapt_coldstart_knowledge.py"
IMPORTER_PATH = BACKEND_DIR / "scripts" / "import_knowledge_base.py"
SOURCE_PATH = REPO_ROOT / "knowledge" / "coldstart_knowledge_seed_comprehensive.json"


def _load(name: str, path: Path):
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = _load("adapt_coldstart_knowledge", ADAPTER_PATH)
importer = _load("import_knowledge_base", IMPORTER_PATH)


def _source_bengali_answer_count() -> int:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    return sum(
        1
        for c in payload.get("categories", [])
        for e in c.get("entries", [])
        if any("\u0980" <= ch <= "\u09ff" for ch in str(e.get("answer", "")))
    )


def test_adapter_output_passes_importer_validation_clean():
    """বাংলা: প্রথম বই-কনভয় — ১৩২-এন্ট্রি validate-প্রমাণিত, ০ error।"""
    manifest = adapter.adapt()
    report = adapter.validate_report(manifest, adapter.DEFAULT_SOURCE)
    assert report["record_count"] == 132
    assert report["errors"] == []


def test_every_coldstart_entry_round_trips():
    """বাংলা: N-rows round-trip — প্রতিটি উৎস-এন্ট্রির জন্য ইউনিক importer-রেকর্ড।"""
    manifest = adapter.adapt()
    records = manifest["records"]
    keys = [r["knowledge_key"] for r in records]
    assert len(keys) == len(set(keys))
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    source_entries = [e for c in payload["categories"] for e in c["entries"]]
    assert len(source_entries) == len(records)
    # কনটেন্ট round-trip: উৎস answer রেকর্ড content-এ অক্ষুণ্ণ (truncate নেই)।
    by_key = {r["knowledge_key"]: r for r in records}
    for c in payload["categories"]:
        for e in c["entries"]:
            rec = by_key[adapter._key_for(e["id"], c["category_id"])]
            assert rec["content"] == str(e["answer"]).strip()
            assert rec["title"] == str(e["question"]).strip()[:200]


def test_bengali_content_preserved():
    """বাংলা: বাংলা উত্তর-কনটেন্ট অনুবাদ/বিকৃতি ছাড়াই রেকর্ডে পৌঁছায়।"""
    manifest = adapter.adapt()
    bengali_records = sum(
        1 for r in manifest["records"] if any("\u0980" <= ch <= "\u09ff" for ch in r["content"])
    )
    assert bengali_records == _source_bengali_answer_count()
    assert bengali_records > 100  # বই-কনভয়ের মূল মূল্যই বাংলা-কর্পাস


def test_all_records_draft_hitl_gate():
    """বাংলা: HITL — adapter কখনো auto-approve করে না; সব রেকর্ড draft।"""
    manifest = adapter.adapt()
    assert all(r["status"] == "draft" for r in manifest["records"])


def test_unknown_confidence_level_fails_closed():
    """বাংলা: অজানা confidence-স্তরে চুপচাপ ডিফল্ট নয় — সৎ ব্যতিক্রম।"""
    import pytest

    src = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    src["categories"][0]["entries"][0]["confidence"] = "ultra"
    tmp = REPO_ROOT / "build" / "tmp_confidence_seed.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="unknown confidence level"):
            adapter.adapt(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def test_secret_scanner_precision_word_boundary():
    """বাংলা: 'task-specific' ভুয়া-ধনাত্মক নয়; প্রকৃত 'sk-…' কি এখনো ধরা পড়ে।"""
    base = {
        "knowledge_key": "unit.test.key",
        "title": "t",
        "domain": "d",
        "namespace": "n",
        "content": "Fine-tune: task-specific behavior, risky-but-fine",
        "source_document": "s",
        "source_section": "s",
        "confidence": 0.9,
        "risk_level": "low",
        "status": "draft",
        "tags": [],
    }
    assert importer.validate([base]) == []
    leak = dict(base, content="use key sk-live-abc123def456 now")
    assert importer.validate([leak]) == ["record[0] possible secret"]


def test_incomplete_entry_raises_not_silently_dropped():
    """বাংলা: অসম্পূর্ণ এন্ট্রি নীরবে বাদ দেওয়া = ভুয়া 'সব ঠিক' — ব্যতিক্রমই সত্য।"""
    import pytest

    src = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    src["categories"][0]["entries"][0]["answer"] = ""
    tmp = REPO_ROOT / "build" / "tmp_incomplete_seed.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="incomplete coldstart entry"):
            adapter.adapt(tmp)
    finally:
        tmp.unlink(missing_ok=True)
