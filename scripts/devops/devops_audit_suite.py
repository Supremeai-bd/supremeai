

# --- Merged from bug_prophet.py ---

#!/usr/bin/env python3
"""
SupremeAI - BugProphet Agent 🔮
================================
Static analysis + AI-driven bug/anti-pattern prediction for PR review.

Purpose:
- AST-based static scanning for common Python bugs and security smells.
- AI-powered deep analysis to predict logical bugs, race conditions,
  and API misuse before code reaches production.
- Generates a structured Markdown report with severity levels.

Author: SupremeAI Core
Date: July 18, 2026
"""

import ast
import os
import sys
import json
import logging
import argparse
import hashlib
import concurrent.futures
import threading
import re
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

import litellm

# --- Path Setup (consistent with ai_scribe_historian.py) ---
# বাংলা মন্তব্য: ক্লিন ইমপোর্ট স্ট্রাকচার এবং পাথ রেজোলিউশন নিশ্চিত করা হচ্ছে।
try:
    from backend.core.config import settings
except ImportError:
    # বাংলা: এই ফলব্যাক পাথটি আগে ভুল ছিল — Path(__file__).parent মানে
    # scripts/devops/ ডিরেক্টরি, যেখানে backend/ সাবফোল্ডার আদৌ নেই। রিপো-রুট
    # খুঁজতে .parent.parent.parent দরকার (scripts/devops/ → scripts/ → repo root)।
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from core.config import settings

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

litellm.set_verbose = False
litellm.max_retries = 3
litellm.retry_strategy = {
    "wait_time": 16,
    "allowed_exceptions": [Exception]
}

CACHE_FILE = Path(__file__).parent / ".bug_prophet_cache.sqlite"
TARGET_DIRECTORIES = ["backend/core", "backend/tools"]
FILE_PATTERN = "*.py"
EXCLUDE_FILES = {"__init__.py", "bug_prophet.py", "ai_scribe_historian.py"}

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

# --- Data Structures ---

@dataclass
class Issue:
    rule_id: str
    category: str
    severity: str
    message: str
    line: int
    column: int
    detection: str  # "static" or "ai"
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileReport:
    file_path: str
    file_hash: str
    issues: list[Issue] = field(default_factory=list)
    ai_summary: str = ""
    risk_score: float = 0.0  # 0.0 - 10.0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "issues": [i.to_dict() for i in self.issues],
            "ai_summary": self.ai_summary,
            "risk_score": self.risk_score,
        }


# --- LLM Infrastructure (same pattern as ai_scribe_historian) ---

class LLMCallError(Exception):
    """সব রিট্রাই শেষে LLM কল ব্যর্থ হলে এই এরর রেইজ হবে।"""

key_index = 0
api_key_lock = threading.Lock()


