"""Tests for scripts/git/acquire_lane_slot.sh (issue #1860 — M2 CAS slot CLI).

Strategy: the script's external processes are injectable (ACQUIRE_GH_CMD /
ACQUIRE_GIT_CMD), so tests install fake `gh` + `git` executables on PATH that
simulate GitHub API semantics against a shared JSON state file — no network.

Covered paths (issue #1860 test matrix):
- fresh-create:      missing branch → POST /git/refs 201 → WON
- race-422:          GET 404 but POST 422 (concurrent creator) → walk to next n
- race-non-FF:       stale branch, claim push rejected non-fast-forward → next n
- stale-reuse:       stale branch CAS-claimed, then reset to origin/main with
                     --force-with-lease → zero previous-agent commits remain
- active-skip:       branch hot within heartbeat window → walk to next n
- concurrency:       two invocations on shared state win different branches
- dry-run:           reports intent, performs zero writes
- exhaustion / arg validation / invalid pool
- real-shape probe (#2299): branch payloads use the REAL GET /branches shape
  (GitHub user objects at commit.committer/author — no .date — and git-level
  dates at commit.commit.*), and the fake gh evaluates the script's actual
  --jq expression instead of printing a pre-joined string, so any future
  jq-path regression fails the suite loudly instead of shipping to prod.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "git" / "acquire_lane_slot.sh"

GH_REPO = "SaifulHaqueNiloy/supremeai"
MAIN_SHA = "main-sha-0000"


# ─── fake gh / fake git builders ─────────────────────────────────────────

FAKE_GH = r'''#!/bin/bash
# Fake gh: GitHub API semantics against $ACQUIRE_TEST_STATE (JSON).
set -u
STATE="${ACQUIRE_TEST_STATE:?}"
LIB="__LIB__"
j() { python3 "$LIB" "$STATE" "$@"; }
# helpers operate via python for JSON safety
ARGS=("$@")

# find the api path: the one arg that looks like a relative API path (repos/...)
PATH_=""
for a in "${ARGS[@]}"; do
  if [[ "$a" == repos/* ]]; then PATH_="$a"; break; fi
done

# record invocation
j append_log "gh $*"

branch_of_ref() { echo "${1#refs/heads/}"; }

if [[ "$PATH_" == repos/*"/branches/"* ]]; then
  b="${PATH_##*/branches/}"
  if j is_hidden "$b"; then echo "gh: Not Found (HTTP 404)" >&2; exit 1; fi
  if j has_branch "$b"; then
    # Real-shape simulation (#2299): evaluate the caller's actual --jq
    # expression against the REAL /branches payload shape — no pre-joined
    # strings. A wrong jq path now fails here exactly like it fails on prod.
    JQ_EXPR=""
    for ((i = 0; i < ${#ARGS[@]} - 1; i++)); do
      [[ "${ARGS[$i]}" == "--jq" ]] && JQ_EXPR="${ARGS[$((i + 1))]}"
    done
    if [[ -z "$JQ_EXPR" ]]; then
      echo "fake-gh: branches probe without --jq (script contract)" >&2
      exit 1
    fi
    j eval_branch_jq "$b" "$JQ_EXPR"
    exit 0
  fi
  echo "gh: Not Found (HTTP 404)" >&2
  exit 1
fi

if [[ "$PATH_" == repos/*"/git/refs" ]]; then
  # -f ref=refs/heads/<b> -f sha=<sha>
  REF=""; NEWSHA=""
  for ((i=0; i<${#ARGS[@]}; i++)); do
    [[ "${ARGS[$i]}" == "-f" ]] || continue
    v="${ARGS[$((i+1))]}"
    [[ "$v" == ref=* ]] && REF="${v#ref=}"
    [[ "$v" == sha=* ]] && NEWSHA="${v#sha=}"
  done
  b="$(branch_of_ref "$REF")"
  if j post_always_422 "$b" || j has_branch "$b"; then
    echo "gh: Reference already exists (HTTP 422)" >&2
    exit 1
  fi
  j post_create "$b" "$NEWSHA"
  echo '{"ref":"'"$REF"'"}'
  exit 0
fi

if [[ "$PATH_" == repos/*"/commits/main" ]]; then
  j echo_main_sha
  exit 0
fi

echo "fake-gh: unhandled call: $*" >&2
exit 1
'''

FAKE_GIT = r'''#!/bin/bash
# Fake git: local object store + remote ref semantics against $ACQUIRE_TEST_STATE.
set -u
STATE="${ACQUIRE_TEST_STATE:?}"
LIB="__LIB__"
j() { python3 "$LIB" "$STATE" "$@"; }
j append_log "git $*"

SUB="$1"; shift

case "$SUB" in
  rev-parse)
    case "$1" in
      origin/main) j echo_main_sha ;;
      *) echo "fatal: bad rev" >&2; exit 1 ;;
    esac ;;
  cat-file)
    # cat-file -e <sha>^{commit}
    sha="$2"
    case "$sha" in
      *"^{commit}") sha="${sha:0:${#sha}-9}" ;;   # strip trailing ^{commit} (9 chars)
    esac
    j know_sha "$sha" || { echo "fatal: bad object $sha" >&2; exit 1; }
    exit 0 ;;
  commit-tree)
    # commit-tree <base> -m <msg>
    base="$1"
    j make_claim_commit "$base"   # prints new sha, records parent
    ;;
  push)
    if [[ "$1" == --force-with-lease=* ]]; then
      lease="${1#--force-with-lease=refs/heads/}"; b="${lease%%:*}"; lease_sha="${lease#*:}"
      spec="$3"   # push --force-with-lease=... origin <src-sha>:refs/heads/<b>
      src_sha="${spec%%:*}"
      dst="${spec#*:}"
      [[ "$dst" == "refs/heads/"* ]] || { echo "fatal: bad dst" >&2; exit 1; }
      if j lease_reset "$b" "$lease_sha" "$src_sha"; then
        j record_lease_reset "$b" "$lease_sha" "$src_sha"
        exit 0
      fi
      echo "To fake-remote" >&2
      echo " ! [rejected] $dst (stale info)" >&2
      exit 1
    fi
    # plain push: push origin <src>:refs/heads/<b>  → fast-forward CAS
    spec="$2"; src_sha="${spec%%:*}"; dst="${spec#*:}"
    b="${dst#refs/heads/}"
    if j ff_push "$b" "$src_sha"; then
      j record_ff_push "$b" "$src_sha"
      exit 0
    fi
    echo "To fake-remote" >&2
    echo " ! [rejected]        $dst (non-fast-forward)" >&2
    exit 1 ;;
  fetch) exit 0 ;;
  *) echo "fake-git: unhandled: $*" >&2; exit 1 ;;
esac
'''

FAKE_LIB = r'''import json, sys, datetime
from pathlib import Path

def _now_iso(minutes_ago: int = 0) -> str:
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def _real_branch_payload(sha: str, iso_date: str) -> dict:
    # Mirrors GET /repos/{owner}/{repo}/branches/<b> — the shape that broke the
    # probe pre-#2299: commit.committer/author are GitHub USER objects (no
    # .date); git-level dates live only under commit.commit.*.
    return {
        "name": None,
        "commit": {
            "sha": sha,
            "node_id": "fake-node",
            "commit": {
                "author": {"name": "Agent", "email": "agent@example.test", "date": iso_date},
                "committer": {"name": "Agent", "email": "agent@example.test", "date": iso_date},
                "message": "fake",
                "url": "https://api.github.test/fake",
            },
            "author": {"login": "fake-agent", "id": 1, "type": "Bot"},
            "committer": {"login": "fake-agent", "id": 1, "type": "Bot"},
            "parents": [],
            "url": "https://api.github.test/fake",
        },
    }

def _jq_eval(expr: str, payload: dict):
    # Mini-evaluator for the probe-expression grammar:
    #   term (+ term)*  where term = "literal" | (path // path) | path
    # Deliberately strict: any expression change the evaluator cannot parse
    # exits 9 so the suite fails loudly instead of silently diverging (#2299).
    def path_get(p):
        cur = payload
        for part in p.strip().lstrip(".").split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def term(tok):
        tok = tok.strip()
        if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
            return tok[1:-1]
        if tok.startswith("(") and tok.endswith(")"):
            for alt in tok[1:-1].split("//"):
                v = path_get(alt)
                if v is not None:
                    return v
            return None
        return path_get(tok)

    parts, depth, cur = [], 0, ""
    for ch in expr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "+" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    vals = [term(t) for t in parts]
    if any(v is None for v in vals):
        sys.stderr.write("fake-gh jq: null operand in string concatenation\n")
        sys.exit(9)
    print("".join(str(v) for v in vals))

state_path = Path(sys.argv[1])
cmd = sys.argv[2]

def load():
    return json.loads(state_path.read_text())

def save(d):
    state_path.write_text(json.dumps(d, indent=1))

d = load()

if cmd == "append_log":
    d.setdefault("log", []).append(sys.argv[3]); save(d)
elif cmd == "echo_main_sha":
    print(d["main_sha"])
elif cmd == "has_branch":
    b = sys.argv[3]
    sys.exit(0 if b in d["branches"] else 1)
elif cmd == "is_hidden":
    b = sys.argv[3]
    sys.exit(0 if b in d.get("hide_branches", []) else 1)
elif cmd == "post_always_422":
    b = sys.argv[3]
    sys.exit(0 if b in d.get("post_refs_422", []) else 1)
elif cmd == "eval_branch_jq":
    b, expr = sys.argv[3], sys.argv[4]
    _jq_eval(expr, d["branches"][b]["payload"])
elif cmd == "post_create":
    b, sha = sys.argv[3], sys.argv[4]
    iso = _now_iso(0)
    d["branches"][b] = {"sha": sha, "date": iso, "payload": _real_branch_payload(sha, iso)}
    d.setdefault("known_shas", []).append(sha)
    save(d)
elif cmd == "know_sha":
    sha = sys.argv[3]
    sys.exit(0 if sha in d.get("known_shas", []) else 1)
elif cmd == "make_claim_commit":
    base = sys.argv[3]
    n = d.get("claim_count", 0) + 1
    new = f"claim-{n}-{base[:4]}"
    d["claim_count"] = n
    d.setdefault("parents", {})[new] = base
    d.setdefault("known_shas", []).append(new)
    save(d)
    print(new)
elif cmd == "ff_push":
    b, src = sys.argv[3], sys.argv[4]
    head = d["remote_heads"].get(b)
    parent = d.get("parents", {}).get(src)
    sys.exit(0 if head is not None and parent == head else 1)
elif cmd == "record_ff_push":
    b, src = sys.argv[3], sys.argv[4]
    d["remote_heads"][b] = src
    d.setdefault("ff_pushes", []).append({"branch": b, "sha": src})
    save(d)
elif cmd == "lease_reset":
    b, lease, src = sys.argv[3], sys.argv[4], sys.argv[5]
    if b in d.get("lease_veto", []):
        sys.exit(1)
    sys.exit(0 if d["remote_heads"].get(b) == lease else 1)
elif cmd == "record_lease_reset":
    b, lease, src = sys.argv[3], sys.argv[4], sys.argv[5]
    d["remote_heads"][b] = src
    d.setdefault("lease_resets", []).append({"branch": b, "lease": lease, "to": src})
    save(d)
else:
    sys.stderr.write(f"fake-lib: unknown cmd {cmd}\n")
    sys.exit(9)
'''


def _now_iso(minutes_ago: int = 0) -> str:
    dt = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _real_branch_payload(sha: str, iso_date: str) -> dict:
    # Module-level copy for make_state (FAKE_LIB carries its own embedded copy
    # for post_create). Mirrors the REAL GET /branches shape (#2299):
    # commit.committer/author = GitHub USER objects without .date; git-level
    # dates live only under commit.commit.{author,committer}.date.
    return {
        "name": None,
        "commit": {
            "sha": sha,
            "node_id": "fake-node",
            "commit": {
                "author": {"name": "Agent", "email": "agent@example.test", "date": iso_date},
                "committer": {"name": "Agent", "email": "agent@example.test", "date": iso_date},
                "message": "fake",
                "url": "https://api.github.test/fake",
            },
            "author": {"login": "fake-agent", "id": 1, "type": "Bot"},
            "committer": {"login": "fake-agent", "id": 1, "type": "Bot"},
            "parents": [],
            "url": "https://api.github.test/fake",
        },
    }


def make_state(tmp_path: Path, **overrides) -> Path:
    base = {
        "main_sha": MAIN_SHA,
        "branches": {},
        "remote_heads": {},
        "known_shas": [MAIN_SHA],
        "hide_branches": [],
        "post_refs_422": [],
        "log": [],
        "parents": {},
    }
    base.update(overrides)
    # every branch tip exists in the local object store (a real agent has
    # fetched origin) — the CAS claim commit parents onto these tips; probes
    # are served from the REAL-shape payload (#2299 regression guard)
    for info in base["branches"].values():
        info.setdefault("payload", _real_branch_payload(info["sha"], info["date"]))
        if info["sha"] not in base["known_shas"]:
            base["known_shas"].append(info["sha"])
    p = tmp_path / "state.json"
    p.write_text(json.dumps(base, indent=1))
    return p


@pytest.fixture()
def fake_env(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    lib = tmp_path / "fake_lib.py"
    lib.write_text(FAKE_LIB)
    for name, body in (("gh", FAKE_GH), ("git", FAKE_GIT)):
        f = bin_dir / name
        body = body.replace("$ACQUIRE_TEST_STATE", str(tmp_path / "state.json"))
        body = body.replace("__LIB__", str(lib))
        f.write_text(body)
        f.chmod(0o755)
    return {"bin": bin_dir, "tmp": tmp_path}


def run_script(state: Path, *args: str, bin_dir: Path | None = None) -> subprocess.CompletedProcess:
    env_path = f"{bin_dir}:{_system_path()}" if bin_dir else _system_path()
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            "PATH": env_path,
            "GH_TOKEN": "test-token",
            "GH_REPO": GH_REPO,
            "ACQUIRE_TEST_STATE": str(state),
            "HOME": "/tmp",
            "LANG": "C.UTF-8",
        },
    )


def _system_path() -> str:
    import os

    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")


def acquired(proc: subprocess.CompletedProcess) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith("ACQUIRED_BRANCH="):
            return line.split("=", 1)[1]
    raise AssertionError(f"no ACQUIRED_BRANCH in stdout:\n{proc.stdout}\n{proc.stderr}")


# ─── issue #1860 test matrix ─────────────────────────────────────────────

class TestRealShapeProbe:
    """#2299 regression: the probe must survive the REAL /branches payload
    shape — GitHub user objects at commit.committer/author carry no .date;
    git-level dates live only at commit.commit.*. Pre-#2299 the fake gh
    printed a pre-joined "<sha> <date>" string, so the script's --jq
    expression was never exercised and prod died 'unparseable commit date'.
    """

    def test_probe_walks_past_existing_branch_without_unparseable_date(self, fake_env):
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": MAIN_SHA, "date": _now_iso(3)}},
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert "unparseable commit date" not in proc.stderr
        assert "API error while probing" not in proc.stderr
        # the probe yielded a REAL age (3 min → ACTIVE skip), not a crash
        assert "ACTIVE (last commit 3min ago" in proc.stderr
        assert acquired(proc) == "coder-2"

    def test_probe_expression_matches_real_shape_contract(self):
        """String-level guard: the --jq expression reads git-level dates."""
        import re

        src = SCRIPT.read_text()
        m = re.search(r"--jq '([^']+)'", src)
        assert m, "branch_exists --jq expression not found in script"
        expr = m.group(1)
        paths = re.findall(r"\.[A-Za-z_][A-Za-z0-9_.]*", expr)  # maximal dotted paths
        assert ".commit.commit.committer.date" in paths
        assert ".commit.commit.author.date" in paths
        # user-object paths (always dateless) must NOT appear as probe sources
        assert ".commit.committer.date" not in paths
        assert ".commit.author.date" not in paths


class TestFreshCreate:
    def test_missing_branch_created_atomically(self, fake_env):
        state = make_state(fake_env["tmp"])  # empty repo state
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-1"
        # the create landed server-side with origin/main as the base SHA
        data = json.loads(state.read_text())
        assert data["branches"]["coder-1"]["sha"] == MAIN_SHA

    def test_two_concurrent_invocations_win_different_branches(self, fake_env):
        """Acceptance #1: same pool, empty state → both exit 0, different numbers.

        The second run shares the first run's state: coder-1 now exists and is
        hot (heartbeat), so the CAS walk must mint coder-2.
        """
        state = make_state(fake_env["tmp"])
        p1 = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        p2 = run_script(state, "--pool", "coder", "--agent-id", "bot-2", bin_dir=fake_env["bin"])
        assert p1.returncode == 0 and p2.returncode == 0
        assert acquired(p1) == "coder-1"
        assert acquired(p2) == "coder-2"


class TestRace422:
    def test_hidden_create_race_walks_to_next_slot(self, fake_env):
        """GET says missing, POST says exists — the concurrent-creator window."""
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": MAIN_SHA, "date": _now_iso(0)}},
            hide_branches=["coder-1"],
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-2"
        assert "raced on coder-1" in proc.stderr


class TestRaceNonFastForward:
    def test_stale_claim_push_rejected_walks_to_next_slot(self, fake_env):
        """Stale branch, but the ref moved after our probe → non-FF → next n."""
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": "stale-sha-1", "date": _now_iso(60)}},
            remote_heads={"coder-1": "moved-sha-999"},  # ≠ probed tip → non-FF
            known_shas=[MAIN_SHA, "moved-sha-999"],  # MAIN_SHA required up front
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-2"
        assert "raced on coder-1" in proc.stderr
        data = json.loads(state.read_text())
        assert data["remote_heads"]["coder-1"] == "moved-sha-999"  # untouched


class TestStaleReuse:
    def test_stale_branch_reused_with_clean_slate(self, fake_env):
        """Acceptance #2: stale (>15 min) reuse leaves zero previous-agent commits."""
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": "stale-sha-1", "date": _now_iso(60)}},
            remote_heads={"coder-1": "stale-sha-1"},
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-1"
        data = json.loads(state.read_text())
        # reset landed: branch head == origin/main, guarded by the CAS lease —
        # the lease must be OUR claim commit sha (the ref's head after the
        # claim push), proving nothing moved between claim and reset
        claim_sha = data["ff_pushes"][0]["sha"]
        assert data["remote_heads"]["coder-1"] == MAIN_SHA
        assert data["lease_resets"] == [
            {"branch": "coder-1", "lease": claim_sha, "to": MAIN_SHA}
        ]
        # the claim commit (first heartbeat) preceded the reset
        assert any("claim-1" in e["sha"] for e in data.get("ff_pushes", []))
        assert "[slot-claim] pool=coder" in " ".join(data["log"])

    def test_reset_lease_violation_walks_to_next_slot(self, fake_env):
        """Ref moved between claim commit and reset → lease aborts → next n."""
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": "stale-sha-1", "date": _now_iso(60)}},
            remote_heads={"coder-1": "stale-sha-1"},
            lease_veto=["coder-1"],  # fake git: force every lease reset to fail
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-2"


