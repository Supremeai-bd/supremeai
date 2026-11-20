#!/usr/bin/env python3
"""
check_hardcoded_deployment_config.py
Scans the codebase for hardcoded production hostnames (e.g. .onrender.com).
Enforces zero-hardcode configuration policy.

SCRIPT-INTELLIGENCE v9: auto-discovers targets via scripts/lib/auto_discovery.py — no hardcoded file inventories.
Scan root, the frontend tree and exception anchors are resolved from the live
filesystem; a stale anchor (like the old "frontend/src/api.ts" example, which no
longer exists) is skipped with a clear "[discovery] ... skipping" warning instead
of silently disabling its exception.

Environment overrides:
  SCAN_ROOT            scan root pin (default: auto-discovered repo root)
  SUPREMEAI_REPO_ROOT  repo root pin (scripts/lib/auto_discovery.py)

Exit codes: 0 = pass, 1 = violations found, 2 = discovery/error (fail-loud)
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/
from lib.auto_discovery import (
    DiscoveryError,
    discover_files,
    get_layout,
    require,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repo_paths import resolve as resolve_repo_path  # noqa: E402

_ROOT_FOR_IGNORE = Path(__file__).resolve().parents[2]

# Directories/files to skip
IGNORE_PATHS = {
    "node_modules",
    "dist",
    "dist-admin",
    "dist-user",
    "ci-reports",
    ".playwright-mcp",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "tests",
    "docs",
    # NOTE: `scripts/ci` used to be listed here. Exempting the guard's own
    # directory from the policy it enforces is how `supremeai-primary-node`
    # (retired; the live host is `supremeai-primary-node-5xso`) survived in
    # `deploy_doctor.py` and `service_latency_probe.py` for as long as it did:
    # the probes were pointed at a dead host and this gate could not see it.
    # Those scripts now read config/service_registry.yaml via
    # repo_paths.service_endpoint(). One one-shot generator
    # (`generate_route_client_inventory.py`) is exempted individually below.
    "scripts/docs",
    "scripts/patches",
    "scripts/advanced_analysis",
    ".env.example",
    ".env",
    ".kilo",
    "secrets_registry.yaml",
    "README.md",
    "AGENTS.md",
    "STATUS.md",
    "CHECKPOINT.md",
    "LESSONS_LEARNED.md",
    "REAL_TESTING_LOG.md",
    "ERROR_AUDIT.md",
    "reports",
    "scratch",
    "specs",
    "backend/pyerrorfix",
    "audit_reports",
    ".agents",
    "_archive",
    ".github/workflows",
    "firebase.json",
    "htmlcov",
    "scripts/archive",
    "scripts/pre_merge_guard.py",
    # SCRIPT-INTELLIGENCE v9: the auto-discovery lib *derives* conventional
    # URLs from render.yaml service names (it holds no deployment pins of
    # its own).
    "scripts/lib/auto_discovery.py",
    # One-shot generator: its OUTPUT is a route inventory whose payload embeds
    # deployment hosts. The generator is not a probe and never runs in CI.
    "scripts/ci/generate_route_client_inventory.py",
    # This file. Its BANNED_PATTERNS table is the policy itself, and its
    # exception specs name hosts in order to permit or describe them; scanning
    # it reports the definition of the rule as a breach of the rule.
    "scripts/ci/check_hardcoded_deployment_config.py",
    # Denylist of RETIRED hosts. The strings exist precisely so the build can
    # reject them; removing them would delete the check.
    "scripts/ci/validate_frontend_build.py",
    # Detector for stale hosts: GHOST_HOST / REAL_HOST / TOWER_HOST are the
    # fixtures it asserts against. Deriving them would make the test agree with
    # its own input, which is the one thing it must not do.
    "scripts/ci/ghost_host_guard.py",
    "out"
}

# The generated script index moved from scripts/_INDEX.md to scripts/ops/.
# The stale literal above had silently stopped matching, so the guard began
# reporting its OWN generated output as a hardcoded-host violation — the file
# says "DO NOT EDIT BY HAND" and quotes URLs from the scripts it indexes.
# Resolved through repo_paths so a future move cannot lapse the same way.
_INDEX_CANDIDATES = (
    "scripts/ops/_INDEX.md",
    "scripts/_INDEX.md",
)
for _candidate in _INDEX_CANDIDATES:
    _resolved = resolve_repo_path(_candidate)
    if _resolved is not None:
        try:
            IGNORE_PATHS.add(_resolved.resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix())
        except ValueError:
            pass

# The service registry is the DECLARATION POINT this policy points everything
# else at: each service entry carries `production_url` (the host) beside
# `canonical_url_env` (the override that wins at runtime). Reporting it as a
# violation is self-contradictory — it is the one file where a production host
# is supposed to be written down. Everything else should read it via
# repo_paths.service_endpoint().
for _registry_file in ("config/service_registry.yaml", "config/service_registry.yml"):
    if (_ROOT_FOR_IGNORE / _registry_file).exists():
        IGNORE_PATHS.add(_registry_file)

# File suffixes that are test fixtures — these intentionally reference
# deployment hostnames to simulate different environments and are not
# themselves hardcoded production configuration.
IGNORE_SUFFIXES = (
    ".test.ts",
    ".test.tsx",
    ".spec.ts",
    ".spec.tsx",
)

# The patterns we want to catch
BANNED_PATTERNS = [
    r"\.onrender\.com",
    r"\.web\.app",
    r"\.firebaseapp\.com",
    r"\.vercel\.app",
    r"supreme-admin-\d+-prod" # hardcoded passwords
]

BANNED_REGEX = re.compile("|".join(BANNED_PATTERNS), re.IGNORECASE)

# Allowed exceptions — SCRIPT-INTELLIGENCE v9: each anchor is resolved against
# the live filesystem at runtime.  Tuple shape:
#   (repo-relative anchor, line-regex, discovery-glob | None)
# A discovery-glob makes the anchor dynamic (frontend entry files are found
# wherever they live, e.g. "index.html" at the frontend root).  Anchors whose
# file genuinely does not exist anywhere are skipped with a "[discovery]"
# warning — never silently kept, never silently scanned-without-exception.
# (Illustrative-only example, kept for format documentation: the historical
#  ("frontend/src/api.ts", r"// Legacy endpoint: .*\.onrender\.com") entry —
#  that file no longer exists, so today it would warn-and-skip.)
# Usage examples inside module docstrings name a host so the reader knows what
# a realistic value looks like. They are documentation, not configuration —
# nothing executes them. Rather than exempt whole files (which is how a stale
# host hid in this directory before), the exception is line-anchored: it only
# applies to lines that are clearly CLI examples.
_DOC_EXAMPLE = (
    r"--?[a-z-]+[\s=]https?://"      # --tower-url https://...  / --url=https://...
    r"|e\.g\.[,\s]+\[?https?://"      # (endpoint e.g. https://...)
    r"|^\s+[A-Z_]+\s+e\.g\."          # GATEWAY_URL  e.g. https://...
    r"|^\s+[-\w]+=https?://"            # GATEWAY_URL=https://...
)

EXCEPTION_SPECS: list[tuple[str, str, tuple[str, ...] | None]] = [
    ("scripts/ci/annotations_census_guard.py", _DOC_EXAMPLE, None),
    ("scripts/ci/health_incident_plane_guard.py", _DOC_EXAMPLE, None),
    ("scripts/ci/hollow_read_guard.py", _DOC_EXAMPLE, None),
    ("scripts/ci/mcp_conformance_selftest.py", _DOC_EXAMPLE, None),
    ("scripts/ci/probe_live_status_453.py", _DOC_EXAMPLE, None),
    ("scripts/ci/tenant_negative_battery.py", _DOC_EXAMPLE, None),
    ("scripts/ci/verify_ci_attestation.py", _DOC_EXAMPLE, None),
    # PROJECT-DERIVED hosting domains, the same sanctioned class as
    # core/config_validation.py's ALLOWED_HOSTS: `f"https://{project}.web.app"`
    # builds a per-project hostname from a config value. There is no pinned
    # production host here to go stale, which is what the policy exists to
    # prevent.
    ("scripts/ci/resolve_production_targets.py", r"\.web\.app|\.firebaseapp\.com", None),
    # render.yaml service names -> https://<name>.onrender.com: a template,
    # not a host. `supremeai-primary-node` is escaped in a regex, not pinned.
    ("scripts/ops/pre_merge_guard.py", r"<name>\.onrender\.com|primary-node\.onrender", None),
    (".github/scripts/ci_summary_v2.py", r"\.onrender\.com", None),
    # Zero-hardcode ALLOWED_HOSTS derivation (#298): the ONLY sanctioned
    # .onrender.com usage — building the REAL per-service hostname
    # "{RENDER_SERVICE_NAME}.onrender.com". The bare-apex fallback this policy
    # exists to prevent was deliberately REMOVED there (fail-closed instead);
    # the f-string suffix plus its explanatory comment are the intended design.
    ("backend/core/config_validation.py", r"\.onrender\.com", None),
    # Pydantic Field() docstring examples — illustrative only, not a runtime default.
    ("backend/core/config_validator.py", r"examples=", None),
    # 2026-09-18 লাইভ ইনসিডেন্ট গার্ড: generate_firebase_config.py এখন BACKEND_URL-কে
    # Hosting ডোমেন (*.web.app / *.firebaseapp.com) হিসেবে fail-closed রিজেক্ট করে —
    # নিষিদ্ধ ডোমেন ক্লাসের নাম না লিখলে সেটি ডিটেক্টই করতে পারে না। এটি deployment
    # pin নয় — mis-pointed URL-এর বিরুদ্ধেই গার্ড (config_validation.py-এর sanctioned
    # .onrender.com ব্যবহারের মতোই)। নীরব ভুয়া পাস এড়াতে exception-টি স্পষ্ট ও ন্যায্য।
    ("scripts/deploy/generate_firebase_config.py", r"\.web\.app|\.firebaseapp\.com", None),
    # FE-05 (Issue #522): the CSP moved from an index.html <meta> tag to the
    # authoritative response-header locations (vercel.json + frontend/nginx.conf).
    # Its allow-list uses wildcard host patterns (e.g. https://*.web.app),
    # not specific deployment hostnames — the same sanctioned exception the
    # inline meta CSP previously held, now pointed at the header blocks.
    ("vercel.json", r"Content-Security-Policy", None),
    # Value-line anchor (FB-02 precedent): if vercel.json is ever pretty-
    # printed, the CSP "value" lands on its own line WITHOUT the
    # "Content-Security-Policy" key text, so the key-line anchor above cannot
    # match it and the policy false-positives (main CI red, run 36055956866 —
    # #1121 reformatted the headers array and split key/value across lines).
    # Mirrors the firebase.template.json entry below: the payload line itself
    # is the anchor. Wildcard host patterns only — same sanctioned class.
    ("vercel.json", r"default-src 'self'", None),
    ("frontend/nginx.conf", r"Content-Security-Policy", None),
    # FB-02 (Issue #583, PR #607): the Firebase Hosting CSP response header lives
    # in firebase.template.json (pretty-printed: the "value" sits on its own line,
    # so the anchor matches the CSP payload, not the key). Wildcard host patterns
    # only — same sanctioned class as the two header CSPs above.
    ("firebase.template.json", r"default-src 'self'", None),
    # issue #1325: update_cors_hosts.py documents the Firebase Hosting UI origin contract
    ("scripts/update_cors_hosts.py", r"FIREBASE_PROJECT_ID", None),
    # Issues #1483/#1484/#1455 (PR #1499): production CORS origins as code-level
    # FAILSAFE DEFAULTS — env vars always win when present; the defaults only
    # fire when CORS env sync to the host fails (live incident guard). This is
    # an allow-list of browser origins, NOT a deployment pin (the app never
    # calls these hosts) — same sanctioned class as config_validation.py's
    # ALLOWED_HOSTS derivation.
    # Admin-host retirement (2026-10-25, PR #1247 follow-up):
    # https://supremeai-admin.web.app is fully removed from the codebase — the
    # admin console now lives at https://supremeai-studio.pages.dev (route
    # /admin), which needs no exception here because *.pages.dev is not a
    # banned pattern class. Anchors updated from the retired backend/* layout
    # to the live core/* + gateway/* duplicates.
    (
        "core/middleware/cors_policy.py",
        r"supremeai-a\.web\.app|supremeai-lac\.vercel\.app|supremeai-studio\.vercel\.app",
        None,
    ),
    (
        "gateway/middleware/cors_policy.py",
        r"supremeai-a\.web\.app|supremeai-lac\.vercel\.app|supremeai-studio\.vercel\.app",
        None,
    ),
    (
        "core/config_fields.py",
        r"supremeai-a\.web\.app|supremeai-lac\.vercel\.app|supremeai-studio\.vercel\.app",
        None,
    ),
]


def resolve_exceptions(root: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Resolve EXCEPTION_SPECS against the live filesystem.

    Returns (resolved[(rel_path, line_regex)], warnings).  A stale anchor is
    dropped with a warning instead of silently never matching.
    """
    resolved: list[tuple[str, str]] = []
    warnings: list[str] = []
    layout = get_layout()

    for anchor, pattern, glob_pat in EXCEPTION_SPECS:
        if glob_pat is not None:
            # dynamic anchor: discover the file wherever it currently lives
            base = root
            if anchor.startswith("frontend") and layout.frontend and layout.frontend.is_dir():
                base = layout.frontend
            hits = discover_files(base, glob_pat)
            if not hits:
                warnings.append(
                    f"[discovery] exception anchor '{anchor}' (glob {glob_pat}) not found — skipping exception"
                )
                continue
            try:
                rel = hits[0].resolve().relative_to(root).as_posix()
            except ValueError:
                warnings.append(
                    f"[discovery] exception anchor {hits[0]} outside scan root — skipping exception"
                )
                continue
            resolved.append((rel, pattern))
            continue

        # Anchors are historical strings, several of which still say `backend/`
        # even though this repository has always kept its package at `core/`.
        # Resolving through repo_paths means a sanctioned exception keeps
        # applying instead of silently lapsing — which is what happened to
        # core/config_validation.py: its anchor said backend/, so the guard
        # reported the deliberately sanctioned ALLOWED_HOSTS derivation as a
        # violation. A lapsed exception is worse than none, because it reports
        # the exact code the policy was written to permit.
        found = resolve_repo_path(anchor)
        if found is None and (root / anchor).exists():
            found = root / anchor
        if found is not None:
            try:
                rel = found.resolve().relative_to(root).as_posix()
            except ValueError:
                rel = anchor
            resolved.append((rel, pattern))
        else:
            warnings.append(
                f"[discovery] exception target '{anchor}' not found — skipping exception"
            )
    return resolved, warnings


