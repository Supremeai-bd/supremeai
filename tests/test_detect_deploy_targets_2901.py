"""#2901 চুক্তি-টেস্ট: deploy-train per-service changed-path detection।

ফরেনসিক প্রেক্ষাপট (#2901 অডিট, run 36733864600 + main run 36912107865):
deploy-train-এর service-selection বাইনারি — core+worker প্রতি push-এ
অপ্রয়োজনীয় redeploy (কোটা অপচয়), scraper/mcp/cloudflare কখনোই auto-deploy
হয় না। এই টেস্ট `scripts/ci/detect_deploy_targets.py`-এর ম্যাপিং চুক্তি
আর স্বয়ং deploy-train.yml-এর job-graph অখণ্ডতা স্থির করে।

নিয়ম (repo প্যাটার্ন):
- classify_paths হলো pure ফাংশন — I/O নেই, তাই এখানেই হুবহু shipped লজিক চলে।
- Workflow চুক্তি PyYAML দিয়ে পার্স করা হয় (কাঁচা টেক্সট নয়) — কারণ টুলিং
  পাইপলাইনে literal `` বাইট-জোড়া গিলে ফেলার নথিভুক্ত প্রদর্শন-আর্টিফ্যাক্ট
  আছে (#2862 ফরেনসিক); PyYAML list/dict-repr সেই আর্টিফ্যাক্ট-মুক্ত।
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from detect_deploy_targets import classify_paths

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-train.yml"


# ─────────────────────────────────────────────────────────────────────────────
# ১. ম্যাপিং চুক্তি — পাথ → সার্ভিস
# ─────────────────────────────────────────────────────────────────────────────
class TestPathMapping:
    def test_docs_only_change_deploys_nothing(self):
        r = classify_paths(["docs/generated/x.json", "README.md", "docs/guide.md", "LICENSE"])
        assert r["deploy_core"] is False
        assert r["deploy_worker"] is False
        assert r["deploy_cloudflare"] is False
        assert r["deploy_needed"] is False
        assert r["noise_files"] == 4

    def test_backend_change_deploys_core_worker(self):
        r = classify_paths(["backend/api/routes.py", "backend/core/engine.py"])
        assert r["deploy_core"] is True
        assert r["deploy_worker"] is True
        assert r["deploy_needed"] is True

    def test_infra_change_deploys_cloudflare_only(self):
        r = classify_paths(["infrastructure/src/worker.ts"])
        assert r["deploy_cloudflare"] is True
        assert r["deploy_core"] is False
        assert r["deploy_worker"] is False

    def test_frontend_only_change_deploys_nothing_on_render(self):
        r = classify_paths(["frontend/src/app.tsx", "client/x.ts", "apps/mission-control/a.ts"])
        assert r["deploy_core"] is False
        assert r["deploy_worker"] is False
        assert r["deploy_cloudflare"] is False
        assert r["frontend_files"] == 3

    def test_mcp_adapters_change_adds_mcp_and_backend(self):
        r = classify_paths(["backend/mcp_adapters/client.py"])
        assert r["deploy_mcp"] is True
        # mcp_adapters backend-গাছের ভেতরে — core/worker-ও সতর্কভাবে ডিপ্লয় হয়
        assert r["deploy_core"] is True
        assert r["deploy_worker"] is True

    def test_root_mcp_json_adds_mcp(self):
        r = classify_paths(["mcp.json"])
        assert r["deploy_mcp"] is True

    def test_ci_scripts_tests_only_change_deploys_nothing(self):
        r = classify_paths(
            [".github/workflows/main.yml", "scripts/ci/gate.py", "tests/test_x.py", "qa/smoke.ts"]
        )
        assert r["deploy_needed"] is False
        assert r["deploy_core"] is False

    def test_unknown_path_conservative_core_worker(self):
        # fail-open: অম্যাপড পাথ → স্থির চুক্তি অনুযায়ী core+worker (স্টেল প্রোড নিষেধ)
        r = classify_paths(["some_new_service/main.py"])
        assert r["deploy_core"] is True
        assert r["deploy_worker"] is True
        assert r["unknown_files"] == 1
        assert r["unknown_examples"] == ["some_new_service/main.py"]

    def test_empty_diff_deploys_nothing(self):
        r = classify_paths([])
        assert r["deploy_needed"] is False
        assert r["total"] == 0

    def test_mixed_change_is_union(self):
        r = classify_paths(
            [
                "backend/api/x.py",
                "infrastructure/wrangler.toml",
                "README.md",
                "frontend/src/a.ts",
            ]
        )
        assert r["deploy_core"] is True
        assert r["deploy_worker"] is True
        assert r["deploy_cloudflare"] is True
        assert r["deploy_mcp"] is False

    def test_backend_md_is_noise_not_backend(self):
        # backend-গাছের ডক-ফাইলও নয়েজ — backend/README.md বদলালে কোটা নষ্ট হবে না
        r = classify_paths(["backend/README.md"])
        assert r["deploy_needed"] is False

    def test_normalizes_leading_dot_slash(self):
        r = classify_paths(["./backend/api/x.py"])
        assert r["deploy_core"] is True


# ─────────────────────────────────────────────────────────────────────────────
# ২. Workflow job-graph চুক্তি (PyYAML — আর্টিফ্যাক্ট-প্রমাণ)
# ─────────────────────────────────────────────────────────────────────────────
class TestDeployTrainWiring:
    @classmethod
    def setup_class(cls):
        cls.graph = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.jobs = cls.graph["jobs"]

    def test_detect_changes_job_exists_with_outputs(self):
        job = self.jobs["detect-changes"]
        outs = job["outputs"]
        for key in (
            "deploy-core",
            "deploy-worker",
            "deploy-scraper",
            "deploy-mcp",
            "deploy-cloudflare",
        ):
            assert key in outs, f"detect-changes outputs-এ {key} নেই"

    def test_core_worker_gated_by_detection(self):
        for svc in ("deploy-core", "deploy-worker"):
            job = self.jobs[svc]
            needs = job["needs"] if isinstance(job["needs"], list) else [job["needs"]]
            assert "detect-changes" in needs, f"{svc} needs-এ detect-changes নেই"
            key = "deploy-core" if svc == "deploy-core" else "deploy-worker"
            assert (
                f"needs.detect-changes.outputs.{key} == 'true'" in job["if"]
            ), f"{svc} if-এ detection গেট নেই"

    def test_selective_services_use_detection_outputs(self):
        for svc, key in (
            ("deploy-scraper", "deploy-scraper"),
            ("deploy-mcp", "deploy-mcp"),
            ("deploy-cloudflare-worker", "deploy-cloudflare"),
        ):
            cond = self.jobs[svc]["if"]
            assert (
                f"needs.detect-changes.outputs.{key} == 'true'" in cond
            ), f"{svc} এখনও detection-আউটপুট দেখছে না"

    def test_quota_preflight_present_on_all_render_services(self):
        # ফাঁক ৩ বন্ধ হচ্ছে কি না: scraper/mcp জবেও কোটা প্রিফ্লাইট থাকতে হবে
        for svc in ("deploy-core", "deploy-worker", "deploy-scraper", "deploy-mcp"):
            steps = self.jobs[svc]["steps"]
            names = [s.get("name", "") for s in steps]
            assert any("quota preflight" in n for n in names), f"{svc}-এ quota preflight নেই"
            runs = [s.get("run", "") for s in steps]
            assert any(
                "render_deploy_preflight.py" in r for r in runs
            ), f"{svc}-এ render_deploy_preflight.py নেই"

    def test_canary_chain_unchanged(self):
        # স্কিপ-ক্যাসকেড সঠিক: skipped ≠ success → canary নিজে থেকেই স্কিপ হবে
        assert set(self.jobs["canary-check"]["needs"]) == {"deploy-core", "deploy-worker"}
        assert "needs.deploy-core.result == 'success'" in self.jobs["canary-check"]["if"]
