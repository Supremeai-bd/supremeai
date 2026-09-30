# বাংলা মন্তব্য: Issue Ops Storm প্রতিরোধের স্থায়ী গার্ড (#2425)।
# ২০২৬-০৯-২৭-এ ২টি ইস্যু তৈরিতে ৪ মিনিটে ১৩টি Issue Ops রান স্পন হয়েছিল এবং
# প্রায় সবগুলো cancel-in-progress-এ ১-২ সেকেন্ডে বাতিল হয়েছিল। এই টেস্টগুলো
# workflow-এর ট্রিগার-সারফেস চুক্তি পিন করে রাখে — ভবিষ্যতে কেউ filter সরালে
# বা cancel-in-progress: true ফিরিয়ে আনলে CI-তেই ধরা পড়বে।

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/issue-ops.yml")

# বাংলা মন্তব্য: queue-প্রাসঙ্গিক লেবেল — RANK ladder + fetch_unclaimed() exclusion
# সেট (scripts/agents/priority_queue_ledger.py এর সাথে সিঙ্কড)।
QUEUE_RELEVANT_LABELS = [
    "P0-critical",
    "P1-high",
    "P2-medium",
    "P3-low",
    "status:unclaimed",
    "status:in-progress",
    "status:planned",
]

# বাংলা মন্তব্য: storm-এর ইতিহাস থেকে নেওয়া non-relevant ট্যাগ — এগুলো রান স্পন করবে না।
STORM_LABELS = ["groq", "cerebras", "error-1010", "platform-sweep", "has-pr", "queue:hold"]


def _workflow() -> dict:
    # বাংলা মন্তব্য: on: কী YAML 1.1-এ boolean True হয়ে যায় — দুই কী-ই সামলাই।
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    trigger = data.get("on") if "on" in data else data.get(True)
    assert trigger is not None, "issue-ops.yml-এ on: ট্রিগার নেই"
    return data


def _refresh_ledger_if() -> str:
    job = _workflow()["jobs"]["refresh-ledger"]
    cond = job["if"]
    assert isinstance(cond, str) and cond.strip(), "refresh-ledger if: কন্ডিশন খালি"
    return cond


def test_event_filter_contains_queue_relevant_labels() -> None:
    # বাংলা মন্তব্য: priority + claim-state লেবেল বদলালে re-rank হবেই — founder
    # directive #1997 ("1st close howar por 2nd auto 1st hoa jabe") অক্ষত থাকে।
    cond = _refresh_ledger_if()
    for label in QUEUE_RELEVANT_LABELS:
        assert label in cond, f"queue-relevant লেবেল '{label}' ফিল্টারে নেই"


def test_event_filter_excludes_storm_labels() -> None:
    # বাংলা মন্তব্য: storm-এর মূল ট্রিগার ছিল non-priority ট্যাগ — এগুলো if-এ
    # উল্লেখ থাকলে সেগুলো ট্রিগার-হোয়াইটলিস্টে ঢুকে যায়, যা নিষিদ্ধ।
    cond = _refresh_ledger_if()
    for label in STORM_LABELS:
        assert label not in cond, f"storm লেবেল '{label}' ফিল্টারে ফিরে এসেছে"


def test_event_filter_keeps_membership_events() -> None:
    # বাংলা মন্তব্য: opened/closed/reopened সবসময় re-rank — কিউ-মেম্বারশিপ বদলায়।
    cond = _refresh_ledger_if()
    for action in ("opened", "closed", "reopened"):
        assert f"github.event.action == '{action}'" in cond
    # বাংলা মন্তব্য: labeled/unlabeled শুধু প্রাসঙ্গিক লেবেলে — contains(fromJSON(...))
    for action in ("labeled", "unlabeled"):
        assert f"github.event.action == '{action}'" in cond
    assert "contains(fromJSON(" in cond
    assert "github.event.label.name" in cond


def test_concurrency_is_non_flapping() -> None:
    # বাংলা মন্তব্য: cancel-in-progress: false — ক্যানসেলেশন থ্র্যাশিং বন্ধ; রানগুলো
    # serial চলে, শেষ রানেই সর্বশেষ state-এর সঠিক re-rank।
    job = _workflow()["jobs"]["refresh-ledger"]
    conc = job.get("concurrency") or {}
    assert conc.get("group") == "priority-queue-ledger"
    assert conc.get("cancel-in-progress") is False, (
        "cancel-in-progress: true থ্র্যাশিং ফিরিয়ে আনবে (#2425) — নিষিদ্ধ"
    )


def test_ledger_script_rank_labels_stay_in_sync() -> None:
    # বাংলা মন্তব্য: drift-guard — ledger স্ক্রিপ্টের RANK ladder-এ নতুন priority
    # লেবেল যোগ হলে এই টেস্ট ব্যর্থ হবে; তখন workflow ফিল্টারও আপডেট করতে হবে।
    import re

    script = Path("scripts/agents/priority_queue_ledger.py").read_text(encoding="utf-8")
    # বাংলা মন্তব্য: #2584 — drift-guard নিজেই annotation-style drift-এ ফেইল করছিল:
    # স্ক্রিপ্টে lowercase `dict[str, int]` (PEP 585), regex-এ typing-style `Dict`।
    # এখন দুই স্টাইলই গৃহীত — guard ভবিষ্যতে স্টাইল বদলালেও ভাঙবে না।
    match = re.search(r"RANK:\s*[Dd]ict\[str,\s*int\]\s*=\s*\{([^}]*)\}", script)
    assert match, "priority_queue_ledger.py-তে RANK dict পাওয়া যায়নি"
    ranked = set(re.findall(r'"([^"]+)"\s*:', match.group(1)))
    cond = _refresh_ledger_if()
    for label in ranked:
        assert label in cond, f"RANK ladder-এর '{label}' workflow ফিল্টারে নেই (drift)"
