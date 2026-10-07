# বাংলা মন্তব্য (#4177, #2492): বোর্ড-ফ্রেশনেস নিয়মের অনুপস্থিতি-চুক্তি।
# সমস্যা: agent-রা task-শুরুর snapshot-কেই পুরো mission ধরে নিত — কাজের মাঝে
# নতুন PR/issue এলে "done" ঘোষণার আগে আর re-check করত না (founder-directive,
# 2026-10-07)। এই চুক্তি-টেস্ট AGENTS.md + AGENT_RULES.md-উভয়েই নিয়ম-টেক্সট
# আছে তা assert করে — কেউ নীরবে সরিয়ে দিলে টেস্টই ধরে ফেলবে (false-green নয়)।
"""#4177 — board-freshness completion rule presence-contract for the 2-file constitution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# বাংলা: প্রতিটি marker = নিয়মের একটি অপরিহার্য প্রান্ত। যেকোনো একটি উধাও হলে
# চুক্তি ভাঙল — টেস্ট ব্যর্থ হবে এবং PR-gate লাল দেখাবে।
AGENTS_MD_REQUIRED = [
    "Board-freshness rule (#4177)",
    "BOARD-FRESHNESS RE-CHECK (#4177",
    "fresh-board re-check",
]

AGENT_RULES_REQUIRED = [
    "Board-freshness at completion (#4177)",
    "board has been re-checked for new arrivals since task start",
    "Real-time board maintenance (#4177)",
    "board re-checked at HH:MMZ",
]


def test_agents_md_contains_board_freshness_rule():
    # বাংলা: AGENTS.md-তে লুপ-ধাপ ৮ + lifecycle + ব্যাখ্যা-অনুচ্ছেদ — তিন প্রান্তই থাকতে হবে।
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    missing = [m for m in AGENTS_MD_REQUIRED if m not in text]
    assert not missing, f"AGENTS.md board-freshness markers missing: {missing} (#4177)"


def test_agent_rules_md_contains_board_freshness_rule():
    # বাংলা: AGENT_RULES.md-তে U5 (completion-freshness) + U7 (completion-condition)
    # + U8 (exit-report statement) — তিন প্রান্তই থাকতে হবে।
    text = (ROOT / "AGENT_RULES.md").read_text(encoding="utf-8")
    missing = [m for m in AGENT_RULES_REQUIRED if m not in text]
    assert not missing, f"AGENT_RULES.md board-freshness markers missing: {missing} (#4177)"


def test_rule_survives_marker_validation():
    # বাংলা: নতুন নিয়ম generate_agents_md.py-র 2-file মডেল ভাঙছে না — validator সবুজ।
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/generate_agents_md.py"), "--check"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    assert "[PASSED]" in r.stdout
