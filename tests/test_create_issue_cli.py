# বাংলা মন্তব্য: #2841 PR-6 — একক create_issue.py CLI-চুক্তি টেস্ট।
"""create_issue.py (blocker+discovery একত্র) — dry-run ও টাইপ-প্রহরের চুক্তি।"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agents" / "create_issue.py"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT),
    )


def test_discovery_dry_run():
    r = run_cli("--type", "discovery", "--parent-issue", "1",
                "--title", "smoke: discovery contract", "--body", "b", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "[DRY-RUN]" in r.stdout
    assert "Discovery issue: #9999" in r.stdout  # (#2528) paste-রেডি লাইন অক্ষত


def test_blocker_dry_run():
    r = run_cli("--type", "blocker", "--parent-issue", "1",
                "--title", "smoke: blocker contract", "--body", "b", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "Dry Run" in r.stdout
    assert "type:blocker" in r.stdout


def test_type_is_required():
    r = run_cli("--parent-issue", "1", "--title", "t", "--body", "b")
    assert r.returncode != 0, "--type ছাড়া চলা উচিত নয়"


def test_cross_type_flags_rejected():
    # বাংলা মন্তব্য: লেন-ভুল ফ্ল্যাগ প্রহর — blocker-এ severity নিষিদ্ধ
    r = run_cli("--type", "blocker", "--parent-issue", "1",
                "--title", "t", "--body", "b", "--severity", "high", "--dry-run")
    assert r.returncode != 0
