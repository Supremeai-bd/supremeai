"""#2893 চুক্তি-টেস্ট: full-suite ratchet gate (scripts/ci/full_suite_ratchet_gate.py)।

প্রেক্ষাপট: main-এর পূর্ণ backend suite-এ ১৭ failed + ২ collection-error আছে
(baseline স্ন্যাপশট: backend/full-suite-baseline.txt, HEAD 2fe47d42 প্রমাণ)।
তাই "যেকোনো ফেইল = BLOCK" হলে প্রতিটি backend PR চিরকাল লাল — pipeline deadlock।
চুক্তি (knip-baseline র্যাচেট-মতবাদ, pr.yml Frontend dead-code ratchet প্যাটার্ন):
- baseline-এর ভেতরে known-red → PASS (ঋণ স্বীকৃত)
- baseline-এর বাইরে নতুন ফেইল → BLOCK (নতুন লাল main-এ যাবে না)
- baseline-এ থেকেও আর ফেইল করছে না → advisory WARNING (র্যাচেট-নামার সুযোগ)
- pytest rc {0,1}-এর বাইরে বা rc=1 অথচ শূন্য ফেইল-লাইন → fail-closed (infra/anomaly)
- rc=0 অথচ FAILED লাইন উপস্থিত → fail-closed (out অসঙ্গতি)

core লজিক pure + main(argv)-injectable — ফাইল-নির্ভর I/O tmp_path দিয়ে মক।
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

from full_suite_ratchet_gate import load_baseline, main, parse_failure_node_ids

SAMPLE_FAIL_OUTPUT = """\
============================= test session starts ==============================
=========================== short test summary info ============================
FAILED tests/api/routes/test_admin_routes_full.py::TestTotpVerify::test_x - AssertionError: boom
FAILED tests/core/test_gcp_firestore.py::test_enqueue_adds_document - NameError: name 'gcp' is not defined
ERROR tests/models/test_ai_memory_schema_contract.py
ERROR tests/services/test_sandbox_service.py
========================= 2 failed, 2 errors in 1.00s ==========================
"""


# ── parse_failure_node_ids ────────────────────────────────────────────────
def test_parses_failed_and_error_node_ids_with_message_suffix() -> None:
    got = parse_failure_node_ids(SAMPLE_FAIL_OUTPUT)
    assert (
        "tests/api/routes/test_admin_routes_full.py::TestTotpVerify::test_x" in got
    )
    assert "tests/core/test_gcp_firestore.py::test_enqueue_adds_document" in got
    assert "tests/models/test_ai_memory_schema_contract.py" in got
    assert "tests/services/test_sandbox_service.py" in got
    assert len(got) == 4


def test_ignores_log_noise_and_non_tests_tokens() -> None:
    # বাংলা মন্তব্য: caplog/রানটাইম "ERROR    logger:..." লাইন short-summary নয় —
    # multi-space বা tests/-প্রিফিক্সহীন টোকেন বাদ যাবে (false-positive র্যাচেট ব্লক আটকাতে)।
    noisy = (
        "ERROR    core.agent_supervisor:agent_supervisor.py:179 Silenced error: x\n"
        "ERROR something_else.py\n"
        "FAILED tests/real/test_a.py - bad\n"
    )
    got = parse_failure_node_ids(noisy)
    assert got == {"tests/real/test_a.py"}


def test_dedupes_and_strips_whitespace() -> None:
    text = "FAILED tests/a/test_x.py - m1\n  FAILED tests/b/test_y.py \nFAILED tests/a/test_x.py\n"
    got = parse_failure_node_ids(text)
    assert got == {"tests/a/test_x.py", "tests/b/test_y.py"}


# ── load_baseline ─────────────────────────────────────────────────────────
def test_baseline_reads_known_red_json(tmp_path: Path) -> None:
    p = tmp_path / "baseline.json"
    p.write_text(
        '{"provenance": "x", "known_red": ["tests/a/test_x.py", "tests/b/test_y.py"]}',
        encoding="utf-8",
    )
    assert load_baseline(p) == {"tests/a/test_x.py", "tests/b/test_y.py"}


def test_missing_baseline_is_empty_set(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "absent.json") == set()


def test_malformed_baseline_raises(tmp_path: Path) -> None:
    # বাংলা মন্তব্য: ভাঙা baseline নীরবে শূন্য-সেট হলে সব নতুন ফেইল অদৃশ্য হয়ে
    # যাবে (গেট ফাঁদ) — raise করে main() fail-closed BLOCK করবে।
    import pytest as _pytest

    p = tmp_path / "broken.json"
    p.write_text("{known_red: not json", encoding="utf-8")
    with _pytest.raises(ValueError):
        load_baseline(p)


def test_wrong_shape_baseline_raises(tmp_path: Path) -> None:
    import pytest as _pytest

    p = tmp_path / "wrong.json"
    p.write_text('{"entries": []}', encoding="utf-8")
    with _pytest.raises(ValueError):
        load_baseline(p)


# ── main() সিদ্ধান্ত-ম্যাট্রিক্স ─────────────────────────────────────────────
def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def test_pass_when_green_with_empty_baseline(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "======================== 100 passed in 5s =========================\n")
    base = _write(tmp_path / "base.json", '{"known_red": []}')
    rc = main([str(out), "--pytest-rc", "0", "--baseline", str(base)])
    assert rc == 0
    assert "সবুজ" in capsys.readouterr().out


def test_pass_when_failures_subset_of_baseline(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "FAILED tests/old/test_a.py - x\nERROR tests/old/mod_b.py\n")
    base = _write(tmp_path / "base.json", '{"known_red": ["tests/old/test_a.py", "tests/old/mod_b.py"]}')
    rc = main([str(out), "--pytest-rc", "1", "--baseline", str(base)])
    assert rc == 0


def test_blocks_on_new_failure_outside_baseline(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "FAILED tests/old/test_a.py\nFAILED tests/new/test_z.py\n")
    base = _write(tmp_path / "base.json", '{"known_red": ["tests/old/test_a.py"]}')
    rc = main([str(out), "--pytest-rc", "1", "--baseline", str(base)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "tests/new/test_z.py" in captured.out
    assert "baseline" in captured.out


def test_advisory_warning_for_stale_baseline_entries(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "FAILED tests/old/test_a.py\n")
    base = _write(tmp_path / "base.json", '{"known_red": ["tests/old/test_a.py", "tests/fixed/test_gone.py"]}')
    rc = main([str(out), "--pytest-rc", "1", "--baseline", str(base)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "tests/fixed/test_gone.py" in captured.out


def test_fail_closed_on_infra_rc(tmp_path: Path) -> None:
    out = _write(tmp_path / "out.txt", "nothing\n")
    base = _write(tmp_path / "base.json", '{"known_red": []}')
    for bad_rc in ("2", "3", "4", "5"):
        assert main([str(out), "--pytest-rc", bad_rc, "--baseline", str(base)]) == 1


def test_fail_closed_when_rc1_but_zero_failure_lines(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "some output without summary lines\n")
    base = _write(tmp_path / "base.json", '{"known_red": []}')
    rc = main([str(out), "--pytest-rc", "1", "--baseline", str(base)])
    assert rc == 1
    assert "অসঙ্গতি" in capsys.readouterr().out


def test_fail_closed_when_rc0_but_failure_lines_present(tmp_path: Path) -> None:
    out = _write(tmp_path / "out.txt", "FAILED tests/a/test_x.py - weird\n")
    base = _write(tmp_path / "base.json", '{"known_red": ["tests/a/test_x.py"]}')
    assert main([str(out), "--pytest-rc", "0", "--baseline", str(base)]) == 1


def test_fail_closed_on_missing_output_file(tmp_path: Path) -> None:
    base = _write(tmp_path / "base.json", '{"known_red": []}')
    assert main(
        [str(tmp_path / "absent_out.txt"), "--pytest-rc", "0", "--baseline", str(base)]
    ) == 1


def test_fail_closed_on_malformed_baseline(tmp_path: Path, capsys) -> None:
    out = _write(tmp_path / "out.txt", "FAILED tests/a/test_x.py\n")
    base = _write(tmp_path / "base.json", "not-json-at-all")
    rc = main([str(out), "--pytest-rc", "1", "--baseline", str(base)])
    assert rc == 1
    assert "fail-closed" in capsys.readouterr().out
