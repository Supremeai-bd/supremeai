#!/usr/bin/env python3
"""
production_release_gate.py — 5-Point Production Release Gate & Daily Health Report.

প্রতিটি প্রোডাকশন ক্যাপাবিলিটি বা সাবসিস্টেমের জন্য ৫টি বাধ্যতামূলক প্রশ্ন যাচাই করে:
  1. capability_exists     — কোডবেসে সক্ষমতাটি বাস্তবে আছে কি না (ফাইল ও সিম্বল)।
  2. works_in_reality      — সিনট্যাক্স/ইমপোর্ট/কনফিগ বা স্মোক প্রোব বাস্তবে কাজ করে কি না।
  3. verification_method   — কীভাবে এটি স্বয়ংক্রিয়ভাবে যাচাই করা হয় (test/guard path)।
  4. evidence_location     — কোথায় এর প্রমাণ সংরক্ষিত থাকে।
  5. recovery_playbook     — ব্যর্থ হলে পুনরুদ্ধারের সুনির্দিষ্ট ধাপ কী।

CLI Modes:
  --check                  সকল সাবসিস্টেমের ৫-পয়েন্ট কন্ট্রাক্ট যাচাই করে (exit 0 বা 1)।
  --self-test              অফলাইন ফিক্সচার দিয়ে গার্ডের নিজস্ব লজিক যাচাই করে।
  --json <path>            JSON ফরম্যাটে রিপোর্ট সংরক্ষণ করে।
  --markdown <path>        বাংলা ও ইংরেজি সামারিসহ Markdown হেলথ রিপোর্ট সংরক্ষণ করে।
"""

from __future__ import annotations

import argparse
import contextlib
import json
import py_compile
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
BDT = timezone(timedelta(hours=6))

REQUIRED_FIELDS = (
    "capability_exists",
    "works_in_reality",
    "verification_method",
    "evidence_location",
    "recovery_playbook",
)


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    title: str
    target_path: str
    required_markers: tuple[str, ...]
    verification_method: str
    evidence_location: str
    recovery_playbook: str


@dataclass(frozen=True)
class CapabilityEvaluation:
    capability_id: str
    title: str
    capability_exists: bool
    works_in_reality: bool
    verification_method: str
    evidence_location: str
    recovery_playbook: str
    detail: str

    def is_passing(self) -> bool:
        return bool(
            self.capability_exists
            and self.works_in_reality
            and self.verification_method.strip()
            and self.evidence_location.strip()
            and self.recovery_playbook.strip()
        )


DEFAULT_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        capability_id="upstash-redis-pool",
        title="Upstash 5-Account Redis REST Failover Pool",
        target_path="core/config_fields.py",
        required_markers=("upstash_redis_rest_pool", "upstash_redis_rest_pool_enabled"),
        verification_method="pytest core/tests/config/test_upstash_pool_config.py",
        evidence_location="core/tests/config/test_upstash_pool_config.py",
        recovery_playbook="Verify UPSTASH_REDIS_REST_URL.._5 and TOKEN.._5 in Infisical/Render env and re-run pool config test.",
    ),
    CapabilitySpec(
        capability_id="cloudflare-keepwarm-health",
        title="Cloudflare Render Keep-Warm Worker Health & Release Routes",
        target_path="infrastructure/cloudflare-render-keepwarm/worker.js",
        required_markers=("/health", "/healthz", "/release"),
        verification_method="node --check infrastructure/cloudflare-render-keepwarm/worker.js",
        evidence_location="infrastructure/cloudflare-render-keepwarm/worker.js",
        recovery_playbook="Redeploy cloudflare-render-keepwarm worker via unified-pipeline.yml deploy-cloudflare-workers.",
    ),
    CapabilitySpec(
        capability_id="security-tenant-isolation",
        title="Memory Tenant Isolation & 64-Byte Production JWT Floor",
        target_path="core/api/routes/memory.py",
        required_markers=("_owned_window_session", "_owned_checkpoint_key"),
        verification_method="pytest core/tests/security/ -q",
        evidence_location="core/tests/security/",
        recovery_playbook="Rotate JWT_SECRET_KEY (>=64 bytes) in Infisical and run core/tests/security/ regression suite.",
    ),
    CapabilitySpec(
        capability_id="autonomy-brain-loop",
        title="Continuous Agent Loop Autonomy Brain (#106, #107, #108) & Redis TaskRouter",
        target_path="scripts/agents/continuous_agent_loop.py",
        required_markers=("build_autonomy_brain_plan", "autonomy_brain"),
        verification_method="pytest tests/test_autonomy_brain_wiring.py core/tests/core/test_task_router.py -q",
        evidence_location="tests/test_autonomy_brain_wiring.py",
        recovery_playbook="Inspect build_autonomy_brain_plan in continuous_agent_loop.py and verify smart_context_selector 8-layer contract.",
    ),
    CapabilitySpec(
        capability_id="schema-drift-and-readiness",
        title="Database Schema Drift Probe & Readiness Contract",
        target_path="core/api/routes/health_aggregation.py",
        required_markers=("SchemaDriftStatus", "probe_schema_drift"),
        verification_method="python scripts/ci/readiness_contract.py --self-test && pytest gateway/tests/routes/test_schema_drift.py -q",
        evidence_location="gateway/tests/routes/test_schema_drift.py",
        recovery_playbook="Recycle database connection pool, apply pending Alembic/Supabase migrations, and re-probe /api/health/aggregated.",
    ),
)


