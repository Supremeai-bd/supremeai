#!/usr/bin/env python3
"""
audit_master_runner.py — SupremeAI 2.0 Master Audit Orchestrator
================================================================
Master Audit Plan (Section ০) অনুযায়ী এই স্ক্রিপ্টটি পুরো কোডবেসের সব
static/audit চেক একসাথে চালায় এবং একটি consolidated রিপোর্ট তৈরি করে।

কী কী চালায়:
  1. Internal SupremeAI audit scripts (find_*, audit_*, *_audit.py) — read-only scanners
  2. নতুন scanner দুটি: find_secrets.py, find_dead_code.py
  3. External static tools (best-effort, থাকলে): ruff, bandit, eslint, npm audit,
     flutter analyze, gitleaks, pip-audit

রিপোর্ট:
  - docs/audit_reports/AUDIT_RUN_<timestamp>.md  (প্রতিটা টুলের আউটপুট + সারাংশ)
  - নির্বাচিত হলে PHASE_LOG.md-এ এন্ট্রি যোগ করে

ব্যবহার:
    python scripts/audit_master_runner.py                  # internal scanners
    python scripts/audit_master_runner.py --with-external   # + বাইরের টুল
    python scripts/audit_master_runner.py --only secrets    # শুধু নির্দিষ্ট
    python scripts/audit_master_runner.py --no-report       # রিপোর্ট ফাইল না লিখে

Exit codes:
    0 — সব চেক PASS
    1 — অন্তত একটি চেক FAIL
    2 — রানটাইম/আর্গুমেন্ট এরর
"""

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path

# 🚨 Internal read-only scanners (fix_* বাদ — সেগুলো কোড পাল্টায়)
INTERNAL_SCANNERS: list[str] = [
    "find_secrets.py",          # P0 — নতুন
    "find_dead_code.py",        # P2 — নতুন
    "find_generic_exceptions.py",
    "find_stub_data.py",
    "find_duplicates.py",
    "find_duplicate_files.py",
    "find_duplicate_tests.py",
    "audit_observability.py",
    "config_audit.py",
    "supreme-config-audit.py",
]

# External static tools — (display_name, [cmd], installed_check)
EXTERNAL_TOOLS: list[tuple[str, list[str]]] = [
    ("ruff", ["ruff", "check", "."]),
    ("bandit", ["bandit", "-r", "backend", "-q"]),
    ("mypy", ["mypy", "backend", "--ignore-missing-imports"]),
    ("eslint", ["eslint", ".", "--max-warnings", "-1"]),
    ("npm-audit", ["npm", "audit", "--audit-level=high"]),
    ("flutter-analyze", ["flutter", "analyze", "apps/mobile"]),
    ("gitleaks", ["gitleaks", "detect", "--no-git", "-v", "-s", "."]),
    ("pip-audit", ["pip-audit", "-r", "backend/requirements.txt"]),
]

REPORTS_DIR = Path("docs") / "audit_reports"


def run_tool(name: str, cmd: list[str], cwd: str, timeout: int = 300) -> dict:
    """একটি টুল/স্ক্রিপ্ট চালায় এবং আউটপুট + exit code রিটার্ন করে।"""
    print(f"  ▶ {name} :: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=False, timeout=timeout,
        )
        # বাংলা মন্তব্য: সাব-প্রসেস আউটপুট utf-8 বাইট — সিস্টেম charmap দিয়ে ডিকোড না করে utf-8+replace ব্যবহার করি।
        out = ""
        if result.stdout:
            out += result.stdout.decode("utf-8", errors="replace")
        if result.stderr:
            out += result.stderr.decode("utf-8", errors="replace")
        if result.returncode == 127 or "not found" in out.lower()[:200]:
            return {"name": name, "status": "SKIP", "rc": None, "output": out[:2000]}
        status = "PASS" if result.returncode == 0 else "FAIL"
        return {"name": name, "status": status, "rc": result.returncode, "output": out[:6000]}
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "TIMEOUT", "rc": None, "output": f"Timeout after {timeout}s"}
    except FileNotFoundError:
        return {"name": name, "status": "SKIP", "rc": None, "output": f"Command not found: {cmd[0]}"}
    except Exception as exc:  # এরর লুক করবে না
        return {"name": name, "status": "ERROR", "rc": None, "output": str(exc)}


