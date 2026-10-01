# বাংলা মন্তব্য (#2893): cross-tier full backend suite গেটের স্থায়ী পিন-টেস্ট।
# PR Gate আগে শুধু changed-tier (critical/important মার্কার) চালাত — বাকি টিয়ারের stale
# assertion ধরা পড়ত না → "merge → red → fix" চক্র (#2728→#2829, #2874→#2888,
# #2733→#2833)। এই টেস্টগুলো pr.yml-এর full-backend-suite job-এর চুক্তি পিন করে —
# ভবিষ্যতে গেট সরালে বা দুর্বল করলে CI-তেই ধরা পড়বে (test_pr_gate_real_tests.py
# প্যাটার্ন অনুসরণ)।
#
# র্যাচেট-চুক্তি: main-এর পূর্ণ suite ১৭ failed + ২ collection-error বহন করে
# (বেসলাইন প্রমাণ HEAD 2fe47d42) — তাই "যেকোনো ফেইল = BLOCK" deadlock তৈরি করত।
# চুক্তি হলো known-red baseline (backend/full-suite-baseline.txt) ভুক্ত ফেইল = PASS,
# বাইরের ফেইল = BLOCK — সিদ্ধান্ত full_suite_ratchet_gate.py (knip-ratchet মতবাদ)।

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/pr.yml")
BASELINE = Path("backend/full-suite-baseline.json")
MARKER_CONTRACT = "not requires_network and not e2e and not chaos"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _dump(obj: object) -> str:
    # বাংলা মন্তব্য: width=১০⁶ — safe_dump ডিফল্টে col-80-এ লম্বা quoted scalar ভেঙে
    # ফেলে, substring পিন false-negative হয়; বিশাল width-এ সোর্স-লাইন অক্ষত থাকে।
    return yaml.safe_dump(obj, allow_unicode=True, width=10**6)


def _full_suite_job() -> dict:
    job = _workflow()["jobs"].get("full-backend-suite")
    assert isinstance(job, dict), "pr.yml-এ full-backend-suite job নেই (#2893 cross-tier gate)"
    return job


def test_full_backend_suite_job_present() -> None:
    # বাংলা মন্তব্য: issue-র স্পষ্ট নির্দেশ — changed-tier fast-path-এর পাশে আলাদা
    # "full backend suite" JOB (step নয়) থাকবে; contract job একে ব্লক-ডিসিশনে যুক্ত করবে।
    job = _full_suite_job()
    assert job.get("needs"), "full-backend-suite job-এ needs অনুপস্থিত"
    assert "context" in job["needs"], "context dependency অনুপস্থিত"
    assert "system-gates" in job["needs"], "system-gates dependency অনুপস্থিত"
    job_if = job.get("if") or ""
    assert "skip" in job_if, "bot-exempt skip condition অনুপস্থিত"


def test_full_suite_runs_complete_pytest_with_marker_contract() -> None:
    # বাংলা মন্তব্য: পূর্ণ suite = tests/ (backend রুট), মার্কার চুক্তি detect_changed_tests
    # ও ci.yml-এর অভিন্ন (requires_network/e2e/chaos hosted CI-তে চলে না);
    # --timeout=60 প্রতি-টেস্ট হ্যাং রক্ষাকাচী (pytest-timeout locked dep)।
    job_yaml = _dump(_full_suite_job())
    assert "pytest tests/" in job_yaml, "পূর্ণ suite pytest টার্গেট অনুপস্থিত"
    assert MARKER_CONTRACT in job_yaml, "মার্কার চুক্তি অনুপস্থিত — CI-অযোগ্য টেস্ট চলে যাবে"
    assert "--timeout=60" in job_yaml, "per-test timeout অনুপস্থিত"
    assert "--no-cov" in job_yaml, "coverage বাদ — এটি ci.yml aggregate gate-এর দায়িত্ব"
    assert "poetry run pytest" in job_yaml, "poetry runner অনুপস্থিত"


def test_no_first_fail_short_circuit() -> None:
    # বাংলা মন্তব্য: প্রথম-ফেইলে-থামো ফ্ল্যাগ নিষিদ্ধ — র্যাচেট তুলনার জন্য সম্পূর্ণ
    # ফেইল-সেট দরকার; প্রথম ফেইলে থামলে নতুন-বনাম-known-red পার্থক্য অসম্ভব
    # (known-red প্রথম পড়লে নতুন ফেইল অদেখা থেকে যায় = গেট ফাঁদ)। job-স্কোপড
    # যাচাই — রিপোর অন্যত্র (targeted fast-path) বৈধভাবে first-fail চলতে পারে।
    job_yaml = _dump(_full_suite_job())
    assert "-x --no-cov" not in job_yaml, "প্রথম-ফেইলে-থামো ফ্ল্যাগ র্যাচেট তুলনা ভাঙে"
    assert "--timeout=60 --no-cov -q" in job_yaml, "suite invocation চুক্তি বদলে গেছে"


