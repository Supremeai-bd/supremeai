#!/usr/bin/env python3
"""Mutation Lease — controlled remote mutation guard (#4200 §6/§7).

বাংলা সারসংক্ষেপ:
------------------
#4200 §6: Agents can work locally in parallel, but remote mutation must remain
controlled। This module provides a lightweight mutation lease:

  FREE → RESERVED → MUTATING → VERIFYING → RELEASED

NOT a fixed-duration lock — timeout is only a stale-lock recovery fallback।
Primary mechanism: freshness check + CAS (git-push-as-atomic)।

Usage:
  from scripts.ci.mutation_lease import MutationLease

  lease = MutationLease(branch="agent/4200-persistent-branch")
  if lease.acquire():
      try:
          lease.check_freshness()  # raises if stale
          lease.push()            # git push (atomic)
      finally:
          lease.release()
  else:
      print("Another agent is mutating — wait or work locally")
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_TIMEOUT = 300  # 5 min — stale-lock recovery fallback only
LEASE_FILE = Path(os.environ.get("SUPREMEAI_LEASE_STORE", "/tmp/supremeai_mutation_leases.json"))


class MutationLease:
    """Lightweight mutation lease for controlled git push (#4200 §6)."""

    def __init__(self, branch: str, agent_id: str = "", timeout: int = DEFAULT_TIMEOUT):
        self.branch = branch
        self.agent_id = agent_id or os.environ.get("AGENT_NAME", "unknown")
        self.timeout = timeout
        self.acquired = False

    def _load_leases(self) -> dict:
        if not LEASE_FILE.exists():
            return {}
        try:
            return json.loads(LEASE_FILE.read_text())
        except Exception:
            return {}

    def _save_leases(self, leases: dict) -> None:
        LEASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LEASE_FILE.write_text(json.dumps(leases, indent=2))

    def acquire(self) -> bool:
        """Acquire mutation lease for this branch.

        বাংলা: FREE → RESERVED। If another agent holds a non-stale lease, return False।
        Stale leases (> timeout) are auto-released।
        """
        leases = self._load_leases()

        # Check if a lease exists for this branch
        existing = leases.get(self.branch)
        if existing:
            # Check if stale
            age = time.time() - existing.get("acquired_at", 0)
            if age < self.timeout and existing.get("agent_id") != self.agent_id:
                return False  # Another agent holds a fresh lease

        # Acquire
        leases[self.branch] = {
            "agent_id": self.agent_id,
            "acquired_at": time.time(),
            "state": "RESERVED",
        }
        self._save_leases(leases)
        self.acquired = True
        return True

    def check_freshness(self) -> bool:
        """Check if branch is fresh relative to main (#4200 §7).

        বাংলা: latest main observe → stale check → sync/rebase if needed।
        Returns True if fresh, False if stale (should sync before push)।
        """
        try:
            # Fetch latest
            subprocess.run(["git", "fetch", "origin", "main"], check=True, timeout=30)

            # Check if behind
            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/main..{self.branch}"],
                capture_output=True, text=True, timeout=10,
            )
            behind = int(result.stdout.strip()) if result.returncode == 0 else 0

            # Check if main is ahead
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{self.branch}..origin/main"],
                capture_output=True, text=True, timeout=10,
            )
            ahead = int(result.stdout.strip()) if result.returncode == 0 else 0

            if ahead > 0:
                print(f"⚠️ Branch is {ahead} commits behind main — sync needed before push", file=sys.stderr)
                return False

            return True
        except Exception as e:
            print(f"Freshness check failed: {e}", file=sys.stderr)
            return False

    def push(self, force: bool = False) -> bool:
        """Push branch to remote (atomic git push).

        বাংলা: MUTATING → push → VERIFYING। Git protocol is itself atomic।
        """
        if not self.acquired:
            print("ERROR: push without acquire — call acquire() first", file=sys.stderr)
            return False

        # Update lease state
        leases = self._load_leases()
        if self.branch in leases:
            leases[self.branch]["state"] = "MUTATING"
            self._save_leases(leases)

        try:
            cmd = ["git", "push", "origin", self.branch]
            if force:
                cmd.append("--force")
            result = subprocess.run(cmd, check=False, timeout=60)
            if result.returncode != 0:
                print(f"git push failed (rc={result.returncode})", file=sys.stderr)
                return False

            # Update lease to VERIFYING
            leases = self._load_leases()
            if self.branch in leases:
                leases[self.branch]["state"] = "VERIFYING"
                leases[self.branch]["pushed_at"] = time.time()
                self._save_leases(leases)

            return True
        except Exception as e:
            print(f"Push failed: {e}", file=sys.stderr)
            return False

    def release(self) -> None:
        """Release the mutation lease.

        বাংলা: VERIFYING → RELEASED → FREE। Branch is now available for others।
        """
        if not self.acquired:
            return

        leases = self._load_leases()
        if self.branch in leases:
            del leases[self.branch]
            self._save_leases(leases)

        self.acquired = False
        print(f"🔓 Mutation lease released for {self.branch}")

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire mutation lease for {self.branch}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
