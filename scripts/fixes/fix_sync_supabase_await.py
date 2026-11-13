#!/usr/bin/env python3
"""Fix the `await <sync Supabase client>...` bug class (AST-based, safe).

The Supabase python client (database.supabase_client.db) is a *sync* Client.
`await`ing its query chains raises TypeError at runtime -> guaranteed HTTP 500
on every endpoint that uses the pattern. The repo already documents and uses
the correct pattern (asyncio.to_thread) in memory_service.py / preferences.py
(Issue #1473), but several route files were never back-ported.

Two bug shapes are handled:

  Pattern A (auto-fixed):
      resp = (await db.client.table("t").select(...).eq(...).execute())
  ->   resp = (await asyncio.to_thread(lambda: db.client.table("t").select(...).eq(...).execute()))

  Pattern B (reported, NOT auto-fixed — needs manual restructure):
      query = await db.client.table("t").select(...)   # no .execute() here
      res  =  query.order(...).execute()               # consumed later

Implementation parses the module with `ast`, finds every `ast.Await` whose
value is an attribute chain rooted at `db` / `supabase_db` with `.client` or
`.service_client`, and rewrites only Pattern A spans (verified by a final
ast.parse + py_compile-able output). Run from the repo root:

    python3 scripts/fixes/fix_sync_supabase_await.py --apply
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO

TARGETS = [
    "core/api/routes/branch_conversations.py",
    "core/api/routes/chat_search.py",
    "core/api/routes/chat_export.py",
    "core/api/routes/prompt_templates.py",
    "core/api/routes/conversations.py",
    "core/api/routes/global_memory.py",
    "core/api/routes/tools_registry.py",
    "core/api/routes/onboarding.py",
    "core/api/routes/scheduled_tasks.py",
    "core/api/routes/deep_research.py",
]
ROOT_NAMES = {"db", "supabase_db"}
CHAIN_RE = re.compile(r"^\s*(supabase_db|db)\.(client|service_client)\b")
PATTERN_A_TAIL = re.compile(r"\.execute\(\s*\)\s*$")


def line_offsets(text: str) -> list[int]:
    offs = [0]
    for line in text.splitlines(keepends=True):
        offs.append(offs[-1] + len(line))
    return offs


def find_awaits(text: str):
    """Yield (start_off, end_off, value_text, is_pattern_a) for each offending
    await. Span = `await` keyword through the end of the value expression.
    NOTE 1 (CPython ast quirks): for a parenthesized value the node's start
    excludes the `(` but its end INCLUDES the matching `)` — so we slice the
    real value text from the span itself instead of get_source_segment().
    NOTE 2: ast col_offset is in UTF-8 BYTES, not characters — files with
    Bengali comments shift byte columns, so convert before slicing."""
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    offs = line_offsets(text)

    def abs_pos(lineno: int, byte_col: int) -> int:
        raw = lines[lineno - 1].encode("utf-8")
        char_col = len(raw[:byte_col].decode("utf-8", errors="ignore"))
        return offs[lineno - 1] + char_col

    for node in ast.walk(tree):
        if not isinstance(node, ast.Await):
            continue
        seg = ast.get_source_segment(text, node.value)
        if not seg or not CHAIN_RE.match(seg.lstrip("(\n \t")):
            continue
        start = abs_pos(node.lineno, node.col_offset)
        end = abs_pos(node.value.end_lineno, node.value.end_col_offset)
        value_text = text[start + len("await"):end].strip()
        if not CHAIN_RE.match(value_text.lstrip("(\n \t")):
            continue
        tail = value_text.rstrip()
        is_a = bool(PATTERN_A_TAIL.search(tail)) or (
            tail.endswith(")") and bool(PATTERN_A_TAIL.search(tail[:-1].rstrip()))
        )
        yield start, end, value_text, is_a


def ensure_asyncio_import(text: str) -> str:
    if re.search(r"^\s*(import asyncio|from asyncio import )", text, re.M):
        return text
    lines = text.splitlines(keepends=True)
    n = len(lines)
    doc_end = 0
    i = 0
    while i < n and (lines[i].strip() == "" or lines[i].lstrip().startswith("#")):
        i += 1
    if i < n and lines[i].lstrip().startswith(('"""', "'''")):
        q = lines[i].lstrip()[:3]
        if lines[i].count(q) >= 2 and len(lines[i].lstrip()) > 3:
            doc_end = i + 1
        else:
            i += 1
            while i < n and q not in lines[i]:
                i += 1
            doc_end = i + 1
    future_last = -1
    for idx, line in enumerate(lines):
        if re.match(r"^from\s+__future__\s+import", line):
            future_last = idx
    insert_at = max(doc_end, future_last + 1)
    if insert_at == 0:
        for idx, line in enumerate(lines):
            if re.match(r"^(import|from)\s+\w", line):
                insert_at = idx
                break
    lines.insert(insert_at, "import asyncio\n")
    return "".join(lines)


def process(rel: str, apply: bool) -> tuple[int, list[str]]:
    path = BACKEND_ROOT / rel
    text = path.read_text()
    spans = list(find_awaits(text))
    fixed, manual = 0, []
    # apply bottom-up by SOURCE position (ast.walk order is not sorted!)
    for start, end, seg, is_a in sorted(spans, key=lambda x: x[0], reverse=True):
        if not is_a:
            manual.append(seg.replace("\n", " ")[:120])
            continue
        replacement = f"await asyncio.to_thread(lambda: {seg})"
        text = text[:start] + replacement + text[end:]
        fixed += 1
    if fixed:
        text = ensure_asyncio_import(text)
        ast.parse(text)  # syntax gate (raises on failure)
        if apply:
            path.write_text(text)
    return fixed, manual


def main() -> int:
    apply = "--apply" in sys.argv
    for rel in TARGETS:
        try:
            fixed, manual = process(rel, apply)
            print(f"OK   {fixed:3d} rewrite(s)  {rel}")
            for seg in manual:
                print(f"     MANUAL (pattern B, not auto-fixed): {seg}")
        except SyntaxError as exc:
            print(f"SKIP parse error {exc.lineno}:{exc.offset} {exc.msg}  {rel}")
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {exc}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
