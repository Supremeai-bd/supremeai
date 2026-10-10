"""Contract test: Bridge automation chain — workflow hardening + watchdog coupling.

এই ফাইল machine-enforced করে সেই ভুল-শ্রেণিগুলো যেগুলো manual review-এ হারিয়ে
গিয়েছিল (E-series audit):

  E2  — `bridge-intake.yml`-এ free-text `workflow_dispatch` input সরাসরি
        `run:`-এর shell-এ interpolated হচ্ছিল (`MODE="${{ ... }}"`)। BRIDGE_TOKEN
        (PAT) ওই shell-এ থাকে, তাই input = command injection।
  E1/E3 — দুই-আলাদা `python … intake` / `python … sync` if-block এবং
        `set -uo pipefail` (no `-e`) → intake-এর সৎ exit code step-এর শেষ
        command-এর কথায় মরে যেত (BOTH = default মোড); অজানা mode মানে নীরব
        no-op run।
  E4/E9 — `cancel-in-progress: true` + job-এ timeout-minutes নেই → মাঝপথে
        cancel হলে orphan `bridge-land/<task>` branch-এর কারণে retry-এর push
        non-fast-forward হয়।
  E10 — `schedule-watchdog.yml`-এর `workflow_run.workflows` তালিকা workflow-র
        **নাম** দেখে (GitHub-এ file/id match নেই)। কোনো workflow-র `name:`
        বদলালে watchdog-এর trigger নীরবে বন্ধ হয়ে যায় → dead cron আর self-heal
        হয় না (E2E-প্রমাণিত: bridge-intake cron ২৫+ স্লট নীরব ছিল)।

Guard contract (dynamic — কোনো workflow-তালিকা maintain করতে হয় না):
   1. bridge-intake-এর `mode` input অবশ্যই `type: choice` + তিনটি বৈধ option।
   2. bridge-intake-এর কোনো `run:` block-এ `${{ ... }}` interpolation নয়।
   3. bridge-intake-এর run fail-fast (`set -e`) + একটাই script invocation
      (shell if-dispatch নয়) — exit code আর চাপা পড়ে না।
   4. concurrency in-progress run আর cancel করে না + job-এ timeout-minutes আছে।
   5. watchdog-এর `workflow_run.workflows`-এর প্রতিটি নাম অবশ্যই বিদ্যমান
      workflow `name:`, এবং সেই workflow-তে `workflow_dispatch` আছে
      (compensation dispatch ওই উৎসেই চলে)।
   6. কোনো দুই workflow একই `name:` মানে থাকে না (workflow_run অনির্দিষ্ট)।
"""

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
BRIDGE_WORKFLOW = WORKFLOWS_DIR / "bridge-intake.yml"
WATCHDOG_WORKFLOW = WORKFLOWS_DIR / "schedule-watchdog.yml"

VALID_MODES = {"intake", "sync", "both"}