def should_ignore(path: Path, root: Path) -> bool:
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        return True

    # We also ignore artifacts/logs
    if ".system_generated" in rel_path or ".gemini" in rel_path:
        return True

    if rel_path.endswith(IGNORE_SUFFIXES):
        return True

    path_parts = Path(rel_path).parts
    for ignore in IGNORE_PATHS:
        if rel_path.startswith(ignore) or rel_path == ignore:
            return True
        # Match a whole path segment — e.g. ignoring "tests" skips any
        # .../tests/... directory (illustrative filename: "backend/tests/x.py",
        # which does not exist in this repo; it only demonstrates the rule).
        if ignore in path_parts:
            return True
        # Match by filename anywhere in the tree (e.g. "REAL_TESTING_LOG.md")
        if path.name == ignore:
            return True
    return False

def scan_file(filepath: Path, root: Path, exceptions: list[tuple[str, str]]) -> list[str]:
    violations = []
    try:
        rel_path = filepath.relative_to(root).as_posix()
        content = filepath.read_text(encoding="utf-8")

        for line_num, line in enumerate(content.splitlines(), 1):
            if BANNED_REGEX.search(line):
                # Check exceptions
                is_exception = False
                for ex_file, ex_pattern in exceptions:
                    if ex_file == rel_path and re.search(ex_pattern, line):
                        is_exception = True
                        break

                if not is_exception:
                    violations.append(f"  ❌ Line {line_num}: {line.strip()}")

    except Exception as e:
        # Ignore binary files or unreadable files
        _ = e
    return violations


