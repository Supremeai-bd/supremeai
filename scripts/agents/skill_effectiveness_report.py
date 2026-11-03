#!/usr/bin/env python3
"""Aggregate skill_usage.jsonl into a per-skill effectiveness report."""
import json, sys
from collections import defaultdict
from pathlib import Path

def main() -> int:
    log = Path(__file__).resolve().parents[2] / "skills" / "skill_usage.jsonl"
    if not log.is_file():
        print("no usage log yet")
        return 0
    counts = defaultdict(int)
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        counts[rec.get("skill", "?")] += 1
    for skill, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"{skill}: {n}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
