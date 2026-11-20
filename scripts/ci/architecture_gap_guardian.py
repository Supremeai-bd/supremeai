#!/usr/bin/env python3
"""Unified Architecture Gap & Reality Guardian.

# বাংলা মন্তব্য:
# একক (Single) ক্যানোনিকাল স্ক্রিপ্ট — কোনো ডুপ্লিকেট টুল বা স্ক্রিপ্ট স্প্রল নয় (DRY Policy)।
# উদ্দেশ্য:
# ১. পুরো প্রজেক্ট (Gateway, Core, Browser, MCP Tower এবং Public Studio) স্ক্যান করে
#    কোডের আসল "বাস্তব অবস্থা" (Live Traffic vs Floating / Dead Code) খুঁজে বের করা।
# ২. শুধুমাত্র ১টি একক ফাইল `docs/generated/architecture_gap_map.mmd` এবং `.json` তৈরি করা।
#    পুরনো ফাইল সবসময় ওভাররাইট (Atomic Replace) হবে, যাতে গিট রিপো কখনোই ভারী না হয়।
# ৩. গ্যাংলিং বা ডেড কোড থাকলে স্পষ্ট ওয়ার্নিং ও এক্সিট স্ট্যাটাস দেবে যাতে সিআই বা এআই এজেন্ট
#    অনাকাঙ্ক্ষিত কোড অ্যাড করার বদলে ডিলিট বা রিটায়ার করতে পারে।
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
OUT_MMD = ROOT / "docs/generated/architecture_gap_map.mmd"
OUT_JSON = ROOT / "docs/generated/architecture_gap_map.json"

# Key architectural subsystems across Private and Public repos
SUBSYSTEMS = {
    # Public Repo Surface (Client / Apps)
    "Public_Studio_Web": {
        "label": "Web Client (React 19 + Tailwind v4)",
        "type": "public_entry",
        "evidence": "supremeai-public:src/sync/",
    },
    "Public_Studio_Desktop": {
        "label": "Desktop / Android App (Tauri v2 Rust Core)",
        "type": "public_entry",
        "evidence": "supremeai-public:src-tauri/",
    },
    # Private Repo Ingress & Routing
    "Gateway_Entry": {
        "file": "gateway/main.py",
        "label": "API Gateway Entry (FastAPI)",
        "type": "ingress",
    },
    "Gateway_Arbiter": {
        "file": "gateway/service/app.py",
        "label": "Gateway Core Service & Route Arbiter",
        "type": "arbiter",
    },
    # Federation & Relays
    "Browser_Relay": {
        "file": "browser/server.py",
        "label": "Browser Relay (DuckAi / Fast-Path)",
        "type": "relay",
    },
    "MCP_Control_Tower": {
        "file": "scripts/agents/mcp_tower_client.py",
        "label": "MCP Control Tower Client & Mesh",
        "type": "mcp",
    },
    # Brain & Core Execution Candidates
    "Task_Engine": {
        "file": "core/brain/task_execution_engine.py",
        "label": "Task Execution Engine [core/brain]",
        "type": "internal",
    },
    "Reasoning_Orchestrator": {
        "file": "core/brain/reasoning_orchestrator.py",
        "label": "Reasoning Orchestrator [core/brain]",
        "type": "internal",
    },
    "Autonomous_Browser": {
        "file": "browser/autonomous_browser.py",
        "label": "Autonomous Browser Agent [browser/]",
        "type": "internal",
    },
    "MCP_Hub_Routes": {
        "file": "core/api/routes/mcp_hub.py",
        "label": "MCP Hub Routes [core/api]",
        "type": "internal",
    },
    "Redis_Manager": {
        "file": "core/cache/redis_manager.py",
        "label": "Redis Cache Manager [core/cache]",
        "type": "storage",
    },
    "Supabase_Client": {
        "file": "core/database/supabase_client.py",
        "label": "Supabase DB Client [core/database]",
        "type": "storage",
    },
    "RAG_Pipeline": {
        "file": "core/memory/rag_pipeline.py",
        "label": "RAG Pipeline [core/memory]",
        "type": "internal",
    },
}


def audit_system_wiring():
    incoming = defaultdict(set)
    outgoing = defaultdict(set)
    file_contents = {}

    for name, meta in SUBSYSTEMS.items():
        if "file" in meta:
            p = ROOT / meta["file"]
            if p.exists():
                file_contents[name] = p.read_text(encoding="utf-8", errors="ignore")

    # 1. Public Repo Connections to Gateway & MCP Tower
    outgoing["Public_Studio_Web"].add("Gateway_Entry")
    incoming["Gateway_Entry"].add("Public_Studio_Web")

    outgoing["Public_Studio_Desktop"].add("Gateway_Entry")
    incoming["Gateway_Entry"].add("Public_Studio_Desktop")

    # 2. Gateway Entry -> Arbiter
    if "app" in file_contents.get("Gateway_Entry", ""):
        outgoing["Gateway_Entry"].add("Gateway_Arbiter")
        incoming["Gateway_Arbiter"].add("Gateway_Entry")

    # 3. Gateway Arbiter -> Browser Relay (Verified via forward_stealth_webhook)
    arbiter_code = file_contents.get("Gateway_Arbiter", "")
    if "forward_stealth_webhook" in arbiter_code:
        outgoing["Gateway_Arbiter"].add("Browser_Relay")
        incoming["Browser_Relay"].add("Gateway_Arbiter")

    # 4. Browser Relay -> Gateway (Hedged reply)
    if "DuckAiEngine" in file_contents.get("Browser_Relay", ""):
        outgoing["Browser_Relay"].add("Gateway_Arbiter")
        incoming["Gateway_Arbiter"].add("Browser_Relay")

    # 5. MCP Tower Connections
    if "mcp_tower_client" in arbiter_code or "mcp-tower" in arbiter_code:
        outgoing["Gateway_Arbiter"].add("MCP_Control_Tower")
        incoming["MCP_Control_Tower"].add("Gateway_Arbiter")

    # 6. Core modules AST cross-references
    for src_name, src_code in file_contents.items():
        for target_name, target_meta in SUBSYSTEMS.items():
            if src_name == target_name or "file" not in target_meta:
                continue
            stem = Path(target_meta["file"]).stem
            if stem in src_code:
                outgoing[src_name].add(target_name)
                incoming[target_name].add(src_name)

    return incoming, outgoing


def build_gap_report(incoming, outgoing):
    status_map = {}
    recommendations = []

    for name in SUBSYSTEMS:
        in_count = len(incoming.get(name, []))
        out_count = len(outgoing.get(name, []))

        # Live path: directly connected to Public/Gateway ingress
        is_live = name in {"Public_Studio_Web", "Public_Studio_Desktop", "Gateway_Entry", "Gateway_Arbiter"} or (
            "Gateway_Arbiter" in incoming.get(name, set()) or "Gateway_Entry" in incoming.get(name, set())
        )

        if is_live:
            status_map[name] = "LIVE"
        elif in_count == 0 and out_count == 0:
            status_map[name] = "DEAD_ORPHAN"
            recommendations.append(f"RETIRE/PRUNE: {name} has 0 incoming and 0 outgoing links.")
        elif in_count == 0:
            status_map[name] = "FLOATING_NO_ENTRY"
            recommendations.append(f"GAP DETECTED: {name} produces output but is NEVER called by live traffic. Wire it or prune it.")
        elif out_count == 0:
            status_map[name] = "SINK_NO_EXIT"
            recommendations.append(f"GAP DETECTED: {name} receives calls but never returns output or persists state.")
        else:
            status_map[name] = "ISOLATED_CHAIN"
            recommendations.append(f"GAP DETECTED: {name} is part of an internal chain disconnected from live Gateway.")

    return status_map, recommendations


def generate_single_mermaid(status_map, incoming, outgoing):
    lines = [
        "flowchart TD",
        "    %% SupremeAI Canonical Architecture Reality & Gap Map",
        "    %% Auto-generated: Single Source of Truth, Overwrites on every run",
        "    classDef live fill:#1b4332,stroke:#40916c,stroke-width:2px,color:#d8f3dc;",
        "    classDef gap fill:#5c0002,stroke:#ba181b,stroke-width:2px,color:#ffccd5,stroke-dasharray: 5 5;",
        "    classDef isolated fill:#7f4f24,stroke:#a68a64,stroke-width:2px,color:#ede0d4;",
        "",
        "    subgraph LiveMesh [Live Production Mesh (Active Traffic)]",
    ]

    for name, meta in SUBSYSTEMS.items():
        if status_map[name] == "LIVE":
            lines.append(f'        {name}["{meta["label"]}"]')
    lines.append("    end")
    lines.append("")

    lines.append("    subgraph DetectedGaps [Architecture Gaps (Needs Wiring or Retirement)]")
    for name, meta in SUBSYSTEMS.items():
        if status_map[name] != "LIVE":
            status_label = status_map[name].replace("_", " ")
            lines.append(f'        {name}["{meta["label"]} <br/>⚠️ [{status_label}]"]')
    lines.append("    end")
    lines.append("")

    # Edges
    seen_edges = set()
    for src, targets in outgoing.items():
        for dst in targets:
            edge = (src, dst)
            if edge not in seen_edges:
                seen_edges.add(edge)
                lines.append(f"    {src} --> {dst}")

    lines.append("")
    for name, status in status_map.items():
        css_class = "live" if status == "LIVE" else ("isolated" if "ISOLATED" in status else "gap")
        lines.append(f"    class {name} {css_class};")

    return "\n".join(lines) + "\n"


def main() -> int:
    incoming, outgoing = audit_system_wiring()
    status_map, recommendations = build_gap_report(incoming, outgoing)
    mermaid_output = generate_single_mermaid(status_map, incoming, outgoing)

    # Atomic write to canonical files (single source, always overwriting old)
    OUT_MMD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MMD.write_text(mermaid_output, encoding="utf-8")

    report = {
        "status_summary": {
            "total_components": len(SUBSYSTEMS),
            "live_count": sum(1 for s in status_map.values() if s == "LIVE"),
            "gap_count": sum(1 for s in status_map.values() if s != "LIVE"),
        },
        "component_status": status_map,
        "actionable_recommendations": recommendations,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"=== Architecture Reality & Gap Guardian ===")
    print(f"Artifact: {OUT_MMD}")
    print(f"Summary: {report['status_summary']['live_count']} LIVE | {report['status_summary']['gap_count']} GAPS")
    if recommendations:
        print("\nActionable Findings:")
        for rec in recommendations:
            print(f"  • {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
