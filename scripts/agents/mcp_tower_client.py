#!/usr/bin/env python3
"""MCP Tower Client — connects to SupremeAI Control Tower.

Auth (#2721 root-cause fix): the client reads MCP_API_KEY from env and injects
`Authorization: Bearer <key>` on every HTTP request via the requests.Session
headers. Without MCP_API_KEY, the client connects in viewer mode (read-only).
MCP_ADMIN_KEY (separate, for human admins) is not used by this client — agents
should never hold admin privileges (principle of least privilege, AGENTS.md Rule #10).

No credentials are stored in this file. Role can be elevated later from the
admin dashboard or database.

Usage:
    # Connect + register + heartbeat
    python scripts/agents/mcp_tower_client.py connect --name z.ai-1 --slot agent-3

    # One-shot heartbeat
    python scripts/agents/mcp_tower_client.py heartbeat --slot agent-3 --name z.ai-1

    # List all agents in the tower
    python scripts/agents/mcp_tower_client.py status

    # List available tools
    python scripts/agents/mcp_tower_client.py tools

    # Call any tool
    python scripts/agents/mcp_tower_client.py call system_summary

    # বাধ্যতামূলক বুটস্ট্র্যাপ হ্যান্ডশেক (issue #2399 §4):
    #   ১. Tower connect + heartbeat register (নাটাই টাওয়ারে)
    #   ২. Graph registry থেকে role/permission/boundary লোড
    #   ৩. Collective memory-তে অতীত সমাধান খোঁজা
    python scripts/agents/mcp_tower_client.py bootstrap \
        --name z.ai-1 --slot agent-3 --node node.mcp-tower-client --task 2399

    # লোকাল গ্রাফ রেজিস্ট্রি কোয়েরি (টাওয়ার ছাড়াই):
    python scripts/agents/mcp_tower_client.py graph domain agent-center
    python scripts/agents/mcp_tower_client.py graph node node.mcp-tower-client
    python scripts/agents/mcp_tower_client.py graph boundary arch-foundation

This file is committed to the repo (no secrets). Per-agent identity (name, slot)
is stored in a local gitignored file: .z-ai-config/agent-identity.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from queue import Empty, Queue
from typing import Any

import requests

# ── Configuration ────────────────────────────────────────────────────────────

# AUDIT-FIX (CI fixer): removed hardcoded deployment URL from default value.
# The URL must be set via MCP_TOWER_URL env var. AGENTS.md Rule #19 references
# the URL in documentation — the actual code reads it from env.
def resolve_mcp_server_url() -> str:
    """Resolve MCP Control Tower URL from env or workspace mcp.json."""
    url = os.environ.get("MCP_TOWER_URL", os.environ.get("MCP_SERVER_URL", ""))
    if url:
        return url.rstrip("/").removesuffix("/sse")
    mcp_file = Path(__file__).resolve().parents[2] / "mcp.json"
    if mcp_file.exists():
        try:
            with open(mcp_file, encoding="utf-8") as f:
                data = json.load(f)
                tower = data.get("mcpServers", {}).get("supremeai-control-tower", {})
                server_url = tower.get("url", "")
                if server_url:
                    return server_url.rstrip("/").removesuffix("/sse")
        except Exception:
            pass
    # AUDIT-FIX (#703 topology leak): no hardcoded deployment fallback. The
    # in-repo live config is mcp.json (baseline-sanctioned); when neither the
    # MCP_TOWER_URL/MCP_SERVER_URL env vars nor mcp.json provides a URL we
    # fail closed — McpTowerClient.connect() then raises a clear error instead
    # of silently dialing an internal hostname from source.
    return ""


MCP_SERVER_URL = resolve_mcp_server_url()
MCP_SSE_PATH = "/sse"
REQUEST_TIMEOUT = 30
SSE_READ_TIMEOUT = 600
RESPONSE_WAIT = 15
HEARTBEAT_INTERVAL = 45  # seconds

# Per-agent identity file (gitignored)
IDENTITY_FILE = Path(os.environ.get("AGENT_IDENTITY_FILE", ".z-ai-config/agent-identity.json"))

# ── Errors ───────────────────────────────────────────────────────────────────


class McpTowerError(Exception):
    pass


class McpTowerConnectionError(McpTowerError):
    pass


class McpTowerTimeoutError(McpTowerError):
    pass


# ── Ecosystem Graph Registry (issue #2399) ───────────────────────────────────
# বাংলা মন্তব্য: "সব কাজের MAP" — কে কার সাথে যুক্ত, কোন DB মডেল কোন domain-এ,
# কোন গ্রুপের বাউন্ডারি কোথায়। Bootstrap handshake এই রেজিস্ট্রি পড়ে এজেন্টকে
# তার role, boundary ও অতীত সমাধান জানিয়ে দেয় (kite & spool: এজেন্ট = ঘুড়ি,
# registry + tower = নাটাই)।
REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_REGISTRY_FILE = Path(
    os.environ.get("GRAPH_REGISTRY_FILE", str(REPO_ROOT / "docs/architecture/ECOSYSTEM_GRAPH_REGISTRY.yaml"))
)

# ৮টি গোল্ডেন প্রশ্নের key গুলো (registry-র eight_questions_spec এর সাথে মিলবে)
EIGHT_QUESTIONS_KEYS = (
    "identity",
    "responsibility",
    "upstream",
    "downstream",
    "side_effects",
    "verification",
    "blast_radius",
    "ultimate_value",
)

# Bootstrap bundle ফাইল — পরবর্তী টুল/CI step এজেন্টের handshake ফলাফল পড়তে পারবে
BOOTSTRAP_BUNDLE_FILE = Path(
    os.environ.get("AGENT_BOOTSTRAP_BUNDLE", ".z-ai-config/bootstrap-bundle.json")
)


class GraphRegistryError(McpTowerError):
    """Ecosystem graph registry লোড/ভ্যালিডেশন ব্যর্থতা।"""


def load_graph_registry(path: Path | None = None) -> dict[str, Any]:
    """ECOSYSTEM_GRAPH_REGISTRY.yaml লোড করে (একমাত্র সোর্স অফ ট্রুথ)।

    বাংলা মন্তব্য: রেজিস্ট্রি না থাকলে বা parse না হলে GraphRegistryError দেবে —
    চুপচাপ খালি গ্রাফ দেওয়া হবে না, কারণ ভুল বাউন্ডারি মানে এজেন্ট ভুল জায়গায়
    কাজ করা। fail-closed নীতি (#703 topology leak শিক্ষা)।
    """
    registry_path = path or GRAPH_REGISTRY_FILE
    if not registry_path.exists():
        raise GraphRegistryError(f"Graph registry not found: {registry_path}")
    try:
        import yaml
    except ImportError as err:
        raise GraphRegistryError(
            "PyYAML ইনস্টল নেই — registry পড়তে পারছি না (pip install pyyaml)"
        ) from err
    try:
        with open(registry_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as err:
        raise GraphRegistryError(f"Graph registry YAML parse error: {err}") from err
    if not isinstance(data, dict) or "domains" not in data or "nodes" not in data:
        raise GraphRegistryError(
            "Graph registry schema অসম্পূর্ণ — 'domains' ও 'nodes' অবশ্যই লাগবে"
        )
    return data


def find_registry_domain(registry: dict[str, Any], domain_id: str) -> dict[str, Any] | None:
    """domain id দিয়ে খোঁজা (না পেলে None)।"""
    for domain in registry.get("domains", []):
        if domain.get("id") == domain_id:
            return domain
    return None


def find_registry_node(registry: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """node id দিয়ে খোঁজা (না পেলে None)।"""
    for node in registry.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


def resolve_agent_context(
    registry: dict[str, Any],
    node_id: str | None = None,
    domain_id: str | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    """এজেন্টের graph context বানানো — node, domain, boundary, group।

    বাংলা মন্তব্য: এজেন্ট কে বলে পরিচিত হবে (node), কোন কেন্দ্রের নাগরিক (domain),
    কোথায় কাজ করতে পারবে (boundaries) এবং কোন গ্রুপের অধীনে (group)। এটিই
    bootstrap handshake-এর দ্বিতীয় ধাপ: "এজেন্ট তার রোল ও পারমিশন গ্রহণ করবে"।
    """
    context: dict[str, Any] = {
        "registry_schema_version": registry.get("schema_version", "unknown"),
        "node": None,
        "domain": None,
        "group": None,
    }

    if node_id:
        node = find_registry_node(registry, node_id)
        if node is None:
            known = ", ".join(n.get("id", "?") for n in registry.get("nodes", [])[:40])
            raise GraphRegistryError(
                f"গ্রাফ রেজিস্ট্রিতে node '{node_id}' নেই। বৈধ node উদাহরণ: {known}"
            )
        context["node"] = {
            "id": node.get("id"),
            "type": node.get("type"),
            "path": node.get("path"),
            "summary": node.get("summary"),
            "eight_questions": node.get("eight_questions", {}),
        }
        # node দেওয়া থাকলে domain সেখান থেকেই নেবে (এক সত্যের নীতি)
        if not domain_id:
            domain_id = node.get("domain")

    if domain_id:
        domain = find_registry_domain(registry, domain_id)
        if domain is None:
            known = ", ".join(d.get("id", "?") for d in registry.get("domains", []))
            raise GraphRegistryError(
                f"গ্রাফ রেজিস্ট্রিতে domain '{domain_id}' নেই। বৈধ domain: {known}"
            )
        context["domain"] = {
            "id": domain.get("id"),
            "name": domain.get("name"),
            "name_bn": domain.get("name_bn"),
            "mission": domain.get("mission"),
            "owning_paths": domain.get("owning_paths", []),
            "boundaries": domain.get("boundaries", {}),
            "eight_questions": domain.get("eight_questions", {}),
        }

    if group:
        found = None
        for boundary in registry.get("group_boundaries", []):
            if boundary.get("group") == group or boundary.get("label") == group:
                found = boundary
                break
        if found is None:
            known = ", ".join(b.get("group", "?") for b in registry.get("group_boundaries", []))
            raise GraphRegistryError(
                f"গ্রুপ '{group}' রেজিস্ট্রিতে নেই। বৈধ গ্রুপ: {known}"
            )
        context["group"] = {
            "group": found.get("group"),
            "label": found.get("label"),
            "issues": found.get("issues", []),
            "allowed_paths": found.get("allowed_paths", []),
            "notes": found.get("notes", ""),
        }

    return context


def search_collective_memory(query: str) -> dict[str, Any]:
    """Collective memory-তে অতীত সমাধান খোঁজা (Search Before Solving)।

    বাংলা মন্তব্য: bootstrap handshake-এর তৃতীয় ধাপ — "কালেক্টিভ মেমরি কুয়েরি
    করে আগের সমাধান জানবে"। sibling module agent_solution_memory থেকে local
    lessons + episodic memory দুই জায়গায়ই খোঁজে; DB না থাকলে lessons-only
    fallback (নীতি: মেমরি না থাকলেও handshake ব্যর্থ হবে না, শুধু খালি ফল)।
    """
    result: dict[str, Any] = {"query": query, "lessons": [], "episodes": [], "source": "none"}
    if not query or not query.strip():
        result["source"] = "skipped-empty-query"
        return result
    try:
        # sibling import — scripts/agents/ ফোল্ডারটাই path-এ যোগ করছি
        agents_dir = str(Path(__file__).resolve().parent)
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)
        import agent_solution_memory as memory_cli

        result["lessons"] = memory_cli.search_local_lessons(query)
        result["episodes"] = memory_cli.search_database_memory(query)
        result["source"] = "lessons+episodic" if (result["lessons"] or result["episodes"]) else "no-hits"
    except Exception as err:  # noqa: BLE001 — মেমরি ঐচ্ছিক, handshake থামবে না
        result["source"] = f"unavailable ({err.__class__.__name__})"
    return result


def _write_bootstrap_bundle(bundle: dict[str, Any]) -> Path:
    """Bootstrap ফলাফল JSON বান্ডেল হিসেবে সংরক্ষণ — পরের টুল এটি পড়বে।"""
    bundle_path = Path(os.environ.get("AGENT_BOOTSTRAP_BUNDLE", str(BOOTSTRAP_BUNDLE_FILE)))
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return bundle_path


def cmd_graph(args: argparse.Namespace) -> int:
    """লোকাল গ্রাফ রেজিস্ট্রি কোয়েরি — টাওয়ার সংযোগ ছাড়াই "সব কাজের MAP"।"""
    try:
        registry = load_graph_registry()
    except GraphRegistryError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    subject = args.subject
    if subject == "overview":
        domains = registry.get("domains", [])
        nodes = registry.get("nodes", [])
        core = registry.get("core_truths", [])
        db_map = registry.get("db_model_domain_map", {})
        print(f"SupremeAI Ecosystem Graph (schema {registry.get('schema_version', '?')})")
        print(f"  Core truths : {len(core)}")
        print(f"  Domains     : {len(domains)}")
        print(f"  Nodes       : {len(nodes)}")
        print(f"  Edges       : {len(registry.get('edges', []))}")
        print(f"  DB models   : {len(db_map)} mapped")
        print(f"  Groups      : {len(registry.get('group_boundaries', []))}")
        for d in domains:
            node_count = sum(1 for n in nodes if n.get("domain") == d.get("id"))
            db_count = sum(1 for v in db_map.values() if v == d.get("id"))
            print(f"    - {d.get('id'):<28} nodes={node_count:<3} db_models={db_count:<3} {d.get('name_bn', '')}")
        return 0

    if subject == "domain":
        domain = find_registry_domain(registry, args.value)
        if domain is None:
            print(f"ERROR: domain '{args.value}' নেই", file=sys.stderr)
            return 1
        print(json.dumps(domain, indent=2, ensure_ascii=False))
        return 0

    if subject == "node":
        node = find_registry_node(registry, args.value)
        if node is None:
            print(f"ERROR: node '{args.value}' নেই", file=sys.stderr)
            return 1
        print(json.dumps(node, indent=2, ensure_ascii=False))
        return 0

    if subject == "boundary":
        # গ্রুপ boundary — "গ্রুপ বাউন্ডারি ঠিক হবে" (issue #2399)
        if args.value:
            for boundary in registry.get("group_boundaries", []):
                if boundary.get("group") == args.value or boundary.get("label") == args.value:
                    print(json.dumps(boundary, indent=2, ensure_ascii=False))
                    return 0
            print(f"ERROR: group '{args.value}' নেই", file=sys.stderr)
            return 1
        print(json.dumps(registry.get("group_boundaries", []), indent=2, ensure_ascii=False))
        return 0

    if subject == "dbmodel":
        # DB schema → domain map: "DB schema সঠিক domain map করতে পারবে"
        db_map = registry.get("db_model_domain_map", {})
        if args.value:
            key = args.value if args.value in db_map else f"{args.value}.py"
            if key not in db_map:
                print(f"ERROR: db model '{args.value}' ম্যাপ করা নেই", file=sys.stderr)
                return 1
            print(json.dumps({"model": key, "domain": db_map[key]}, indent=2, ensure_ascii=False))
            return 0
        print(json.dumps(db_map, indent=2, ensure_ascii=False))
        return 0

    if subject == "edges":
        print(json.dumps(registry.get("edges", []), indent=2, ensure_ascii=False))
        return 0

    print(f"ERROR: অজানা subject '{subject}'", file=sys.stderr)
    return 2


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """বাধ্যতামূলক এজেন্ট বুটস্ট্র্যাপ হ্যান্ডশেক (issue #2399 §4 Kite & Spool)।

    তিনটি ধাপ:
      ১. Tower handshake — connect + agent_heartbeat register (নাটাই টাওয়ারে)
      ২. Graph registry — role, domain, boundaries লোড (কে আমি, কোথায় কাজ করব)
      ৩. Collective memory — অতীত সমাধান খোঁজা (Search Before Solving)

    নীতি: --strict হলে tower না পেলে ব্যর্থ (CI/উৎপাদন)। ডিফল্ট মোডে tower
    না থাকলে warn করে বাকি ধাপ চালিয়ে যায় (লোকাল ডেভ) — কিন্তু registry
    না পেলে সবসময় ব্যর্থ, কারণ বাউন্ডারি ছাড়া এজেন্ট অন্ধ।
    """
    name = resolve_name(args.name)
    identity = load_identity()
    slot = args.slot or identity.get("slot", "agent-3")
    # বাংলা মন্তব্য: bootstrap-নিজস্ব --server প্রাধান্য পাবে; না দিলে
    # top-level --server (যার ডিফল্ট env/mcp.json থেকে resolve হয়) ব্যবহার হবে।
    server_url = getattr(args, "server", None) or MCP_SERVER_URL

    bundle: dict[str, Any] = {
        "agent": {"name": name, "slot": slot},
        "handshake_version": "1.0",
        "issue": 2399,
        "tower": {"connected": False, "registered": False, "detail": ""},
        "graph": {},
        "memory": {},
    }

    # ── ধাপ ১: Tower handshake ──
    if args.offline:
        bundle["tower"]["detail"] = "offline mode (--offline) — tower step skipped"
        print("[bootstrap] ⚠️  offline মোড — tower handshake skip করা হলো")
    else:
        try:
            client = McpTowerClient(server_url=server_url, verbose=args.verbose)
            client.connect()
            bundle["tower"]["connected"] = True
            try:
                result = client.call_tool("agent_heartbeat", {"slot": slot, "agentId": name})
                text = (
                    result["content"][0]["text"]
                    if isinstance(result, dict) and "content" in result
                    else str(result)
                )
                bundle["tower"]["registered"] = True
                bundle["tower"]["detail"] = text[:400]
            except McpTowerError as err:
                bundle["tower"]["detail"] = f"heartbeat ব্যর্থ: {err}"
            finally:
                client.close()
            print(f"[bootstrap] ✅ Tower: connected + heartbeat (slot={slot}, name={name})")
        except (McpTowerError, requests.exceptions.RequestException, OSError) as err:
            # বাংলা মন্তব্য: DNS/connection failure requests.exceptions.RequestException দেয়,
            # MCP protocol error McpTowerError — দুটোই handshake ব্যর্থতা।
            # (লক্ষ্য: আগে ভুলবশত requests.RequestError লেখা ছিল — requests 2.32-তে
            # ওই attribute নেই, তাই connection error ধরার বদলে AttributeError হতো।)
            bundle["tower"]["detail"] = str(err)
            if args.strict:
                print(f"ERROR: --strict মোডে tower unreachable: {err}", file=sys.stderr)
                return 1
            print(f"[bootstrap] ⚠️  Tower unreachable (লোকাল ডেভ fallback): {err}")

    # ── ধাপ ২: Graph registry context ──
    try:
        registry = load_graph_registry()
        bundle["graph"] = resolve_agent_context(
            registry, node_id=args.node, domain_id=args.domain, group=args.group
        )
        print("[bootstrap] ✅ Graph registry: context লোড হয়েছে")
        domain_info = bundle["graph"].get("domain") or {}
        if domain_info:
            boundaries = domain_info.get("boundaries", {})
            print(f"           Domain : {domain_info.get('id')} ({domain_info.get('name_bn', '')})")
            for rule in boundaries.get("may_touch", [])[:5]:
                print(f"           may    : {rule}")
            for rule in boundaries.get("must_not_touch", [])[:5]:
                print(f"           mustNOT: {rule}")
        group_info = bundle["graph"].get("group") or {}
        if group_info:
            print(f"           Group  : {group_info.get('label')} (issues: {group_info.get('issues')})")
            for p in group_info.get("allowed_paths", [])[:8]:
                print(f"           scope  : {p}")
    except GraphRegistryError as err:
        # fail-closed: বাউন্ডারি ছাড়া এজেন্টকে কাজ করানো হবে না
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # ── ধাপ ৩: Collective memory search ──
    query = args.query or (f"issue {args.task}" if args.task else "")
    bundle["memory"] = search_collective_memory(query)
    hits = len(bundle["memory"].get("lessons", [])) + len(bundle["memory"].get("episodes", []))
    print(f"[bootstrap] ✅ Memory: {bundle['memory'].get('source')} ({hits} টি ম্যাচ)")

    # ── বান্ডেল সংরক্ষণ + সারসংক্ষেপ ──
    bundle_path = _write_bootstrap_bundle(bundle)
    if args.json:
        print(json.dumps(bundle, indent=2, ensure_ascii=False))
    else:
        print(f"[bootstrap] বান্ডেল সংরক্ষিত: {bundle_path}")
        print("[bootstrap] হ্যান্ডশেক সম্পন্ন — এখন অনুমোদিত বাউন্ডারির ভেতরে কাজ শুরু করো।")
    return 0



# ── Identity management ────────────────────────────────────────────────────


def load_identity() -> dict[str, str]:
    """Load agent identity from local gitignored file."""
    if IDENTITY_FILE.exists():
        with open(IDENTITY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_identity(identity: dict[str, str]) -> None:
    """Save agent identity to local gitignored file."""
    IDENTITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
        json.dump(identity, f, indent=2)
        f.write("\n")


def resolve_name(preferred: str | None = None) -> str:
    """Resolve agent name — use preferred, or from identity file, or generate."""
    identity = load_identity()
    if preferred:
        return preferred
    if identity.get("agent_name"):
        return identity["agent_name"]
    # Auto-generate based on environment
    env_type = os.environ.get("AGENT_TYPE", "z.ai")
    return f"{env_type}-1"


# ── MCP Tower SSE Client ────────────────────────────────────────────────────


class McpTowerClient:
    """Synchronous MCP client over SSE transport (no auth)."""

    def __init__(
        self,
        server_url: str = MCP_SERVER_URL,
        sse_path: str = MCP_SSE_PATH,
        verbose: bool = False,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.sse_path = sse_path if sse_path.startswith("/") else "/" + sse_path
        self.verbose = verbose
        self._session_id: str | None = None
        self._message_endpoint: str | None = None
        self._sse_thread: threading.Thread | None = None
        self._sse_stop = threading.Event()
        self._http = requests.Session()
        # ROOT-CAUSE FIX (#2721): inject MCP_API_KEY auth header on the session
        # so ALL HTTP requests (SSE connect, JSON-RPC POST, notifications)
        # carry `Authorization: Bearer <key>`. Previously the client sent 0 auth
        # headers — 112 MCP tools were publicly callable by any internet user.
        # Graceful: if MCP_API_KEY env var is unset, client still connects in
        # viewer mode (tower returns 401 only for privileged tools, not for
        # connect). This matches AGENTS.md Step 2 "graceful offline fallback".
        _api_key = os.environ.get("MCP_API_KEY", "")
        if _api_key:
            self._http.headers.update({"Authorization": f"Bearer {_api_key}"})
            self._log(f"Auth header injected (MCP_API_KEY len={len(_api_key)})")
        else:
            self._log("No MCP_API_KEY env var — connecting in viewer mode (read-only)")
        self._response_queues: dict[str, Queue] = {}
        self._response_lock = threading.Lock()
        self._initialized = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[mcp] {msg}", file=sys.stderr, flush=True)

    def connect(self) -> None:
        if self._initialized:
            return
        sse_url = self.server_url + self.sse_path
        self._log(f"Opening SSE: {sse_url}")
        resp = self._http.get(
            sse_url,
            stream=True,
            timeout=(REQUEST_TIMEOUT, SSE_READ_TIMEOUT),
            headers={"Accept": "text/event-stream"},
        )
        if resp.status_code != 200:
            raise McpTowerConnectionError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        self._sse_thread = threading.Thread(
            target=self._sse_reader, args=(resp,), daemon=True, name="mcp-sse"
        )
        self._sse_thread.start()
        deadline = time.time() + RESPONSE_WAIT
        while self._message_endpoint is None and time.time() < deadline:
            time.sleep(0.1)
        if self._message_endpoint is None:
            raise McpTowerConnectionError("No endpoint event received")
        self._log(f"Session: {self._session_id}")
        init = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "supremeai-agent", "version": "1.0.0"},
            },
        )
        self._log(f"Server: {init.get('serverInfo', {})}")
        self._send_notification("notifications/initialized", {})
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        return self._send_request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        return self._send_request("tools/call", {"name": name, "arguments": arguments or {}})

    def ping(self) -> bool:
        try:
            self._send_request("ping", {})
            return True
        except McpTowerError:
            return False

    def start_heartbeat(self, slot: str, agent_id: str) -> None:
        """Start background heartbeat loop (every 45s)."""
        def _loop():
            while not self._heartbeat_stop.is_set():
                try:
                    self.call_tool("agent_heartbeat", {"slot": slot, "agentId": agent_id})
                    self._log(f"heartbeat sent: {slot} / {agent_id}")
                except Exception as e:
                    self._log(f"heartbeat failed: {e}")
                self._heartbeat_stop.wait(HEARTBEAT_INTERVAL)

        self._heartbeat_thread = threading.Thread(
            target=_loop, daemon=True, name="mcp-heartbeat"
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()

    def close(self) -> None:
        self.stop_heartbeat()
        self._sse_stop.set()
        self._initialized = False
        try:
            self._http.close()
        except Exception:
            pass

    def __enter__(self) -> McpTowerClient:
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _sse_reader(self, resp: requests.Response) -> None:
        event_type = None
        data_lines: list[str] = []
        try:
            for raw in resp.iter_lines(decode_unicode=True):
                if self._sse_stop.is_set():
                    break
                if raw is None:
                    continue
                line = raw.rstrip("\r")
                if line == "":
                    if event_type and data_lines:
                        self._dispatch(event_type, "\n".join(data_lines))
                    event_type = None
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
        except Exception as e:
            if not self._sse_stop.is_set():
                self._log(f"SSE error: {e}")

    def _dispatch(self, event_type: str, data: str) -> None:
        if event_type == "endpoint":
            self._message_endpoint = self.server_url + data
            if "sessionId=" in data:
                self._session_id = data.split("sessionId=", 1)[1].split("&", 1)[0]
            self._log(f"endpoint: {self._message_endpoint}")
            return
        if event_type == "message":
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                return
            mid = payload.get("id")
            if mid is None:
                return
            with self._response_lock:
                q = self._response_queues.get(mid)
            if q:
                q.put(payload)

    def _send_request(self, method: str, params: dict[str, Any]) -> Any:
        if not self._message_endpoint:
            raise McpTowerConnectionError("Not connected")
        mid = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": mid, "method": method, "params": params}
        q: Queue = Queue()
        with self._response_lock:
            self._response_queues[mid] = q
        self._log(f"-> {method}")
        try:
            r = self._http.post(
                self._message_endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
            if r.status_code not in (200, 202):
                with self._response_lock:
                    self._response_queues.pop(mid, None)
                raise McpTowerConnectionError(f"HTTP {r.status_code}")
        # AUDIT-FIX (#2399 কাজের সময় ধরা পড়েছে): requests.RequestError বলে কোনো
        # attribute নেই (সঠিক base: requests.exceptions.RequestException) — আগে
        # POST-এর connection error এখানে ধরা না পড়ে AttributeError হয়ে যেত।
        except requests.exceptions.RequestException as e:
            with self._response_lock:
                self._response_queues.pop(mid, None)
            raise McpTowerConnectionError(str(e))
        try:
            rpc = q.get(timeout=RESPONSE_WAIT)
        except Empty:
            with self._response_lock:
                self._response_queues.pop(mid, None)
            raise McpTowerTimeoutError(f"Timeout: {method}")
        finally:
            with self._response_lock:
                self._response_queues.pop(mid, None)
        if "error" in rpc:
            err = rpc["error"]
            raise McpTowerError(f"RPC error {err.get('code')}: {err.get('message')}")
        return rpc.get("result")

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        if not self._message_endpoint:
            return
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        try:
            self._http.post(
                self._message_endpoint,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            pass


# ── CLI ──────────────────────────────────────────────────────────────────────


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="MCP Tower client — connect, heartbeat, bootstrap, graph queries (no auth)"
    )
    parser.add_argument("--server", default=MCP_SERVER_URL)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="Check server connectivity")
    sub.add_parser("status", help="List all agents in the tower")
    sub.add_parser("tools", help="List available tools")

    # ── লোকাল-অনলি কমান্ড (টাওয়ার সংযোগ লাগে না) — issue #2399 ──
    graph_p = sub.add_parser(
        "graph", help="Ecosystem graph registry query (local, no tower needed)"
    )
    graph_p.add_argument(
        "subject",
        choices=("overview", "domain", "node", "boundary", "dbmodel", "edges"),
        help="কী দেখতে চাও: overview / domain / node / boundary / dbmodel / edges",
    )
    graph_p.add_argument(
        "value", nargs="?", default=None,
        help="subject-এর id (যেমন agent-center, node.mcp-tower-client, arch-foundation)",
    )

    boot = sub.add_parser(
        "bootstrap",
        help="বাধ্যতামূলক এজেন্ট হ্যান্ডশেক: tower + graph registry + collective memory (#2399)",
    )
    boot.add_argument("--name", default=None, help="Agent name (default: identity file থেকে)")
    boot.add_argument("--slot", default=None, help="Agent slot (default: identity file থেকে)")
    boot.add_argument("--node", default=None, help="গ্রাফ node id (যেমন node.mcp-tower-client)")
    boot.add_argument("--domain", default=None, help="domain id (যেমন agent-center) — node দিলে লাগবে না")
    boot.add_argument("--group", default=None, help="গ্রুপ boundary id (যেমন arch-foundation)")
    boot.add_argument("--task", default=None, help="বর্তমান issue নম্বর — memory search এ ব্যবহৃত হবে")
    boot.add_argument("--query", default=None, help="memory search query (--task এর বিকল্প)")
    boot.add_argument("--offline", action="store_true", help="Tower ধাপ skip (শুধু registry+memory)")
    boot.add_argument("--strict", action="store_true", help="Tower unreachable হলে hard fail (CI/উৎপাদন)")
    boot.add_argument("--json", action="store_true", help="ফলাফল JSON-এ প্রিন্ট")
    # top-level --server ছাড়াও সরাসরি bootstrap-এর পরে দেওয়া যাবে (subcommand override)
    boot.add_argument("--server", default=None, help="Tower URL override (না দিলে top-level/env থেকে)")

    c = sub.add_parser("connect", help="Connect + register + start heartbeat")
    c.add_argument("--name", default=None, help="Agent name (default: from identity file)")
    c.add_argument("--slot", default=None, help="Agent slot (default: from identity file)")
    c.add_argument("--auto-register", action="store_true", default=False,
                   help="Auto-register: connect, send heartbeat, save identity, start loop (Rule #19)")

    hb = sub.add_parser("heartbeat", help="Send one heartbeat")
    hb.add_argument("--slot", required=True)
    hb.add_argument("--name", required=True)

    call_p = sub.add_parser("call", help="Call a tool")
    call_p.add_argument("tool_name")
    call_p.add_argument("arguments", nargs="?", default="{}")

    args = parser.parse_args()

    # বাংলা মন্তব্য: graph ও bootstrap নিজেদের connection নিজেরাই সামলায় —
    # (bootstrap ঐচ্ছিক tower fallback সহ, graph সম্পূর্ণ লোকাল) — তাই নিচের
    # সাধারণ connect পথে যাওয়ার আগেই dispatch করে দিচ্ছি।
    if args.cmd == "graph":
        return cmd_graph(args)
    if args.cmd == "bootstrap":
        return cmd_bootstrap(args)

    try:
        arguments = json.loads(args.arguments) if args.cmd == "call" else {}
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON arguments: {e}", file=sys.stderr)
        return 2

    client = McpTowerClient(server_url=args.server, verbose=args.verbose)
    try:
        client.connect()
    except McpTowerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    try:
        if args.cmd == "ping":
            ok = client.ping()
            print(json.dumps({"ok": ok}, indent=2))
            return 0 if ok else 1

        if args.cmd == "status":
            result = client.call_tool("agent_status", {})
            text = result["content"][0]["text"] if isinstance(result, dict) and "content" in result else str(result)
            try:
                data = json.loads(text)
                slots = data.get("slots", [])
                print(f"Agents in tower: {len(slots)}")
                for s in slots:
                    print(f"  {s.get('slot','?'):<15} state={s.get('state','?'):<10} agentId={s.get('agentId','?')}")
            except json.JSONDecodeError:
                print(text)
            return 0

        if args.cmd == "tools":
            tools = client.list_tools()
            print(f"Total tools: {len(tools)}")
            for t in tools:
                print(f"  {t.get('name','?'):<40} {(t.get('description') or '')[:60]}")
            return 0

        if args.cmd == "connect":
            name = resolve_name(args.name)
            identity = load_identity()
            slot = args.slot or identity.get("slot", "agent-3")

            # AUDIT-FIX (#2030): --auto-register sends initial heartbeat immediately
            # and saves the response (which may contain auto-incremented name from server)
            if args.auto_register:
                print("Auto-registering with MCP Tower (Rule #19)...")
                try:
                    result = client.call_tool("agent_heartbeat", {"slot": slot, "agentId": name})
                    text = result["content"][0]["text"] if isinstance(result, dict) and "content" in result else str(result)
                    # Parse response — server may return auto-incremented name
                    try:
                        hb_data = json.loads(text)
                        if hb_data.get("ok"):
                            print(f"✅ Registered: slot={slot}, name={name}")
                            print(f"   TTL: {hb_data.get('ttlSeconds', 300)}s")
                            print(f"   Redis: {hb_data.get('redisAccount', 'default')}")
                    except json.JSONDecodeError:
                        print(f"Heartbeat response: {text[:200]}")
                except McpTowerError as e:
                    print(f"⚠️ Heartbeat failed (server may not support new slot format yet): {e}")
                    print("   Server needs redeploy after PR merge. Continuing with heartbeat loop...")

            print(f"Connecting as: {name} (slot: {slot})")
            client.start_heartbeat(slot, name)
            save_identity({"agent_name": name, "slot": slot, "mcp_server": args.server})
            print(f"Identity saved to {IDENTITY_FILE}")
            print("Heartbeat running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping...")
            return 0

        if args.cmd == "heartbeat":
            result = client.call_tool("agent_heartbeat", {"slot": args.slot, "agentId": args.name})
            text = result["content"][0]["text"] if isinstance(result, dict) and "content" in result else str(result)
            print(text)
            return 0

        if args.cmd == "call":
            result = client.call_tool(args.tool_name, arguments)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

    except McpTowerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
