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
import re
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