def _load(path: Path) -> dict:
    """Parse a workflow YAML (unparseable → empty dict; caller asserts shape)."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _triggers(doc: dict) -> dict:
    """`on:` block — PyYAML (YAML 1.1) `on` key-কে boolean True বানায়।"""
    raw = doc.get("on")
    if not isinstance(raw, dict):
        raw = doc.get(True)
    return raw if isinstance(raw, dict) else {}


def _steps(doc: dict):
    """Yield (job_id, step_index, step_dict) for every step of every job।"""
    for job_id, job in (doc.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for idx, step in enumerate(job.get("steps") or []):
            if isinstance(step, dict):
                yield job_id, idx, step


def _workflow_names() -> list[tuple[str, str]]:
    """[(workflow name, relative file name)] — duplicate detection-সহ।"""
    names: list[tuple[str, str]] = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        name = _load(path).get("name")
        if isinstance(name, str) and name.strip():
            names.append((name.strip(), path.name))
    return names


class BridgeWorkflowHardening(unittest.TestCase):
    """GUARD class: bridge-intake.yml-এর dispatch/execution hardening (E1–E4, E9)।"""

    def setUp(self):
        self.assertTrue(BRIDGE_WORKFLOW.is_file(), "bridge-intake.yml missing")
        self.doc = _load(BRIDGE_WORKFLOW)
        self.triggers = _triggers(self.doc)
    # ---- E2: choice-typed input (no free-text injection surface) -------------

    def test_dispatch_mode_input_is_choice_with_valid_options(self):
        dispatch = self.triggers.get("workflow_dispatch")
        self.assertIsInstance(dispatch, dict, "bridge-intake must stay dispatchable")
        inputs = dispatch.get("inputs") or {}
        mode = inputs.get("mode")
        self.assertIsInstance(mode, dict, "`mode` input missing")
        self.assertEqual(
            mode.get("type"),
            "choice",
            "`mode` must be `type: choice` — free-text input `run:`-এর shell-এ গিয়ে "
            "command injection বানাত (E2; BRIDGE_TOKEN সেই shell-এ থাকে)",
        )
        self.assertEqual(
            set(mode.get("options") or []),
            VALID_MODES,
            f"`mode` options must be exactly {sorted(VALID_MODES)}",
        )

    # ---- E2: no expression interpolation inside run blocks -------------------

    def test_no_expression_interpolation_in_run_blocks(self):
        for job_id, idx, step in _steps(self.doc):
            run = step.get("run")
            if run is None:
                continue
            for line_no, line in enumerate(str(run).splitlines(), 1):
                self.assertNotIn(
                    "${{",
                    line,
                    f"jobs.{job_id}.steps[{idx}] (run, line {line_no}) interpolates "
                    f"`{line.strip()}` — value-গুলো `env:` দিয়ে পাস করুন, shell-এ নয় (E2)",
                )

    # ---- E1/E3: fail-fast + single script invocation -------------------------

    def test_run_is_fail_fast_and_invokes_script_once_with_mode(self):
        run_steps = [
            (job_id, idx, step)
            for job_id, idx, step in _steps(self.doc)
            if "bridge_intake.py" in str(step.get("run") or "")
        ]
        self.assertEqual(
            len(run_steps),
            1,
            "bridge_intake.py-কে ঠিক একটি step থেকে একবারই চালানো উচিত — "
            "আলাদা intake/sync shell-if exit code চাপা দেয় (E1/E3)",
        )
        _, _, step = run_steps[0]
        run = str(step["run"])
        self.assertIn(
            "set -e",
            run,
            "run block must be fail-fast (`set -euo pipefail`) — নাহলে intake-র "
            "সৎ exit code step-এর শেষ command-এর কথায় মরে যায় (E1)",
        )
        self.assertIn(
            'bridge_intake.py "$MODE"',
            run,
            "script must receive the mode argument (`\"$MODE\"`) so bridge_intake.py "
            "main() validates it and propagates rc — অজানা মানে নীরব no-op নয় (E3)",
        )
        mode_env = (step.get("env") or {}).get("MODE", "")
        self.assertTrue(
            isinstance(mode_env, str) and mode_env.startswith("${{"),
            "MODE must reach the script via `env: MODE: ${{ ... }}` indirection (E2/E3)",
        )

    # ---- E4/E9: concurrency + timeout ---------------------------------------

    def test_concurrency_never_cancels_in_progress(self):
        concur = self.doc.get("concurrency") or {}
        self.assertIs(
            concur.get("cancel-in-progress"),
            False,
            "`cancel-in-progress: true` মাঝপথে orphan bridge-land branch ফেলে → "
            "retry-এর push non-fast-forward → ভ্যালিড অর্ডার ভুল করে rejected (E4)",
        )

    def test_job_has_timeout_minutes(self):
        for job_id, job in (self.doc.get("jobs") or {}).items():
            self.assertIn(
                "timeout-minutes",
                job,
                f"jobs.{job_id} needs `timeout-minutes` — বাঁধা রান concurrency "
                "queue চিরকাল আটকে রাখতে পারে (E4/E9)",
            )


class WatchdogNameCoupling(unittest.TestCase):
    """GUARD class: watchdog ↔ workflow name coupling (E10) — নীরব drift রোধ।"""

    def setUp(self):
        self.assertTrue(WATCHDOG_WORKFLOW.is_file(), "schedule-watchdog.yml missing")
        self.doc = _load(WATCHDOG_WORKFLOW)
        self.triggers = _triggers(self.doc)

    def _watched(self) -> list[str]:
        wr = self.triggers.get("workflow_run") or {}
        return [str(n) for n in (wr.get("workflows") or [])]

    def test_watched_names_resolve_to_real_workflows(self):
        watched = self._watched()
        self.assertTrue(watched, "watchdog must watch at least one workflow")
        known = {name: fname for name, fname in _workflow_names()}
        missing = [n for n in watched if n not in known]
        self.assertEqual(
            missing,
            [],
            "watchdog `workflow_run.workflows`-এ এই নামগুলো নেই: "
            f"{missing} — workflow-র `name:` বদলেছে কিন্তু watchdog-এর তালিকা যায়নি; "
            "GitHub শুধু নাম দেখে, তাই trigger নীরবে বন্ধ (E10)। "
            f"বিদ্যমান নাম: {sorted(known)}",
        )

    def test_watched_workflows_are_dispatchable(self):
        """compensation (`/dispatches`) শুধু workflow_dispatch-সম্পন্ন workflow-এ চলে।"""
        for name in self._watched():
            path = WORKFLOWS_DIR / next(
                fname for wname, fname in _workflow_names() if wname == name
            )
            self.assertIn(
                "workflow_dispatch",
                _triggers(_load(path)),
                f"{path.name} must keep `workflow_dispatch` — watchdog-এর compensation "
                "dispatch ওই উৎসেই চলে (E10)",
            )

    def test_workflow_names_are_unique(self):
        names = [n for n, _ in _workflow_names()]
        dupes = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(
            dupes,
            [],
            f"duplicate workflow `name:` {dupes} — workflow_run কোন workflow-র "
            "completion ধরছে তা অনির্দিষ্ট হয়ে যায় (E10)",
        )

    def test_guard_is_not_vacuous(self):
        """The scanner actually sees the known files (guards against empty scan)।"""
        names = dict(_workflow_names())
        self.assertIn("Bridge Intake (public work orders → private gates)", names)
        self.assertIn("Main CI/CD", names)
        self.assertIn("bridge-intake.yml", [f for _, f in _workflow_names()])
        self.assertIn(
            "Bridge Intake (public work orders → private gates)",
            self._watched(),
            "bridge-intake must stay watched — নাহলে guard নীরব হয়ে যায়",
        )


if __name__ == "__main__":
    unittest.main()
