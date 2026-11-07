#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
VAULT_ENV_PATH = SCRIPTS_DIR.parent / "vault.env"

# (#2644) SSOT refactor: slot → GitHub App mapping + vault fetch + JIT mint
# এখন scripts/agents/credential_manager.py-তে (SSOT) — এই স্ক্রিপ্ট আর inline
# কপি রাখে না; #1821-এর নোট করা ৫ম-registry-copy drift ঝুঁকি এখানেই বন্ধ।
# push_as_agent থাকলো push-এর একক দায়িত্বে (single responsibility)।
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.agents import credential_manager as _cm  # noqa: E402

# Re-export surface: SSOT wiring kept visible for the drift gate + tests.
BOT_SLOT_CREDENTIALS = _cm.BOT_SLOT_CREDENTIALS
load_vault = _cm.load_vault_env
_mask_prefix = _cm.mask_token


def fetch_creds(slot_or_vault, vault_or_slot=None, transport=None):
    """Backward-compatible adapter supporting (slot, vault) and legacy (vault, slot).

    # বাংলা (#2644 fix): আর্গুমেন্ট অর্ডার রিগ্রেশন প্রতিরোধে দুটি সিগনেচারই সাপোর্ট করে।
    """
    if isinstance(slot_or_vault, dict) and isinstance(vault_or_slot, str):
        return _cm.fetch_credentials(vault_or_slot, slot_or_vault, transport=transport)
    return _cm.fetch_credentials(slot_or_vault, vault_or_slot, transport=transport)


def log(s, m):
    print(f"[{s}] {m}", file=sys.stderr, flush=True)


def mint_token(c):
    """JIT installation token via credential_manager (RS256 JWT + POST).

    # বাংলা (#2644): mint লজিক SSOT-তে (credential_manager.mint_installation_token)
    # — এখানে শুধু backward-compatible wrapper।
    """
    from scripts.agents.credential_manager import mint_installation_token

    minted = mint_installation_token(
        c["app_id"], c["installation_id"], c["private_key"]
    )
    return minted["token"]


def _mask(text, token):
    """Mask the installation token before it can reach logs/CI output."""
    if not token or not text:
        return text
    return text.replace(token, _mask_prefix(token))


def push(token, owner, name, branch, dry=False):
    url = f"https://x-access-token:{token}@github.com/{owner}/{name}.git"
    if dry:
        log("git", f"[DRY-RUN] would push {branch} -> {owner}/{name}")
        return True, "dry-run"
    r = subprocess.run(
        ["git", "push", url, f"HEAD:refs/heads/{branch}"],
        cwd=SCRIPTS_DIR.parent,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    out, err = _mask(r.stdout, token), _mask(r.stderr, token)
    if r.returncode == 0:
        return True, out or "(no output)"
    return False, err or out


def main():
    import argparse

    p = argparse.ArgumentParser(description="Push HEAD to upstream as a GitHub App bot")
    p.add_argument("--slot", default=os.environ.get("AGENT_SLOT", "agent-3"))
    p.add_argument(
        "--repo", default=None, help="owner/name (default: SaifulHaqueNiloy/supremeai)"
    )
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    vault = load_vault(VAULT_ENV_PATH)
    creds = fetch_creds(a.slot, vault)
    token = mint_token(creds)
    owner, name = a.repo.split("/", 1) if a.repo else ("SaifulHaqueNiloy", "supremeai")
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=SCRIPTS_DIR.parent, text=True
    ).strip()
    ok, msg = push(token, owner, name, branch, dry=a.dry_run)
    print(msg, file=sys.stderr)
    return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())
