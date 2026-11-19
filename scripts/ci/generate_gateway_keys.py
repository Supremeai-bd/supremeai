#!/usr/bin/env python3
"""Generate a pool of SupremeAI gateway client keys (the "N keys" plan).

Why this exists: until 2026-11-19 the gateway derived a key's secret env name
from its `owner` (`SUPREMEAI_API_KEY_<OWNER>`), so two keys with the same owner
collided and could never hold different secrets — and `rate_limit` was global,
so every authenticated caller drained one shared window. A pool of independent
client keys therefore could not be expressed at all: one noisy client 429'd the
whole fleet.

Now `gateway/routing_policy.json` supports, per key:

    "supremeai-key-client-1": {
      "owner": "client-1",
      "scopes": ["chat"],
      "env": "SUPREMEAI_API_KEY_CLIENT_1",     # optional, must be unique
      "rate_limit": {"max_requests": 120}      # optional per-owner budget
    }

This tool produces that policy block plus the matching secret assignments. The
secret VALUES are printed once, to stdout, for you to paste into the secret
manager — they are never written into the repository.

Usage:
    python scripts/ci/generate_gateway_keys.py --count 6
    python scripts/ci/generate_gateway_keys.py --count 6 --scopes chat,models \
        --max-requests 120 --write-policy        # patch routing_policy.json (no secrets)
    python scripts/ci/generate_gateway_keys.py --count 6 \
        --secrets-out ~/gateway-keys.env         # 0600 file to import, never stdout
    python scripts/ci/generate_gateway_keys.py --write-policy --dry-run

The key id is random and looks like `supremeai-key-<32 url-safe chars>`; it is
the credential itself (the gateway compares it by exact match, and the limiter
buckets by non-secret owner label, so no hashing of credentials is needed
anywhere — see gateway/rate_limit.py).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "gateway" / "routing_policy.json"
KEY_PREFIX = "supremeai-key-"
ALLOWED_SCOPES = ("chat", "models", "embeddings", "admin")


def build_keys(
    count: int,
    *,
    scopes: tuple[str, ...],
    owner_prefix: str,
    max_requests: int | None,
    window_seconds: int | None,
    token_factory=secrets.token_urlsafe,
) -> list[dict]:
    """Return `count` key entries: public policy metadata + the secret value."""
    if count < 1:
        raise ValueError("count must be >= 1")
    unknown = set(scopes) - set(ALLOWED_SCOPES)
    if unknown:
        raise ValueError(f"unknown scopes: {sorted(unknown)}")
    keys: list[dict] = []
    for index in range(1, count + 1):
        owner = f"{owner_prefix}-{index}"
        env = f"SUPREMEAI_API_KEY_{owner.upper().replace('-', '_')}"
        rate_limit: dict[str, int] = {}
        if max_requests is not None:
            rate_limit["max_requests"] = max_requests
        if window_seconds is not None:
            rate_limit["window_seconds"] = window_seconds
        entry: dict = {
            "key_id": KEY_PREFIX + token_factory(24),
            "owner": owner,
            "env": env,
            "scopes": list(scopes),
            "secret": KEY_PREFIX + token_factory(32),
        }
        if rate_limit:
            entry["rate_limit"] = rate_limit
        keys.append(entry)
    return keys


def policy_block(keys: list[dict]) -> dict[str, dict]:
    """Public half of the generated entries (never contains the secret)."""
    block: dict[str, dict] = {}
    for key in keys:
        meta: dict = {
            "owner": key["owner"],
            "scopes": key["scopes"],
            "env": key["env"],
        }
        if key.get("rate_limit"):
            meta["rate_limit"] = key["rate_limit"]
        block[key["key_id"]] = meta
    return block


def merge_policy(existing: dict, keys: list[dict], *, replace_owners: bool) -> dict:
    """Merge generated entries into a routing policy without dropping others."""
    policy = json.loads(json.dumps(existing))  # deep copy, order preserved
    api_keys = policy.setdefault("api_keys", {})
    owners = {meta["owner"] for meta in policy_block(keys).values()}
    if replace_owners:
        api_keys = {
            key_id: meta for key_id, meta in api_keys.items()
            if meta.get("owner") not in owners
        }
    api_keys.update(policy_block(keys))
    policy["api_keys"] = api_keys
    return policy


def write_secrets_file(path: Path, keys: list[dict]) -> None:
    """Write `ENV=secret` lines, readable by the owner only (0600).

    Written with O_CREAT|O_EXCL|O_WRONLY so an existing file is never silently
    overwritten (which would destroy secrets that are already in the vault).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{key['env']}={key['secret']}\n" for key in keys)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    os.chmod(path, 0o600)


