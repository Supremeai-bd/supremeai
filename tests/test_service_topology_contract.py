"""Service Topology SSOT contract tests (#4246 Phase 1).

বাংলা: ফাউন্ডার নির্দেশনা — "আমি MCP tower বা core tower চিনি না; সিস্টেম
নিজেই জানবে।" এই টেস্ট-সেট স্থির করে:

  ১. config/service_topology.yaml = বৈধ, সম্পূর্ণ রেজিস্ট্রি (প্রতি সার্ভিসের
     platform/deploy_key/watch_paths চুক্তি মেনে)
  ২. detect_deploy_targets.py রেজিস্ট্রি-চালিত — লাইভ-বাগ রিগ্রেশন সহ:
     infrastructure/mcp-control-plane/** → mcp (cloudflare নয়)
  ৩. deploy-train.yml-এ vercel/firebase স্টেশন detect-changes-আউটপুট-গেটেড
  ৪. smart-deploy.yml soft-retired — schedule নেই, নিজস্ব deploy-লজিক নেই
  ৫. Rule 10 meta-test: নতুন স্টেশনের deploy-লাইনে `|| true` ফাঁদ-সবুজ নেই
     (comment-line স্ট্রিপ করে — doctrine-মন্তব্যে লিটারাল থাকলে মিথ্যা লাল নয়)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from detect_deploy_targets import SERVICE_KEYS, classify_paths, load_topology  # noqa: E402

TOPOLOGY = REPO_ROOT / "config" / "service_topology.yaml"
DEPLOY_TRAIN = REPO_ROOT / ".github" / "workflows" / "deploy-train.yml"
SMART_DEPLOY = REPO_ROOT / ".github" / "workflows" / "smart-deploy.yml"
VALID_PLATFORMS = {"render", "cloudflare", "vercel", "firebase", "none"}


def _code_lines(text: str) -> str:
    """Comment-only লাইন বাদ — meta-test মিথ্যা-লাল প্রতিষেধ (plan-gov-10 lesson)।"""
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )


class TopologyRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topo = yaml.safe_load(TOPOLOGY.read_text(encoding="utf-8"))
        cls.services = cls.topo["services"]

    def test_parses_with_version_and_unknown_policy(self):
        self.assertEqual(self.topo["version"], 1)
        self.assertEqual(self.topo["unknown_policy"], "conservative-backend")

    def test_every_service_declares_valid_platform_and_key(self):
        for key, svc in self.services.items():
            self.assertIn(svc["platform"], VALID_PLATFORMS, f"{key}: platform invalid")
            self.assertEqual(svc["deploy_key"], key, f"{key}: deploy_key mismatch")

    def test_detector_service_keys_cover_topology_exactly(self):
        topo_keys = {f"deploy_{k}" for k in self.services}
        self.assertEqual(topo_keys, set(SERVICE_KEYS))

    def test_manual_only_service_has_empty_watch(self):
        manual = [k for k, s in self.services.items() if s.get("manual_only")]
        self.assertIn("scraper", manual)
        for k in manual:
            self.assertEqual(self.services[k]["watch_paths"], [])

    def test_load_topology_fail_closed_on_missing(self):
        with self.assertRaises(SystemExit):
            load_topology("/nonexistent/service_topology.yaml")


class DetectorTopologyBehaviorTests(unittest.TestCase):
    """লাইভ-বাগ রিগ্রেশন (#4246 case study: run #392, PR #4238)।"""

    @classmethod
    def setUpClass(cls):
        cls.topo = load_topology()

    def test_mcp_control_plane_deploys_mcp_not_cloudflare(self):
        r = classify_paths(["infrastructure/mcp-control-plane/server.py"], self.topo)
        self.assertTrue(r["deploy_mcp"])
        self.assertFalse(r["deploy_cloudflare"])
        self.assertFalse(r["deploy_core"])

    def test_other_infrastructure_still_cloudflare(self):
        r = classify_paths(["infrastructure/src/worker.ts"], self.topo)
        self.assertTrue(r["deploy_cloudflare"])
        self.assertFalse(r["deploy_mcp"])

    def test_frontend_paths_trigger_vercel_station(self):
        r = classify_paths(["frontend/src/app.tsx"], self.topo)
        self.assertTrue(r["deploy_frontend"])
        self.assertFalse(r["deploy_core"])

    def test_firebase_rules_trigger_firebase_station(self):
        # বাংলা (#4269): বাস্তব rules/indexes SSOT = firebase/ (config/ টপোলজি-noise-
        # prefix, সেখানকার পাথ detector watch-match-এ পৌঁছায় না); রুট-লেভেল
        # firestore.rules ছিল টপোলজি-ড্রিফট (ফাইল রুটে নেই)।
        r = classify_paths(["firebase/firestore.rules"], self.topo)
        self.assertTrue(r["deploy_firebase"])
        r2 = classify_paths(["firebase/firebase.json", "firebase/firestore.indexes.json"], self.topo)
        self.assertTrue(r2["deploy_firebase"])
        # নয়েজ-চুক্তি অটুট: config/-অন্যান্য ফাইল এখনো কোনো স্টেশন ট্রিগার করে না।
        r3 = classify_paths(["config/agent_rules.json"], self.topo)
        self.assertFalse(r3["deploy_firebase"])
        self.assertTrue(r3["deploy_needed"] is False or r3["noise_files"] + r3["unknown_files"] >= 1)

    def test_backend_change_deploys_core_worker_as_before(self):
        r = classify_paths(["backend/api/x.py"], self.topo)
        self.assertTrue(r["deploy_core"] and r["deploy_worker"])
        self.assertEqual(r["backend_files"], 1)  # এক পাথ = একবার কাউন্ট (doubled নয়)

    def test_noise_still_deploys_nothing(self):
        r = classify_paths(["docs/x.md", ".github/workflows/a.yml"], self.topo)
        self.assertFalse(r["deploy_needed"])

    def test_unknown_path_still_conservative_core_worker(self):
        r = classify_paths(["brand_new_tower/main.py"], self.topo)
        self.assertTrue(r["deploy_core"] and r["deploy_worker"])
        self.assertEqual(r["unknown_files"], 1)


class DeployTrainStationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = yaml.safe_load(DEPLOY_TRAIN.read_text(encoding="utf-8"))
        cls.jobs = cls.graph["jobs"]
        # YAML 1.1 ফাঁদ: `on` কী True হয়ে পার্স হতে পারে
        on = cls.graph.get("on", cls.graph.get(True, {}))
        cls.triggers = on

    def test_vercel_and_firebase_stations_exist(self):
        self.assertIn("deploy-vercel", self.jobs)
        self.assertIn("deploy-firebase", self.jobs)

    def test_stations_gated_by_detect_changes_outputs(self):
        vcond = self.jobs["deploy-vercel"]["if"]
        fcond = self.jobs["deploy-firebase"]["if"]
        self.assertIn("needs.detect-changes.outputs.deploy-frontend == 'true'", vcond)
        self.assertIn("needs.detect-changes.outputs.deploy-firebase == 'true'", fcond)

    def test_detect_job_exposes_new_outputs(self):
        outs = self.jobs["detect-changes"]["outputs"]
        self.assertIn("deploy-frontend", outs)
        self.assertIn("deploy-firebase", outs)

    def test_inputs_declared_on_both_triggers(self):
        for trig in ("workflow_call", "workflow_dispatch"):
            inputs = self.triggers[trig]["inputs"]
            self.assertIn("deploy-frontend", inputs, f"{trig}: deploy-frontend missing")
            self.assertIn("deploy-firebase", inputs, f"{trig}: deploy-firebase missing")

    def test_new_stations_declare_production_environment(self):
        for job in ("deploy-vercel", "deploy-firebase"):
            self.assertEqual(self.jobs[job]["environment"]["name"], "production")


class SmartDeployRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SMART_DEPLOY.is_file():
            raise unittest.SkipTest("smart-deploy.yml retired")
        cls.graph = yaml.safe_load(SMART_DEPLOY.read_text(encoding="utf-8"))
        cls.jobs = cls.graph["jobs"]
        on = cls.graph.get("on", cls.graph.get(True, {}))
        cls.triggers = on

    def test_schedule_trigger_removed(self):
        # Rule 9: টাইম-উইন্ডো ডিপ্লয় অবসর — schedule কী থাকবে না (comment-ও নয়:
        # PyYAML পার্সের পরেও অবশ্যই অনুপস্থিত)
        self.assertNotIn("schedule", self.triggers)

    def test_dispatch_only_with_deploy_train_delegate(self):
        self.assertIn("workflow_dispatch", self.triggers)
        jobs_using_call = [
            name for name, j in self.jobs.items() if "uses" in j
            and str(j["uses"]).startswith("./.github/workflows/deploy-train.yml")
        ]
        self.assertTrue(jobs_using_call, "smart-deploy must delegate to deploy-train")

    def test_no_duplicate_detect_or_platform_jobs(self):
        # পুরনো দ্বৈত পথ — detect-and-deploy/deploy-vercel/deploy-firebase/deploy-render সরানো
        for gone in ("detect-and-deploy", "deploy-render", "deploy-vercel", "deploy-firebase"):
            self.assertNotIn(gone, self.jobs, f"{gone} duplicate job must be retired")

    def test_time_window_literal_absent_from_code(self):
        # `4 hours ago` টাইম-উইন্ডো ডিটেকশনের শেষ — কোডলাইনে আর থাকবে না
        raw = SMART_DEPLOY.read_text(encoding="utf-8")
        self.assertNotIn("4 hours ago", _code_lines(raw))

    def test_vercel_deploy_step_has_no_false_green_swallow(self):
        # Rule 10: deploy-train-এর vercel স্টেশনে `vercel deploy ... || true` নিষিদ্ধ
        raw = DEPLOY_TRAIN.read_text(encoding="utf-8")
        code = _code_lines(raw)
        for line in code.splitlines():
            if "vercel deploy" in line:
                self.assertFalse(
                    line.rstrip().endswith("|| true"),
                    f"false-green swallow found: {line.strip()}",
                )


if __name__ == "__main__":
    unittest.main()