def test_ratchet_gate_wired_with_fail_closed_contract() -> None:
    # বাংলা মন্তব্য: সিদ্ধান্ত full_suite_ratchet_gate.py-এর — pytest output ফাইল + RC
    # দিয়ে; baseline ফাইল থাকতেই হবে; গেট fail-closed (infra-rc/অসঙ্গতিতে ব্লক)।
    job_yaml = _dump(_full_suite_job())
    assert "full_suite_ratchet_gate.py" in job_yaml, "র্যাচেট গেট স্ক্রিপ্ট wired নয়"
    assert "--pytest-rc" in job_yaml, "pytest RC গেটে যাচ্ছে না — fail-closed চুক্তি ভাঙবে"
    assert "full-suite-baseline.json" in job_yaml, "baseline ফাইল রেফারেন্স অনুপস্থিত"
    assert "full_suite_output.txt" in job_yaml, "আউটপুট ক্যাপচার অনুপস্থিত — গেট পার্স করবে কী?"


def test_baseline_snapshot_committed_and_wellformed() -> None:
    # বাংলা মন্তব্য: baseline ফাইল রিপোতেই থাকতে হবে (gitignore *-baseline.json-এর
    # নিগেশন-ব্যতিক্রম, knip প্যাটার্ন); known_red প্রতিটি এন্ট্রি tests/-প্রিফিক্সড bare
    # node-id (গেটের পার্সিং চুক্তি) — ভাঙা এন্ট্রি থাকলে গেট মিথ্যা ব্লক/মিথ্যা পাস করবে।
    import json

    assert BASELINE.is_file(), "backend/full-suite-baseline.json রিপোতে নেই"
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    known_red = data.get("known_red")
    assert isinstance(known_red, list) and known_red, "known_red অ্যারে অনুপস্থিত/শূন্য"
    for entry in known_red:
        assert isinstance(entry, str) and entry.startswith("tests/"), (
            f"baseline এন্ট্রি tests/ প্রিফিক্সড নয়: {entry}"
        )


def test_full_suite_path_filtered_with_backend_setup() -> None:
    # বাংলা মন্তব্য: merge-base path-filter চুক্তি — docs/infra-only PR স্কিপ (দ্রুত
    # পাস), backend/tests স্পর্শলেই পূর্ণ suite; poetry env setup-backend action দিয়ে।
    job_yaml = _dump(_full_suite_job())
    assert "merge-base" in job_yaml, "merge-base diff লজিক অনুপস্থিত"
    assert "backend/|tests/" in job_yaml, "backend path-filter অনুপস্থিত"
    assert "./.github/actions/setup-backend" in job_yaml, "setup-backend action অনুপস্থিত"
    assert "PYTHONPATH" in job_yaml, "PYTHONPATH=.. অনুপস্থিত — scripts প্যাকেজ ইমপোর্ট ভাঙবে"


def test_contract_job_blocks_on_full_suite_failure() -> None:
    # বাংলা মন্তব্য: contract (Unified PR Decision) full-backend-suite ফল দেখবে —
    # failure হলে BLOCK (লাল main-এ merge নিষিদ্ধ), skipped (non-backend PR) বৈধ।
    data = _workflow()
    contract = data["jobs"]["contract"]
    assert "full-backend-suite" in (contract.get("needs") or []), (
        "contract job full-backend-suite-কে needs-এ রাখে না — গেট প্রভাবহীন"
    )
    contract_yaml = _dump(contract)
    assert "FULL_SUITE_RESULT" in contract_yaml, "full suite result যাচাই অনুপস্থিত"
    assert "skipped" in contract_yaml, "non-backend PR-এর skipped-বৈধতা অনুপস্থিত — সব PR মিথ্যা লাল হবে"


def test_changed_tier_fast_path_not_removed() -> None:
    # বাংলা মন্তব্য: নতুন গেট fast-path প্রতিস্থাপন করে না — targeted/tier রানার অক্ষত
    # (issue: "the changed-tier fast-path remains for quick feedback")।
    tests_job_yaml = _dump(_workflow()["jobs"]["tests"])
    assert "detect_changed_tests.py" in tests_job_yaml, "targeted selector সরানো হয়েছে"
    assert "Real backend code tests" in tests_job_yaml, "targeted pytest সরানো হয়েছে"
