"""Regression tests: rules_breaker localhost-binding FP classes (#3823, P6).

বাংলা: Rules Breaker-এর naive substring-ম্যাচ তিনটি FP-ক্লাস তৈরি করছিল —
#3727 (২০ FP) বন্ধ করেছিল, #3823-ফ্লাড (৬২ issue) আবার জন্ম নিল। এই টেস্টগুলো
এখন থেকে ক্লাসটিকে মেশিন-এনফোর্সড ভাবে আটকে রাখবে (symptom-patch নয় —
প্রতিটি ক্লাসের একটি প্রতিনিধি লাইন এখানে চিরস্থায়ী ভাবে pinned)।

Classes pinned:
  1. negation-context  — `"localhost" not in o` (CORS origin *filter*) কোনো binding নয়
  2. env-driven host   — `os.getenv('X', 'localhost')` (আগে থেকেই আছে; এখন pinned)
  3. real binding      — `host="127.0.0.1"` এখনো ধরা পড়বে (over-suppression guard)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "agents"))

from rules_breaker import (
    _BINDING_PATTERNS,
    _line_is_localhost_binding,
    scan_localhost_binding,
    scan_render_service_ids,
)

# ---------------------------------------------------------------- class 1: negation
# pre_merge_guard.py:425 — প্রকৃত FP (issue #3823-এর স্নিপেট, অক্ষরে-অক্ষরে)
CORS_FILTER_LINE = (
    'origins = {o for o in origins if o.startswith("https://") and "localhost" not in o}'
)


def test_negation_cors_origin_filter_not_flagged():
    assert _line_is_localhost_binding(CORS_FILTER_LINE) is False


def test_negation_variants_not_flagged():
    assert _line_is_localhost_binding("if 'localhost' not in allowed_hosts: continue") is False
    assert _line_is_localhost_binding('assert request.host != "127.0.0.1"') is False
    assert _line_is_localhost_binding('hosts = [h for h in hosts if "localhost" not in h]') is False


# ---------------------------------------------------------------- class 2: env-driven
def test_env_driven_host_not_flagged():
    assert _line_is_localhost_binding(
        "host=self.source_config.get('host') or os.getenv('REDIS_HOST', 'localhost'),"
    ) is False


# ---------------------------------------------------------------- over-suppression guard
def test_real_bindings_still_flagged():
    # এই চারটি সত্যিকারের binding-আকৃতি — স্ক্যানার এগুলো ধরবেই (চুপ হলে টেস্ট লাল)
    assert _line_is_localhost_binding('config = uvicorn.Config(app, host="127.0.0.1", port=8765)') is True
    assert _line_is_localhost_binding("s.bind(('localhost', 8080))") is True
    assert _line_is_localhost_binding('run(app, host="0.0.0.0", port=8000)') is True
    assert _line_is_localhost_binding("subprocess.run(['tool', 'C:\\\\work\\\\x'])") is True


def test_is_local_marker_still_honored():
    assert _line_is_localhost_binding('config = uvicorn.Config(app, host="127.0.0.1")  # is_local()') is False


def test_comments_never_flagged():
    assert _line_is_localhost_binding('# connect to localhost for dev') is False


# ---------------------------------------------------------------- SSOT / exclusions
def test_self_file_excluded_from_scan():
    """স্ক্যানার নিজের সোর্স কখনো ফ্ল্যাগ করবে না (docstring/regex-এ localhost থাকে)।"""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "agents" / "rules_breaker.py").read_text(
        encoding="utf-8"
    )
    assert '"rules_breaker.py"' in src, "self-exclusion filename check missing from scanner"


def test_tooling_dirs_excluded_from_scan():
    """k6/load-test টুলিং localhost টার্গেট করে by-design — scan-বহির্ভূত হতে হবে।"""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "agents" / "rules_breaker.py").read_text(
        encoding="utf-8"
    )
    assert '"k6"' in src
    assert '"load_test"' in src


def test_k6_env_default_line_guarded_by_dir_exclusion():
    """k6/load_test.js:16 — `|| 'http://127.0.0.1:8000'` env-default FP।

    এই লাইনটি line-স্তরে ধরা পড়ে (env-default শুধু `||` fallback), তাই প্রাথমিক
    guard হলো k6/ ডিরেক্টরি-বহিষ্কার (test_tooling_dirs_excluded_from_scan)।
    ভবিষ্যতে কেউ লাইন-স্তরের নিয়ম সরালে এই টেস্ট সেই প্রভাব document করে রাখে।
    """
    line = "const BASE_URL = __ENV.SUPREMEAI_URL || 'http://127.0.0.1:8000';"
    assert _line_is_localhost_binding(line) is True  # line-level: flagged
    # কিন্তু k6/ dir-বহিষ্কার থাকায় scan_localhost_binding ফাইলটিই পড়ে না —
    # তাই বাস্তবে FP emit হয় না (dir-exclusion হলো কার্যকর guard)।


# ---------------------------------------------------------------- scanner wiring
def test_scanner_uses_ssot_patterns():
    """scan loop আর verdict helper একই pattern-SSOT ব্যবহার করছে কিনা (drift guard)।"""
    assert len(_BINDING_PATTERNS) == 2
    assert any("localhost" in p for p, _ in _BINDING_PATTERNS)
    assert any("mnt/c" in p for p, _ in _BINDING_PATTERNS)


def test_scanner_function_smoke():
    """scan_localhost_binding চলন্ত অবস্থায় crash করে না + list রিটার্ন করে।"""
    findings = scan_localhost_binding(limit=5)
    assert isinstance(findings, list)


# ---------------------------------------------------------------- #3774: service-ID gate
def test_render_service_ids_clean_on_main():
    """#3774 মেরামতের পর public deploy tooling-এ কোনো হার্ডকোডেড srv- ID থাকবে না।"""
    findings = scan_render_service_ids(limit=20)
    assert findings == [], f"hardcoded service IDs resurfaced: {[(f['file'], f['line']) for f in findings]}"


def test_render_service_id_pattern_detects_id():
    """প্যাটার্ন সত্যিই ID চেনে (over-suppression guard — স্ক্যান অন্ধ হলে টেস্ট লাল)।"""
    import rules_breaker as rb

    assert rb._RENDER_SERVICE_ID_RE.search('SERVICE_ID = "srv-da666f8u01pc739bm3t0"')
    assert not rb._RENDER_SERVICE_ID_RE.search('SERVICE_ID = os.environ["RENDER_SERVICE_ID"]')
    assert not rb._RENDER_SERVICE_ID_RE.search("srv-")  # খালি prefix যথেষ্ট নয়
    assert not rb._RENDER_SERVICE_ID_RE.search("srv-short")  # খাটো স্ট্রিং নয়