def _print_usage() -> None:
    print(
        """ব্যবহার: check_hardcoded_deployment_config.py [অপশন]

অপশন:
  --help, -h    এই সাহায্য বার্তা
  --advisory    নন-ব্লকিং অ্যাডভাইজরি মোড

Environment:
  SCAN_ROOT            স্ক্যান রুট ওভাররাইড (ডিফল্ট: auto-discovered repo root)
  SUPREMEAI_REPO_ROOT  রিপো রুট ওভাররাইড (scripts/lib/auto_discovery.py)

Exit codes: 0 = pass | 1 = violations found | 2 = discovery/error (fail-loud)"""
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if any(a in ("--help", "-h") for a in sys.argv[1:]):
        _print_usage()
        return 0

    valid_args = {"--help", "-h", "--advisory"}
    unknown = [a for a in sys.argv[1:] if a not in valid_args]
    if unknown:
        print(f"❌ অজানা অপশন: {' '.join(unknown)}", file=sys.stderr)
        _print_usage()
        return 2

    try:
        env_root = os.getenv("SCAN_ROOT")
        if env_root:
            root = Path(env_root).resolve()
            if not root.is_dir():
                raise DiscoveryError(f"SCAN_ROOT={env_root!r} is not a directory")
        else:
            root = get_layout().root
        layout = get_layout()
    except DiscoveryError as exc:
        print(f"[discovery] {exc}", file=sys.stderr)
        return 2

    exceptions, exception_warnings = resolve_exceptions(root)

    # Frontend entry discovery — dynamic: scan whatever actually exists.
    frontend_note = str(layout.frontend) if layout.frontend else "(no frontend dir — skipping)"
    fe_entries: list[Path] = []
    if layout.frontend and layout.frontend.is_dir():
        fe_entries = discover_files(layout.frontend, ("src/**/*.ts", "src/**/*.tsx"))

    print("🔍 Scanning codebase for hardcoded deployment configuration...")
    print(
        f"[discovery] SCRIPT-INTELLIGENCE v9 | scan root: {root} | frontend: {frontend_note} | "
        f"frontend src entries: {len(fe_entries)} ts/tsx | "
        f"exceptions resolved: {len(exceptions)}/{len(EXCEPTION_SPECS)}"
    )
    for w in exception_warnings:
        print(w)
    if layout.frontend and layout.frontend.is_dir() and not fe_entries:
        print("[discovery] WARNING: frontend present but 0 src/**/*.ts(x) entries found — frontend layout changed?")

    has_errors = False
    scanned: list[Path] = []

    for root_dir, dirs, files in os.walk(root):
        # Filter directories in-place to avoid traversing ignored paths
        dirs[:] = [d for d in dirs if not should_ignore(Path(root_dir) / d, root)]

        for file in files:
            filepath = Path(root_dir) / file
            if should_ignore(filepath, root):
                continue

            # Only check files that can CARRY configuration.
            #
            # Markdown was in this set, so the policy reported prose: a doc
            # that *documents* a production host ("archived console:
            # https://...") was a violation, while the code the doc describes
            # was not. A zero-hardcode policy is about what the program READS,
            # and no program reads its own documentation as config. Dropping
            # .md removes that whole false-positive class; genuine examples in
            # docs stay visible in a link checker, which is where broken doc
            # URLs belong.
            if filepath.suffix not in {'.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yml', '.yaml', '.html', '.sh', ''}:
                continue

            scanned.append(filepath)
            violations = scan_file(filepath, root, exceptions)
            if violations:
                has_errors = True
                print(f"\n📄 {filepath.relative_to(root)}:")
                for v in violations:
                    print(v)

    # বাংলা: fail-loud — একটাও ফাইল স্ক্যান না হলে 'PASS' বলা যাবে না
    try:
        require(scanned, f"files to scan under {root}")
    except DiscoveryError as exc:
        print(f"[discovery] {exc}", file=sys.stderr)
        return 2

    print(f"[discovery] scanned {len(scanned)} files")

    advisory = "--advisory" in sys.argv

    if has_errors:
        print("\n🚨 Hardcoded deployment configuration detected!")
        if advisory:
            print("⚠️ ADVISORY MODE: Hardcoded deployment configuration detected but non-blocking.")
            sys.exit(0)
        else:
            print("Please move these values to environment variables/Settings.")
            sys.exit(1)
    else:
        print("\n✅ PASS: No hardcoded deployment configuration found.")
        sys.exit(0)


if __name__ == "__main__":
    sys.exit(main())