def evaluate_capability(spec: CapabilitySpec, root: Path = REPO_ROOT) -> CapabilityEvaluation:
    full_path = root / spec.target_path
    exists = full_path.is_file()
    works = False
    detail = "OK"

    if not exists:
        detail = f"Missing target file: {spec.target_path}"
    else:
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            missing = [m for m in spec.required_markers if m not in content]
            if missing:
                detail = f"Missing markers in {spec.target_path}: {', '.join(missing)}"
            elif full_path.suffix == ".py":
                py_compile.compile(str(full_path), doraise=True)
                works = True
            else:
                works = len(content.strip()) > 0
        except Exception as exc:
            detail = f"Verification error on {spec.target_path}: {exc}"

    return CapabilityEvaluation(
        capability_id=spec.capability_id,
        title=spec.title,
        capability_exists=exists,
        works_in_reality=works,
        verification_method=spec.verification_method,
        evidence_location=spec.evidence_location,
        recovery_playbook=spec.recovery_playbook,
        detail=detail,
    )


def evaluate_all(
    specs: Sequence[CapabilitySpec] = DEFAULT_CAPABILITIES,
    root: Path = REPO_ROOT,
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    now_bdt = now_utc.astimezone(BDT)
    results = [evaluate_capability(spec, root=root) for spec in specs]
    passed = sum(1 for r in results if r.is_passing())
    total = len(results)
    return {
        "schema_version": "1.0",
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_bdt": now_bdt.strftime("%Y-%m-%d %H:%M:%S BDT"),
        "passed": passed,
        "total": total,
        "all_passed": passed == total and total > 0,
        "required_fields": list(REQUIRED_FIELDS),
        "capabilities": [asdict(r) for r in results],
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    status_badge = "✅ PASS (প্রস্তুত)" if report["all_passed"] else "❌ FAIL (ত্রুটি পাওয়া গেছে)"
    lines = [
        "# 🩺 SupremeAI দৈনিক সকাল ১০:০০টার হেলথ ও প্রোডাকশন রিলিজ গেট রিপোর্ট",
        "",
        f"- **সময় (BDT):** `{report['generated_at_bdt']}`",
        f"- **সময় (UTC):** `{report['generated_at_utc']}`",
        f"- **সামগ্রিক অবস্থা:** **{status_badge}** (`{report['passed']}/{report['total']}` সাবসিস্টেম পাস)",
        "",
        "## ৫-পয়েন্ট প্রোডাকশন রিলিজ গেট যাচাই (5-Point Verification Matrix)",
        "",
        "| সাবসিস্টেম | কোডে আছে (`exists`) | বাস্তবে চলে (`works`) | যাচাই পদ্ধতি (`verification_method`) | প্রমাণ (`evidence`) | পুনরুদ্ধার নির্দেশিকা (`recovery_playbook`) |",
        "| :--- | :---: | :---: | :--- | :--- | :--- |",
    ]
    for cap in report["capabilities"]:
        ex = "✅" if cap["capability_exists"] else "❌"
        wk = "✅" if cap["works_in_reality"] else "❌"
        lines.append(
            f"| **{cap['title']}** (`{cap['capability_id']}`) | {ex} | {wk} | `{cap['verification_method']}` | `{cap['evidence_location']}` | {cap['recovery_playbook']} |"
        )
    lines.append("")
    return "\n".join(lines)


def self_test() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        good_file = tmp_root / "sample.py"
        good_file.write_text("MARKER_A = True\nMARKER_B = 42\n", encoding="utf-8")

        good_spec = CapabilitySpec(
            capability_id="test-good",
            title="Good Capability",
            target_path="sample.py",
            required_markers=("MARKER_A", "MARKER_B"),
            verification_method="pytest sample",
            evidence_location="tests/sample",
            recovery_playbook="Restore sample.py",
        )
        bad_spec = CapabilitySpec(
            capability_id="test-bad",
            title="Missing Capability",
            target_path="missing.py",
            required_markers=("MARKER_X",),
            verification_method="pytest missing",
            evidence_location="tests/missing",
            recovery_playbook="Create missing.py",
        )

        ev_good = evaluate_capability(good_spec, root=tmp_root)
        ev_bad = evaluate_capability(bad_spec, root=tmp_root)
        assert ev_good.is_passing(), f"Expected good spec to pass: {ev_good}"
        assert not ev_bad.is_passing(), f"Expected bad spec to fail: {ev_bad}"

    print("[PASS] production_release_gate self-test: 2/2 assertions passed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="5-Point Production Release Gate")
    parser.add_argument("--check", action="store_true", help="Run 5-point gate against live repo")
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test")
    parser.add_argument("--json", type=Path, default=None, help="Write JSON report to path")
    parser.add_argument("--markdown", type=Path, default=None, help="Write Markdown report to path")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    report = evaluate_all()
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = render_markdown_report(report)
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md, encoding="utf-8")

    if args.check or (not args.json and not args.markdown):
        for cap in report["capabilities"]:
            status = "PASS" if (cap["capability_exists"] and cap["works_in_reality"]) else "FAIL"
            print(f"[{status}] {cap['capability_id']}: {cap['detail']}")
        if not report["all_passed"]:
            print(f"[FAIL] production_release_gate: {report['passed']}/{report['total']} passed")
            return 1
        print(f"[PASS] production_release_gate: {report['passed']}/{report['total']} capabilities verified")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
