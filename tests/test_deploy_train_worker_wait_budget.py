"""#4037 চুক্তি-টেস্ট: deploy-train Deploy Worker wait-budget বাস্তবতার সাথে।

ফরেনসিক প্রেক্ষাপট (run 37413526850, job 112107654656):
`🚀 Deploy Worker` — deploy dep-db27h2rbc2fs73fi2osg স্বাভাবিক চলছিল
(build_in_progress ~7m → update_in_progress ≥4m), কিন্তু render-deploy-status-এর
ডিফল্ট `wait-timeout-seconds: 660` (11m) শেষ হয়ে যায় → false-red +
Station 3/4/5 (canary/rollback/tag) স্কিপ। Render free-tier-এ Worker build-সময়ের
variance-এ 660s প্রায়ই হারে।

নিরাময় (#4037): deploy-worker job-ছাদ 15→25 মিনিট + step-input
`wait-timeout-seconds: '1080'` (18m poll)।

চুক্তি-স্তর (repo প্যাটার্ন, PyYAML-পার্স — #2862 আর্টিফ্যাক্ট-মুক্ত):
- টিয়ার-২: worker-বাজেট রেগ্রেশন-গার্ড — কেউ আবার 660/15-এ নামালে ধরা পড়বে
- টিয়ার-৩: scope-isolation — core/scraper/mcp-এর বাজেট অপরিবর্তিত (ডিফল্ট),
  অর্থাৎ এই fix-এর ব্লাস্ট-রেডিয়াস শুধু worker
- গাণিতিক সামঞ্জস্য: poll-budget + সেটআপ-overhead জব-ছাদের ভেতরে থাকতে হবে
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-train.yml"

# #4037-এর নির্ধারিত চুক্তি-মান
WORKER_WAIT_SECONDS = 1080
WORKER_JOB_CEILING_MINUTES = 25
# সেটআপ-overhead: checkout + ৩টি Infisical ইমপোর্ট + ২টি গার্ড (run 37413526850:
# job-start 04:24 → deploy-step 04:26:51 ≈ 2-3 মিনিট; রক্ষণশীল 5 মিনিট ধরা)
SETUP_OVERHEAD_MINUTES = 5


def _jobs() -> dict:
    graph = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return graph["jobs"]


def _render_step(job: dict) -> dict:
    for step in job["steps"]:
        if "render-deploy-status" in str(step.get("uses", "")):
            return step
    raise AssertionError("render-deploy-status step পাওয়া যায়নি")


# ─────────────────────────────────────────────────────────────────────────────
# ১. Worker-বাজেট চুক্তি (Tier-2 regression guard)
# ─────────────────────────────────────────────────────────────────────────────
class TestWorkerWaitBudget:
    def setup_class(cls):
        cls.jobs = _jobs()
        cls.worker = cls.jobs["deploy-worker"]

    def test_worker_wait_timeout_explicitly_raised(self):
        wt = _render_step(self.worker)["with"]["wait-timeout-seconds"]
        assert int(wt) >= WORKER_WAIT_SECONDS, (
            f"Deploy Worker poll-budget {wt}s < {WORKER_WAIT_SECONDS}s — "
            "#4037-এর আগের 660s false-red-এ ফেরার পথ"
        )

    def test_worker_job_ceiling_accommodates_poll_budget(self):
        ceiling = int(self.worker["timeout-minutes"])
        assert ceiling >= WORKER_JOB_CEILING_MINUTES, (
            f"job-ছাদ {ceiling}m < {WORKER_JOB_CEILING_MINUTES}m — poll শেষ হওয়ার "
            "আগেই job মরবে (গার্ড-ছাড়া early-exit, ঠিক যেটা ঠিক করছি)"
        )

    def test_poll_plus_setup_fits_inside_job_ceiling(self):
        # গাণিতিক সামঞ্জস্য: 18m poll + 5m সেটআপ = 23m ≤ 25m ছাদ
        wt = int(_render_step(self.worker)["with"]["wait-timeout-seconds"])
        ceiling = int(self.worker["timeout-minutes"])
        assert wt / 60 + SETUP_OVERHEAD_MINUTES <= ceiling, (
            f"poll {wt}s + সেটআপ {SETUP_OVERHEAD_MINUTES}m > job-ছাদ {ceiling}m — "
            "বাজেট-ম্যাথ ভাঙা"
        )

    def test_worker_string_quoted_to_survive_yaml_bool_coercion(self):
        # YAML-1.1 শিক্ষা (#3731): unquoted সংখ্যা-স্ট্রিং input composite-action-এ
        # পৌঁছানোর আগেই coercion-ঝুঁকি — action.yml input সবসময় স্ট্রিং চায়
        wt = _render_step(self.worker)["with"]["wait-timeout-seconds"]
        assert isinstance(wt, str), "wait-timeout-seconds অবশ্যই quoted-string"


# ─────────────────────────────────────────────────────────────────────────────
# ২. Scope-isolation চুক্তি (Tier-3) — ব্লাস্ট-রেডিয়াস শুধু worker
# ─────────────────────────────────────────────────────────────────────────────
class TestScopeIsolation:
    def test_other_render_services_keep_default_budget(self):
        # core/scraper/mcp 660s ডিফল্টেই সবুজ ছিল (run 37413526850 + 37386932013) —
        # তাদের বদলানো এই PR-এর scope-এ নয়; নীরব পরিবর্তন রেগ্রেশন হিসেবে ধরা হবে
        jobs = _jobs()
        for svc in ("deploy-core", "deploy-scraper", "deploy-mcp"):
            step = _render_step(jobs[svc])
            assert "wait-timeout-seconds" not in step.get("with", {}), (
                f"{svc}-এ wait-timeout-seconds যোগ হয়েছে — #4037 শুধু worker-এর "
                "fix; অন্য সার্ভিসে সচেতন পরিবর্তন হলে এই চুক্তি-টেস্ট আগে আপডেট করুন"
            )

    def test_worker_concurrency_group_unchanged(self):
        # cancel-in-progress: false — সিরিয়ালাইজড নিরাপত্তা অপরিবর্তিত
        conc = _jobs()["deploy-worker"]["concurrency"]
        assert conc["group"] == "render-worker"
        assert conc["cancel-in-progress"] is False
