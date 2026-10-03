# বাংলা মন্তব্য: #3095-রির্স্ট্রাকচার-পরবর্তী চুক্তি — ভ্যালিডেটর-মার্কার
# আর কখনো ডক-কাঠামোর সাথে নীরবে বিচ্যুত হবে না (এই পরীক্ষা ব্যর্থ হলেই ধরা পড়বে)।
"""generate_agents_md.py — মার্কার-তালিকা ↔ প্রকৃত ডক-কাঠামোর সমন্বয়-চুক্তি।"""
import subprocess
import sys
from pathlib import Path

from scripts.ci.generate_agents_md import AGENTS_REQUIRED_MARKERS, RULES_REQUIRED_MARKERS

ROOT = Path(__file__).resolve().parents[1]


def test_every_marker_actually_exists_in_current_docs():
    # বাংলা মন্তব্য: মার্কার-প্রতিটি বর্তমান ডকে বিদ্যমান — এটাই আগের ব্লকের রুট-কজ ছিল।
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    rules = (ROOT / "AGENT_RULES.md").read_text(encoding="utf-8")
    assert not [m for m in AGENTS_REQUIRED_MARKERS if m not in agents]
    assert not [m for m in RULES_REQUIRED_MARKERS if m not in rules]


def test_check_mode_passes():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci/generate_agents_md.py"), "--check"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    assert "[PASSED]" in r.stdout