def generated_by_owner(block: dict[str, dict]) -> dict[str, str]:
    """owner -> env name for a generated policy block."""
    return {meta["owner"]: meta["env"] for meta in block.values()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate SupremeAI gateway client keys")
    ap.add_argument("--count", type=int, default=6, help="how many keys (default 6)")
    ap.add_argument("--scopes", default="chat", help="comma-separated scopes")
    ap.add_argument("--owner-prefix", default="client", help="owner label prefix")
    ap.add_argument("--max-requests", type=int, default=None,
                    help="per-key budget (max requests per window)")
    ap.add_argument("--window-seconds", type=int, default=None,
                    help="per-key budget window (defaults to the global window)")
    ap.add_argument("--policy", type=Path, default=POLICY_PATH,
                    help="routing policy to patch with --write-policy")
    ap.add_argument("--write-policy", action="store_true",
                    help="write the public entries into the policy file (no secrets)")
    ap.add_argument("--replace-owners", action="store_true",
                    help="drop existing entries for the same owners before merging")
    ap.add_argument("--secrets-out", type=Path, default=None,
                    help="write ENV=secret lines here (0600), outside the repo")
    ap.add_argument("--allow-in-repo", action="store_true",
                    help="permit --secrets-out inside the repository (do not commit it)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args(argv)

    scopes = tuple(s.strip() for s in args.scopes.split(",") if s.strip())
    keys = build_keys(
        args.count,
        scopes=scopes,
        owner_prefix=args.owner_prefix,
        max_requests=args.max_requests,
        window_seconds=args.window_seconds,
    )

    print("# --- routing_policy.json: api_keys (public, commit this) ---")
    print(json.dumps(policy_block(keys), indent=2, ensure_ascii=False))
    print()
    print("# clients send the key id in the `X-SupremeAI-Key` header.")
    print("# secret values are NOT printed: pass --secrets-out <file> instead.")

    if args.secrets_out is not None:
        target = args.secrets_out.expanduser().resolve()
        if REPO_ROOT in target.parents and not args.allow_in_repo:
            print(
                f"::error::{target} is inside the repository; secrets must not be "
                "committed. Pick a path outside it or pass --allow-in-repo.",
                file=sys.stderr,
            )
            return 2
        write_secrets_file(target, keys)
        print(f"# wrote {len(keys)} secret lines to {target} (mode 0600) — import them "
              "into the secret manager, then delete the file.")

    if args.write_policy:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        merged = merge_policy(policy, keys, replace_owners=args.replace_owners)
        generated = policy_block(keys)
        duplicate_owners = sorted(
            {
                meta["owner"]
                for key_id, meta in merged["api_keys"].items()
                if key_id not in generated
                and meta["owner"] in {m["owner"] for m in generated.values()}
                and meta.get("env") == generated_by_owner(generated)[meta["owner"]]
            }
        )
        if duplicate_owners:
            # Two entries for one owner would claim the same env var; the loader
            # rejects that, so say it here with the exact owner names.
            print(
                "::error::existing entries claim the same env as the generated ones "
                f"for owners {duplicate_owners} — rerun with --replace-owners",
                file=sys.stderr,
            )
            return 2
        if args.dry_run:
            print(f"\n[dry-run] would write {len(keys)} entries to {args.policy}")
            return 0
        args.policy.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {len(keys)} entries to {args.policy} (secrets were NOT written)")
    elif not args.dry_run:
        print("\n(no --write-policy: nothing written; copy the block above by hand)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
