"""Contract test (#3265): pnpm version SSOT — workflows must never hardcode a pnpm version.

Incident (main CI RED): `dependency-health-check.yml` pinned
`pnpm/action-setup@v4` with `version: 9.0.0` while root `package.json`
declared `"packageManager": "pnpm@10.15.0"`. pnpm/action-setup refuses to run
when the action `version` input conflicts with `packageManager`
(ERR_PNPM_BAD_PM_VERSION) → setup step died → main RED after PR #3244 merged.

Same drift class existed in 5 more places (audit-release VSIX/EXE lanes,
nightly-ops corepack pin, deploy-train npm -g install, setup-frontend
composite action used by 6 lanes including the PR gate). Any future
packageManager bump would silently break those lanes at the worst time.

Guard contract (dynamic, zero workflow list):
  1. Root `package.json` MUST declare `packageManager: pnpm@<version>`.
  2. NO `pnpm/action-setup` step may set the `version:` input — the action
     then reads the version from `packageManager` (single source of truth).
  3. NO `corepack prepare pnpm@<version>` explicit pin — bare
     `corepack prepare --activate` reads `packageManager` from the project.
  4. NO `npm install -g pnpm@<version>` (or bare `-g pnpm`) global install —
     use the corepack path so the version always follows `packageManager`.

Scanned surfaces: every `.github/workflows/*.yml` AND every composite action
`.github/actions/*/action.yml` — newly added workflows/actions are covered
automatically (no list to update).
"""

from pathlib import Path
import json
import re
import unittest

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
COMPOSITE_ACTIONS_DIR = REPO_ROOT / ".github" / "actions"
ROOT_PACKAGE_JSON = REPO_ROOT / "package.json"

# `pnpm/action-setup@...` — action name must match exactly this action.
ACTION_SETUP_RE = re.compile(r"^pnpm/action-setup@")
# `corepack prepare pnpm@10.15.0 --activate` (explicit version pin = violation).
COREPACK_PIN_RE = re.compile(r"corepack\s+prepare\s+pnpm@[0-9]", re.IGNORECASE)
# `npm install -g pnpm@10.15.0` / `npm i -g pnpm` (global install = violation).
NPM_GLOBAL_PNPM_RE = re.compile(
    r"npm\s+(?:install|i)\s+(?:-g|--global)\s+pnpm(?:@[^\s]+)?", re.IGNORECASE
)
# packageManager must be `pnpm@<semver-ish>` (no bare pnpm / no other PM).
PACKAGE_MANAGER_RE = re.compile(r"^pnpm@[0-9]+\.[0-9]+\.[0-9]+")


def _yaml_files() -> list[Path]:
    """Every workflow + composite-action YAML file (dynamic discovery)."""
    files: list[Path] = []
    if WORKFLOWS_DIR.is_dir():
        files.extend(sorted(WORKFLOWS_DIR.glob("*.yml")))
        files.extend(sorted(WORKFLOWS_DIR.glob("*.yaml")))
    if COMPOSITE_ACTIONS_DIR.is_dir():
        files.extend(sorted(COMPOSITE_ACTIONS_DIR.glob("*/action.yml")))
        files.extend(sorted(COMPOSITE_ACTIONS_DIR.glob("*/action.yaml")))
    return files


def _iter_steps(doc: dict):
    """Yield (step_path, step_dict) for every step of every job in a parsed workflow.

    Composite actions have a top-level `runs.steps` instead of `jobs.*.steps`;
    both shapes are walked so the guard covers actions too.
    """
    jobs = doc.get("jobs") or {}
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for idx, step in enumerate(job.get("steps") or []):
                if isinstance(step, dict):
                    yield f"jobs.{job_name}.steps[{idx}]", step
    runs = doc.get("runs") or {}
    if isinstance(runs, dict):
        for idx, step in enumerate(runs.get("steps") or []):
            if isinstance(step, dict):
                yield f"runs.steps[{idx}]", step


def _violations() -> list[str]:
    """Collect all pnpm-version-SSOT violations across workflows/actions."""
    found: list[str] = []

    for path in _yaml_files():
        rel = path.relative_to(REPO_ROOT)
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            found.append(f"{rel}: unparseable YAML ({exc}) — cannot verify pnpm SSOT")
            continue
        if not isinstance(doc, dict):
            continue
        for step_path, step in _iter_steps(doc):
            uses = str(step.get("uses") or "")
            with_block = step.get("with") or {}
            if ACTION_SETUP_RE.match(uses):
                if isinstance(with_block, dict) and "version" in with_block:
                    found.append(
                        f"{rel} → {step_path}: `pnpm/action-setup` sets "
                        f"`version: {with_block['version']!r}` — remove it; the "
                        "action reads the version from package.json "
                        "`packageManager` (SSOT). Hardcoding it caused "
                        "ERR_PNPM_BAD_PM_VERSION → main RED (#3265)."
                    )
            run_cmd = str(step.get("run") or "")
            for line_no, line in enumerate(run_cmd.splitlines(), 1):
                if COREPACK_PIN_RE.search(line):
                    found.append(
                        f"{rel} → {step_path} (run, line {line_no}): "
                        f"`{line.strip()}` — explicit corepack pin drifts from "
                        "package.json `packageManager`; use bare "
                        "`corepack prepare --activate` (reads packageManager)."
                    )
                if NPM_GLOBAL_PNPM_RE.search(line):
                    found.append(
                        f"{rel} → {step_path} (run, line {line_no}): "
                        f"`{line.strip()}` — global npm pnpm install bypasses "
                        "package.json `packageManager` (SSOT); use "
                        "`corepack enable && corepack prepare --activate`."
                    )
    return found


class WorkflowPnpmSsotContract(unittest.TestCase):
    """GUARD-class contract: pnpm version follows package.json packageManager."""

    def test_root_package_json_declares_pnpm_package_manager(self):
        """Contract precondition — without packageManager, action-setup/corepack
        have no SSOT to read and every workflow lane would need a hardcode."""
        self.assertTrue(
            ROOT_PACKAGE_JSON.is_file(), "root package.json missing"
        )
        pkg = json.loads(ROOT_PACKAGE_JSON.read_text(encoding="utf-8"))
        pm = pkg.get("packageManager")
        self.assertTrue(
            isinstance(pm, str) and PACKAGE_MANAGER_RE.match(pm),
            f"package.json must declare `packageManager: pnpm@<version>` "
            f"(found: {pm!r}) — it is the SSOT all CI lanes follow (#3265)",
        )

    def test_no_workflow_hardcodes_pnpm_version(self):
        """The #3265 incident class: any hardcoded pnpm version drifts from
        packageManager and breaks CI lanes (ERR_PNPM_BAD_PM_VERSION)."""
        violations = _violations()
        self.assertEqual(
            violations,
            [],
            "pnpm version SSOT violations (#3265 class):\n" + "\n".join(violations),
        )

    def test_scanner_actually_covers_current_repo(self):
        """Sanity: the dynamic scanner sees the known files — guards against a
        silently-empty scan (e.g. path/layout change making the test vacuous)."""
        files = _yaml_files()
        names = [f.name for f in files]
        self.assertIn("pr.yml", names, "scanner must discover .github/workflows/pr.yml")
        self.assertIn(
            "action.yml",
            [f.name for f in files if f.parent.name == "setup-frontend"],
            "scanner must discover composite action setup-frontend/action.yml",
        )
        # The incident file itself must be covered.
        self.assertTrue(
            any(f.name == "dependency-health-check.yml" for f in files),
            "scanner must discover dependency-health-check.yml",
        )


if __name__ == "__main__":
    unittest.main()
