# tests/test_env_example_drift_2865.py
"""#2865 — .env.example drift চুক্তি-টেস্ট।

চুক্তি (issue #2865):
1. `generate_env_example.py --check` exit 0 — কমিট করা `.env.example`
   CONFIG_SPECS-এর সাথে সম (drift-শূন্য)। #2826-এর gate-wiring মার্জের
   পরে এই চেক blocking হবে — main আগে থেকেই পরিষ্কার থাকতে হবে।
2. দুটি অবর্গীকৃত-কী (COSTGUARD_UNATTRIBUTED_DAILY_CAP #2732,
   VERCEL_TOKEN_2) টেমপ্লেটে উপস্থিত — রিজেন-পথে হারিয়ে যায় নি।
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "scripts" / "ci" / "generate_env_example.py"
ENV_EXAMPLE = REPO / ".env.example"


def test_env_example_check_passes_no_drift():
    assert GEN.exists(), f"generator missing: {GEN}"
    assert ENV_EXAMPLE.exists(), f".env.example missing: {ENV_EXAMPLE}"
    proc = subprocess.run(
        ["python3", str(GEN), "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, (
        f".env.example drifted from CONFIG_SPECS (exit {proc.returncode}):\n"
        f"{proc.stdout[-800:]}\n{proc.stderr[-400:]}"
    )


def test_ungrouped_keys_still_present_in_template():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in ("COSTGUARD_UNATTRIBUTED_DAILY_CAP", "VERCEL_TOKEN_2"):
        assert f"{key}=" in text, f"key lost in regen: {key}"
