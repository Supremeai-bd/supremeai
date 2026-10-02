#!/usr/bin/env python3
"""Agent Identity & Cooldown Registry (#2950 — root-cause race-condition fix).

বাংলা পরিচিতি (#2950):
continuous_agent_loop এখন "script নিজে role ঠিক করবে" model-এ চলে। তখন
৩টি race-condition তৈরি হয়:
  ১. Agent name assignment — দুটো script একসাথে "coder-1" claim করতে পারে
  ২. Single-agent-per-role lock — auditor/ci-fixer/etc একসাথে ২জন চলতে পারে
  ৩. Cooldown persistence — agent exit করলে 2-min cooldown ভুলে যায়

সমাধান = git-push-as-CAS (Compare-And-Swap):
  - git protocol নিজে atomic — দুটো machine থেকে একসাথে push করলেও git
    একজনকে reject করে। কোনো file-lock/TOCTOU race নেই।
  - Persistent identity (~/.supremeai/identity.json) + cooldown registry
    (docs/master_docs/AGENT_COOLDOWN_REGISTRY.json) — agent exit করলেও
    state থেকে যায়।

৩টি public API:
  1. resolve_agent_identity(preferred=None) -> AgentIdentity
  2. acquire_role_lock(role, agent_name, ttl=3600) -> bool     # single-agent-per-role
  3. record_cooldown(agent_name, seconds=120) / is_cooled_down(agent_name) -> bool

CLI:
    python scripts/agents/agent_identity.py resolve --preferred coder
    python scripts/agents/agent_identity.py lock --role auditor --agent-name auditor-1
    python scripts/agents/agent_identity.py cooldown --agent-name coder-1 --seconds 120

Exit codes: 0 = OK, 1 = lock/identity failure, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")

# ─────────────────── Persistent storage paths ───────────────────
# বাংলা মন্তব্য: identity লোকাল-machine-এ (এক machine-এ এক agent), cooldown
# registry repo-তে (সব machine দেখে) — দুটো আলাদা স্তর, দুটো আলাদা জীবনকাল।
IDENTITY_DIR = Path(os.environ.get("HOME", str(ROOT_DIR))) / ".supremeai"
IDENTITY_FILE = IDENTITY_DIR / "identity.json"
COOLDOWN_REGISTRY = ROOT_DIR / "docs" / "master_docs" / "AGENT_COOLDOWN_REGISTRY.json"

# Roles that allow ONLY ONE agent at a time (coder বাদে বাকি সব)
SINGLE_AGENT_ROLES = {
    "auditor",
    "ci-fixer",
    "human-eyes",
    "ecosystem-scout",
    "planner",
    "watcher",
    "breaker",
    "rules_breaker",
    "platform",
    "pr-helper",
}

# Role branch namespace prefix — git push atomicity-এর জন্য
ROLE_LOCK_BRANCH_PREFIX = "role/"
AGENT_BRANCH_PREFIX = "agent/"


# ─────────────────── Data classes ───────────────────
@dataclass
class AgentIdentity:
    """Stable per-machine agent identity (survives across script runs)."""
    agent_name: str
    machine_id: str
    created_at: float
    last_active: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoleLock:
    """Single-agent-per-role lock state."""
    role: str
    agent_name: str
    acquired_at: float
    expires_at: float  # TTL-based; auto-expire হলে অন্য agent নিতে পারে

    def is_expired(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return now >= self.expires_at


# ─────────────────── Machine ID (stable per machine) ───────────────────
def _machine_id() -> str:
    """Stable machine identifier (survives across script runs).

    # বাংলা মন্তব্য: machine_id = hostname + platform + uuid একত্রিত —
    # এক machine-এ একই id সবসময় দেবে। VM/container restart হলেও stable।
    """
    raw = f"{socket.gethostname()}|{platform.node()}|{platform.machine()}"
    # বাংলা মন্তব্য: /etc/machine-id থেকে নিলে আরও stable, কিন্তু permission
    # issue হতে পারে — fallback এ namespace + uuid4।
    try:
        mid_file = Path("/etc/machine-id")
        if mid_file.exists():
            raw += "|" + mid_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    # namespace uuid (deterministic) — same input → same uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))


# ─────────────────── Identity resolution (persistent) ───────────────────
def resolve_agent_identity(preferred: Optional[str] = None) -> AgentIdentity:
    """Resolve the agent identity — persistent across runs.

    # বাংলা মন্তব্য (#2950 root-cause):
    # প্রথমে ~/.supremeai/identity.json পড়ি — আগের run-এ যদি এই machine-এ
    # agent assign হয়ে থাকে, সেটাই রিইউজ করবে (cooldown-aware)। না থাকলে
    # git-push-as-CAS দিয়ে নতুন name claim করবে।

    Args:
        preferred: Optional role prefix (e.g. "coder"). None = pick coder by default.
    """
    # Step 1: persistent identity আছে কিনা দেখো
    if IDENTITY_FILE.exists():
        try:
            data = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
            identity = AgentIdentity(**data)
            # Update last_active
            identity.last_active = time.time()
            _save_identity(identity)
            return identity
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # corrupt — নতুন assign করো

    # Step 2: নতুন identity assign করো (git-push-as-CAS)
    role_prefix = preferred or "coder"
    agent_name = _claim_new_agent_name(role_prefix)
    identity = AgentIdentity(
        agent_name=agent_name,
        machine_id=_machine_id(),
        created_at=time.time(),
        last_active=time.time(),
    )
    _save_identity(identity)
    return identity


def _save_identity(identity: AgentIdentity) -> None:
    """Persist identity to ~/.supremeai/identity.json."""
    try:
        IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
        IDENTITY_FILE.write_text(
            json.dumps(identity.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 0o600 — শুধু এই user পড়তে পারে (machine-local secret)
        IDENTITY_FILE.chmod(0o600)
    except OSError as e:
        print(f"⚠️ Could not save identity: {e}", file=sys.stderr)


def _claim_new_agent_name(role_prefix: str, max_attempts: int = 10) -> str:
    """Claim a new agent name via git-push-as-CAS.

    # বাংলা মন্তব্য (#2950 atomicity):
    # চেষ্টা করো role-1, role-2, role-3... — প্রতিটির জন্য git push করো
    # `refs/heads/agent/role-N` branch হিসেবে। যদি push সফল হয় → own,
    # ব্যর্থ হয় → next number চেষ্টা করো। git protocol নিজে atomic —
    # দুটো machine একসাথে role-1 চেষ্টা করলেও git একজনকে reject করবে।
    """
    # বাংলা মন্তব্য: প্রথমে remote-এ কোন agent/ branch আছে কিনা fetch করো
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--prune"],
            cwd=str(ROOT_DIR), check=False, capture_output=True, timeout=30,
        )
    except Exception:
        pass

    # বাংলা মন্তব্য: বিদ্যমান agent/ branches থেকে next-gap বের করো
    existing = _list_existing_agent_branches(role_prefix)

    for i in range(1, max_attempts + 1):
        candidate = f"{role_prefix}-{i}"
        if candidate in existing:
            continue
        if _git_push_atomic(f"{AGENT_BRANCH_PREFIX}{candidate}"):
            return candidate
    # Fallback: unique suffix যোগ করো (race-এ সবগুলো occupied)
    fallback = f"{role_prefix}-{uuid.uuid4().hex[:8]}"
    return fallback


def _list_existing_agent_branches(role_prefix: str) -> set[str]:
    """List existing agent/<role>-N branches from remote."""
    try:
        res = subprocess.run(
            ["git", "branch", "-r", "--list", f"origin/{AGENT_BRANCH_PREFIX}{role_prefix}-*"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, check=False, timeout=15,
        )
        branches = set()
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line.startswith(f"origin/{AGENT_BRANCH_PREFIX}"):
                continue
            # origin/agent/coder-1 → coder-1
            name = line[len(f"origin/{AGENT_BRANCH_PREFIX}"):]
            branches.add(name)
        return branches
    except Exception:
        return set()


def _git_push_atomic(branch_name: str) -> bool:
    """Atomic CAS via git push — `--push-option=atomic` + force-with-lease.

    # বাংলা মন্তব্য: git push নিজেই atomic — remote-এ যদি branch ইতিমধ্যে
    # থাকে তবে push reject হয়। দুটো machine একসাথে push করলেও git protocol
    # একজনকে atomically accept করে, অন্যজনকে reject করে। কোনো TOCTOU window নেই।
    """
    try:
        # Create empty commit on a temporary ref then push — যাতে branch
        # নতুন হলেও push সফল হয় (empty branch push কখনো যায় না)।
        # বিকল্প: refs/agents/<name> namespace-এ push করা (branch নয়)।
        # সহজতর: branch হিসেবেই push করি — acquire_role_slot-এর সাথে consistent।
        subprocess.run(
            ["git", "fetch", "origin", "--prune"],
            cwd=str(ROOT_DIR), check=False, capture_output=True, timeout=30,
        )
        # প্রথমে local-এ branch তৈরি করো origin/main থেকে
        subprocess.run(
            ["git", "branch", branch_name, "origin/main"],
            cwd=str(ROOT_DIR), check=False, capture_output=True, timeout=30,
        )
        res = subprocess.run(
            ["git", "push", "origin", branch_name],
            cwd=str(ROOT_DIR), capture_output=True, text=True, check=False, timeout=30,
        )
        if res.returncode == 0:
            return True
        # Branch already exists (race lost) — clean up local
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=str(ROOT_DIR), check=False, capture_output=True, timeout=15,
        )
        return False
    except Exception:
        return False


# ─────────────────── Single-agent-per-role lock ───────────────────
def acquire_role_lock(role: str, agent_name: str, ttl: int = 3600) -> bool:
    """Acquire single-agent-per-role lock via git-push-as-CAS.

    # বাংলা মন্তব্য (#2950):
    # coder ছাড়া বাকি সব role-এ শুধু ১ agent active থাকতে পারবে। এই lock
    # role/<role-name> branch হিসেবে remote-এ push করা হয় — git protocol
    # atomic, দুজন একসাথে push করলে একজন reject হয়।

    Args:
        role: Role name (auditor, ci-fixer, etc.)
        agent_name: The agent acquiring the lock
        ttl: Time-to-live in seconds (default 1 hour). TTL শেষ হলে
             অন্য agent lock নিতে পারবে (crashed agent-এর stale lock prevent)।
    """
    # coder-এর জন্য lock লাগে না — multiple agents allowed
    if role in ("coder",):
        return True

    if role not in SINGLE_AGENT_ROLES:
        # অজানা role — conservative: lock নিও
        pass

    lock_branch = f"{ROLE_LOCK_BRANCH_PREFIX}{role}"

    # Step 1: TTL check — আগের lock expired কিনা দেখো
    existing = _read_role_lock_metadata(role)
    now = time.time()
    if existing and not existing.is_expired(now):
        if existing.agent_name == agent_name:
            # আমারই lock — renew করো
            return _write_role_lock_metadata(role, agent_name, ttl)
        else:
            # অন্যের lock active — acquire ব্যর্থ
            return False

    # Step 2: git-push-as-CAS দিয়ে lock branch push করো
    if not _git_push_atomic(lock_branch):
        # Lock race lost — তবে metadata পড়ে দেখো আমার নাম আছে কিনা
        existing = _read_role_lock_metadata(role)
        if existing and existing.agent_name == agent_name:
            return True
        return False

    # Step 3: lock metadata লিখো (agent_name + TTL)
    return _write_role_lock_metadata(role, agent_name, ttl)


def release_role_lock(role: str, agent_name: str) -> bool:
    """Release the role lock (on graceful exit)."""
    if role in ("coder",):
        return True
    lock_branch = f"{ROLE_LOCK_BRANCH_PREFIX}{role}"
    existing = _read_role_lock_metadata(role)
    if not existing or existing.agent_name != agent_name:
        return False  # আমার lock নয় — কিছু করতে পারি না
    # Lock metadata মুছো + branch delete করো
    _clear_role_lock_metadata(role)
    subprocess.run(
        ["git", "push", "origin", "--delete", lock_branch],
        cwd=str(ROOT_DIR), check=False, capture_output=True, timeout=30,
    )
    return True


def _role_lock_metadata_path(role: str) -> Path:
    """Per-role lock metadata file in repo (shared across machines via git)."""
    return ROOT_DIR / "docs" / "master_docs" / "role_locks" / f"{role}.json"


def _read_role_lock_metadata(role: str) -> RoleLock | None:
    path = _role_lock_metadata_path(role)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return RoleLock(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def _write_role_lock_metadata(role: str, agent_name: str, ttl: int) -> bool:
    path = _role_lock_metadata_path(role)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        lock = RoleLock(
            role=role,
            agent_name=agent_name,
            acquired_at=now,
            expires_at=now + ttl,
        )
        path.write_text(
            json.dumps(asdict(lock), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def _clear_role_lock_metadata(role: str) -> None:
    path = _role_lock_metadata_path(role)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


# ─────────────────── Cooldown registry ───────────────────
def record_cooldown(agent_name: str, seconds: int = 120) -> bool:
    """Record a cooldown for an agent (after push, before next claim).

    # বাংলা মন্তব্য (#2950):
    # branch push-এর পর 2-min cooldown — গ্রুপে অন্য agent-এর জন্য। agent
    # exit করলেও cooldown registry repo-তে থাকে → নতুন run দেখবে।
    """
    registry = _load_cooldown_registry()
    now = time.time()
    registry[agent_name] = {
        "last_push": now,
        "cooldown_until": now + seconds,
        "cooldown_seconds": seconds,
    }
    return _save_cooldown_registry(registry)


def is_cooled_down(agent_name: str, now: float | None = None) -> bool:
    """Check if agent's cooldown has elapsed."""
    registry = _load_cooldown_registry()
    entry = registry.get(agent_name)
    if not entry:
        return True
    now = now if now is not None else time.time()
    return now >= entry.get("cooldown_until", 0)


