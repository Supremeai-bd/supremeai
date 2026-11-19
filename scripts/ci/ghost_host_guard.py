#!/usr/bin/env python3
"""scripts/ci/ghost_host_guard.py — retire dead hosts, permanently (multi-target).

Two hosts have been retired from this repo's runtime surfaces, and both were
re-introduced *silently* after being cleaned up once. The guard exists because
"the defect is the class, not the instance":

  1. **Ghost host** (no-server): answers plain-text 404 with
     `x-render-routing: no-server` while the real gateway
     `supremeai-api-ulw0.onrender.com` (README service-table SSOT) serves 200.
     Root-cause closure for #2355 → #2348 → #2377.

  2. **Suspended Tower host** (2026-11-19): the un-suffixed Tower host (see
     TOWER_HOST below) was suspended by its owner; the canonical control plane is
     `supremeai-mcp-tower-live.onrender.com`. Commit `bea2978` reverted the
     host across 36 files (mcp.json, CI probes, watchdogs, the Cloudflare
     keepwarm worker, the studio proxy), so every MCP-dependent gate was
     dialing a suspended service. Fixed in the 2026-11-19 sweep; this target
     keeps it fixed.

Policy per target, applied to the tracked tree:

  - ZERO TOLERANCE on executable/config surfaces (*.py, *.sh, *.ps1, *.ts,
    *.tsx, *.js, *.mjs, *.json, *.yaml, *.yml, *.toml, Dockerfile, _redirects,
    vercel.json, and any extensionless executable): a dead default there is
    always a live trap — no marker can whitewash it.
  - HISTORICAL-EVIDENCE lanes (docs/reports/**, docs/bridge/**) are allowed:
    they are immutable measured-evidence receipts; rewriting them would
    falsify the audit trail.
  - Other Markdown (docs/**/*.md and any *.md elsewhere) may retain a dead-host
    string ONLY inside a retirement banner carrying that target's exact marker
    within the first 20 lines. Strip the banner, keep the string -> fail.

Modes (dual, house style):
  --check      scan the tracked tree (git ls-files, fs-walk fallback) and
               fail-closed on any violation; exit 0 clean, 1 findings.
  --self-test  hermetic tempdir scenarios proving every rule above for both
               targets, including the live-host non-match cases.

Stdlib-only, offline, deterministic. Exit codes: 0 pass, 1 findings,
2 usage error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TAG = "[ghost-host-guard]"

# Assembled at runtime: a scanner must name its target, but naming it as a
# literal would put the dead string into this very file for the guard to
# trip on (self-scan is part of the live sweep). The concatenation keeps the
# contiguous substring out of the source text.
GHOST_HOST = "supremeai-api" "." "onrender.com"
REAL_HOST = "supremeai-api-ulw0.onrender.com"
BANNER_MARKER = "ghost-host-retired: #2355/#2365/#2377"

TOWER_HOST = "supremeai-mcp-tower" "." "onrender.com"
TOWER_LIVE = "supremeai-mcp-tower-live.onrender.com"
TOWER_BANNER = "tower-host-retired: 2026-11-19"

BANNER_WINDOW_LINES = 20


@dataclass(frozen=True)
class RetiredHost:
    """One dead host plus how to repair a reference to it."""

    label: str
    host: str
    remedy: str
    banner: str


RETIRED_HOSTS = (
    RetiredHost(
        label="ghost host (no-server)",
        host=GHOST_HOST,
        remedy=f"point it at {REAL_HOST}, the README SSOT",
        banner=BANNER_MARKER,
    ),
    RetiredHost(
        label="suspended Tower host",
        host=TOWER_HOST,
        remedy=f"point it at {TOWER_LIVE}, the registry SSOT",
        banner=TOWER_BANNER,
    ),
)

# Immutable measured-evidence receipts: occurrences there are the historical
# record of probes actually made against a dead host (SENTRY_* series, bridge
# closure receipts). Rewriting history is falsification; allowlisting is not.
ALLOWED_PREFIXES = (
    "docs/reports/",
    "docs/bridge/",
)

# Executable/config surfaces: zero tolerance regardless of any banner.
ZERO_TOLERANCE_SUFFIXES = (
    ".py", ".sh", ".ps1", ".ts", ".tsx", ".js", ".mjs", ".cjs",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
)
ZERO_TOLERANCE_NAMES = (
    "Dockerfile", "_redirects", "vercel.json",
)

WALK_PRUNE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def is_zero_tolerance(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name in ZERO_TOLERANCE_NAMES or rel in ZERO_TOLERANCE_NAMES:
        return True
    return rel.endswith(ZERO_TOLERANCE_SUFFIXES)


def is_allowed_evidence(rel: str) -> bool:
    return rel.startswith(ALLOWED_PREFIXES)


def has_banner(text: str, marker: str = BANNER_MARKER) -> bool:
    head = text.splitlines()[:BANNER_WINDOW_LINES]
    return any(marker in line for line in head)


def list_tracked_files(root: Path) -> list[str]:
    """Tracked files via git (respects ignores); fs-walk fallback."""
    try:
        r = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root, capture_output=True, timeout=60, check=True,
        )
        entries = [e for e in r.stdout.decode("utf-8", "replace").split("\0") if e]
        if entries:
            return sorted(entries)
    except (OSError, subprocess.SubprocessError):
        pass
    out: list[str] = []
    for base, dirs, files in __import__("os").walk(root):
        dirs[:] = [d for d in dirs if d not in WALK_PRUNE_DIRS]
        for f in files:
            p = Path(base) / f
            out.append(str(p.relative_to(root)))
    return sorted(out)


def classify(rel_norm: str, text: str, target: RetiredHost) -> str | None:
    """Return a violation string for one dead-host hit, or None if allowed."""
    if is_allowed_evidence(rel_norm):
        return None
    if is_zero_tolerance(rel_norm):
        return (
            f"{rel_norm}: {target.label} in EXECUTABLE/CONFIG surface "
            f"(zero tolerance — {target.remedy})"
        )
    if text.endswith((".md", ".markdown", ".rst", ".txt")) or "/docs/" in f"/{rel_norm}":
        if has_banner(text, target.banner):
            return None
        return (
            f"{rel_norm}: {target.label} in doc WITHOUT retirement banner — "
            f"{target.remedy}, or add a top banner carrying the exact marker: "
            f"{target.banner}"
        )
    return (
        f"{rel_norm}: {target.label} in unrecognized surface class — "
        f"{target.remedy} or file an explicit allowlist amendment"
    )


def scan(root: Path) -> list[str]:
    """Return sorted violation strings for the tree rooted at `root`."""
    violations: list[str] = []
    for rel in list_tracked_files(root):
        path = root / rel
        try:
            if path.is_symlink() or not path.is_file():
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:8192]:  # binary heuristic
            continue
        text = raw.decode("utf-8", "replace")
        hits = [t for t in RETIRED_HOSTS if t.host in text]
        if not hits:
            continue
        rel_norm = rel.replace("\\", "/")
        for target in hits:
            finding = classify(rel_norm, text, target)
            if finding:
                violations.append(finding)
    return sorted(violations)


def run_check() -> int:
    violations = scan(REPO_ROOT)
    if violations:
        print(f"{TAG} FAIL — {len(violations)} dead-host violation(s):")
        for v in violations:
            print(f"  - {v}")
        print(f"{TAG} live hosts: {REAL_HOST} (gateway), {TOWER_LIVE} (Tower)")
        return 1
    labels = ", ".join(t.label for t in RETIRED_HOSTS)
    print(f"{TAG} OK — no actionable dead-host surfaces for {labels} "
          f"(evidence lanes + bannered historical docs only)")
    return 0


# --------------------------------------------------------------------------- #
# self-test: hermetic scenarios, no repo mutation                              #
# --------------------------------------------------------------------------- #

def _make_tree(files: dict[str, str]) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="ghost-guard-selftest-"))
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


def run_self_test() -> int:
    failures: list[str] = []

    def expect(label: str, cond: bool) -> None:
        if not cond:
            failures.append(label)

    clean = _make_tree({
        "examples/client.py": f'URL = "https://{REAL_HOST}/v1"\n',
        "docs/CONSUMERS.md": f"Base URL: https://{REAL_HOST}\n",
        "docs/reports/SENTRY_X.md": f"measured: {GHOST_HOST} 404 at 01:45Z\n",
        "mcp.json": f'{{"url": "https://{TOWER_LIVE}/mcp"}}\n',
    })
    expect("clean tree (live hosts + evidence lane) passes", scan(clean) == [])

    trap = _make_tree({
        "examples/run_smoke.sh": f'URL="${{GATEWAY_URL:-https://{GHOST_HOST}}}"\n',
    })
    expect("ghost in executable surface fails", len(scan(trap)) == 1)

    no_banner = _make_tree({
        "docs/LEGACY.md": f"see https://{GHOST_HOST}/v1/models\n",
    })
    expect("ghost in unbannered doc fails", len(scan(no_banner)) == 1)

    bannered = _make_tree({
        "docs/LEGACY.md": (
            f"# old receipt\n\n> {BANNER_MARKER} — historical, ghost retired\n\n"
            f"see https://{GHOST_HOST}/v1/models\n"
        ),
    })
    expect("ghost in bannered doc passes", scan(bannered) == [])

    stripped = _make_tree({
        "docs/LEGACY.md": (
            "# old receipt\n" + "\n" * 25
            + f"line {BANNER_MARKER} beyond window\n"
            + f"see https://{GHOST_HOST}/v1/models\n"
        ),
    })
    expect("banner beyond 20-line window does not whitewash", len(scan(stripped)) == 1)

    marker_on_code = _make_tree({
        "scripts/probe.py": (
            f"# {BANNER_MARKER}\nURL = 'https://{GHOST_HOST}/healthz'\n"
        ),
    })
    expect("banner marker cannot whitewash executable surface",
           len(scan(marker_on_code)) == 1)

    ulw0 = _make_tree({"a.py": f'U = "https://{REAL_HOST}"\n'})
    expect(f"{REAL_HOST} never matches the ghost pattern", scan(ulw0) == [])

    # --- target 2: the suspended MCP Tower host (2026-11-19 sweep) --------- #
    tower_trap = _make_tree({
        "mcp.json": f'{{"url": "https://{TOWER_HOST}/mcp"}}\n',
    })
    expect("suspended tower in executable/config surface fails",
           len(scan(tower_trap)) == 1)

    tower_probe = _make_tree({
        "scripts/probe.py": f'BASE = "https://{TOWER_HOST}/health"\n',
    })
    expect("suspended tower in python probe fails", len(scan(tower_probe)) == 1)

    tower_live = _make_tree({
        "mcp.json": f'{{"url": "https://{TOWER_LIVE}/sse"}}\n',
        "gateway/app.py": f'URL = "https://{TOWER_LIVE}/health"\n',
    })
    expect(f"{TOWER_LIVE} never matches the suspended pattern", scan(tower_live) == [])

    tower_bannered = _make_tree({
        "docs/HISTORY.md": (
            f"# receipt\n\n> {TOWER_BANNER} — host suspended, live host is "
            f"{TOWER_LIVE}\n\nprobe: https://{TOWER_HOST}/health\n"
        ),
    })
    expect("suspended tower in bannered doc passes", scan(tower_bannered) == [])

    cross_banner = _make_tree({
        # The ghost banner must NOT whitewash a suspended-tower reference:
        # each target carries its own marker.
        "docs/HISTORY.md": (
            f"> {BANNER_MARKER}\n\nprobe: https://{TOWER_HOST}/health\n"
        ),
    })
    expect("one target's banner does not whitewash another target",
           len(scan(cross_banner)) == 1)

    expect("real repo tree passes --check semantics", scan(REPO_ROOT) == [])

    if failures:
        print(f"{TAG} SELF-TEST FAIL ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{TAG} self-test OK — 13/13 scenarios pass")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Dead-host guard (see module docstring)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="scan the tracked tree, fail-closed")
    mode.add_argument("--self-test", action="store_true", help="hermetic scenario suite")
    args = ap.parse_args(argv)
    if args.self_test:
        return run_self_test()
    return run_check()


if __name__ == "__main__":
    sys.exit(main())
