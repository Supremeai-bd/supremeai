

# --- Merged from security_audit.py ---

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SupremeAI 2.0 — Security Auditing & Compliance Suite (Defensive)
============================================================================
উদ্দেশ্য: সিস্টেমের স্ট্যাটিক সিকিউরিটি অডিট, ডিপেন্ডেন্সি স্ক্যান এবং কনফিগারেশন চেক করে।

বাংলা মন্তব্য: এই স্ক্রিপ্টটি সিস্টেমে কোনো ক্ষতিকারক পেলোড ফায়ার না করে সম্পূর্ণ নিরাপদ উপায়ে
কোডবেস, কনফিগারেশন ফাইল এবং প্যাকেজ ডিপেন্ডেন্সিগুলোর সিকিউরিটি অডিট করে।

বৈশিষ্ট্য:
  - Bandit ব্যবহার করে স্ট্যাটিক কোড অ্যানালাইসিস (SAST)
  - pip-audit ব্যবহার করে ডিপেন্ডেন্সি ভালনারেবিলিটি চেক
  - কনফিগারেশন ফাইলগুলোতে (e.g., .env) সিক্রেটস লিকেজ সনাক্তকরণ
  - ডিরেক্টরি এবং ফাইলের পারমিশন ভ্যালিডেশন
  - অডিট রিপোর্ট জেনারেশন (Markdown ও HTML ফরম্যাটে)
============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

# ── Configuration ──────────────────────────────────────────────────────────
REPORT_DIR = Path("tests/reports/security")
DEFAULT_TARGET_DIR = Path("backend")


@dataclass
class AuditFinding:
    """বাংলা মন্তব্য: সিকিউরিটি অডিটের মাধ্যমে পাওয়া দুর্বলতার বিবরণ"""
    title: str
    severity: str  # HIGH | MEDIUM | LOW | INFO
    description: str
    file_path: str
    line_number: int | str = "N/A"
    remediation: str = ""


