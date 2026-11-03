#!/usr/bin/env python3
"""memory_consolidation_guard.py — Guardian gate for Memory (dedup/contradiction).

Pure functions operate on memory entry lists so the gate is offline-testable.
Entry shape: {"key": str, "text": str, "source": str (optional)}.

Flags:
  - exact duplicate entries (same key+text)
  - near-duplicate text (normalized equality) across keys
  - contradictory entries (same key, differing text)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def find_exact_duplicates(entries: list[dict[str, Any]]) -> list[str]:
    seen: set[tuple[str, str]] = set()
    out: list[str] = []
    for e in entries or []:
        key = str(e.get("key", ""))
        text = str(e.get("text", ""))
        sig = (key, _norm(text))
        if sig in seen:
            out.append(f"exact duplicate: key={key!r}")
        else:
            seen.add(sig)
    return out


def find_contradictions(entries: list[dict[str, Any]]) -> list[str]:
    by_key: dict[str, set[str]] = {}
    for e in entries or []:
        key = str(e.get("key", ""))
        by_key.setdefault(key, set()).add(_norm(str(e.get("text", ""))))
    out: list[str] = []
    for key, texts in by_key.items():
        if len(texts) > 1:
            out.append(f"contradiction: key={key!r} has {len(texts)} distinct texts")
    return out


def find_near_duplicates(entries: list[dict[str, Any]]) -> list[str]:
    # normalized text equality across different keys
    by_text: dict[str, list[str]] = {}
    for e in entries or []:
        t = _norm(str(e.get("text", "")))
        if not t:
            continue
        by_text.setdefault(t, []).append(str(e.get("key", "")))
    out: list[str] = []
    for t, keys in by_text.items():
        distinct = set(keys)
        if len(distinct) > 1:
            out.append(f"near-duplicate text across keys: {sorted(distinct)}")
    return out


def audit_memory(entries: list[dict[str, Any]]) -> dict[str, Any]:
    errs = []
    errs.extend(find_exact_duplicates(entries))
    errs.extend(find_contradictions(entries))
    errs.extend(find_near_duplicates(entries))
    return {"entries": len(entries or []), "issues": errs, "ok": not errs}


def load_input(path: str) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("entries", "memories", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def self_test() -> int:
    fails = 0
    clean = [
        {"key": "a", "text": "Hello world"},
        {"key": "b", "text": "Different text"},
    ]
    if not audit_memory(clean)["ok"]:
        fails += 1
        print("FAIL clean", audit_memory(clean))
    else:
        print("PASS clean")
    dup = [
        {"key": "a", "text": "Hello world"},
        {"key": "a", "text": "Hello world"},
    ]
    if not any("exact duplicate" in e for e in audit_memory(dup)["issues"]):
        fails += 1
        print("FAIL dup", audit_memory(dup))
    else:
        print("PASS dup")
    contra = [
        {"key": "a", "text": "v1"},
        {"key": "a", "text": "v2"},
    ]
    if not any("contradiction" in e for e in audit_memory(contra)["issues"]):
        fails += 1
        print("FAIL contra", audit_memory(contra))
    else:
        print("PASS contra")
    near = [
        {"key": "a", "text": "same text"},
        {"key": "b", "text": "same text"},
    ]
    if not any("near-duplicate" in e for e in audit_memory(near)["issues"]):
        fails += 1
        print("FAIL near", audit_memory(near))
    else:
        print("PASS near")
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.input:
        print("memory_consolidation_guard: provide --input or --self-test", file=sys.stderr)
        return 2
    entries = load_input(args.input)
    res = audit_memory(entries)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
