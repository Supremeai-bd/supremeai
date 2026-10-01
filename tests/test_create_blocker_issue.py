# বাংলা মন্তব্য (#2856 ফলো-আপ): অনাথ-টেস্ট মাইগ্রেশন-শিম।
# create_blocker_issue.py / create_discovery_issue.py একত্রীকরণের (dedup) পর
# পুরনো টেস্টটি মুছে-ফেলা মডিউল ইমপোর্ট করছিল → collection-error → CI লাল।
# Test Guard টেস্ট-ফাইল ডিলিট ব্লক করে (নীতিগতভাবে সঠিক), তাই ফাইলটি থেকে
# যাবে — এখন এটি create_issue.py-এর **legacy API-সংরক্ষণ চুক্তি** যাচাই করে:
# পুরনো ভোক্তাদের জন্য ফাংশন-নামগুলো অপরিবর্তিত থাকতে হবে।
# গভীর কভারেজ: tests/test_create_issue_cli.py

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.agents.create_issue import (
    create_blocker_issue,  # noqa: F401 — legacy নাম-সংরক্ষণ চুক্তির অংশ
    format_blocker_body,
    format_parent_comment,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agents" / "create_issue.py"


class TestLegacyApiSurface:
    """create_issue.py-এ legacy ফাংশন-নামগুলোর অস্তিত্ব ও আচরণ-চুক্তি।"""

    def test_format_blocker_body_structure(self):
        body = format_blocker_body(parent_issue=1690, description="tenant isolation missing", role="platform")
        assert "🛑 Prerequisite Blocker" in body
        assert "#1690" in body
        assert "**Blocks:** #1690" in body
        assert "`platform`" in body
        assert "tenant isolation missing" in body

    def test_format_parent_comment_structure(self):
        note = format_parent_comment(new_issue_number=1234, title="fix: upstream race", role="coder")
        assert "Blocked by Prerequisite Issue: #1234" in note
        assert "status:unclaimed" in note
        assert "`coder`" in note


class TestLegacyCliBlockerMode:
    def test_dry_run_json_reports_blocker_labels(self):
        # বাংলা মন্তব্য: legacy dry-run চুক্তি — blocker লেবেলসেট অক্ষত
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--type", "blocker", "--parent-issue", "1690",
             "--title", "shim: legacy contract", "--body", "b", "--dry-run"],
            capture_output=True, text=True, timeout=60, cwd=str(ROOT),
        )
        assert r.returncode == 0, r.stderr
        assert "type:blocker" in r.stdout
        assert "status:unclaimed" in r.stdout