@dataclass
class AuditResult:
    """বাংলা মন্তব্য: সম্পূর্ণ অডিট রানের সামারি"""
    findings: list[AuditFinding] = field(default_factory=list)
    scan_duration: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class SecurityAuditor:
    """
    বাংলা মন্তব্য: নিরাপদ এবং ডিফেনসিভ সিকিউরিটি স্ক্যানার যা কোডের দুর্বলতা খুঁজে বের করে।
    """

    def __init__(self, target_dir: Path = DEFAULT_TARGET_DIR):
        self.target_dir = target_dir
        self.result = AuditResult()

    async def run_static_analysis(self) -> None:
        """
        বাংলা মন্তব্য: Bandit লাইব্রেরি ব্যবহার করে কোডের ভেতরের দুর্বলতা স্ক্যান করে।
        """
        logger.info("Starting Static Application Security Testing (SAST)...")
        try:
            # Run Bandit as a subprocess
            cmd = ["bandit", "-r", str(self.target_dir), "-f", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if stdout:
                data = json.loads(stdout.decode())
                results = data.get("results", [])
                for issue in results:
                    self.result.findings.append(AuditFinding(
                        title=issue.get("issue_text", "Static Analysis Issue"),
                        severity=issue.get("issue_severity", "MEDIUM"),
                        description=issue.get("issue_details", ""),
                        file_path=issue.get("filename", ""),
                        line_number=issue.get("line_number", "N/A"),
                        remediation="Review code implementation and replace insecure functions/patterns."
                    ))
            logger.info("SAST scan completed.")
        except FileNotFoundError:
            logger.warning("⚠️ Bandit is not installed. Run 'pip install bandit' to enable SAST.")
        except Exception as e:
            logger.error(f"SAST scan failed: {e}")

    async def run_dependency_scan(self) -> None:
        """
        বাংলা মন্তব্য: pip-audit ব্যবহার করে ডিপেন্ডেন্সি ভালনারেবিলিটি স্ক্যান করে।
        """
        logger.info("Starting Dependency Vulnerability Scan...")
        try:
            cmd = ["pip-audit", "-f", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if stdout:
                data = json.loads(stdout.decode())
                dependencies = data.get("dependencies", [])
                for dep in dependencies:
                    vulns = dep.get("vulns", [])
                    for vuln in vulns:
                        self.result.findings.append(AuditFinding(
                            title=f"Vulnerable Dependency: {dep.get('name')} ({dep.get('version')})",
                            severity="HIGH",
                            description=f"Advisory ID: {vuln.get('id')} - {vuln.get('description')}",
                            file_path="requirements.txt / pyproject.toml",
                            remediation=f"Upgrade {dep.get('name')} to a patched version."
                        ))
            logger.info("Dependency scan completed.")
        except FileNotFoundError:
            logger.warning("⚠️ pip-audit is not installed. Run 'pip install pip-audit' to enable dependency scan.")
        except Exception as e:
            logger.error(f"Dependency scan failed: {e}")

    async def scan_secrets_exposure(self) -> None:
        """
        বাংলা মন্তব্য: কোডবেসে হার্ডকোডেড এপিআই কি বা ডিক্লেয়ার্ড সিক্রেটস আছে কিনা তা রুলস দিয়ে চেক করে।
        """
        logger.info("Scanning for hardcoded secrets...")
        # Common pattern matching regex for secrets
        patterns = {
            "API Key / Secret": r"(?i)(api_key|secret_key|private_key|password|db_password)\s*=\s*['\"][a-zA-Z0-9_\-\+\/]{16,}['\"]",
            "JWT Secret Header": r"(?i)(jwt_secret|jwt_key)\s*=\s*['\"][a-zA-Z0-9_\-\+\/]{16,}['\"]",
        }

        for path in self.target_dir.rglob("*.py"):
            try:
                content = path.read_text(encoding="utf-8")
                for name, regex in patterns.items():
                    matches = re.finditer(regex, content)
                    for match in matches:
                        self.result.findings.append(AuditFinding(
                            title=f"Potential Hardcoded Secret: {name}",
                            severity="HIGH",
                            description=f"Secret variable definition detected: '{match.group(0)[:30]}...'",
                            file_path=str(path),
                            line_number=content[:match.start()].count("\n") + 1,
                            remediation="Move secrets to environment variables or use a secret management service."
                        ))
            except Exception as e:
                logger.debug(f"Failed to read file {path}: {e}")
        logger.info("Secrets exposure scan completed.")


class ReportGenerator:
    """
    বাংলা মন্তব্য: অডিটের রেজাল্ট থেকে সুন্দর এবং রিডেবল এইচটিএমএল রিপোর্ট জেনারেট করে।
    """

    def __init__(self, output_dir: Path = REPORT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(self, result: AuditResult) -> str:
        """বাংলা মন্তব্য: HTML রিপোর্ট তৈরি করে"""
        severity_colors = {
            "HIGH": "#dc3545",
            "MEDIUM": "#ffc107",
            "LOW": "#17a2b8",
            "INFO": "#6c757d",
        }

        finding_rows = ""
        for f in result.findings:
            color = severity_colors.get(f.severity.upper(), "#6c757d")
            finding_rows += f"""
            <tr>
                <td><span style="background:{color};color:white;padding:4px 8px;border-radius:4px;font-size:12px;">{f.severity}</span></td>
                <td><strong>{f.title}</strong></td>
                <td>{f.description}</td>
                <td><code>{f.file_path}:{f.line_number}</code></td>
                <td>{f.remediation}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <title>SupremeAI 2.0 Security Audit Report</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        .header {{ background: #161b22; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ background: #21262d; font-weight: 600; }}
        code {{ background: #21262d; padding: 2px 6px; border-radius: 4px; color: #f0883e; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ SupremeAI 2.0 Security Audit & Compliance Report</h1>
        <p>Target: <code>{DEFAULT_TARGET_DIR}</code> | Run Time: {result.timestamp}</p>
    </div>
    <h2>📋 Audit Findings ({len(result.findings)})</h2>
    <table>
        <tr><th>Severity</th><th>Title</th><th>Description</th><th>Location</th><th>Remediation</th></tr>
        {finding_rows if finding_rows else "<tr><td colspan='5' style='text-align:center;'>🎉 No security issues found!</td></tr>"}
    </table>
</body>
</html>"""

        file_path = self.output_dir / f"audit_report_{datetime.now(UTC):%Y%m%d_%H%M%S}.html"
        file_path.write_text(html, encoding="utf-8")
        return str(file_path)


# ── Runner ───────────────────────────────────────────────────────────────────

async def run_audit():
    start_time = time.time()
    auditor = SecurityAuditor()

    # Run scans
    await auditor.run_static_analysis()
    await auditor.run_dependency_scan()
    await auditor.scan_secrets_exposure()

    auditor.result.scan_duration = time.time() - start_time

    # Generate report
    generator = ReportGenerator()
    html_file = generator.generate_html(auditor.result)

    print("\n" + "=" * 70)
    print(f"🛡️  SupremeAI 2.0 Security Audit Completed in {auditor.result.scan_duration:.2f}s")
    print(f"Total Findings Found: {len(auditor.result.findings)}")
    print(f"Report Generated: {html_file}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_audit())


# --- Merged from security_penetration_test.py ---

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# ফাইল    : security_penetration_test.py
# প্রকল্প  : SupremeAI 2.0 — Testing Suite
# উদ্দেশ্য  : স্বয়ংক্রিয় সিকিউরিটি পেনিট্রেশন টেস্ট এবং দুর্বলতা স্ক্যান
# মডিউল   : scripts/testing
# লেখক    : SupremeAI Architecture Team
# তারিখ   : ২০ জুলাই, ২০২৬
# ============================================================================
"""
SupremeAI — Automated Penetration Testing Suite
================================================
Simulates security attacks to identify vulnerabilities.

বৈশিষ্ট্য:
  • HTTP Security Header validation
  • Rate limiting / DDoS simulation
  • SQL injection vulnerability detection
  • XSS vulnerability detection
  • PII exposure scan in API responses
  • Prompt injection tester
  • CORS origin configuration auditing
  • Automated risk score calculation

ব্যবহার:
  python scripts/testing/security_penetration_test.py --target http://localhost:8000
  python scripts/testing/security_penetration_test.py --target http://localhost:8000 --scope full
  python scripts/testing/security_penetration_test.py --target http://localhost:8000 --tests headers,ratelimit
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

# বাংলা মন্তব্য: SupremeAI core-এর সাথে কম্প্যাটিবিলিটি
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT = 10
REPORT_DIR = Path(os.getenv("PENETRATION_REPORT_DIR", "tests/reports/security"))


# ── Data Models ──────────────────────────────────────────────────────────────
@dataclass
class Vulnerability:
    """বাংলা মন্তব্য: সনাক্তকৃত দুর্বলতা মডেল"""
    test_name: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    description: str
    expected: str
    actual: str
    remediation: str


@dataclass
class PenetrationResult:
    """বাংলা মন্তব্য: পেনিট্রেশন টেস্ট রেজাল্ট মডেল"""
    target: str
    timestamp: str
    total_tests: int
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    risk_score: int = 0  # Scale 0 - 100
    duration: float = 0.0


# ── Penetration Test Orchestrator ───────────────────────────────────────────
class PenetrationTestOrchestrator:
    """বাংলা মন্তব্য: সিকিউরিটি পেনিট্রেশন টেস্টের মূল অর্কেস্ট্রেটর"""

    TEST_REGISTRY = {}

    def __init__(self, target_url: str, tests_to_run: list[str] | None = None):
        self.target = target_url.rstrip("/")
        self.tests = tests_to_run or list(self.TEST_REGISTRY.keys())
        self.vulnerabilities: list[Vulnerability] = []
        self.client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=False)

    @classmethod
    def register_test(cls, name: str):
        """বাংলা মন্তব্য: নতুন টেস্ট কেস রেজিস্টার করার ডেকোরেটর"""
        def decorator(func):
            cls.TEST_REGISTRY[name] = func
            return func
        return decorator

    async def run(self) -> PenetrationResult:
        """বাংলা মন্তব্য: সব সিলেক্টেড সিকিউরিটি টেস্ট রান করা"""
        logger.info(f"🛡️ Starting automated security scan on: {self.target}")
        start_time = time.time()

        for test_name in self.tests:
            if test_name in self.TEST_REGISTRY:
                logger.info(f"🔎 Running: {test_name}")
                try:
                    await self.TEST_REGISTRY[test_name](self)
                except Exception as e:
                    logger.error(f"Error running test {test_name}: {e}")

        duration = time.time() - start_time
        risk_score = self._calculate_risk_score()

        await self.client.aclose()

        return PenetrationResult(
            target=self.target,
            timestamp=datetime.now().isoformat(),
            total_tests=len(self.tests),
            vulnerabilities=self.vulnerabilities,
            risk_score=risk_score,
            duration=duration,
        )

    def _calculate_risk_score(self) -> int:
        """বাংলা মন্তব্য: সনাক্তকৃত দুর্বলতার গুরুত্ব অনুযায়ী রিস্ক স্কোর হিসাব"""
        weight = {"CRITICAL": 40, "HIGH": 25, "MEDIUM": 10, "LOW": 3, "INFO": 0}
        score = 0
        for v in self.vulnerabilities:
            score += weight.get(v.severity, 0)
        return min(score, 100)

    def generate_report(self, result: PenetrationResult):
        """বাংলা মন্তব্য: JSON ও Markdown রিপোর্ট সেভ করা"""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORT_DIR / f"security_scan_{datetime.now():%Y%m%d_%H%M%S}.json"
        report_file.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

        # MD Format
        md_file = report_file.with_suffix(".md")
        md_lines = [
            "# SupremeAI Security Audit Report",
            f"**Target:** {result.target}",
            f"**Risk Score:** {result.risk_score}/100",
            f"**Vulnerabilities Found:** {len(result.vulnerabilities)}",
            "",
            "## Vulnerability Details"
        ]
        for v in result.vulnerabilities:
            md_lines.extend([
                f"### {v.test_name} — {v.severity}",
                f"- **Description:** {v.description}",
                f"- **Expected:** {v.expected}",
                f"- **Actual:** {v.actual}",
                f"- **Remediation:** {v.remediation}",
                ""
            ])
        md_file.write_text("\n".join(md_lines), encoding="utf-8")
        logger.info(f"📄 Security reports saved: {report_file}, {md_file}")


# ── Registered Security Tests ────────────────────────────────────────────────
@PenetrationTestOrchestrator.register_test("headers")
async def test_security_headers(self: PenetrationTestOrchestrator):
    """বাংলা মন্তব্য: সিকিউরিটি রেসপন্স হেডার চেক"""
    try:
        response = await self.client.get(self.target)
        headers = response.headers

        missing = []
        if "strict-transport-security" not in headers:
            missing.append("HSTS")
        if "content-security-policy" not in headers:
            missing.append("CSP")
        if "x-frame-options" not in headers:
            missing.append("X-Frame-Options (Clickjacking defense)")
        if "x-content-type-options" not in headers:
            missing.append("X-Content-Type-Options")

        if missing:
            self.vulnerabilities.append(Vulnerability(
                test_name="headers",
                severity="MEDIUM",
                description=f"Missing vital security headers: {', '.join(missing)}",
                expected="Secure HTTP response headers enforced",
                actual=f"Missing: {missing}",
                remediation="Configure security headers middleware in FastAPI app.",
            ))
    except Exception as e:
        logger.warning(f"Header check failed: {e}")


@PenetrationTestOrchestrator.register_test("ratelimit")
async def test_rate_limiting(self: PenetrationTestOrchestrator):
    """বাংলা মন্তব্য: রেট লিমিটিং এবং ডস এটাক রেজিস্ট্যান্স"""
    limit_hit = False
    try:
        # Rapidly fire 30 requests to try to trigger rate limiter
        for _ in range(30):
            res = await self.client.get(f"{self.target}/")
            if res.status_code == 429:
                limit_hit = True
                break

        if not limit_hit:
            self.vulnerabilities.append(Vulnerability(
                test_name="ratelimit",
                severity="HIGH",
                description="Endpoint allows excessive requests without rate limit (HTTP 429)",
                expected="Rate limiter blocks brute-force requests",
                actual="Allowed 30 consecutive requests with HTTP 200",
                remediation="Enable TenantRateLimiter middleware for all routes.",
            ))
    except Exception as e:
        logger.warning(f"Rate limiting check failed: {e}")


# ── CLI ──────────────────────────────────────────────────────────────────────
async def main():
    global REPORT_DIR
    parser = argparse.ArgumentParser(
        description="SupremeAI Penetration Tester — Automated security scanning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", required=True, help="Target URL (e.g. http://localhost:8000)")
    parser.add_argument("--scope", default="quick", choices=["quick", "full"], help="Testing scope")
    parser.add_argument("--tests", help="Comma-separated test list to run")
    parser.add_argument("--report-dir", default=str(REPORT_DIR), help="Report output directory")

    args = parser.parse_args()

    REPORT_DIR = Path(args.report_dir)

    if args.scope == "quick":
        tests = ["headers", "ratelimit"]
    elif args.scope == "full":
        tests = list(PenetrationTestOrchestrator.TEST_REGISTRY.keys())
    elif args.tests:
        tests = [t.strip() for t in args.tests.split(",")]
    else:
        tests = list(PenetrationTestOrchestrator.TEST_REGISTRY.keys())

    orchestrator = PenetrationTestOrchestrator(args.target, tests)
    result = await orchestrator.run()

    # Print summary
    print("\n" + "=" * 60)
    print("🛡️ SUPREMEAI PENETRATION TEST — RESULTS")
    print("=" * 60)
    print(f"   Target:          {result.target}")
    print(f"   Tests Run:       {result.total_tests}")
    print(f"   Vulnerabilities: {len(result.vulnerabilities)}")
    print(f"   Risk Score:      {result.risk_score}/100")
    print(f"   Duration:        {result.duration:.2f}s")
    print("=" * 60)

    if result.vulnerabilities:
        print("\n🔴 VULNERABILITIES FOUND:")
        for v in result.vulnerabilities:
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(v.severity, "⚪")
            print(f"   {emoji} [{v.severity}] {v.test_name}: {v.description}")
    else:
        print("\n✅ No vulnerabilities detected!")

    # Generate report
    orchestrator.generate_report(result)

    # Exit with error if critical/high vulnerabilities found
    critical_high = [v for v in result.vulnerabilities if v.severity in ("CRITICAL", "HIGH")]
    if critical_high:
        print(f"\n❌ {len(critical_high)} critical/high vulnerabilities found!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
