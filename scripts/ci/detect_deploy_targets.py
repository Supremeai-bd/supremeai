#!/usr/bin/env python3
"""Deploy-train changed-path detection (#2901).

প্রেক্ষাপট (#2901 ফরেনসিক অডিট): deploy-train.yml-এর service-selection
বাইনারি ছিল — core+worker প্রতি eligible push-এ অন্ধ redeploy হতো (ফ্রি-টিয়ার
৪৫০-মিনিট কোটার অপচয়), আর scraper/mcp/cloudflare কখনোই auto-deploy হতো না
(main.yml কলার কোনো input পাস করত না)। এই স্ক্রিপ্ট push-ইভেন্টে বদলানো
পাথ দেখে ঠিক কোন সার্ভিস deploy দরকার তা সিদ্ধান্ত করে।

ম্যাপিং চুক্তি (টেস্ট: tests/test_detect_deploy_targets_2901.py):
  backend/**                → core + worker (mcp_adapters/** ও mcp.json → +mcp)
  infrastructure/**         → cloudflare worker
  frontend/, client/, apps/ → শূন্য Render deploy (frontend আলাদা প্ল্যাটফর্ম)
  docs/, tests/, qa/, scripts/, .github/, data/, reports/, knowledge/,
  archives/, config/, **.md, LICENSE → শূন্য deploy (নয়েজ)
  অজানা পাথ                 → conservative fail-open: core + worker
                              (স্টেল প্রোডের ঝুঁকি অপচয়ের চেয়ে বড়)

manual dispatch মোডে (--mode manual) সব সিদ্ধান্ত মানুষের স্পষ্ট input-এ —
ডিটেক্টর শুধু pass-through (মানুষ যা চান তা-ই আইন)।

GITHUB_OUTPUT চুক্তি:
  deploy-core / deploy-worker / deploy-scraper / deploy-mcp /
  deploy-cloudflare = true|false, deploy-needed = true|false,
  summary = মানুষ-পাঠযোগ্য এক-লাইন
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── ম্যাপিং টেবিল (SSOT — workflow এই স্ক্রিপ্টের সিদ্ধান্তই মানে) ─────────────
NOISE_PREFIXES = (
    "docs/",
    "tests/",
    "qa/",
    "scripts/",
    ".github/",
    "data/",
    "reports/",
    "knowledge/",
    "archives/",
    "config/",
)
NOISE_EXACT = {"LICENSE", "CHANGELOG.md", "CODEOWNERS"}
FRONTEND_PREFIXES = ("frontend/", "client/", "apps/")
BACKEND_PREFIX = "backend/"
MCP_PREFIX = "backend/mcp_adapters/"
MCP_FILES = {"mcp.json"}
INFRA_PREFIX = "infrastructure/"
# ভেতরের চুক্তি underscore (Python-বান্ধব); GITHUB_OUTPUT-এ emit-এর সময়
# hyphen-এ রূপান্তর হয় (workflow outputs-এর নামকরণ deploy-core ইত্যাদি)।
SERVICE_KEYS = (
    "deploy_core",
    "deploy_worker",
    "deploy_scraper",
    "deploy_mcp",
    "deploy_cloudflare",
)


def _gha_key(key: str) -> str:
    return key.replace("_", "-")


def _norm(path: str) -> str:
    # lstrip("./") নয় — সেটি '.' ও '/' দুটোই বামদিক থেকে খেয়ে ফেলে
    # (.github/ → github/ হয়ে নয়েজ-মিস); removeprefix-ই সঠিক।
    return str(path).strip().replace("\\", "/").removeprefix("./")


def classify_paths(paths: list[str]) -> dict:
    """Pure ম্যাপিং — পরিবর্তিত পাথ তালিকা → প্রতি-সার্ভিস deploy সিদ্ধান্ত।"""
    result: dict = {
        "deploy_core": False,
        "deploy_worker": False,
        "deploy_scraper": False,  # scraper কোড backend-গাছেই — পাথ-বিয়োজন অসম্ভব;
        "deploy_mcp": False,      # তাই scraper সবসময় explicit/manual
        "deploy_cloudflare": False,
        "backend_files": 0,
        "infra_files": 0,
        "frontend_files": 0,
        "noise_files": 0,
        "unknown_files": 0,
        "unknown_examples": [],
        "total": 0,
    }
    for raw in paths:
        p = _norm(raw)
        if not p:
            continue
        result["total"] += 1
        name = p.rsplit("/", 1)[-1]
        if p in NOISE_EXACT or name in NOISE_EXACT or p.endswith(".md") or p.startswith(NOISE_PREFIXES):
            result["noise_files"] += 1
        elif p.startswith(MCP_PREFIX) or p in MCP_FILES:
            result["backend_files"] += 1
            result["deploy_core"] = True
            result["deploy_worker"] = True
            result["deploy_mcp"] = True
        elif p.startswith(BACKEND_PREFIX):
            result["backend_files"] += 1
            result["deploy_core"] = True
            result["deploy_worker"] = True
        elif p.startswith(INFRA_PREFIX):
            result["infra_files"] += 1
            result["deploy_cloudflare"] = True
        elif p.startswith(FRONTEND_PREFIXES):
            result["frontend_files"] += 1
        else:
            # conservative fail-open: অজানা পাথ = ব্যাকএন্ড-ঝুঁকি ধরে নেওয়া
            result["unknown_files"] += 1
            if len(result["unknown_examples"]) < 5:
                result["unknown_examples"].append(p)
            result["deploy_core"] = True
            result["deploy_worker"] = True
    result["deploy_needed"] = any(result[k] for k in SERVICE_KEYS)
    return result


def changed_paths(base: str, head: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def emit_github_output(result: dict, manual_summary: str | None = None) -> None:
    dest = os.getenv("GITHUB_OUTPUT")
    if not dest:
        return
    with open(dest, "a", encoding="utf-8") as fh:
        for key in SERVICE_KEYS:
            fh.write(f"{_gha_key(key)}={'true' if result[key] else 'false'}\n")
        fh.write(f"deploy-needed={'true' if result['deploy_needed'] else 'false'}\n")
        fh.write(f"summary={manual_summary or _summary_line(result)}\n")


def _summary_line(result: dict) -> str:
    on = [k.removeprefix("deploy_") for k in SERVICE_KEYS if result[k]]
    targets = ", ".join(on) if on else "শূন্য (deploy স্কিপ — কোটা সাশ্রয়)"
    return (
        f"targets=[{targets}] "
        f"backend={result['backend_files']} infra={result['infra_files']} "
        f"frontend={result['frontend_files']} noise={result['noise_files']} "
        f"unknown={result['unknown_files']}/{result['total']}"
    )


def write_step_summary(result: dict, manual_summary: str | None = None) -> None:
    dest = os.getenv("GITHUB_STEP_SUMMARY")
    if not dest:
        return
    lines = [
        "### 🔬 Deploy-target detection (#2901)",
        "",
        f"- **decision:** {manual_summary or _summary_line(result)}",
    ]
    if result.get("unknown_examples"):
        lines.append(f"- **unknown paths (fail-open → core+worker):** {result['unknown_examples']}")
    with open(dest, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="#2901 deploy-target detection")
    ap.add_argument("--base", help="git diff base sha/ref (push mode)")
    ap.add_argument("--head", default="HEAD", help="git diff head sha/ref")
    ap.add_argument("--paths-file", help="নিজস্ব পাথ-তালিকা ফাইল (প্রতি লাইনে একটি)")
    ap.add_argument(
        "--mode",
        choices=("push", "manual"),
        default="push",
        help="push=diff-ভিত্তিক ডিটেকশন; manual=মানুষের input pass-through",
    )
    ap.add_argument("--scraper", choices=("true", "false"), default="false")
    ap.add_argument("--mcp", choices=("true", "false"), default="false")
    ap.add_argument("--cloudflare", choices=("true", "false"), default="false")
    args = ap.parse_args()

    if args.mode == "manual":
        # manual dispatch = স্পষ্ট মানুষের অভিপ্রায়: core+worker সবসময়,
        # বাকিগুলো resolve-হওয়া input অনুযায়ী। কোনো diff-বিশ্লেষণ নেই।
        result: dict = {k: False for k in SERVICE_KEYS}
        result["deploy_core"] = True
        result["deploy_worker"] = True
        result["deploy_scraper"] = args.scraper == "true"
        result["deploy_mcp"] = args.mcp == "true"
        result["deploy_cloudflare"] = args.cloudflare == "true"
        result["deploy_needed"] = True
        result["total"] = 0
        summary = f"manual dispatch → core+worker, scraper={result['deploy_scraper']}, mcp={result['deploy_mcp']}, cloudflare={result['deploy_cloudflare']}"
        emit_github_output(result, summary)
        write_step_summary(result, summary)
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.paths_file:
        paths = [l for l in Path(args.paths_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    elif args.base:
        paths = changed_paths(args.base, args.head)
    else:
        # base নেই (যেমন নতুন ব্রাঞ্চে event.before = শূন্য-শা) → fail-open manual-সমতুল্য
        result = {k: False for k in SERVICE_KEYS}
        result["deploy_core"] = True
        result["deploy_worker"] = True
        result["deploy_needed"] = True
        result["total"] = 0
        summary = "no base sha (fresh push) → conservative core+worker"
        emit_github_output(result, summary)
        write_step_summary(result, summary)
        print(json.dumps(result, sort_keys=True))
        return 0

    result = classify_paths(paths)
    emit_github_output(result)
    write_step_summary(result)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
