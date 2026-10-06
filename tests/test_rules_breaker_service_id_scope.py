"""#4091 — scan_render_service_ids gate scope regression tests (P6).

Defect class: **detector scope < class surface**। #3774 গেট বানিয়েছিল কিন্তু
স্কোপ ছিল scripts/deploy/** + Dockerfile মাত্র — ফলে ৮টি hardcoded `srv-` ID
গেটের বাইরে টিকে ছিল (.github/scripts/** × ৭, infrastructure/** TS × ১)।

এই টেস্ট-বান্ডেল নতুন স্কোপ-চুক্তি মেশিন-এনফোর্সড রাখে:
  1. সম্পূর্ণ ট্রি ক্লিন (conversion-পরবর্তী অবস্থা চিরস্থায়ী)
  2. স্কোপ-সারফেস প্রমাণ: .github/scripts/** ও infrastructure/** (TS সহ)
     ভেতরে ইচ্ছাকৃত planted literal ধরা পড়ে (নয়তো স্ক্যান অন্ধ)
  3. node_modules বাদ — vendored ট্রি সারফেস নয় (FP/বৃহৎ-ট্রি গার্ড)
  4. Over-suppression guard: env-driven লাইন কখনোই ফ্ল্যাগ হয় না (#3774 থেকে)
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "agents"))

import rules_breaker as rb  # noqa: E402
from rules_breaker import scan_render_service_ids  # noqa: E402

FAKE_ID = "srv-aaaaaaaaaaaaaaaaaaaa"  # আকৃতিসম্পন্ন ডামি ID (srv- + 20 lowercase)


# ------------------------------------------------------------------ 1: clean tree
def test_full_tree_clean_after_conversion():
    """Conversion-পরবর্তী main: তিন সারফেসেই শূন্য hardcoded srv- ID।"""
    findings = scan_render_service_ids(limit=50)
    assert findings == [], (
        f"hardcoded service IDs resurfaced: {[(f['file'], f['line']) for f in findings]}"
    )


# --------------------------------------------------- 2: scope surface detection
def _plant(tmp_root: Path, rel: str, body: str) -> Path:
    f = tmp_root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


def test_planted_literal_in_github_scripts_detected(tmp_path):
    """ইচ্ছাকৃত literal .github/scripts/**-এ → অবশ্যই ধরা পড়বে (#4091 scope proof)।"""
    _plant(tmp_path, ".github/scripts/fake_check.py",
           f'SVC = os.environ.get("SVC_ID", "{FAKE_ID}")\n')
    findings = scan_render_service_ids(limit=10, root=tmp_path)
    assert [f["file"] for f in findings] == [".github/scripts/fake_check.py"], (
        "gate is BLIND to .github/scripts/** — scope regression (#4091 class alive)"
    )


def test_planted_literal_in_infrastructure_ts_detected(tmp_path):
    """TS-aware: infrastructure/**-এর .ts ফাইলে planted literal → ধরা পড়বে।"""
    _plant(tmp_path, "infrastructure/mcp-plane/src/engine.ts",
           f'const id = env.render.primary.serviceId || "{FAKE_ID}";\n')
    findings = scan_render_service_ids(limit=10, root=tmp_path)
    assert [f["file"] for f in findings] == ["infrastructure/mcp-plane/src/engine.ts"], (
        "gate is BLIND to infrastructure/** .ts — TS surface regression (#4091)"
    )


def test_deploy_scope_still_covered(tmp_path):
    """মূল #3774 সারফেস (scripts/deploy/**) অক্ষত — scope extension মূল পথ ভাঙে না।"""
    _plant(tmp_path, "scripts/deploy/update_image.py",
           f'SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "{FAKE_ID}")\n')
    findings = scan_render_service_ids(limit=10, root=tmp_path)
    assert [f["file"] for f in findings] == ["scripts/deploy/update_image.py"]


# ------------------------------------------------------------- 3: node_modules
def test_node_modules_excluded_from_scan(tmp_path):
    """vendored node_modules সারফেস নয় — planted literal সেখানে ফ্ল্যাগ হয় না।"""
    _plant(tmp_path, "infrastructure/mcp-plane/node_modules/pkg/index.ts",
           f'const id = "{FAKE_ID}";\n')
    findings = scan_render_service_ids(limit=10, root=tmp_path)
    assert findings == [], "node_modules must stay outside the gate surface"


# ------------------------------------------------------- 4: over-suppression guard
def test_env_driven_lines_not_flagged():
    """env-driven ব্যবহার বৈধ — স্ক্যান অন্ধ হওয়ার বিপরীত চরমও ভুল (#3774 সূত্র)।"""
    assert not rb._RENDER_SERVICE_ID_RE.search(
        'os.environ["RENDER_SERVICE_ID"]'
    )
    assert not rb._RENDER_SERVICE_ID_RE.search(
        'os.environ.get("PRIMARY_SVC_ID", "")'
    )
    assert rb._RENDER_SERVICE_ID_RE.search(f'"{FAKE_ID}"')  # literal এখনো চেনে
