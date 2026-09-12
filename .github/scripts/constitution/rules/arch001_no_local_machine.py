"""ARCH-001: No Local-Machine Dependency (Production Environment Agnostic)."""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AuditFinding, RuleCategory, RuleDefinition, Severity
from .base import BaseRule


class NoLocalMachineRule(BaseRule):
    """Detects hardcoded localhost, 127.0.0.1, and Windows-specific paths in production code."""

    DEFINITION = RuleDefinition(
        rule_id="ARCH-001",
        category=RuleCategory.ARCHITECTURE,
        title="No Local-Machine Dependency",
        description="Production code must not reference localhost, 127.0.0.1, or Windows-specific paths.",
        severity=Severity.BLOCK,
        fixable=True,
        details="Detected hardcoded local machine dependencies that would break in cloud environments.",
    )

    def __init__(self):
        """Initialize the rule."""
        super().__init__(self.DEFINITION)

    def audit(self, files: list[Path]) -> list[AuditFinding]:
        """Scan files for local machine dependencies."""
        findings = []

        for file_path in files:
            if self.should_skip_file(file_path):
                continue

            # Skip infrastructure/docker/compose files that legitimately reference localhost
            if any(x in str(file_path) for x in ["docker", "compose", "infra", "k8s"]):
                continue

            findings.extend(self._check_file(file_path))

        return findings

    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        """Check a single file for violations."""
        findings = []

        # Patterns to detect
        localhost_pattern = re.compile(
            r"(?:localhost|127\.0\.0\.1|127\.0\.1\.1|0\.0\.0\.0|::\s*1)(?:\D|$)",
            re.IGNORECASE,
        )
        windows_path_pattern = re.compile(r"[cCdDeE]:\\|\\\\(?:\.\\)?(?:Users|Windows|Program Files)")

        # Exclude patterns (comments, strings that are clearly safe)
        exclude_patterns = [
            r"#.*(?:localhost|127\.0\.0\.1)",  # Comments
            r"test.*http://localhost",  # Test URLs
            r"127\.0\.0\.1.*test",  # Test IPs
            r"docker-compose",  # Docker files
        ]

        matches = self._find_in_file(file_path, localhost_pattern, exclude_patterns)
        for line_num, line_text in matches:
            # Skip test and fixture files
            if "test" in file_path.name.lower():
                continue

            findings.append(
                self._create_finding(
                    file_path,
                    line_number=line_num,
                    message=f"Hardcoded localhost/127.0.0.1 detected: {line_text.strip()[:80]}",
                    remediation="Use environment variables or cloud-agnostic service discovery.",
                    confidence=0.95,
                )
            )

        # Check for Windows paths (much stricter in non-Windows code)
        matches = self._find_in_file(file_path, windows_path_pattern)
        for line_num, line_text in matches:
            if "test" in file_path.name.lower():
                continue

            findings.append(
                self._create_finding(
                    file_path,
                    line_number=line_num,
                    message=f"Windows-specific path detected: {line_text.strip()[:80]}",
                    remediation="Use pathlib.Path or os.path.join for cross-platform paths.",
                    confidence=0.9,
                )
            )

        return findings
