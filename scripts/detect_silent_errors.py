#!/usr/bin/env python3
"""SupremeAI Silent Error Detector (সাইলেন্ট এরর ডিটেক্টর) — static + runtime audit.

A zero-dependency (Python stdlib only) scanner that finds every category of
"silent error" in the SupremeAI codebase and reports each finding with a
severity. It is built for both local use and CI automation — see
`.github/workflows/silent-error-scan.yml`.

Why this exists
---------------
Silent errors are the most expensive bugs to find: the code path keeps running,
but failures are swallowed (`except Exception: pass`), or the error is dumped
into a default value that looks legitimate, or an `asyncio.create_task()` is
fired and forgotten so a whole background feature dies with zero trace.
This scanner makes them visible and gives CI a regression gate so the count
can only go down.

Detected Python patterns (AST-based):
  except-pass             bare/broad `except` whose body is only `pass`
  except-continue         bare/broad `except: continue` — silent loop skip
  except-break            `except: break` — silent loop exit
  except-return-default   `except` returning None/False/""/0/[]/{}/True with no log
  except-no-log           broad exception handled but never logged / re-raised
  bare-except             bare `except:` (also swallows KeyboardInterrupt/SystemExit)
  suppress-exception      contextlib.suppress(Exception)
  create-task-unref       asyncio.create_task(...) with the task reference discarded
  syntax-error            file that cannot be parsed (definitely broken)

Detected JS/TS patterns (regex + brace matching):
  empty-catch             catch { } with an empty body
  catch-return-silent     catch returning null/undefined/false/[]/{}/'' or continue/break
  promise-catch-silent    .catch(() => {}) — rejection discarded
  json-parse-unguarded    JSON.parse outside any try/catch
  floating-fetch          fetch(...) fired and forgotten (no await/return)
  onerror-empty           onerror = () => {}

Runtime log scan (--logs):
  python tracebacks, "Exception ignored in", "Silenced error",
  unhandled promise rejections, "Task was destroyed but it is pending!",
  coroutine never awaited, ERROR/CRITICAL bursts.

Usage
-----
    python scripts/detect_silent_errors.py                       # scan repo, human output
    python scripts/detect_silent_errors.py --json report.json --markdown report.md
    python scripts/detect_silent_errors.py --fail-on high        # CI gate (default)
    python scripts/detect_silent_errors.py --baseline scripts/silent_errors_baseline.json
    python scripts/detect_silent_errors.py --update-baseline     # refresh snapshot
    python scripts/detect_silent_errors.py --logs auto           # also scan *.{log} files
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent  # project root (parent of scripts/)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - not all consoles support reconfigure
    pass

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1, "info": 0}

DEFAULT_EXCLUDE_DIRS = {
    "node_modules", ".venv", ".venv_ci", ".venv_probe", "venv", "site-packages",
    "dist", "dist-admin", "dist-user", "dist-electron", "__pycache__", ".git",
    "htmlcov", "coverage", "coverage-tmp", ".turbo", ".next", "out",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "playwright-report",
    "test-results", "_archive", "archive", ".secrets", ".firebase",
    ".playwright-mcp", ".agents", ".continue", ".kilo", ".lingma", ".vscode",
    ".devcontainer", ".github", "snapshots", "__snapshots__", "storybook-static",
    "build", "e2e-artifacts", "generated", ".terraform", "node_modules_cache",
    ".cache",
}

DEFAULT_SCAN_DIRS = [
    "backend", "frontend/src", "apps", "packages", "shared", "tools",
    "config", "configs", "scripts", "migrations",
]

MAX_FILE_BYTES = 600_000

LOG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("python-traceback", re.compile(r"Traceback \(most recent call last\)")),
    ("exception-ignored", re.compile(r"Exception ignored[^\n]*")),
    ("silenced-error-log", re.compile(r"Silenced error[^\n]*", re.IGNORECASE)),
    ("unhandled-rejection", re.compile(r"Unhandled(?:PromiseRejection| Rejection| Error)[^\n]*", re.IGNORECASE)),
    ("task-destroyed-pending", re.compile(r"Task was destroyed but it is pending")),
    ("coroutine-never-awaited", re.compile(r"was never awaited|never fetched from this coroutine")),
    ("error-burst", re.compile(r"\b(ERROR|CRITICAL|FATAL)\b[^\n\u2588]*")),
]


def rel(path: str | Path) -> str:
    """Return a repo-relative, forward-slash path (stable across OS/CI)."""
    return os.path.relpath(str(path), str(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def iter_files(root_dir: str, exts: tuple[str, ...], exclude: set[str]):
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, root_dir)):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1].lower() in exts and os.path.getsize(path) <= MAX_FILE_BYTES:
                yield path


def is_test_file(path: str) -> bool:
    """Heuristic: path lives under tests dirs or is a *_test / test_* / *.spec file."""
    p = rel(path)
    parts = p.split("/")
    if any(seg in ("tests", "__tests__", "test", "testing") for seg in parts):
        return True
    name = parts[-1].lower()
    return name.startswith("test_") or name.endswith("_test") or name.endswith("_test.py") or ".spec." in name or ".test." in name