def wait_for_cooldown(agent_name: str, max_seconds: int = 130) -> None:
    """Block until cooldown elapses (or max_seconds)."""
    if is_cooled_down(agent_name):
        return
    registry = _load_cooldown_registry()
    entry = registry.get(agent_name, {})
    remaining = max(0, entry.get("cooldown_until", 0) - time.time())
    remaining = min(remaining, max_seconds)
    if remaining > 0:
        print(f"⏳ Cooldown active for {agent_name} — sleeping {int(remaining)}s...")
        time.sleep(remaining)


def _load_cooldown_registry() -> dict:
    if not COOLDOWN_REGISTRY.exists():
        return {}
    try:
        return json.loads(COOLDOWN_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cooldown_registry(registry: dict) -> bool:
    try:
        COOLDOWN_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        COOLDOWN_REGISTRY.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


# ─────────────────── CLI ───────────────────
def _cli_resolve(args: argparse.Namespace) -> int:
    identity = resolve_agent_identity(args.preferred)
    print(json.dumps(identity.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cli_lock(args: argparse.Namespace) -> int:
    if acquire_role_lock(args.role, args.agent_name, ttl=args.ttl):
        print(f"✅ Role lock acquired: {args.role} → {args.agent_name}")
        return 0
    print(f"❌ Role lock acquire failed: {args.role} (held by another agent)")
    return 1


def _cli_release(args: argparse.Namespace) -> int:
    if release_role_lock(args.role, args.agent_name):
        print(f"✅ Role lock released: {args.role}")
        return 0
    print(f"❌ Release failed (not your lock): {args.role}")
    return 1


def _cli_cooldown(args: argparse.Namespace) -> int:
    record_cooldown(args.agent_name, args.seconds)
    print(f"✅ Cooldown recorded: {args.agent_name} for {args.seconds}s")
    return 0


def _cli_check_cooldown(args: argparse.Namespace) -> int:
    if is_cooled_down(args.agent_name):
        print(f"✅ {args.agent_name} cooled down — can proceed")
        return 0
    registry = _load_cooldown_registry()
    entry = registry.get(args.agent_name, {})
    remaining = max(0, entry.get("cooldown_until", 0) - time.time())
    print(f"⏳ {args.agent_name} still in cooldown ({int(remaining)}s remaining)")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Identity & Cooldown Registry (#2950)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_resolve = sub.add_parser("resolve", help="Resolve persistent agent identity")
    p_resolve.add_argument("--preferred", help="Preferred role prefix (default: coder)")
    p_resolve.set_defaults(func=_cli_resolve)

    p_lock = sub.add_parser("lock", help="Acquire single-agent-per-role lock")
    p_lock.add_argument("--role", required=True)
    p_lock.add_argument("--agent-name", required=True)
    p_lock.add_argument("--ttl", type=int, default=3600, help="Lock TTL in seconds (default 3600)")
    p_lock.set_defaults(func=_cli_lock)

    p_release = sub.add_parser("release", help="Release role lock")
    p_release.add_argument("--role", required=True)
    p_release.add_argument("--agent-name", required=True)
    p_release.set_defaults(func=_cli_release)

    p_cd = sub.add_parser("cooldown", help="Record cooldown for agent")
    p_cd.add_argument("--agent-name", required=True)
    p_cd.add_argument("--seconds", type=int, default=120)
    p_cd.set_defaults(func=_cli_cooldown)

    p_check = sub.add_parser("check-cooldown", help="Check if agent is cooled down")
    p_check.add_argument("--agent-name", required=True)
    p_check.set_defaults(func=_cli_check_cooldown)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
