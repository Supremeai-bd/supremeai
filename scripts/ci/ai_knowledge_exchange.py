#!/usr/bin/env python3
"""Cross-AI Collective Knowledge Exchange Hub for SupremeAI GitHub Pipeline.

বাংলা মন্তব্য:
বিভিন্ন AI এজেন্ট (Arena, Claude, Copilot, Gemini, Kilo, Cursor, Codex ইত্যাদি) যেন
গিটহাব পাইপলাইনের মাধ্যমে নিজেদের অর্জিত আর্কিটেকচারাল নলেজ, রুট-কজ ও সতর্কতা (pitfalls)
পূর্বে Supabase-এ সরাসরি পাঠানো হতো। স্বতন্ত্র review ও provenance যাচাই
প্রতিষ্ঠিত না হওয়া পর্যন্ত live writes এবং unreviewed briefing নিষ্ক্রিয়।
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SHARE_MARKER_OPEN = "<!-- ai-knowledge-share v1 -->"
SHARE_MARKER_CLOSE = "<!-- /ai-knowledge-share -->"
DEFAULT_REPO = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai"

_UNSAFE_PAYLOAD_RE = re.compile(
    r"(?:"
    r"sk-[A-Za-z0-9_\-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sb_secret_[A-Za-z0-9_\-]{12,}"
    r"|eyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{15,}"
    r"|AIza[0-9A-Za-z_\-]{25,}"
    r"|xox[baprs]-[A-Za-z0-9\-]{15,}"
    r"|\b(?:password|passwd|api_key|secret_key|access_token|private_key)\s*[:=]"
    r"|\.onion(?:/|:|\b)"
    r"|ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions"
    r"|disregard\s+system\s+prompt"
    r"|<script\b"
    r")",
    re.IGNORECASE,
)


def is_clean_knowledge_payload(text: str) -> bool:
    """বাংলা মন্তব্য: বাহ্যিক AI এজেন্টের পাঠানো নলেজে কোনো সিক্রেট, `.onion` বা প্রম্পট ইনজেকশন আছে কি না যাচাই।"""
    cleaned = (text or "").strip()
    if not cleaned or len(cleaned) > 16000:
        return False
    return _UNSAFE_PAYLOAD_RE.search(cleaned) is None


def _slug(raw: str, fallback: str = "general") -> str:
    tokens = re.findall(r"[a-z0-9]+", (raw or "").lower())
    return "-".join(tokens)[:48] if tokens else fallback


def normalize_share_packet(raw: dict[str, Any], default_source: str = "github-pipeline") -> dict[str, Any] | None:
    """Normalize untrusted AI packets; this is not provenance or review verification."""
    if not isinstance(raw, dict):
        return None
    serialized = json.dumps(raw, ensure_ascii=False)
    if not is_clean_knowledge_payload(serialized):
        print("::warning::Rejected AI knowledge packet due to security/secret/injection guard.", file=sys.stderr)
        return None

    agent_name = str(raw.get("agent_name") or raw.get("agent") or raw.get("author") or "external-ai").strip()[:64]
    domain = _slug(str(raw.get("domain") or raw.get("role") or "architecture"), fallback="architecture")
    topic = str(raw.get("topic") or raw.get("title") or "").strip()[:180]
    insight = str(
        raw.get("insight")
        or raw.get("summary")
        or raw.get("lesson")
        or raw.get("why_this_way")
        or ""
    ).strip()[:2400]
    if len(insight) < 10:
        return None
    if not topic:
        topic = insight[:96]

    raw_pitfalls = raw.get("pitfalls") or raw.get("pitfalls_to_avoid") or []
    if isinstance(raw_pitfalls, str):
        pitfalls = [raw_pitfalls.strip()[:400]] if raw_pitfalls.strip() else []
    elif isinstance(raw_pitfalls, list):
        pitfalls = [str(p).strip()[:400] for p in raw_pitfalls if str(p).strip()][:8]
    else:
        pitfalls = []

    raw_files = raw.get("touched_files") or raw.get("files") or []
    if isinstance(raw_files, str):
        touched_files = [f.strip() for f in raw_files.split(",") if f.strip()][:25]
    elif isinstance(raw_files, list):
        touched_files = [str(f).strip() for f in raw_files if str(f).strip()][:25]
    else:
        touched_files = []

    reusable_pattern = str(raw.get("reusable_pattern") or raw.get("fix_mechanism") or "").strip()[:800]
    source_ref = str(raw.get("source") or default_source).strip()[:120]
    try:
        confidence = max(0.5, min(1.0, float(raw.get("confidence", 0.92))))
    except (TypeError, ValueError):
        confidence = 0.92

    content_hash = hashlib.sha256(f"{agent_name}|{domain}|{topic}|{insight}".encode("utf-8")).hexdigest()[:24]
    knowledge_key = f"ai-share-{_slug(agent_name, 'ai')}-{content_hash[:12]}"

    return {
        "knowledge_key": knowledge_key,
        "content_hash": content_hash,
        "agent_name": agent_name,
        "domain": domain,
        "topic": topic,
        "insight": insight,
        "pitfalls": pitfalls,
        "reusable_pattern": reusable_pattern,
        "touched_files": touched_files,
        "source": source_ref,
        "confidence": round(confidence, 3),
    }


def extract_ai_share_packets_from_text(body: str, default_source: str = "github-comment") -> list[dict[str, Any]]:
    """বাংলা মন্তব্য: PR বা Issue কমেন্ট থেকে একাধিক `<!-- ai-knowledge-share v1 -->` ব্লক পার্স করে।"""
    if not body or SHARE_MARKER_OPEN not in body:
        return []
    packets: list[dict[str, Any]] = []
    cursor = 0
    while True:
        start_idx = body.find(SHARE_MARKER_OPEN, cursor)
        if start_idx < 0:
            break
        json_start = start_idx + len(SHARE_MARKER_OPEN)
        end_idx = body.find(SHARE_MARKER_CLOSE, json_start)
        if end_idx < 0:
            break
        cursor = end_idx + len(SHARE_MARKER_CLOSE)
        snippet = body[json_start:end_idx].strip()
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError as err:
            print(f"::warning::Invalid ai-knowledge-share JSON block ({err})", file=sys.stderr)
            continue
        normalized = normalize_share_packet(parsed, default_source=default_source)
        if normalized is not None:
            packets.append(normalized)
    return packets


def _http_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: Any = None,
    timeout: float = 15.0,
) -> Any:
    """বাংলা মন্তব্য: একক কেন্দ্রীয় HTTP JSON ক্লায়েন্ট (GitHub ও Supabase উভয় কলের জন্য)।"""
    req_headers = dict(headers or {})
    body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    if body_bytes is not None and "Content-Type" not in req_headers:
        req_headers["Content-Type"] = "application/json"
    req_obj = urllib.request.Request(url=url, data=body_bytes, headers=req_headers, method=method)
    with urllib.request.urlopen(req_obj, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw.strip() else None


def _gh_api_get(endpoint: str) -> Any:
    """বাংলা মন্তব্য: মেয়াদোত্তীর্ণ `GH_TOKEN` ব্যর্থ হলে `GH_FALLBACK_TOKEN`/`GITHUB_TOKEN` দিয়ে GitHub API কল করে।"""
    tokens: list[str] = []
    for key_name in ("GH_TOKEN", "GH_FALLBACK_TOKEN", "GITHUB_TOKEN"):
        val = (os.environ.get(key_name) or "").strip()
        if val and val not in tokens:
            tokens.append(val)
    if not tokens:
        tokens = [""]

    api_url = f"https://api.github.com/{endpoint.lstrip('/')}"
    for idx, tok in enumerate(tokens):
        hdrs = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if tok:
            hdrs["Authorization"] = f"Bearer {tok}"
        try:
            return _http_json(api_url, method="GET", headers=hdrs, timeout=20.0)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403) and (idx + 1) < len(tokens):
                continue
            raise
    return None


def persist_shared_packet(packet: dict[str, Any], dry_run: bool = False) -> bool:
    """Legacy free-text records have no verified provenance or review.

    Do not write or print their contents. A dry run validates only and must not
    be mistaken for storage, independent review, or a quarantine inbox.
    """
    if not dry_run:
        print("::error::Legacy knowledge writes are disabled pending independent review and provenance.", file=sys.stderr)
        return False
    try:
        valid = isinstance(packet, dict) and normalize_share_packet(packet) is not None
    except (TypeError, ValueError, RecursionError):
        valid = False
    if not valid:
        print("::error::Invalid legacy knowledge packet; nothing stored.", file=sys.stderr)
        return False
    print("[ai-knowledge-exchange] Validation only; nothing was stored or approved.")
    return True


def scan_issue_or_pr_shared_notes(repo: str, issue_number: int, dry_run: bool = False) -> int:
    """Legacy scan is validation-only; incomplete reads must not appear successful."""
    if not dry_run:
        raise RuntimeError("Legacy knowledge writes are disabled; use a read-only candidate collector")
    if (issue_number <= 0 or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or any(part in (".", "..") for part in repo.split("/"))):
        raise ValueError("Invalid repository or issue number")
    try:
        issue_obj = _gh_api_get(f"repos/{repo}/issues/{issue_number}")
        comments = _gh_api_get(f"repos/{repo}/issues/{issue_number}/comments?per_page=100")
    except Exception as exc:
        raise RuntimeError("GitHub source unavailable; scan not completed") from exc
    if (not isinstance(issue_obj, dict) or issue_obj.get("number") != issue_number
            or not isinstance(comments, list) or len(comments) >= 100):
        raise RuntimeError("Invalid or incomplete source response; scan not completed")
    if any(not isinstance(c, dict) for c in comments):
        raise RuntimeError("Invalid source comment; scan not completed")
    documents = [issue_obj, *comments]
    count = 0
    for obj in documents:
        text = obj.get("body") or ""
        if not isinstance(text, str) or len(text.encode("utf-8")) > 256_000:
            raise RuntimeError("Invalid source document; scan not completed")
        packets = extract_ai_share_packets_from_text(text)
        if text.count(SHARE_MARKER_OPEN) != text.count(SHARE_MARKER_CLOSE) or text.count(SHARE_MARKER_OPEN) != len(packets):
            raise RuntimeError("Invalid share packet; scan not completed")
        for pkt in packets:
            if not persist_shared_packet(pkt, dry_run=True):
                raise RuntimeError("Validation failed")
            count += 1
    print(f"[ai-knowledge-exchange] Validation only; {count} packets, none stored or approved.")
    return count


def export_collective_briefing(limit: int = 15, output_path: str | None = None) -> dict[str, Any]:
    """Legacy active rows have no enforced independent review or privacy boundary."""
    raise RuntimeError("Unreviewed legacy briefing disabled; review provenance before use")


def format_briefing_markdown(briefing: dict[str, Any]) -> str:
    """বাংলা মন্তব্য: GitHub Actions `$GITHUB_STEP_SUMMARY`-এর জন্য পাঠযোগ্য মার্কডাউন সারাংশ তৈরি করে।"""
    lines = [
        "## 🧠 SupremeAI Cross-AI Collective Knowledge Briefing",
        f"- **Generated At:** `{briefing.get('generated_at')}`",
        f"- **Active Shared Entries:** `{briefing.get('count', 0)}`",
        "",
    ]
    for item in briefing.get("entries") or []:
        title = item.get("title") or item.get("knowledge_key")
        domain = item.get("domain") or "general"
        src = item.get("source") or "pipeline"
        know = item.get("knowledge") if isinstance(item.get("knowledge"), dict) else {}
        insight = (
            know.get("insight")
            or know.get("why_this_way")
            or know.get("fix_mechanism")
            or know.get("summary")
            or ""
        )
        lines.append(f"- **[{domain}] {title}** _(source: `{src}`)_ — {str(insight)[:220]}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SupremeAI Cross-AI Knowledge Exchange Hub")
    parser.add_argument("--share-json", type=str, default="", help="Direct JSON packet from an AI agent")
    parser.add_argument("--scan-issue", type=int, default=0, help="Issue or PR number to scan for ai-knowledge-share blocks")
    parser.add_argument("--repo", type=str, default=DEFAULT_REPO, help="GitHub owner/repo slug")
    parser.add_argument("--export-briefing", action="store_true", help="Export collective AI knowledge briefing")
    parser.add_argument("--output", type=str, default="", help="Optional path to save exported JSON briefing")
    parser.add_argument("--summary-md", action="store_true", help="Print Markdown briefing to stdout")
    parser.add_argument("--limit", type=int, default=15, help="Max entries to export")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to Supabase")
    args = parser.parse_args(argv)

    acted = False
    if args.share_json.strip():
        acted = True
        try:
            raw_pkt = json.loads(args.share_json)
        except json.JSONDecodeError as err:
            print(f"::error::Invalid --share-json payload: {err}", file=sys.stderr)
            return 2
        pkt = normalize_share_packet(raw_pkt, default_source="workflow_dispatch")
        if pkt is None:
            print("::error::AI knowledge packet failed schema or security validation.", file=sys.stderr)
            return 2
        if not persist_shared_packet(pkt, dry_run=args.dry_run):
            return 1
        print("[ai-knowledge-exchange] Validation complete; no knowledge was stored or approved.")

    if args.scan_issue > 0:
        acted = True
        try:
            scan_issue_or_pr_shared_notes(args.repo, args.scan_issue, dry_run=args.dry_run)
        except (ValueError, RuntimeError) as err:
            print(f"::error::{err}", file=sys.stderr)
            return 1

    if args.export_briefing or args.summary_md:
        acted = True
        try:
            briefing = export_collective_briefing(limit=args.limit, output_path=args.output or None)
        except RuntimeError as err:
            print(f"::error::{err}", file=sys.stderr)
            return 1
        if args.summary_md:
            print(format_briefing_markdown(briefing))
        elif not args.output:
            print(json.dumps(briefing, ensure_ascii=False, indent=2))

    if not acted:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
