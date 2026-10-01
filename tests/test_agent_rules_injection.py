# বাংলা মন্তব্য: #2841 PR-4 — AGENT_RULES.md পার্সার + রোল-অ্যালিয়াস চুক্তি-টেস্ট।
"""রুল-ইনজেকশন সোর্স-সুইচ চুক্তি: AGENT_RULES.md প্রাথমিক উৎস, rules.yml শুধু fallback।

- পুরনো লেন-নাম (ci_devops, platform, rules_breaker...) অ্যালিয়াসে ৭-রোলে পৌঁছায়
- ভাগ-সীমা লিক-প্রুফ (ভাগ ৩-এর বুলেট রোল-সেকশনে ঢুকবে না)
- AGENT_RULES.md অনুপস্থিত হলে লুপ ভাঙে না — rules.yml fallback
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.agents.continuous_agent_loop as loop  # noqa: E402
from scripts.agents.continuous_agent_loop import (  # noqa: E402
    ROLE_ALIASES,
    _parse_agent_rules_md,
)

SAMPLE = """## ভাগ ২: ৭টি স্পেশালাইজড রোলের টাস্ক-স্পেসিফিক রুলস

### রোল: coder (কোডার এজেন্ট)
- ব্যাকলগ থেকে হাই-প্রায়োরিটি ইস্যু ক্লেইম করে কোড লেখা।
- হার্ডকোডেড সিক্রেট নিষিদ্ধ — ব্রোকার টোকেন বাধ্যতামূলক।

### রোল: breaker (রুল-ব্রেকার)
- এক্সট্রিম কেস-এ ভাঙার চেষ্টা।
- ফিক্স বাস্তবায়ন নয় — শুধু ফাঁক খোঁজা।

## ভাগ ৩: ব্রাঞ্চিং, PR ও লেবেল শৃঙ্খলা

- ভাগ-৩-এর এই বুলেট কোনো রোল-সেকশনে ঢুকতে পারবে না।
"""


def test_direct_role_parsed():
    a, p = _parse_agent_rules_md(SAMPLE, "coder")
    assert len(a) == 2, "coder-এর ২টি বুলেটই রুল"
    assert any("নিষিদ্ধ" in x for x in p), "'নিষিদ্ধ'-বুলেট prohibited-এ যায়"


def test_old_role_names_via_alias():
    # পুরনো rules.yml নাম (super_agent, rules_breaker) একই ক্যানোনিকাল সেকশনে পৌঁছায়
    a_super, _ = _parse_agent_rules_md(SAMPLE, "super_agent")
    a_direct, _ = _parse_agent_rules_md(SAMPLE, "coder")
    assert a_super == a_direct
    a_breaker, _ = _parse_agent_rules_md(SAMPLE, "rules_breaker")
    assert any("ভাঙার" in x for x in a_breaker)


def test_unknown_role_empty_not_crash():
    a, p = _parse_agent_rules_md(SAMPLE, "no-such-role")
    assert a == [] and p == []


def test_section_boundary_respected():
    # ভাগ ৩-এর বুলেট কারো রোল-সেকশনে লিক হবে না
    for role in ("coder", "breaker", "super_agent", "rules_breaker"):
        a, _ = _parse_agent_rules_md(SAMPLE, role)
        assert all("ভাগ-৩-এর" not in x for x in a), f"{role}-এ ভাগ ৩ লিক!"


def test_alias_map_covers_legacy_lanes():
    # চলমান পুরনো লেন-নামগুলো সবই ক্যানোনিকাল ৭-রোলে ম্যাপ হয়
    canonical = {"coder", "auditor", "planner", "ci-fixer", "watcher", "human-eyes", "breaker"}
    for legacy in ("ci_devops", "pr_helper", "platform", "browser", "ecosystem_scout"):
        assert ROLE_ALIASES.get(legacy) in canonical, f"{legacy} ম্যাপ হয়নি!"


def test_primary_source_wins(tmp_path, monkeypatch):
    # AGENT_RULES.md থাকলে সেটাই উৎস — rules.yml-এ কারো হাত দেওয়া লাগে না
    f = tmp_path / "AGENT_RULES.md"
    f.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(loop, "AGENT_RULES_PATH", f)
    a, _ = loop._load_agent_rules("coder")
    assert any("ক্লেইম" in x for x in a), "প্রাথমিক উৎস (AGENT_RULES.md) কার্যকর হয়নি"


def test_fallback_when_md_absent(monkeypatch):
    # ফাইল না থাকলে (PR-1 মার্জের আগের অবস্থা) rules.yml fallback — লুপ ভাঙে না
    monkeypatch.setattr(loop, "AGENT_RULES_PATH", Path("/nonexistent/AGENT_RULES.md"))
    a, p = loop._load_agent_rules("coder")
    assert (a, p) == loop._load_agent_rules_yaml("coder")
    assert a, "rules.yml fallback-ও ফাঁকা ফিরিয়েছে — উৎস-চেইন ভাঙা!"