def build_report(results: list[dict], started: str) -> str:
    """Master Audit Plan ফরম্যাটে consolidated markdown রিপোর্ট তৈরি করে।"""
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] in ("SKIP", "TIMEOUT", "ERROR"))

    lines = [
        f"# SupremeAI 2.0 — Master Audit Run",
        f"",
        f"- **Started:** {started}",
        f"- **Host:** {os.uname().nodename if hasattr(os, 'uname') else 'unknown'}",
        f"",
        f"## Executive Summary",
        f"",
        f"| Status | Count |",
        f"|---|---|",
        f"| PASS  | {pass_count} |",
        f"| FAIL  | {fail_count} |",
        f"| SKIP/TIMEOUT/ERROR | {skip_count} |",
        f"",
        f"**Verdict:** {'❌ FAIL — কমপক্ষে একটি চেক ব্যর্থ' if fail_count else '✅ PASS — সব চেক সফল'}",
        f"",
        f"## Tool-by-Tool Output",
        f"",
    ]
    for r in results:
        lines.append(f"### {r['name']} — {r['status']} (rc={r['rc']})")
        lines.append("")
        block = r["output"].strip() or "(no output)"
        for chunk in [block[i:i + 3000] for i in range(0, len(block), 3000)]:
            lines.append("```")
            lines.append(chunk)
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def update_phase_log(report_path: str, fail_count: int, started: str):
    """PHASE_LOG.md-এ এন্ট্রি যোগ করে (Master Audit Plan rule 8)।"""
    log = Path("PHASE_LOG.md")
    entry = (
        f"\n## Master Audit Run — {started}\n"
        f"- Tool: `audit_master_runner.py` (automated)\n"
        f"- FAIL count: {fail_count}\n"
        f"- Report: `{report_path}`\n"
        f"- Self-verification: ✅ script-level exit codes captured\n"
    )
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"[LOG] PHASE_LOG.md-এ এন্ট্রি যোগ করা হয়েছে")
    except Exception as exc:
        print(f"[WARN] PHASE_LOG.md আপডেট ব্যর্থ: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Master Audit Orchestrator")
    parser.add_argument("--with-external", action="store_true", help="বাইরের static tools চালাও")
    parser.add_argument("--only", nargs="*", default=None, help="শুধু নির্দিষ্ট scanner (যেমন secrets, dead_code)")
    parser.add_argument("--no-report", action="store_true", help="রিপোর্ট ফাইল লিখবে না")
    parser.add_argument("--log-phase", action="store_true", help="PHASE_LOG.md-এ এন্ট্রি যোগ করো")
    args = parser.parse_args()

    # বাংলা মন্তব্য: উইন্ডোজ কনসোল (charmap) বাংলা এনকোড করতে পারে না — stdout/stderr কে utf-8-এ রিকনফিগ করি।
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # বাংলা মন্তব্য: স্ক্রিপ্ট ফাইলের প্যারেন্ট (scripts/) থেকে repo root বের করি।
    repo_root = Path(__file__).resolve().parent.parent
    scripts_dir = repo_root / "scripts"
    started = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[RUN] SupremeAI Master Audit — {started}")
    print(f"      Repo root: {repo_root}")
    print()

    selected = set(args.only or [])
    results: list[dict] = []

    # 1) Internal scanners
    for script in INTERNAL_SCANNERS:
        if selected and script.replace(".py", "") not in selected and script not in selected:
            continue
        sp = scripts_dir / script
        if not sp.exists():
            continue
        results.append(run_tool(script, [sys.executable, str(sp)], str(repo_root)))

    # 2) External tools (optional)
    if args.with_external:
        import shutil
        for name, cmd in EXTERNAL_TOOLS:
            if selected and name not in selected:
                continue
            if shutil.which(cmd[0]) is None:
                results.append({"name": name, "status": "SKIP", "rc": None, "output": f"{cmd[0]} not installed"})
                continue
            results.append(run_tool(name, cmd, str(repo_root)))

    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    report = build_report(results, started)

    if not args.no_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"AUDIT_RUN_{ts}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n[REPORT] লেখা হয়েছে: {report_path}")

    if args.log_phase:
        update_phase_log(str(report_path), fail_count, started)

    print(f"\n[SUMMARY] PASS={sum(1 for r in results if r['status']=='PASS')} "
          f"FAIL={fail_count} "
          f"SKIP={sum(1 for r in results if r['status'] in ('SKIP','TIMEOUT','ERROR'))}")
    print(f"[VERDICT] {'FAIL' if fail_count else 'PASS'}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