class TestActiveSkip:
    def test_hot_branch_skipped_within_heartbeat_window(self, fake_env):
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": MAIN_SHA, "date": _now_iso(5)}},  # 5 min < 15 min
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert acquired(proc) == "coder-2"
        assert "ACTIVE" in proc.stderr


class TestExhaustion:
    def test_all_slots_hot_exits_1(self, fake_env):
        state = make_state(
            fake_env["tmp"],
            branches={f"coder-{i}": {"sha": MAIN_SHA, "date": _now_iso(0)} for i in range(1, 4)},
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", "--max", "3", bin_dir=fake_env["bin"])
        assert proc.returncode == 1
        assert "exhausted" in proc.stderr


class TestDryRun:
    def test_dry_run_reports_create_without_writes(self, fake_env):
        state = make_state(fake_env["tmp"])
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", "--dry-run", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert "DRY_RUN_WOULD_CREATE=coder-1" in proc.stdout
        data = json.loads(state.read_text())
        assert data["branches"] == {}          # zero writes
        assert not any("-X POST" in e for e in data["log"])

    def test_dry_run_reports_stale_reuse(self, fake_env):
        state = make_state(
            fake_env["tmp"],
            branches={"coder-1": {"sha": "stale-sha-1", "date": _now_iso(60)}},
            remote_heads={"coder-1": "stale-sha-1"},
        )
        proc = run_script(state, "--pool", "coder", "--agent-id", "bot-1", "--dry-run", bin_dir=fake_env["bin"])
        assert proc.returncode == 0, proc.stderr
        assert "DRY_RUN_WOULD_REUSE=coder-1" in proc.stdout
        assert json.loads(state.read_text())["remote_heads"]["coder-1"] == "stale-sha-1"


class TestValidation:
    def test_invalid_pool_rejected(self, fake_env):
        state = make_state(fake_env["tmp"])
        proc = run_script(state, "--pool", "nuclear", "--agent-id", "bot-1", bin_dir=fake_env["bin"])
        assert proc.returncode == 2
        assert "invalid pool" in proc.stderr

    def test_missing_agent_id_rejected(self, fake_env):
        state = make_state(fake_env["tmp"])
        proc = run_script(state, "--pool", "coder", bin_dir=fake_env["bin"])
        assert proc.returncode == 2

    def test_all_six_lanes_accepted(self, fake_env):
        for pool in ("planner", "coder", "pr-helper", "ci", "browser", "platform"):
            state = make_state(fake_env["tmp"])
            proc = run_script(state, "--pool", pool, "--agent-id", "bot-1", bin_dir=fake_env["bin"])
            assert proc.returncode == 0, f"{pool}: {proc.stderr}"
            assert acquired(proc) == f"{pool}-1"
