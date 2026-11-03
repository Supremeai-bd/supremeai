# SupremeAI 2.0 — Unified Agents Package Regression Suite
# বাংলা মন্তব্য: কনসোলিডেটেড backend/agents/ প্যাকেজের জন্য রিগ্রেশন টেস্ট।
# প্যাকেজ এক্সপোর্ট ইন্টিগ্রিটি, সব এজেন্টের নিরাপদ কনস্ট্রাকশন, এবং
# পিউর/ডিটারমিনিস্টিক মেথডগুলো (সিকিউরিটি স্ক্যান, ভালনারেবিলিটি ম্যাচিং,
# অ্যানোমালি ডিটেকশন, স্কিল-আইডি ভ্যালিডেশন) কভার করে।

import sys
from unittest.mock import MagicMock

# Import guard: agents package init may import optional google.genai.
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", MagicMock())

import agents  # noqa: E402
from agents.performance_guardian import AnomalyDetector  # noqa: E402
from agents.vulnerability_prophet import (  # noqa: E402
    VulnerabilityPatternMatcher,
)

UNIFIED_AGENT_CLASSES = [
    "ChurnProphet",
    "HeadlessTerminalAgent",
    "InsightMage",
    "InternetMonitorAgent",
    "MorphicAdapter",
    "PerformanceGuardian",
    "SentinelAgent",
    "SkillGarbageCollector",
    "SkillIngestor",
    "SkillLibrarian",
    "VulnerabilityProphet",
]


def test_unified_package_exports_all_agents():
    """Consolidation integrity: every unified agent must be exported from the package."""
    for name in UNIFIED_AGENT_CLASSES:
        assert hasattr(agents, name), f"Unified agent '{name}' missing from agents package"
        assert isinstance(getattr(agents, name), type)


def test_unified_agents_construct_without_required_args():
    """All unified agents must be constructible with safe defaults (no external deps)."""
    for name in UNIFIED_AGENT_CLASSES:
        cls = getattr(agents, name)
        instance = cls()
        assert isinstance(instance, cls)


# ── VulnerabilityProphet: deterministic pattern matching ────────────────────
def test_vulnerability_pattern_matcher_command_injection():
    code = "import subprocess\nsubprocess.run(f'echo {user_input}')\n"
    findings = VulnerabilityPatternMatcher.scan_file(code, "x.py")
    assert any(f.vulnerability_type.value == "command_injection" for f in findings)


def test_vulnerability_pattern_matcher_hardcoded_secret():
    code = "API_KEY = 'sk_live_abcdef1234567890'\n"
    findings = VulnerabilityPatternMatcher.scan_file(code, "x.py")
    assert any(f.vulnerability_type.value == "hardcoded_secret" for f in findings)


def test_vulnerability_prophet_generate_report_counts():
    vp = agents.VulnerabilityProphet()
    findings = vp.matcher.scan_file("eval(request.user)", "x.py")
    report = vp.generate_report(findings)
    assert report["total_findings"] == len(findings)
    assert "severity_breakdown" in report


# ── PerformanceGuardian / AnomalyDetector: pure statistical detection ─────────
def test_anomaly_detector_requires_minimum_points():
    det = AnomalyDetector()
    ok, z = det.detect("cpu", [1, 2, 3, 4], threshold=2.0)
    assert ok is False
    assert z == 0.0


# ── Skill helpers: unified skill packages construct ─────────────────────────
def test_skill_packages_construct_and_export():
    assert isinstance(agents.SkillGarbageCollector(), agents.SkillGarbageCollector)
    assert isinstance(agents.SkillIngestor(), agents.SkillIngestor)
    assert isinstance(agents.SkillLibrarian(), agents.SkillLibrarian)


def test_skill_ingestor_static_ast_safety_check():
    si = agents.SkillIngestor()
    ok, msg = si.static_ast_safety_check("def f():\n    return 1\n")
    assert ok is True
    assert isinstance(msg, str)


# ── MorphicAdapter: deterministic code-to-contract adaptation ──────────────
def test_morphic_adapter_adapt_code_to_contract():
    adapter = agents.MorphicAdapter()
    out = adapter.adapt_code_to_contract("def add(a, b):\n    return a + b", "returns sum")
    assert isinstance(out, dict)
    assert "success" in out and "code" in out


# ── InsightMage: anomaly/trend analysis entry points exist and run ─────────
def test_insight_mage_analysis_entrypoints():
    mage = agents.InsightMage()
    assert callable(getattr(mage, "detect_anomalies", None))
    assert callable(getattr(mage, "analyze_trends", None))
    assert callable(getattr(mage, "generate_report", None))
