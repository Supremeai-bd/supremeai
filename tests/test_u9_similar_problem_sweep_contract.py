# বাংলা মন্তব্য (#4174, #2492): U9 Similar-Problem Sweep নিয়মের উপস্থিতি-চুক্তি।
# সমস্যা: agent-রা কোনো সমস্যা পেলে তাকে বিচ্ছিন্ন মনে করে একক ফিক্স করত,
# কিন্তু একই ত্রুটি-ক্লাসের ভাইবোন অন্যান্য ফাইলে ছড়িয়ে থাকত।
# এই চুক্তি-টেস্ট AGENT_RULES.md এবং agent_task.yml-এ U9 রুল নিশ্চিত করে।
"""#4174 — U9 Similar-Problem Sweep presence contract test."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

AGENT_RULES_U9_REQUIRED = [
    "## U9 — Similar-Problem Sweep / Pattern-Aware Resolution",
    "targeted sweep for sibling occurrences",
    "similar found: N | fixed in-task: M | filed follow-up: K",
    "U9 Sweep Mandate",
]


def test_agent_rules_contains_u9_sweep_rule():
    # বাংলা: AGENT_RULES.md-এ U9 সেকশন এবং কোডার ম্যান্ডেট বিদ্যমান থাকতে হবে।
    text = (ROOT / "AGENT_RULES.md").read_text(encoding="utf-8")
    missing = [m for m in AGENT_RULES_U9_REQUIRED if m not in text]
    assert not missing, f"AGENT_RULES.md U9 markers missing: {missing} (#4174)"


def test_agent_task_template_contains_u9_checkbox():
    # বাংলা: agent_task.yml টেমপ্লেটে U9 সুইপ চেকবক্স বৈধ YAML হিসেবে পার্স হতে হবে।
    raw = (ROOT / ".github" / "ISSUE_TEMPLATE" / "agent_task.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    assert data is not None, "agent_task.yml must be valid YAML"
    assert "U9 Similar-Problem Sweep" in raw, "agent_task.yml must contain U9 checkbox label"


def test_constitution_validator_passes():
    # বাংলা: নতুন U9 রুল generate_agents_md.py ভ্যালিডেটর অক্ষত রাখছে।
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/generate_agents_md.py"), "--check"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    assert "[PASSED]" in r.stdout
