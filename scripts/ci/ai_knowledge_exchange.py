#!/usr/bin/env python3
"""Cross-AI Collective Knowledge Exchange Hub for SupremeAI GitHub Pipeline.

বাংলা মন্তব্য:
বিভিন্ন AI এজেন্ট (Arena, Claude, Copilot, Gemini, Kilo, Cursor, Codex ইত্যাদি) যেন
গিটহাব পাইপলাইনের মাধ্যমে নিজেদের অর্জিত আর্কিটেকচারাল নলেজ, রুট-কজ ও সতর্কতা (pitfalls)
SupremeAI-এর কেন্দ্রীয় ব্রেইনে (`Supabase knowledge_base` ও `learned_facts`) নিরাপদে শেয়ার
ও পুনঃব্যবহার করতে পারে, তার সম্পূর্ণ stdlib-only ও সিক্রেট-স্যানিটাইজড ইঞ্জিন।
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
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
    """বাংলা মন্তব্য: যেকোনো AI এজেন্টের পাঠানো JSON প্যাকেটকে ক্যানোনিকাল ভেরিফায়েড স্কিমায় রূপান্তর করে।"""
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
    """বাংলা মন্তব্য: ভেরিফায়েড AI নলেজ প্যাকেট idempotent উপায়ে Supabase `knowledge_base` ও `learned_facts`-এ সংরক্ষণ করে।"""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    kb_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"supremeai:kb:{packet['knowledge_key']}"))
    fact_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"supremeai:fact:{packet['knowledge_key']}"))

    kb_content_obj = {
        "agent_name": packet["agent_name"],
        "topic": packet["topic"],
        "insight": packet["insight"],
        "pitfalls_to_avoid": packet["pitfalls"],
        "reusable_pattern": packet["reusable_pattern"],
        "touched_files": packet["touched_files"],
    }
    kb_record = {
        "id": kb_uuid,
        "knowledge_key": packet["knowledge_key"],
        "title": f"[{packet['agent_name']}] {packet['topic']}"[:200],
        "domain": packet["domain"],
        "namespace": "cross-ai-exchange",
        "content": json.dumps(kb_content_obj, ensure_ascii=False, indent=2),
        "content_hash": packet["content_hash"],
        "source": packet["source"],
        "confidence": packet["confidence"],
        "risk_level": "low",
        "status": "active",
        "metadata": {
            "agent_name": packet["agent_name"],
            "touched_files": packet["touched_files"],
            "pitfalls_count": len(packet["pitfalls"]),
            "ingested_at": now_iso,
            "schema": "ai-knowledge-share/1",
        },
        "updated_at": now_iso,
    }

    fact_record = {
        "id": fact_uuid,
        "content": {
            "text": f"[{packet['agent_name']} · {packet['domain']}] {packet['topic']}: {packet['insight']}",
            "agent_name": packet["agent_name"],
            "domain": packet["domain"],
            "pitfalls": packet["pitfalls"],
            "reusable_pattern": packet["reusable_pattern"],
            "source": packet["source"],
        },
        "tags": [
            "cross_ai_share",
            packet["domain"],
            _slug(packet["agent_name"], "ai"),
        ],
        "created_at": now_iso,
    }

    if dry_run:
        print(json.dumps({"kb_record": kb_record, "fact_record": fact_record}, ensure_ascii=False, indent=2))
        return True

    sb_url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    sb_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not sb_url or not sb_key:
        print("::notice::SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not configured; validated packet in dry-mode.")
        return True

    sb_headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    ok = True
    for tbl, row_payload in (("knowledge_base", kb_record), ("learned_facts", fact_record)):
        try:
            _http_json(
                f"{sb_url}/rest/v1/{tbl}?on_conflict=id",
                method="POST",
                headers=sb_headers,
                payload=row_payload,
                timeout=12.0,
            )
        except Exception as err:
            print(f"::warning::Supabase upsert to {tbl} failed: {err}", file=sys.stderr)
            ok = False
    return ok


def scan_issue_or_pr_shared_notes(repo: str, issue_number: int, dry_run: bool = False) -> int:
    """বাংলা মন্তব্য: কোনো গিটহাব ইস্যু বা PR থ্রেডের কমেন্টগুলো স্ক্যান করে সব AI এজেন্টের শেয়ার করা নলেজ ইনজেস্ট করে।"""
    if issue_number <= 0:
        return 0
    ingested = 0
    try:
        issue_obj = _gh_api_get(f"repos/{repo}/issues/{issue_number}") or {}
        comments = _gh_api_get(f"repos/{repo}/issues/{issue_number}/comments?per_page=100") or []
    except Exception as err:
        print(f"::warning::Could not read issue/PR #{issue_number} comments: {err}", file=sys.stderr)
        return 0

    candidates: list[tuple[str, str]] = []
    if isinstance(issue_obj, dict) and issue_obj.get("body"):
        author = ((issue_obj.get("user") or {}).get("login")) or "github-agent"
        candidates.append((str(issue_obj["body"]), f"{repo}#{issue_number} ({author})"))
    if isinstance(comments, list):
        for idx, c in enumerate(comments):
            if isinstance(c, dict) and c.get("body"):
                c_author = ((c.get("user") or {}).get("login")) or "github-agent"
                candidates.append((str(c["body"]), f"{repo}#{issue_number}:comment-{idx + 1} ({c_author})"))

    for text_body, src_label in candidates:
        for pkt in extract_ai_share_packets_from_text(text_body, default_source=src_label):
            if persist_shared_packet(pkt, dry_run=dry_run):
                ingested += 1
    print(f"[ai-knowledge-exchange] Processed {repo}#{issue_number}: ingested={ingested}")
    return ingested


def export_collective_briefing(limit: int = 15, output_path: str | None = None) -> dict[str, Any]:
    """বাংলা মন্তব্য: Supabase থেকে সকল AI এজেন্টের শেয়ার করা সর্বশেষ ভেরিফায়েড নলেজ ব্রিফিং আকারে এক্সপোর্ট করে।"""
    sb_url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    sb_key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    entries: list[dict[str, Any]] = []
    if sb_url and sb_key:
        try:
            rows = _http_json(
                f"{sb_url}/rest/v1/knowledge_base"
                f"?status=eq.active&select=id,knowledge_key,title,domain,namespace,content,source,confidence,updated_at"
                f"&order=updated_at.desc&limit={max(1, min(limit, 50))}",
                method="GET",
                headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
                timeout=12.0,
            )
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    parsed_content: Any = row.get("content")
                    if isinstance(parsed_content, str):
                        try:
                            parsed_content = json.loads(parsed_content)
                        except json.JSONDecodeError:
                            parsed_content = {"summary": parsed_content}
                    entries.append(
                        {
                            "knowledge_key": row.get("knowledge_key"),
                            "title": row.get("title"),
                            "domain": row.get("domain"),
                            "namespace": row.get("namespace"),
                            "source": row.get("source"),
                            "confidence": row.get("confidence"),
                            "updated_at": row.get("updated_at"),
                            "knowledge": parsed_content,
                        }
                    )
        except Exception as err:
            print(f"::warning::Collective briefing read warning: {err}", file=sys.stderr)

    briefing = {
        "schema": "supremeai-collective-ai-briefing/1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(entries),
        "entries": entries,
    }
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(briefing, fh, ensure_ascii=False, indent=2)
    return briefing


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
        print(f"[ai-knowledge-exchange] Shared packet '{pkt['knowledge_key']}' accepted.")

    if args.scan_issue > 0:
        acted = True
        scan_issue_or_pr_shared_notes(args.repo, args.scan_issue, dry_run=args.dry_run)

    if args.export_briefing or args.summary_md:
        acted = True
        briefing = export_collective_briefing(limit=args.limit, output_path=args.output or None)
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