def get_ai_response(prompt: str, temperature: float = 0.2, max_retries_per_key: int = 3, retry_backoff_seconds: float = 2.0) -> str:
    """
    প্রম্পট পাঠায় এবং LLM-এর উত্তর রিটার্ন করে। ব্যর্থ হলে LLMCallError রেইজ করে।
    """
    global key_index
    api_keys_str = settings.gemini_api_key
    if not api_keys_str:
        raise LLMCallError("settings.gemini_api_key কনফিগার করা নেই।")

    keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
    if not keys:
        raise LLMCallError("কোনো বৈধ Gemini API key পাওয়া যায়নি।")

    max_retries = max_retries_per_key * len(keys)
    last_error: Exception | None = None

    for attempt in range(max_retries):
        current_key = keys[key_index % len(keys)]
        try:
            response = litellm.completion(
                model=settings.gemini_model_name,
                messages=[{"content": prompt, "role": "user"}],
                temperature=temperature,
                api_key=current_key
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            error_msg = str(e)
            recoverable = any(code in error_msg for code in (
                "429", "RESOURCE_EXHAUSTED", "RateLimit", "403",
                "PERMISSION_DENIED", "API_KEY_SERVICE_BLOCKED"
            ))
            if not recoverable:
                raise

            logging.warning(f"Key ending in ...{current_key[-4:]} failed (attempt {attempt+1}/{max_retries}), rotating key...")
            with api_key_lock:
                key_index += 1
            import time
            time.sleep(retry_backoff_seconds * (2 ** (attempt // len(keys))))

    raise LLMCallError(f"সব API key দিয়ে চেষ্টার পরও ব্যর্থ: {last_error}")


# --- Static Analysis Engine ---

class StaticBugVisitor(ast.NodeVisitor):
    """
    বাংলা মন্তব্য: AST ভিজিটর যা কমন পাইথন বাগ, সিকিউরিটি স্মেল এবং অ্যান্টি-প্যাটার্ন ধরে।
    """

    DANGEROUS_BUILTINS = {"eval", "exec", "compile", "__import__", "input"}
    SQL_METHODS = {"execute", "executemany", "executescript", "cursor", "raw"}
    SECRET_PATTERNS = [
        re.compile(r'password\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
        re.compile(r'secret\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
        re.compile(r'api_key\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
        re.compile(r'token\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
    ]

    def __init__(self, source_lines: list[str], file_path: str):
        self.source_lines = source_lines
        self.file_path = file_path
        self.issues: list[Issue] = []
        self.function_nesting = 0
        self.loop_nesting = 0
        self.current_function: str | None = None

    def _add(self, rule_id: str, category: str, severity: str, message: str, node: ast.AST):
        snippet = ""
        try:
            if hasattr(node, 'lineno') and node.lineno:
                idx = node.lineno - 1
                if 0 <= idx < len(self.source_lines):
                    snippet = self.source_lines[idx].strip()
        except Exception:
            pass

        self.issues.append(Issue(
            rule_id=rule_id,
            category=category,
            severity=severity,
            message=message,
            line=getattr(node, 'lineno', 0),
            column=getattr(node, 'col_offset', 0),
            detection="static",
            snippet=snippet,
        ))

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        self.function_nesting += 1
        prev_func = self.current_function
        self.current_function = node.name

        # BP007: Function too long
        body_lines = node.end_lineno - node.lineno if node.end_lineno else 0
        if body_lines > 50:
            self._add("BP007", "Maintainability", SEVERITY_MEDIUM,
                      f"Function '{node.name}' is {body_lines} lines long. Consider breaking it down.", node)

        # BP006: Too many arguments
        arg_count = len(node.args.args) + len(node.args.kwonlyargs)
        if node.args.vararg:
            arg_count += 1
        if node.args.kwarg:
            arg_count += 1
        if arg_count > 7:
            self._add("BP006", "Complexity", SEVERITY_MEDIUM,
                      f"Function '{node.name}' has {arg_count} parameters. Consider using a data class or config object.", node)

        # BP008: Deep nesting
        if self.function_nesting + self.loop_nesting > 4:
            self._add("BP008", "Complexity", SEVERITY_MEDIUM,
                      f"Deep nesting detected inside '{node.name}'. Refactor to reduce cognitive load.", node)

        self.generic_visit(node)
        self.current_function = prev_func
        self.function_nesting -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # BP001: Bare except
        if node.type is None:
            self._add("BP001", "Reliability", SEVERITY_HIGH,
                      "Bare 'except:' clause catches KeyboardInterrupt and SystemExit. Use 'except Exception:' instead.", node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For | ast.While | ast.If | ast.With):
        self.loop_nesting += 1
        if self.loop_nesting > 3:
            self._add("BP008", "Complexity", SEVERITY_LOW,
                      "Deep loop/conditional nesting detected. Consider extracting helper functions.", node)
        self.generic_visit(node)
        self.loop_nesting -= 1

    visit_While = visit_For
    visit_If = visit_For
    visit_With = visit_For

    def visit_Call(self, node: ast.Call):
        # BP003: Dangerous builtins
        if isinstance(node.func, ast.Name) and node.func.id in self.DANGEROUS_BUILTINS:
            self._add("BP003", "Security", SEVERITY_CRITICAL,
                      f"Dangerous builtin '{node.func.id}()' used. This is a major security risk.", node)

        # BP005: SQL injection risk (heuristic)
        if isinstance(node.func, ast.Attribute) and node.func.attr in self.SQL_METHODS:
            for arg in node.args:
                if isinstance(arg, (ast.JoinedStr, ast.Call)):
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr in {"format", "replace"}:
                        self._add("BP005", "Security", SEVERITY_CRITICAL,
                                  f"Possible SQL injection via string formatting in '{node.func.attr}()'. Use parameterized queries.", node)
                    elif isinstance(arg, ast.JoinedStr):
                        self._add("BP005", "Security", SEVERITY_CRITICAL,
                                  f"Possible SQL injection via f-string in '{node.func.attr}()'. Use parameterized queries.", node)

        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        # BP009: Assert in production code
        self._add("BP009", "Reliability", SEVERITY_MEDIUM,
                  "'assert' statements are removed when Python runs with -O. Do not use them for production logic.", node)
        self.generic_visit(node)

    def scan_source_text(self, source: str):
        """বাংলা মন্তব্য: সোর্স টেক্সট স্ক্যান করে হার্ডকোডেড সিক্রেট এবং কমেন্টেড কোড খোঁজে।"""
        for line_no, line in enumerate(self.source_lines, 1):
            stripped = line.strip()
            # BP010: Hardcoded secrets
            for pattern in self.SECRET_PATTERNS:
                if pattern.search(line) and not stripped.startswith("#"):
                    # Avoid matching env var lookups
                    if "os.getenv" not in line and "environ" not in line and "settings." not in line:
                        self._add("BP010", "Security", SEVERITY_HIGH,
                                  "Possible hardcoded secret detected. Move to environment variables or secrets manager.",
                                  type('obj', (object,), {'lineno': line_no, 'col_offset': line.index('=') if '=' in line else 0})())

            # BP011: TODO/FIXME with high severity keywords
            if "#" in stripped and any(k in stripped.lower() for k in ["hack", "temporary", "temp fix", "xxx"]):
                self._add("BP011", "Maintainability", SEVERITY_LOW,
                          "Temporary/hacky code comment found. Address before merging.",
                          type('obj', (object,), {'lineno': line_no, 'col_offset': 0})())


def run_static_analysis(file_path: Path) -> list[Issue]:
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return [Issue("BP-SYNTAX", "ParseError", SEVERITY_CRITICAL,
                      f"Syntax error: {e}", e.lineno or 1, e.offset or 0, "static")]

    visitor = StaticBugVisitor(lines, str(file_path))
    visitor.visit(tree)
    visitor.scan_source_text(content)
    return visitor.issues


# --- AI Analysis Engine ---

AI_BUG_PROMPT_TEMPLATE = """
You are **BugProphet**, an expert Python code reviewer and security analyst for the SupremeAI project.
Analyze the following Python file and predict bugs, race conditions, logic errors, API misuse, and performance anti-patterns.

**File Path:** `{file_path}`

**Instructions:**
1. Focus on issues that static analysis CANNOT catch (logical errors, concurrency, API misuse, type safety, resource leaks).
2. Return ONLY a valid JSON array. No markdown, no explanation outside JSON.
3. Each object must have: `rule_id` (string, prefix with AI-), `category` (string), `severity` ("CRITICAL"|"HIGH"|"MEDIUM"|"LOW"), `message` (string), `line` (int, best guess), `column` (int, 0 if unknown).
4. If no issues found, return an empty array `[]`.

**Code:**
```python
{code}
```
JSON Output:
"""

def run_ai_analysis(file_path: Path) -> list[Issue]:
    # বাংলা মন্তব্য: এআই বিশ্লেষণ যা রানটাইম/লজিক বাগ এবং এপিআই মিসইউজ ধরতে পারে।
    content = file_path.read_text(encoding="utf-8")
    prompt = AI_BUG_PROMPT_TEMPLATE.format(file_path=file_path, code=content)
    try:
        raw = get_ai_response(prompt, temperature=0.2)
        # Extract JSON from possible markdown fences
        raw = raw.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)
        if not isinstance(data, list):
            logging.warning(f"AI analysis for {file_path} did not return a list.")
            return []

        issues = []
        for item in data:
            issues.append(Issue(
                rule_id=item.get("rule_id", "AI-UNKNOWN"),
                category=item.get("category", "AI"),
                severity=item.get("severity", SEVERITY_MEDIUM),
                message=item.get("message", "AI-detected issue"),
                line=item.get("line", 1),
                column=item.get("column", 0),
                detection="ai",
                snippet=""
            ))
        return issues
    except json.JSONDecodeError as e:
        logging.warning(f"AI analysis JSON parse failed for {file_path}: {e}")
        return []
    except LLMCallError:
        raise
    except Exception as e:
        logging.error(f"Unexpected error during AI analysis of {file_path}: {e}")
        return []


# --- Cache & Hash ---
import sqlite3

def _get_db_connection():
    conn = sqlite3.connect(CACHE_FILE)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
    )
    return conn

def load_cache() -> dict:
    cache = {}
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM cache")
            for row in cursor.fetchall():
                cache[row[0]] = json.loads(row[1])
    except Exception as e:
        logging.warning(f"Failed to load cache: {e}")
    return cache

def save_cache(cache: dict):
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            for key, value in cache.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                    (key, json.dumps(value))
                )
            conn.commit()
    except Exception as e:
        logging.warning(f"Failed to save cache: {e}")


def get_file_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# --- Report Generation ---
def calculate_risk_score(issues: list[Issue]) -> float:
    score = 0.0
    weights = {SEVERITY_CRITICAL: 3.0, SEVERITY_HIGH: 1.5, SEVERITY_MEDIUM: 0.7, SEVERITY_LOW: 0.2}
    for issue in issues:
        score += weights.get(issue.severity, 0.5)
    # Cap at 10.0, normalize roughly
    return min(round(score, 1), 10.0)


def generate_markdown_report(reports: list[FileReport], output_path: Path):
    # বাংলা মন্তব্য: প্রাপ্ত ফলাফলের উপর ভিত্তি করে একটি সুন্দর এবং ডেকোরেটিভ রিপোর্ট ফাইল তৈরি করা।
    lines = [
        "# 🔮 BugProphet Analysis Report",
        f"Generated: {datetime.datetime.now().isoformat()}",
        f"Files Scanned: {len(reports)}",
        "",
        "## Summary",
        "| File | Risk Score | Critical | High | Medium | Low |",
        "|------|-----------|----------|------|--------|-----|",
    ]

    total_crit = total_high = total_med = total_low = 0
    for r in reports:
        c = sum(1 for i in r.issues if i.severity == SEVERITY_CRITICAL)
        h = sum(1 for i in r.issues if i.severity == SEVERITY_HIGH)
        m = sum(1 for i in r.issues if i.severity == SEVERITY_MEDIUM)
        l = sum(1 for i in r.issues if i.severity == SEVERITY_LOW)
        total_crit += c; total_high += h; total_med += m; total_low += l
        lines.append(f"| `{r.file_path}` | {r.risk_score}/10 | {c} | {h} | {m} | {l} |")

    lines.extend([
        "",
        f"**Totals:** {total_crit} Critical, {total_high} High, {total_med} Medium, {total_low} Low",
        "",
        "---",
        "",
        "## Detailed Findings",
    ])

    for r in reports:
        if not r.issues:
            continue
        lines.append(f"### `{r.file_path}` (Risk: {r.risk_score}/10)")
        if r.ai_summary:
            lines.append(f"**AI Summary:** {r.ai_summary}")
        lines.append("")
        lines.append("| Rule | Severity | Category | Line | Message |")
        lines.append("|------|----------|----------|------|---------|")
        for issue in sorted(r.issues, key=lambda x: (x.line, x.severity)):
            lines.append(f"| `{issue.rule_id}` | {issue.severity} | {issue.category} | {issue.line} | {issue.message} |")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(f"✅ Markdown report saved to {output_path}")


# --- Main Orchestrator ---
def process_file(file_path: Path, cache: dict, force: bool, use_ai: bool) -> FileReport | None:
    # বাংলা মন্তব্য: প্রতিটি ফাইলকে স্ক্যান করে এবং ক্যাশে আপডেট করে।
    logging.info(f"Scanning: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    content_hash = get_file_hash(content)

    cache_key = str(file_path)
    # বাংলা মন্তব্য: ক্যাশ কি চেক করা হচ্ছে 'file_hash' এর মাধ্যমে যাতে রিবিল্ড ফাস্ট হয়।
    if not force and cache_key in cache and cache[cache_key].get("file_hash") == content_hash:
        logging.info(f"Skipping {file_path} (cached).")
        cached = cache[cache_key]
        report = FileReport(
            file_path=str(file_path),
            file_hash=content_hash,
            issues=[Issue(**i) for i in cached.get("issues", [])],
            ai_summary=cached.get("ai_summary", ""),
            risk_score=cached.get("risk_score", 0.0),
        )
        return report

    # Static analysis
    static_issues = run_static_analysis(file_path)

    # AI analysis
    ai_issues: list[Issue] = []
    ai_summary = ""
    if use_ai:
        try:
            ai_issues = run_ai_analysis(file_path)
            if ai_issues:
                ai_summary = f"AI identified {len(ai_issues)} potential runtime/logic issue(s)."
        except LLMCallError as e:
            logging.error(f"AI analysis failed for {file_path}: {e}")
            ai_summary = "AI analysis unavailable due to LLM error."

    all_issues = static_issues + ai_issues
    risk = calculate_risk_score(all_issues)

    report = FileReport(
        file_path=str(file_path),
        file_hash=content_hash,
        issues=all_issues,
        ai_summary=ai_summary,
        risk_score=risk,
    )

    cache[cache_key] = report.to_dict()
    return report


def main(dry_run: bool = False, force: bool = False, workers: int = 4, use_ai: bool = True, files: list[str] | None = None, output: str = "bug_prophet_report.md"):
    if not settings.gemini_api_key:
        logging.error("FATAL: GEMINI_API_KEY is not set in backend settings.")
        return

    if dry_run:
        logging.warning("Running in DRY-RUN mode. No files will be modified.")
    if force:
        logging.warning("Running in FORCE mode. Cache ignored.")

    cache = load_cache()
    reports: list[FileReport] = []

    if files:
        file_paths = [Path(f) for f in files if Path(f).exists() and Path(f).name not in EXCLUDE_FILES]
    else:
        file_paths = []
        for target_dir in TARGET_DIRECTORIES:
            base = Path(target_dir)
            if not base.exists():
                logging.warning(f"Directory not found: {base}")
                continue
            for py_file in base.rglob(FILE_PATTERN):
                if py_file.name not in EXCLUDE_FILES:
                    file_paths.append(py_file)

    if not file_paths:
        logging.info("No files to scan.")
        return

    logging.info(f"BugProphet scanning {len(file_paths)} file(s) with {workers} workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_file = {
            executor.submit(process_file, fp, cache, force, use_ai): fp for fp in file_paths
        }
        for future in concurrent.futures.as_completed(future_to_file):
            try:
                report = future.result()
                if report:
                    reports.append(report)
            except Exception as e:
                logging.error(f"Error processing file: {e}")

    if not dry_run:
        save_cache(cache)

    # Sort by risk score descending
    reports.sort(key=lambda r: r.risk_score, reverse=True)

    generate_markdown_report(reports, Path(output))
    logging.info("BugProphet analysis complete. 🔮")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BugProphet: AI-powered bug prediction agent")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing cache or reports.")
    parser.add_argument("--force", action="store_true", help="Ignore cache and rescan everything.")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Concurrent workers.")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI analysis (static only).")
    parser.add_argument("-o", "--output", type=str, default="bug_prophet_report.md", help="Output Markdown report path.")
    parser.add_argument("--files", nargs="*", help="Specific files to scan (git hook mode).")
    args = parser.parse_args()

    main(
        dry_run=args.dry_run,
        force=args.force,
        workers=args.workers,
        use_ai=not args.no_ai,
        files=args.files,
        output=args.output,
    )

# --- Streaming Anomaly Detector ---
import asyncio
import math
from collections import deque
# বাংলা: এই ইমপোর্টে আগে try/except fallback ছিল না — ফলে যখন এই মডিউলটি লাইভ
# backend অ্যাপ থেকে `run_anomaly_detector_loop` হিসেবে ইমপোর্ট করা হতো (core.lifespan
# app_lifespan-এর ভেতর থেকে, যেখানে sys.path-এ শুধু backend/-এর ভেতরের প্যাকেজ
# (core.*) দৃশ্যমান, `backend` নিজে একটা top-level প্যাকেজ হিসেবে দৃশ্যমান নয়),
# এটি সবসময় `ModuleNotFoundError: No module named 'backend'` দিত এবং BugProphet
# Anomaly Detector agent-টি চালুই হতো না (render_admin_.txt লগে এই এররই বারবার
# দেখা যাচ্ছিল)। উপরের config import-এর মতোই একই try/except fallback প্যাটার্ন এখানে
# প্রয়োগ করা হলো।
try:
    from backend.core.messaging.event_bus import error_event_bus, ErrorEvent, ErrorContext
except ImportError:
    from core.messaging.event_bus import error_event_bus, ErrorEvent, ErrorContext

class AnomalyDetector:
    def __init__(self):
        # Tracking error frequencies per module. (timestamp, error_type)
        self.history = {}
        self.window_size_seconds = 60
        self.baseline_avg = {}
        self.baseline_std = {}

    def _update_baselines(self):
        # A lightweight Z-score model update
        now = datetime.datetime.now(datetime.UTC).timestamp()
        for module, events in self.history.items():
            # Keep only events in the window
            valid_events = [e for e in events if now - e[0] <= self.window_size_seconds]
            self.history[module] = valid_events

            count = len(valid_events)

            if module not in self.baseline_avg:
                self.baseline_avg[module] = count
                self.baseline_std[module] = 1.0 # Default std
            else:
                # Exponential moving average
                alpha = 0.1
                old_avg = self.baseline_avg[module]
                self.baseline_avg[module] = (alpha * count) + ((1 - alpha) * old_avg)

                # variance update
                var = (count - self.baseline_avg[module]) ** 2
                self.baseline_std[module] = math.sqrt((alpha * var) + ((1 - alpha) * (self.baseline_std[module] ** 2)))

    def process_event(self, event: ErrorEvent):
        module = event.module
        if module not in self.history:
            self.history[module] = []

        now = datetime.datetime.now(datetime.UTC).timestamp()
        self.history[module].append((now, event.error_type))

        self._update_baselines()

        # Check Z-score
        current_count = len(self.history[module])
        avg = self.baseline_avg.get(module, 0)
        std = self.baseline_std.get(module, 1.0)
        if std == 0:
            std = 1.0

        z_score = (current_count - avg) / std

        # If 10x more warnings than baseline (or very high Z-score)
        if current_count > 10 and current_count > (avg * 10) and z_score > 3.0:
            logging.critical(f"[BugProphet] PREDICTED OUTAGE in {module}! Z-score: {z_score:.2f}, Count: {current_count}, Avg: {avg:.2f}")

            outage_event = ErrorEvent(
                module=module,
                error_type="PREDICTED_OUTAGE",
                message=f"Anomaly detected! Module '{module}' error rate is {current_count} (baseline {avg:.2f}).",
                severity="CRITICAL",
                structured_context=ErrorContext(module=module, env="production")
            )
            # Emit directly to bus (ensure we don't infinitely loop by checking error type)
            if event.error_type != "PREDICTED_OUTAGE":
                asyncio.create_task(error_event_bus.async_emit(outage_event))


async def run_anomaly_detector_loop():
    """
    বাংলা মন্তব্য: Background loop that integrates bug_prophet directly with the ErrorEventBus.
    It predicts outages before they crash the process.
    """
    logging.info("🔮 BugProphet Anomaly Detector started.")
    detector = AnomalyDetector()

    # We register a listener to the error_event_bus
    def listener(event: ErrorEvent):
        if event.error_type not in ["PREDICTED_OUTAGE", "SILENT_PATTERN_ESCALATED"]:
            detector.process_event(event)

    error_event_bus.register_listener("*", listener)

    try:
        while True:
            # The loop just keeps the task alive, the listener does the work synchronously
            # Or we could poll the dead letter queue if we wanted, but listener is real-time.
            await asyncio.sleep(60)
            detector._update_baselines()
    except asyncio.CancelledError:
        error_event_bus.unregister_listener("*", listener)
        logging.info("🔮 BugProphet Anomaly Detector shutting down.")


# --- Merged from refactor_wiz.py ---

#!/usr/bin/env python3
"""
SupremeAI - RefactorWiz Agent 🧙
=================================
Technical debt identifier and safe refactoring planner.

Purpose:
- AST-based metrics collection (complexity, coupling, duplication, length).
- AI-generated safe refactoring plans with before/after suggestions.
- Produces Markdown reports with Mermaid diagrams showing module relationships.

Author: SupremeAI Core
Date: July 18, 2026
"""

import ast
import os
import sys
import json
import logging
import argparse
import hashlib
import concurrent.futures
import threading
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any
from collections import defaultdict

import litellm

# --- Path Setup ---
# বাংলা মন্তব্য: ক্লিন ইমপোর্ট স্ট্রাকচার এবং পাথ রেজোলিউশন নিশ্চিত করা হচ্ছে।
try:
    from backend.core.config import settings
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
    sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core.config import settings

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

litellm.set_verbose = False
litellm.max_retries = 3
litellm.retry_strategy = {
    "wait_time": 16,
    "allowed_exceptions": [Exception]
}

CACHE_FILE = Path(__file__).parent / ".refactor_wiz_cache.sqlite"
TARGET_DIRECTORIES = ["backend/core", "backend/tools"]
FILE_PATTERN = "*.py"
EXCLUDE_FILES = {"__init__.py", "refactor_wiz.py", "ai_scribe_historian.py"}

# --- LLM Infrastructure ---

class LLMCallError(Exception):
    """সব রিট্রাই শেষে LLM কল ব্যর্থ হলে এই এরর রেইজ হবে।"""

key_index = 0
api_key_lock = threading.Lock()


def get_ai_response(prompt: str, temperature: float = 0.3, max_retries_per_key: int = 3, retry_backoff_seconds: float = 2.0) -> str:
    global key_index
    api_keys_str = settings.gemini_api_key
    if not api_keys_str:
        raise LLMCallError("settings.gemini_api_key কনফিগার করা নেই।")

    keys = [k.strip() for k in api_keys_str.split(',') if k.strip()]
    if not keys:
        raise LLMCallError("কোনো বৈধ Gemini API key পাওয়া যায়নি।")

    max_retries = max_retries_per_key * len(keys)
    last_error: Exception | None = None

    for attempt in range(max_retries):
        current_key = keys[key_index % len(keys)]
        try:
            response = litellm.completion(
                model=settings.gemini_model_name,
                messages=[{"content": prompt, "role": "user"}],
                temperature=temperature,
                api_key=current_key
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            error_msg = str(e)
            recoverable = any(code in error_msg for code in (
                "429", "RESOURCE_EXHAUSTED", "RateLimit", "403",
                "PERMISSION_DENIED", "API_KEY_SERVICE_BLOCKED"
            ))
            if not recoverable:
                raise

            logging.warning(f"Key ending in ...{current_key[-4:]} failed (attempt {attempt+1}/{max_retries}), rotating key...")
            with api_key_lock:
                key_index += 1
            import time
            time.sleep(retry_backoff_seconds * (2 ** (attempt // len(keys))))

    raise LLMCallError(f"সব API key দিয়ে চেষ্টার পরও ব্যর্থ: {last_error}")


# --- Data Structures ---

@dataclass
class DebtItem:
    rule_id: str
    category: str
    severity: str
    message: str
    line: int
    metric_value: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FunctionMetrics:
    name: str
    line_start: int
    line_end: int
    length: int
    arg_count: int
    return_count: int
    complexity: int  # Approximate cyclomatic complexity
    nested_depth: int


@dataclass
class FileDebtReport:
    file_path: str
    file_hash: str
    debts: list[DebtItem] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    ai_plan: str = ""
    refactoring_priority: float = 0.0  # 0.0 - 10.0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "debts": [d.to_dict() for d in self.debts],
            "metrics": self.metrics,
            "ai_plan": self.ai_plan,
            "refactoring_priority": self.refactoring_priority,
        }


# --- AST Metrics Collector ---

class MetricsVisitor(ast.NodeVisitor):
    """
    বাংলা মন্তব্য: ফাংশন-লেভেল মেট্রিক্স কালেক্ট করে — সাইক্লোম্যাটিক কমপ্লেক্সিটি, নেস্টিং ডেপ্থ, ইত্যাদি।
    """

    def __init__(self):
        self.functions: list[FunctionMetrics] = []
        self.imports: list[str] = []
        self.classes: list[str] = []
        self.current_func: FunctionMetrics | None = None
        self.nesting_stack = 0
        self.max_nesting_seen = 0

    def _complexity_increment(self, node: ast.AST):
        if self.current_func:
            self.current_func.complexity += 1
        self.nesting_stack += 1
        self.max_nesting_seen = max(self.max_nesting_seen, self.nesting_stack)
        self.generic_visit(node)
        self.nesting_stack -= 1

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        prev = self.current_func
        prev_nesting = self.nesting_stack
        self.nesting_stack = 0
        self.max_nesting_seen = 0

        func = FunctionMetrics(
            name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            length=(node.end_lineno or node.lineno) - node.lineno,
            arg_count=len(node.args.args) + len(node.args.kwonlyargs) + (1 if node.args.vararg else 0) + (1 if node.args.kwarg else 0),
            return_count=0,
            complexity=1,  # Base complexity
            nested_depth=0,
        )
        self.current_func = func
        self.generic_visit(node)
        func.nested_depth = self.max_nesting_seen
        self.functions.append(func)

        self.current_func = prev
        self.nesting_stack = prev_nesting

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If):
        self._complexity_increment(node)

    def visit_While(self, node: ast.While):
        self._complexity_increment(node)

    def visit_For(self, node: ast.For):
        self._complexity_increment(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        self._complexity_increment(node)

    def visit_With(self, node: ast.With):
        self._complexity_increment(node)

    def visit_Assert(self, node: ast.Assert):
        self._complexity_increment(node)

    def visit_Return(self, node: ast.Return):
        if self.current_func:
            self.current_func.return_count += 1
        self.generic_visit(node)


def collect_metrics(file_path: Path) -> tuple[MetricsVisitor, list[str]]:
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return MetricsVisitor(), lines

    visitor = MetricsVisitor()
    visitor.visit(tree)
    return visitor, lines


# --- Debt Detection Engine ---

def detect_debts(file_path: Path, visitor: MetricsVisitor, lines: list[str]) -> list[DebtItem]:
    debts: list[DebtItem] = []

    # RW001: High cyclomatic complexity
    for func in visitor.functions:
        if func.complexity > 10:
            debts.append(DebtItem(
                rule_id="RW001",
                category="Complexity",
                severity="HIGH",
                message=f"Function '{func.name}' has approximate cyclomatic complexity of {func.complexity}. Refactor into smaller helpers.",
                line=func.line_start,
                metric_value=str(func.complexity),
                suggestion="Extract nested conditionals into private helper methods."
            ))

    # RW002: Long function
    for func in visitor.functions:
        if func.length > 40:
            debts.append(DebtItem(
                rule_id="RW002",
                category="Size",
                severity="MEDIUM",
                message=f"Function '{func.name}' spans {func.length} lines.",
                line=func.line_start,
                metric_value=str(func.length),
                suggestion="Apply Extract Method to isolate logical sections."
            ))

    # RW006: Deep nesting
    for func in visitor.functions:
        if func.nested_depth > 3:
            debts.append(DebtItem(
                rule_id="RW006",
                category="Complexity",
                severity="MEDIUM",
                message=f"Function '{func.name}' has nesting depth of {func.nested_depth}.",
                line=func.line_start,
                metric_value=str(func.nested_depth),
                suggestion="Use early returns or extract nested blocks into functions."
            ))

    # RW007: Long parameter list
    for func in visitor.functions:
        if func.arg_count > 5:
            debts.append(DebtItem(
                rule_id="RW007",
                category="Interface",
                severity="LOW",
                message=f"Function '{func.name}' accepts {func.arg_count} parameters.",
                line=func.line_start,
                metric_value=str(func.arg_count),
                suggestion="Introduce a parameter object or builder pattern."
            ))

    # RW008: God class
    if len(visitor.classes) == 1 and len(visitor.functions) > 20:
        debts.append(DebtItem(
            rule_id="RW008",
            category="Architecture",
            severity="HIGH",
            message=f"Possible God Class detected with {len(visitor.functions)} methods.",
            line=1,
            metric_value=str(len(visitor.functions)),
            suggestion="Split responsibilities into multiple collaborator classes."
        ))

    # RW009: Duplicate code blocks (simple heuristic: identical line sequences of >= 4 lines)
    block_map: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i in range(len(lines) - 3):
        block = tuple(line.strip() for line in lines[i:i+4])
        if len(block[0]) > 10:  # Ignore trivial short lines
            block_map[block].append(i + 1)

    for block, line_nums in block_map.items():
        if len(line_nums) > 1:
            debts.append(DebtItem(
                rule_id="RW009",
                category="Duplication",
                severity="MEDIUM",
                message=f"Duplicate 4-line block found at lines {line_nums}. Consider extracting a shared function.",
                line=line_nums[0],
                metric_value=str(len(line_nums)),
                suggestion="Apply Extract Function to eliminate duplication."
            ))
            # Limit duplicate warnings to avoid noise
            if len([d for d in debts if d.rule_id == "RW009"]) >= 3:
                break

    return debts


# --- AI Refactoring Planner ---

AI_REFACTOR_PROMPT_TEMPLATE = """
You are **RefactorWiz**, an expert Python architect for the SupremeAI project.
Given the following file's code and detected metrics, produce a safe, step-by-step refactoring plan.

**File:** `{file_path}`

**Detected Metrics:**
{metrics_json}

**Detected Debts:**
{debts_json}

**Instructions:**
1. Provide a concise refactoring plan (max 400 words).
2. Prioritize by safety (do not change behavior).
3. Suggest specific design patterns if applicable (Strategy, Factory, Repository, etc.).
4. Include a "Quick Wins" section for immediate improvements.
5. If the code is clean, simply state: "No major refactoring needed."

**Code:**
```python
{code}
```
Refactoring Plan:
"""

def generate_ai_plan(file_path: Path, metrics: dict, debts: list[DebtItem]) -> str:
    # বাংলা মন্তব্য: এআই জেনারেটেড রিফ্যাক্টরিং প্ল্যান।
    content = file_path.read_text(encoding="utf-8")
    prompt = AI_REFACTOR_PROMPT_TEMPLATE.format(
        file_path=file_path,
        metrics_json=json.dumps(metrics, indent=2),
        debts_json=json.dumps([d.to_dict() for d in debts], indent=2),
        code=content,
    )
    try:
        return get_ai_response(prompt, temperature=0.3)
    except LLMCallError as e:
        logging.error(f"AI planning failed for {file_path}: {e}")
        return "AI refactoring plan unavailable due to LLM error."


# --- Cache & Hash ---
import sqlite3

def _get_db_connection():
    conn = sqlite3.connect(CACHE_FILE)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
    )
    return conn

def load_cache() -> dict:
    cache = {}
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM cache")
            for row in cursor.fetchall():
                cache[row[0]] = json.loads(row[1])
    except Exception as e:
        logging.warning(f"Failed to load cache: {e}")
    return cache

def save_cache(cache: dict):
    try:
        with _get_db_connection() as conn:
            cursor = conn.cursor()
            for key, value in cache.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                    (key, json.dumps(value))
                )
            conn.commit()
    except Exception as e:
        logging.warning(f"Failed to save cache: {e}")


def get_file_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# --- Report Generation ---
def calculate_priority(debts: list[DebtItem]) -> float:
    score = 0.0
    weights = {"HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.3}
    for d in debts:
        score += weights.get(d.severity, 0.5)
    return min(round(score, 1), 10.0)


def generate_markdown_report(reports: list[FileDebtReport], output_path: Path):
    # বাংলা মন্তব্য: রিফ্যাক্টরিং ডেব্ট রিপোর্ট তৈরি করা।
    lines = [
        "# 🧙 RefactorWiz Technical Debt Report",
        f"Generated: {datetime.datetime.now().isoformat()}",
        f"Files Analyzed: {len(reports)}",
        "",
        "## Summary",
        "| File | Priority | Debts | Complexity |",
        "|------|----------|-------|------------|",
    ]

    for r in reports:
        debt_count = len(r.debts)
        comp = r.metrics.get("avg_complexity", 0)
        lines.append(f"| `{r.file_path}` | {r.refactoring_priority}/10 | {debt_count} | {comp} |")

    lines.extend([
        "",
        "---",
        "",
        "## Refactoring Plans by File",
    ])

    for r in reports:
        if not r.debts and not r.ai_plan:
            continue

        lines.append(f"### `{r.file_path}` (Priority: {r.refactoring_priority}/10)")
        lines.append("")
        lines.append("**Metrics:**")
        lines.append(f"- Total Functions: {r.metrics.get('function_count', 0)}")
        lines.append(f"- Average Complexity: {r.metrics.get('avg_complexity', 0)}")
        lines.append(f"- Total Imports: {r.metrics.get('import_count', 0)}")
        lines.append(f"- Classes: {r.metrics.get('class_count', 0)}")
        lines.append("")

        if r.debts:
            lines.append("**Detected Debts:**")
            lines.append("")
            lines.append("| Rule | Severity | Category | Line | Message | Suggestion |")
            lines.append("|------|----------|----------|------|---------|------------|")
            for d in sorted(r.debts, key=lambda x: (x.line, x.severity)):
                lines.append(f"| `{d.rule_id}` | {d.severity} | {d.category} | {d.line} | {d.message} | {d.suggestion} |")
            lines.append("")

        if r.ai_plan:
            lines.append("**AI Refactoring Plan:**")
            lines.append("")
            lines.append(r.ai_plan)
            lines.append("")

        # Mermaid diagram for class/function structure (simplified)
        func_names = [f for f in r.metrics.get("functions", [])]
        if func_names:
            lines.append("**Structure Overview:**")
            lines.append("```mermaid")
            lines.append("graph TD;")
            for fn in func_names[:10]:  # Limit to 10 for readability
                safe_name = fn.replace('"', "'")
                lines.append(f'    {safe_name}["{safe_name}()"];')
            lines.append("```")
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(f"✅ RefactorWiz report saved to {output_path}")


# --- Main Orchestrator ---
def process_file(file_path: Path, cache: dict, force: bool, use_ai: bool) -> FileDebtReport | None:
    # বাংলা মন্তব্য: ফাইল অ্যানালাইসিস এবং মেট্রিক্স সংরক্ষণ প্রক্রিয়া।
    logging.info(f"Analyzing: {file_path}")
    content = file_path.read_text(encoding="utf-8")
    content_hash = get_file_hash(content)

    cache_key = str(file_path)
    # বাংলা মন্তব্য: ক্যাশ কি চেক করা হচ্ছে 'file_hash' এর মাধ্যমে।
    if not force and cache_key in cache and cache[cache_key].get("file_hash") == content_hash:
        logging.info(f"Skipping {file_path} (cached).")
        c = cache[cache_key]
        return FileDebtReport(
            file_path=str(file_path),
            file_hash=content_hash,
            debts=[DebtItem(**d) for d in c.get("debts", [])],
            metrics=c.get("metrics", {}),
            ai_plan=c.get("ai_plan", ""),
            refactoring_priority=c.get("refactoring_priority", 0.0),
        )

    visitor, lines = collect_metrics(file_path)
    debts = detect_debts(file_path, visitor, lines)

    metrics = {
        "function_count": len(visitor.functions),
        "class_count": len(visitor.classes),
        "import_count": len(visitor.imports),
        "avg_complexity": round(sum(f.complexity for f in visitor.functions) / max(len(visitor.functions), 1), 1),
        "functions": [f.name for f in visitor.functions],
    }

    ai_plan = ""
    if use_ai and debts:
        try:
            ai_plan = generate_ai_plan(file_path, metrics, debts)
        except LLMCallError as e:
            logging.error(f"AI planning failed: {e}")
            ai_plan = "Unavailable."

    priority = calculate_priority(debts)

    report = FileDebtReport(
        file_path=str(file_path),
        file_hash=content_hash,
        debts=debts,
        metrics=metrics,
        ai_plan=ai_plan,
        refactoring_priority=priority,
    )

    cache[cache_key] = report.to_dict()
    return report


def main(dry_run: bool = False, force: bool = False, workers: int = 4, use_ai: bool = True, files: list[str] | None = None, output: str = "refactor_wiz_report.md"):
    if not settings.gemini_api_key:
        logging.error("FATAL: GEMINI_API_KEY is not set in backend settings.")
        return

    if dry_run:
        logging.warning("Running in DRY-RUN mode.")
    if force:
        logging.warning("Running in FORCE mode. Cache ignored.")

    cache = load_cache()
    reports: list[FileDebtReport] = []

    if files:
        file_paths = [Path(f) for f in files if Path(f).exists() and Path(f).name not in EXCLUDE_FILES]
    else:
        file_paths = []
        for target_dir in TARGET_DIRECTORIES:
            base = Path(target_dir)
            if not base.exists():
                logging.warning(f"Directory not found: {base}")
                continue
            for py_file in base.rglob(FILE_PATTERN):
                if py_file.name not in EXCLUDE_FILES:
                    file_paths.append(py_file)

    if not file_paths:
        logging.info("No files to analyze.")
        return

    logging.info(f"RefactorWiz analyzing {len(file_paths)} file(s) with {workers} workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_file = {
            executor.submit(process_file, fp, cache, force, use_ai): fp for fp in file_paths
        }
        for future in concurrent.futures.as_completed(future_to_file):
            try:
                report = future.result()
                if report:
                    reports.append(report)
            except Exception as e:
                logging.error(f"Error analyzing file: {e}")

    if not dry_run:
        save_cache(cache)

    reports.sort(key=lambda r: r.refactoring_priority, reverse=True)
    generate_markdown_report(reports, Path(output))
    logging.info("RefactorWiz analysis complete. 🧙")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RefactorWiz: Technical debt detection & refactoring planner")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing cache or reports.")
    parser.add_argument("--force", action="store_true", help="Ignore cache.")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Concurrent workers.")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI planning (metrics only).")
    parser.add_argument("-o", "--output", type=str, default="refactor_wiz_report.md", help="Output report path.")
    parser.add_argument("--files", nargs="*", help="Specific files to analyze.")
    args = parser.parse_args()

    main(
        dry_run=args.dry_run,
        force=args.force,
        workers=args.workers,
        use_ai=not args.no_ai,
        files=args.files,
        output=args.output,
    )


# --- Merged from generate_modular_audits.py ---

# ruff: noqa: E501
"""
SupremeAI 2.0 — Elite Modular Audit Generator (v2.0)
======================================================
Generates 14 + 1 hyper-focused, self-contained audit markdown files into
`docs/autogen/modular_audits/` that ANY AI auditor (GPT-4o, Claude 3.5,
Gemini 1.5 Pro, etc.) can use to give their absolute BEST review.

Key upgrades over v1:
  - Removes the 15-file cap: all files embedded
  - AI-optimized audit prompt header per part
  - Per-file metadata: size, line count, last-modified
  - Token budget estimate so auditor knows what to expect
  - Smart skip: __pycache__, node_modules, .pyc, binary, autogen dirs
  - Generates a master INDEX.md for easy navigation
  - Output now goes to docs/autogen/modular_audits/

বাংলা মন্তব্য: এই স্ক্রিপ্টটি যেকোনো AI কে সর্বোচ্চ মানের অডিট দেওয়ার জন্য
একটি সম্পূর্ণ, স্বনির্ভর (self-contained) কনটেক্সট প্যাকেজ তৈরি করে।
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: স্কিপ করা এক্সটেনশন — বাইনারি, ক্যাশ, বা অপ্রয়োজনীয় ফাইল
# ─────────────────────────────────────────────────────────────────────────────
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".pdf", ".docx", ".xlsx", ".zip", ".gz", ".tar", ".whl",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".ogg", ".avi",
    ".lock",  # poetry.lock, package-lock.json — too large
    ".map",   # JS source maps
}

# বাংলা মন্তব্য: এই ডিরেক্টরিগুলো সম্পূর্ণ স্কিপ করা হবে
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", ".env",
    "dist", "build", ".next", ".turbo", ".cache", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "autogen",  # skip own output dir
}

# বাংলা মন্তব্য: ফাইল এক্সটেনশন থেকে markdown code fence ভাষা নির্ধারণ
EXT_TO_LANG: dict[str, str] = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript",
    ".jsx": "jsx", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".md": "markdown", ".sh": "bash", ".bash": "bash",
    ".env": "bash", ".tf": "hcl", ".hcl": "hcl", ".sql": "sql",
    ".dart": "dart", ".go": "go", ".rs": "rust", ".html": "html",
    ".css": "css", ".scss": "scss", ".xml": "xml", ".proto": "protobuf",
    ".graphql": "graphql", ".dockerfile": "dockerfile",
}

# Max file size to embed (skip files larger than this — e.g. large test fixtures)
MAX_FILE_BYTES = 150_000  # 150 KB

# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: ১৪টি মডিউলার অডিট পার্টের সংজ্ঞা
# ─────────────────────────────────────────────────────────────────────────────
AUDIT_PARTS: dict[str, dict] = {
    "PART_01_LLM_GATEWAY_ROUTER.md": {
        "title": "Part 1: LLM Gateway, Predictive Router & Quota Governor",
        "description": "Multi-provider AI routing, predictive free-tier quota governor, and gateway fallback logic.",
        "focus_areas": [
            "Provider selection & fallback chain correctness",
            "Quota enforcement & Redis-based token budget atomicity",
            "Circuit breaker open/close logic under concurrent load",
            "Rate limit tracking accuracy across providers",
        ],
        "target_paths": [
            "backend/core/llm_router.py",
            "backend/core/llm/free_tier_tracker.py",
            "backend/core/llm/distributed_budget.py",
            "backend/core/autonoguard_engine.py",
        ],
    },
    "PART_02_SECURITY_GUARDRAILS.md": {
        "title": "Part 2: Security Guardrails, Prompt Firewall & RBAC",
        "description": "Prompt firewall, anti-hacking middleware, rate limiters, honeypot, and RBAC authentication.",
        "focus_areas": [
            "Prompt injection & jailbreak detection coverage",
            "CORS origin validation bypass risks",
            "RBAC role escalation vectors",
            "Rate limiter bypass under distributed load",
            "Honeypot fingerprinting effectiveness",
        ],
        "target_paths": ["backend/core/security/"],
    },
    "PART_03_MULTI_DB_OUTBOX.md": {
        "title": "Part 3: Multi-DB Architecture & Transactional Outbox",
        "description": "Transactional outbox pattern, Supabase, Cloudflare D1, Upstash Redis, and code_to_db_sync daemon.",
        "focus_areas": [
            "Outbox event delivery guarantees (at-least-once vs exactly-once)",
            "Multi-DB router fail-closed correctness under all circuit breaker states",
            "Feature flag percentage rollout determinism",
            "Write-behind batcher flush atomicity",
        ],
        "target_paths": [
            "backend/database/multi_db_router.py",
            "backend/pipelines/code_to_db_sync.py",
            "backend/core/persistence/write_behind.py",
            "backend/database/supabase_client.py",
        ],
    },
    "PART_04_TIER8_SELF_EVOLUTION.md": {
        "title": "Part 4: Tier 8 Self-Evolution Engine & Auto-Healer",
        "description": "Error fingerprinting, mutation depth guardrails, model training, and auto-git-revert triggers.",
        "focus_areas": [
            "Mutation depth <= 3 guardrail enforcement",
            "Fingerprint collision risk in failure_fingerprint.py",
            "Rollback monitor gcloud dependency failure handling",
            "Model trainer status fabrication prevention",
        ],
        "target_paths": [
            "backend/core/auto_healer_service.py",
            "backend/core/failure_fingerprint.py",
            "backend/tools/learning/model_trainer.py",
            "backend/core/resilience/rollback_monitor.py",
        ],
    },
    "PART_05_SWARM_WEBSOCKETS.md": {
        "title": "Part 5: Swarm Real-Time WebSockets & Telemetry Buffer",
        "description": "250ms sliding window ring-buffer streaming, Redis pubsub, and HITL escalation channels.",
        "focus_areas": [
            "PubSub message delivery ordering & backpressure",
            "Oversized broadcast payload handling",
            "Wall-clock timer flush correctness in buffered_subscribe",
            "Admin route authentication coverage completeness",
        ],
        "target_paths": [
            "backend/core/swarm_pubsub.py",
            "backend/core/admin_routes.py",
        ],
    },
    "PART_06_P2P_COMPUTE_MESH.md": {
        "title": "Part 6: P2P Compute Mesh & Zero-Trust Sandboxing",
        "description": "Zero-trust MicroVM sandbox execution, hardware resource broker, and crypto proof-of-work credit system.",
        "focus_areas": [
            "Resource broker race conditions under concurrent allocation",
            "MicroVM escape vectors (filesystem, network, process)",
            "Credit deduction atomicity & refund guarantees",
            "Firecracker/gVisor payload injection security",
        ],
        "target_paths": [
            "backend/p2p/resource_broker.py",
            "backend/p2p/credit_system.py",
            "backend/core/microvm_sandbox.py",
        ],
    },
    "PART_07_BACKEND_API_ROUTERS.md": {
        "title": "Part 7: Backend API Routers, Middleware & Core App Builder",
        "description": "FastAPI application entrypoints, middleware stack, dependencies, and v1 API routers.",
        "focus_areas": [
            "Middleware ordering & dependency injection safety",
            "Unauthenticated endpoint exposure",
            "Request validation & schema enforcement gaps",
            "CORS, HTTPS, and security header configuration",
        ],
        "target_paths": [
            "backend/api/",
            "backend/core/app.py",
            "backend/core/app_builder.py",
        ],
    },
    "PART_08_BACKEND_AI_AGENT_TOOLS.md": {
        "title": "Part 8: Backend AI Agents, MCP Tools & Orchestration Services",
        "description": "Autonomous AI agent tools, MCP server integrations, checkpointing, and execution tools.",
        "focus_areas": [
            "Agent loop infinite recursion risks",
            "MCP tool permission scope creep",
            "Checkpoint state integrity under concurrent agents",
            "External tool execution sandboxing completeness",
        ],
        "target_paths": ["backend/tools/"],
    },
    "PART_09_REACT_STUDIO_CLIENT.md": {
        "title": "Part 9: React/Vite Studio Client Web Application",
        "description": "React Studio Client frontend app, Admin Console UI components, and state management hooks.",
        "focus_areas": [
            "XSS vectors in rendered user/AI content",
            "Auth token storage & expiry handling in zustand stores",
            "Error boundary completeness & telemetry reporting",
            "Sensitive data leakage in frontend error messages",
        ],
        "target_paths": ["apps/studio-client/src/"],
    },
    "PART_10_FLUTTER_MOBILE_APP.md": {
        "title": "Part 10: Flutter Mobile Cross-Platform Application",
        "description": "Flutter Mobile application source code, state management, and mobile API services.",
        "focus_areas": [
            "API key storage security (Keychain/Keystore vs plain storage)",
            "Certificate pinning implementation",
            "Deep link validation & open redirect risks",
            "Biometric auth bypass vectors",
        ],
        "target_paths": ["apps/mobile/"],
    },
    "PART_11_PACKAGES_SHARED_TYPES.md": {
        "title": "Part 11: Shared Monorepo Packages & TypeScript Interfaces",
        "description": "Monorepo shared TypeScript types, design tokens, and reusable UI components.",
        "focus_areas": [
            "Type safety gaps that could mask runtime errors",
            "Shared secret / credential handling in shared packages",
            "Circular dependency risks",
        ],
        "target_paths": ["packages/"],
    },
    "PART_12_TEST_SUITE_PYTEST.md": {
        "title": "Part 12: Pytest Test Suite & Integration Tests",
        "description": "Backend pytest test suite, API integration test cases, and resilience coverage.",
        "focus_areas": [
            "Test coverage gaps in security-critical paths",
            "Mocking correctness (wrong module paths, incomplete mocks)",
            "Async test isolation & event loop leaks",
            "Integration test environment variable dependency risks",
        ],
        "target_paths": ["backend/tests/"],
    },
    "PART_13_CICD_DEV_WORKFLOWS.md": {
        "title": "Part 13: GitHub Actions CI/CD & DevOps Scripts",
        "description": "Monorepo GitHub Actions workflows, maintenance automation pipelines, and CI scripts.",
        "focus_areas": [
            "Secret exposure in workflow logs (echo, env printing)",
            "Workflow trigger scope (pull_request vs push)",
            "Third-party action pinning (SHA vs tag)",
            "Script injection via untrusted PR data",
        ],
        "target_paths": [
            ".github/workflows/",
            "scripts/ci/",
            "scripts/devops/",
        ],
    },
    "PART_14_CLOUD_INFRASTRUCTURE.md": {
        "title": "Part 14: Cloud Infrastructure, Edge Workers & Docker Prod",
        "description": "Terraform, Cloudflare Worker JS, Firebase Functions, Docker Prod, and deployment specs.",
        "focus_areas": [
            "Docker image hardening (non-root user, read-only FS)",
            "Terraform state file secret exposure",
            "Cloudflare Worker secret binding completeness",
            "Network exposure of internal services",
        ],
        "target_paths": [
            "infrastructure/",
            "cloudflare-worker/",
            "Dockerfile",
            "render.yaml",
            "vercel.json",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: helper ফাংশন — ফাইল সংগ্রহ করে metadata সহ
# ─────────────────────────────────────────────────────────────────────────────

def _should_skip(path: Path) -> bool:
    """বাংলা মন্তব্য: ফাইলটি স্কিপ করা উচিত কিনা তা নির্ধারণ করে।"""
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    if path.name.startswith("."):
        return True
    if path.stat().st_size > MAX_FILE_BYTES:
        return False  # Still embed, but truncated
    return False


def _collect_files(root_path: Path, target: str) -> list[Path]:
    """বাংলা মন্তব্য: একটি target path থেকে সমস্ত eligible ফাইল সংগ্রহ করে।"""
    full_target = root_path / target
    if not full_target.exists():
        return []

    if full_target.is_file():
        return [full_target]

    # Directory — recursively collect, skip forbidden dirs
    collected: list[Path] = []
    for child in sorted(full_target.rglob("*")):
        if not child.is_file():
            continue
        # Check if any parent dir is in SKIP_DIRS
        if any(part in SKIP_DIRS for part in child.parts):
            continue
        if child.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if child.name.startswith("."):
            continue
        collected.append(child)
    return collected


def _get_git_log(filepath: Path, root_path: Path) -> str:
    """বাংলা মন্তব্য: ফাইলের সর্বশেষ ৩টি git commit সংক্ষিপ্তভাবে দেখায়।"""
    try:
        rel = str(filepath.relative_to(root_path)).replace("\\", "/")
        result = subprocess.run(
            ["git", "log", "--oneline", "-3", "--", rel],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=root_path, timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        if lines:
            return "\n".join(f"  - `{ln}`" for ln in lines)
        return "  - *(no commits yet)*"
    except Exception:  # noqa: BLE001
        return "  - *(git log unavailable)*"


def _estimate_tokens(text: str) -> int:
    """বাংলা মন্তব্য: Rough token estimate (1 token ≈ 4 chars for English code)."""
    return max(1, len(text) // 4)


def _embed_file(filepath: Path, rel_path: str, root_path: Path) -> tuple[str, dict]:
    """বাংলা মন্তব্য: একটি ফাইলের সম্পূর্ণ content markdown codeblock-এ embed করে।"""
    ext = filepath.suffix.lower()
    lang = EXT_TO_LANG.get(ext, ext.lstrip(".") or "text")
    # Special case: Dockerfile
    if filepath.name.lower() == "dockerfile":
        lang = "dockerfile"

    size_bytes = filepath.stat().st_size
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        mtime = "unknown"

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        content = f"# Error reading file: {exc}"

    line_count = content.count("\n") + 1
    truncated = ""
    if size_bytes > MAX_FILE_BYTES:
        # Embed first 120 lines + last 20 lines with a note
        lines = content.splitlines()
        head = "\n".join(lines[:120])
        tail = "\n".join(lines[-20:])
        content = f"{head}\n\n# ... [{line_count - 140} lines truncated — file too large] ...\n\n{tail}"
        truncated = " ⚠️ *truncated*"

    git_log = _get_git_log(filepath, root_path)

    block = (
        f"### 📄 `{rel_path}`{truncated}\n\n"
        f"> **Size:** `{size_bytes:,} bytes` | "
        f"**Lines:** `{line_count:,}` | "
        f"**Modified:** `{mtime}`\n>\n"
        f"> **Recent commits:**\n{git_log}\n\n"
        f"```{lang}\n{content}\n```\n"
    )
    meta = {
        "path": rel_path,
        "size_bytes": size_bytes,
        "lines": line_count,
        "tokens": _estimate_tokens(content),
    }
    return block, meta


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: AI-optimized audit prompt — যেকোনো AI সর্বোচ্চ মানের রিভিউ দিতে পারবে
# ─────────────────────────────────────────────────────────────────────────────

def _build_ai_audit_prompt(title: str, description: str, focus_areas: list[str]) -> str:
    areas_md = "\n".join(f"  - {a}" for a in focus_areas)
    return f"""## 🤖 AI Audit Instructions

> **You are acting as a Senior Security & Code Quality Auditor.**
> This document is **100% self-contained** — all source code is embedded below.
> You do NOT need access to any external repository or file system.

### Your Mission
Perform a **deep, exhaustive audit** of the **{title}** subsystem.
Your audit must be production-grade — do not give vague or generic feedback.

### Mandatory Focus Areas for This Module
{areas_md}

### Required Output Format
For every issue found, provide **exactly**:
1. **🔴 Severity:** `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO`
2. **📁 File + Line:** e.g. `backend/core/llm_router.py:L142`
3. **🐛 Issue Title:** One-line summary
4. **📖 Description:** What is wrong and why it matters
5. **🛠️ Delta Patch:** Exact code fix (before/after diff)
6. **✅ Test Suggestion:** How to verify the fix

### Quality Gates (you must meet ALL of these)
- [ ] Zero hallucinations — only cite actual code lines visible in Section 3
- [ ] Every CRITICAL/HIGH issue must have a working patch
- [ ] Do not repeat pre-existing comments as issues
- [ ] Check for Bangla comments (`# বাংলা মন্তব্য`) — verify they match the code logic
- [ ] Flag any `# TODO`, `pass`, or `NotImplemented` left in production paths

---"""


# ─────────────────────────────────────────────────────────────────────────────
# বাংলা মন্তব্য: মূল generation ফাংশন
# ─────────────────────────────────────────────────────────────────────────────

def generate_audit_markdowns(project_root: str = ".") -> None:
    """
    বাংলা মন্তব্য: সম্পূর্ণ monorepo স্ক্যান করে ১৪টি AI-optimized audit ফাইল তৈরি করে।
    সব ফাইল docs/autogen/modular_audits/ ফোল্ডারে যাবে।
    """
    root_path = Path(project_root).resolve()
    output_dir = root_path / "docs" / "autogen" / "modular_audits"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*70}")
    print(f"  SupremeAI 2.0 — Elite Modular Audit Generator v2.0")
    print(f"  Output  : {output_dir}")
    print(f"  Started : {timestamp}")
    print(f"{'='*70}\n")

    index_rows: list[str] = []
    grand_total_files = 0
    grand_total_bytes = 0
    grand_total_tokens = 0

    for filename, meta in AUDIT_PARTS.items():
        filepath = output_dir / filename
        title = meta["title"]
        description = meta["description"]
        focus_areas = meta.get("focus_areas", [])

        print(f"  [>] Generating {filename} ...", end="", flush=True)

        # ── Collect all files ──────────────────────────────────────────────
        all_files: list[Path] = []
        missing_targets: list[str] = []

        for target in meta["target_paths"]:
            found = _collect_files(root_path, target)
            if found:
                all_files.extend(found)
            else:
                missing_targets.append(target)

        # De-duplicate (in case of overlapping target paths)
        seen: set[Path] = set()
        unique_files: list[Path] = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        # ── Build inventory + embedded blocks ─────────────────────────────
        inventory_lines: list[str] = []
        embedded_blocks: list[str] = []
        part_files = 0
        part_bytes = 0
        part_tokens = 0

        for child in unique_files:
            rel = str(child.relative_to(root_path)).replace("\\", "/")
            size = child.stat().st_size
            block, file_meta = _embed_file(child, rel, root_path)
            inventory_lines.append(
                f"| `{rel}` | {size:,} B | {file_meta['lines']:,} | ~{file_meta['tokens']:,} |"
            )
            embedded_blocks.append(block)
            part_files += 1
            part_bytes += size
            part_tokens += file_meta["tokens"]

        for m in missing_targets:
            inventory_lines.append(f"| `{m}` | — | — | *(not found)* |")

        grand_total_files += part_files
        grand_total_bytes += part_bytes
        grand_total_tokens += part_tokens

        inventory_md = "\n".join(inventory_lines) if inventory_lines else "*(no files found)*"
        source_dump = "\n---\n".join(embedded_blocks) if embedded_blocks else "*(no source files)*"
        ai_prompt = _build_ai_audit_prompt(title, description, focus_areas)

        # ── Write part file ────────────────────────────────────────────────
        content = f"""# {title}

> **Audit Generated:** `{timestamp}`
> **Description:** {description}
> **Files:** `{part_files}` | **Total Size:** `{part_bytes:,} bytes` | **Est. Tokens:** `~{part_tokens:,}`
> **Status:** `SELF_CONTAINED — READY FOR AI AUDIT`

---

{ai_prompt}

---

## 2. 📁 File Inventory

| File Path | Size | Lines | Est. Tokens |
|-----------|------|-------|-------------|
{inventory_md}

**Totals:** `{part_files}` files · `{part_bytes:,}` bytes · `~{part_tokens:,}` tokens

---

## 3. 📦 Complete Source Code

> **Instructions for AI:** Read ALL code below before writing any findings.
> Line numbers in your output must match the actual code shown here.

{source_dump}

---

## 4. 🔴 Identified Vulnerabilities & Issues

*Populate this section by feeding Section 2 + Section 3 into your AI auditor.*

<!-- AUDIT_START -->
<!-- AUDIT_END -->

---

## 5. 🛠️ Recommended Delta Patches

*Each patch must be in unified diff format with file path and line numbers.*

---

## 6. ✅ Verification Checklist

- [ ] All CRITICAL/HIGH patches applied and tested
- [ ] Regression tests pass for changed files
- [ ] Bangla comments updated to reflect changes
- [ ] No new `# TODO` or `pass` introduced in production paths

---
*Generated by SupremeAI 2.0 Elite Audit Generator v2.0*
"""
        filepath.write_text(content, encoding="utf-8")
        size_kb = len(content) / 1024
        print(f" [OK] ({part_files} files, {size_kb:.0f} KB, ~{part_tokens:,} tokens)")

        # Index entry
        index_rows.append(
            f"| [{filename}](./{filename}) | {part_files} | {part_bytes:,} B | ~{part_tokens:,} |"
        )

    # ── Generate master INDEX.md ───────────────────────────────────────────
    index_path = output_dir / "INDEX.md"
    index_table = "\n".join(index_rows)
    index_content = f"""# SupremeAI 2.0 — Modular Audit Index

> **Generated:** `{timestamp}`
> **Total Files Covered:** `{grand_total_files}`
> **Total Codebase Size:** `{grand_total_bytes:,} bytes`
> **Total Estimated Tokens:** `~{grand_total_tokens:,}`

---

## How to Use These Audits

1. **Pick a Part** from the table below based on what you want audited.
2. **Open the Part file** — it contains everything (instructions, code, checklist).
3. **Paste the full Part file** into your AI assistant (GPT-4o / Claude / Gemini).
4. **The AI will self-audit** using the embedded instructions and source code.
5. **Paste the AI's output** back into Section 4 (Vulnerabilities) of the Part file.

> **Tip:** For maximum audit quality, use a model with **128K+ context window**
> and instruct it to read ALL of Section 3 before answering.

---

## Part Index

| Part File | Files | Size | Est. Tokens |
|-----------|-------|------|-------------|
{index_table}

---

## Audit Coverage Map

```
SupremeAI 2.0 Monorepo
├── backend/
│   ├── core/llm*           → PART_01 (LLM Gateway)
│   ├── core/security/      → PART_02 (Security Guardrails)
│   ├── database/           → PART_03 (Multi-DB Outbox)
│   ├── core/auto_healer*   → PART_04 (Self-Evolution)
│   ├── core/swarm_*        → PART_05 (WebSockets)
│   ├── core/admin_routes*  → PART_05 (Admin Auth)
│   ├── p2p/                → PART_06 (P2P Compute)
│   ├── core/microvm*       → PART_06 (Sandboxing)
│   ├── api/                → PART_07 (API Routers)
│   └── tools/              → PART_08 (AI Agent Tools)
├── apps/studio-client/     → PART_09 (React Frontend)
├── apps/mobile/            → PART_10 (Flutter Mobile)
├── packages/               → PART_11 (Shared Types)
├── backend/tests/          → PART_12 (Test Suite)
├── .github/workflows/      → PART_13 (CI/CD)
├── scripts/                → PART_13 (DevOps Scripts)
└── infrastructure/         → PART_14 (Cloud Infra)
```

---
*SupremeAI 2.0 Elite Audit Generator v2.0*
"""
    index_path.write_text(index_content, encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"  [OK] INDEX.md generated: {index_path}")
    print(f"  [+]  Grand Total: {grand_total_files} files · "
          f"{grand_total_bytes:,} bytes · ~{grand_total_tokens:,} tokens")
    print(f"  [/]  Output: {output_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    generate_audit_markdowns()


# --- Merged from run_local_audit.py ---

# ruff: noqa: E501
"""
SupremeAI 2.0 — Local AI Audit Runner
=====================================
Automates local LLM auditing of the 12 generated modular audit markdowns using
Ollama (local offline) or free-tier APIs (Gemini / Groq / OpenRouter / DeepSeek).

Bangla inline comments included as per AGENTS.md requirements.
"""

import argparse
import json
import os
import urllib.request
from pathlib import Path

# বাংলা নির্দেশিকা: প্রম্পট যা যেকোনো AI মডেলে পাঠানো হবে
AUDIT_SYSTEM_PROMPT = """You are an elite Autonomous AI Code Architect auditing SupremeAI 2.0.
Your task is to audit the attached self-contained markdown file containing complete source code dumps.

Check for:
1. Security vulnerabilities & secret leaks.
2. Silent exceptions & unhandled failure edge-cases.
3. Free-tier quota exhaustion risks.
4. Code quality & performance bottlenecks.

Output your findings clearly in GitHub-style Markdown with Section 4 (Vulnerabilities) and Section 5 (Recommended Delta Patches).
"""

def audit_file_with_ollama(markdown_path: Path, model_name: str = "llama3.2") -> str:
    """
    Executes audit using local Ollama instance (HTTP API).
    বাংলা মন্তব্য: লোকাল Ollama HTTP API ব্যবহার করে অফলাইনে সম্পূর্ণ ফ্রিতে অডিট সম্পন্ন করে।
    """
    file_content = markdown_path.read_text(encoding="utf-8", errors="ignore")
    prompt = f"{AUDIT_SYSTEM_PROMPT}\n\n---\n\nAUDIT DOCUMENT CONTENT:\n\n{file_content}"

    url = "http://localhost:11434/api/generate"
    payload = json.dumps({"model": model_name, "prompt": prompt, "stream": False}).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("response", "No response received from Ollama.")
    except Exception as exc:
        return f"Ollama execution error: {exc}. Ensure Ollama is running (`ollama serve`)."

def audit_file_with_gemini_api(markdown_path: Path, api_key: str) -> str:
    """
    Executes audit using free-tier Gemini API (HTTP REST).
    বাংলা মন্তব্য: ফ্রি Gemini API ব্যবহার করে খুব দ্রুত অডিট সম্পূর্ণ করে।
    """
    file_content = markdown_path.read_text(encoding="utf-8", errors="ignore")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": AUDIT_SYSTEM_PROMPT},
                {"text": f"Document File: {markdown_path.name}\n\n{file_content}"}
            ]
        }]
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                return candidates[0]["content"]["parts"][0]["text"]
            return "No response text generated by Gemini API."
    except Exception as exc:
        return f"Gemini API execution error: {exc}"

def run_local_audit(target_part: str = "PART_03_MULTI_DB_OUTBOX.md", provider: str = "ollama", model: str = "llama3.2") -> None:
    """
    Reads markdown file and runs local LLM audit.
    বাংলা মন্তব্য: অডিট ফাইলটি লোকাল ডিভাইস থেকে পেস্ট না করে স্ক্রিপ্টের মাধ্যমে অটো রান করায়।
    """
    audit_dir = Path("docs/01-admin-plans/modular_audits").resolve()
    target_file = audit_dir / target_part

    if not target_file.exists():
        print(f"Error: Target audit file {target_file} does not exist.")
        return

    print(f"🚀 Running Local AI Audit on: {target_file.name} (Provider: {provider}, Model: {model})...")

    if provider.lower() == "ollama":
        result = audit_file_with_ollama(target_file, model_name=model)
    elif provider.lower() == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            print("Error: GEMINI_API_KEY environment variable not set.")
            return
        result = audit_file_with_gemini_api(target_file, api_key=api_key)
    else:
        print(f"Unknown provider: {provider}")
        return

    report_path = audit_dir / f"REPORT_{target_file.stem}.md"
    report_path.write_text(result, encoding="utf-8")
    print(f"✅ Local Audit Completed! Saved findings report to: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SupremeAI Local AI Audit Runner")
    parser.add_argument("--file", default="PART_03_MULTI_DB_OUTBOX.md", help="Audit markdown file name in modular_audits/")
    parser.add_argument("--provider", default="ollama", choices=["ollama", "gemini"], help="AI Provider")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name")
    args = parser.parse_args()

    run_local_audit(target_part=args.file, provider=args.provider, model=args.model)
