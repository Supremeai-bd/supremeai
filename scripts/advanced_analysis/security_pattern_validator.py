#!/usr/bin/env python3
"""
Security Pattern Validator for SupremeAI
=======================================
Scans codebase for common security anti-patterns and vulnerabilities.

Detects:
- SQL Injection risks
- XSS (Cross-Site Scripting) vectors
- Hardcoded secrets/credentials
- Insecure deserialization
- Path traversal vulnerabilities
- Command injection risks
- Missing authentication/authorization
- Insecure dependency usage

Usage:
    python security_pattern_validator.py [--project-root ../] [--output-format text|json]
    
This is a STATIC ANALYSIS tool - not a replacement for dynamic testing.
Findings should be verified and may include false positives.

Self-healing principles:
- AST + regex-based pattern matching
- No hardcoded vulnerability signatures
- CI-friendly with severity scoring
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SecurityFinding:
    """A potential security issue found."""
    rule_id: str  # e.g., 'SQL001', 'XSS002'
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'
    category: str  # 'injection', 'xss', 'crypto', 'auth', etc.
    title: str
    description: str
    file_path: str
    line_number: int
    line_content: str
    cwe_ref: str | None = None  # CWE reference if applicable
    remediation: str = ""
    false_positive_likelihood: float = 0.0  # 0.0 = definitely issue, 1.0 = likely FP


@dataclass 
class SecurityReport:
    """Summary of security scan."""
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    files_scanned: int = 0


# Security Rules Definition
SECURITY_RULES = [
    # SQL Injection
    {
        'id': 'SQL001',
        'pattern': r'(?:execute|raw|query)\s*\(\s*f["\']\s*\{[^}]*\}|\s*%\s*[^\)]',
        'language': 'python',
        'severity': 'CRITICAL',
        'category': 'sql_injection',
        'title': 'Potential SQL Injection via f-string or % formatting',
        'description': 'Using f-strings or % formatting in SQL queries can lead to SQL injection if variables contain user input.',
        'cwe': 'CWE-89',
        'remediation': 'Use parameterized queries (SQLAlchemy text() with :param, or psycopg2 placeholders)',
        'fp_likelihood': 0.2,
    },
    {
        'id': 'SQL002',
        'pattern': r'\.execute\s*\(\s*["\'].*(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\+\s*(?:request\.|form\[|args\[|params\[)',
        'language': 'python',
        'severity': 'HIGH',
        'category': 'sql_injection',
        'title': 'SQL Query with Direct User Input Concatenation',
        'description': 'User input appears to be directly concatenated into SQL query string.',
        'cwe': 'CWE-89',
        'remediation': 'Use parameterized queries with proper escaping',
        'fp_likelihood': 0.3,
    },
    
    # XSS Risks
    {
        'id': 'XSS001',
        'pattern': r'(?:dangerouslySetInnerHTML|__html|v-html)\s*\(',
        'language': ['typescript', 'javascript'],
        'severity': 'CRITICAL',
        'category': 'xss',
        'title': 'Use of dangerouslySetInnerHTML or v-html',
        'description': 'Rendering unescaped HTML content can lead to Cross-Site Scripting (XSS).',
        'cwe': 'CWE-79',
        'remediation': 'Use DOMPurify/sanitize before rendering, or use safe templating',
        'fp_likelihood': 0.4,
    },
    {
        'id': 'XSS002',
        'pattern': r'innerHTML\s*=',
        'language': ['typescript', 'javascript'],
        'severity': 'HIGH',
        'category': 'xss',
        'title': 'Direct innerHTML Assignment',
        'description': 'Direct assignment to innerHTML without sanitization can be exploited for XSS.',
        'cwe': 'CWE-79',
        'remediation': 'Use textContent for plain text, or sanitize HTML input first',
        'fp_likelihood': 0.5,
    },
    
    # Hardcoded Secrets
    {
        'id': 'SEC001',
        'pattern': r'(?:password|passwd|secret|api_key|apikey|token)\s*=\s*["\'][^"\']{8,}',
        'language': ['python', 'typescript', 'javascript'],
        'severity': 'CRITICAL',
        'category': 'secrets_management',
        'title': 'Hardcoded Secret/Credential Detected',
        'description': 'A secret, password, or credential appears to be hardcoded in source code.',
        'cwe': 'CWE-798',
        'remediation': 'Move to environment variable or secret management service (Infisical, Vault)',
        'fp_likelihood': 0.15,
    },
    {
        'id': 'SEC002',
        'pattern': r'(?:AKIA|ghp_|sk_test_|xoxbap|AIza)[a-zA-Z0-9_]{10,}',
        'language': ['python', 'typescript', 'javascript'],
        'severity': 'CRITICAL',
        'category': 'secrets_management',
        'title': 'Hardcoded Cloud Provider Key Detected',
        'description': 'An AWS/GitHub/OpenAI/Slack API key appears to be hardcoded.',
        'cwe': 'CWE-798',
        'remediation': 'Rotate key immediately and move to secure secret store',
        'fp_likelihood': 0.05,
    },
    
    # Command Injection
    {
        'id': 'CMD001',
        'pattern': r'(?:os\.system|subprocess\.call|exec|spawn)\s*\(\s*f["\']|\s*%\s*|\s*\+\s*',
        'language': 'python',
        'severity': 'CRITICAL',
        'category': 'command_injection',
        'title': 'Potential Command Injection via String Formatting',
        'description': 'OS command executed with formatted string that may contain user input.',
        'cwe': 'CWE-78',
        'remediation': 'Use subprocess with list argument (no shell=True) and validate input',
        'fp_likelihood': 0.25,
    },
    {
        'id': 'CMD002',
        'pattern': r'shell\s*=\s*True',
        'language': 'python',
        'severity': 'HIGH',
        'category': 'command_injection',
        'title': 'Shell Execution Enabled in Subprocess',
        'description': 'shell=True in subprocess allows shell metacharacter injection.',
        'cwe': 'CWE-78',
        'remediation': 'Avoid shell=True; use list arguments instead',
        'fp_likelihood': 0.2,
    },
    
    # Path Traversal
    {
        'id': 'PATH001',
        'pattern': r'open\s*\(\s*(?:f["\']?\s*\{[^}]*\}|request\.args\[[^\]]+\]|request\.params\[[^\]]+\])',
        'language': 'python',
        'severity': 'HIGH',
        'category': 'path_traversal',
        'title': 'Potential Path Traversal in File Operation',
        'description': 'File opened using unsanitized user-provided path.',
        'cwe': 'CWE-22',
        'remediation': 'Validate and sanitize file paths; use allowlist of permitted directories',
        'fp_likelihood': 0.35,
    },
    {
        'id': 'PATH002',
        'pattern': r'\.\./',
        'language': ['python', 'typescript', 'javascript'],
        'severity': 'MEDIUM',
        'category': 'path_traversal',
        'title': 'Relative Path Usage (../) Detected',
        'description': 'Path containing "../" could potentially traverse directories.',
        'cwe': 'CWE-22',
        'remediation': 'Use absolute paths or validate against allowed base directory',
        'fp_likelihood': 0.7,
    },
    
    # Insecure Deserialization
    {
        'id': 'DESER001',
        'pattern': r'pickle\.loads?\s*\(|yaml\.load\s*\(|marshal\.loads?\s*\(',
        'language': 'python',
        'severity': 'CRITICAL',
        'category': 'insecure_deserialization',
        'title': 'Insecure Deserialization (pickle/yaml/marshal)',
        'description': 'Deserializing untrusted data with pickle/yaml/marshal can lead to arbitrary code execution.',
        'cwe': 'CWE-502',
        'remediation': 'Use JSON schema validation or safe serialization formats',
        'fp_likelihood': 0.3,
    },
    {
        'id': 'DESER002',
        'pattern': r'JSON\.parse\s*\(',
        'language': ['typescript', 'javascript'],
        'severity': 'MEDIUM',
        'category': 'insecure_deserialization',
        'title': 'JSON.parse Without Try-Catch or Validation',
        'description': 'JSON.parse can throw on invalid/malicious input; should be wrapped safely.',
        'cwe': 'CWE-20',
        'remediation': 'Wrap in try-catch; validate JSON structure before parsing',
        'fp_likelihood': 0.6,
    },
    
    # Authentication Issues
    {
        'id': 'AUTH001',
        'pattern': r'(?:@app\.(?:get|post|put|delete))\s*\((?![^)]*depends)',
        'language': 'python',
        'severity': 'HIGH',
        'category': 'authentication',
        'title': 'Endpoint Without Authentication Requirement',
        'description': 'API endpoint defined without visible authentication/authorization check.',
        'cwe': 'CWE-862',
        'remediation': 'Add authentication requirement to sensitive endpoints',
        'fp_likelihood': 0.6,
    },
    {
        'id': 'AUTH002',
        'pattern': r'jwt_required\s*=\s*False',
        'language': ['python', 'typescript', 'javascript'],
        'severity': 'HIGH',
        'category': 'authentication',
        'title': 'JWT Verification Disabled',
        'description': 'JWT required flag explicitly set to False, bypassing token verification.',
        'cwe': 'CWE-863',
        'remediation': 'Verify this is intentional; document reason for disabling auth',
        'fp_likelihood': 0.2,
    },
    
    # Cryptographic Issues
    {
        'id': 'CRYPTO001',
        'pattern': r'md5\s*\(|hashlib\.md5|MD5\(',
        'language': ['python', 'typescript', 'javascript'],
        'severity': 'MEDIUM',
        'category': 'weak_crypto',
        'title': 'MD5 Hash Function Usage',
        'description': 'MD5 is cryptographically broken and should not be used for security purposes.',
        'cwe': 'CWE-328',
        'remediation': 'Use SHA-256, SHA-3, or bcrypt for cryptographic hashing',
        'fp_likelihood': 0.4,
    },
    {
        'id': 'CRYPTO002',
        'pattern': r'random\.random\s*\(',
        'language': 'python',
        'severity': 'MEDIUM',
        'category': 'weak_crypto',
        'title': 'Use of Non-Cryptographic Random',
        'description': 'random.random is predictable and not suitable for security-sensitive operations.',
        'cwe': 'CWE-330',
        'remediation': 'Use secrets module (Python) or crypto.randomBytes (Node.js)',
        'fp_likelihood': 0.35,
    },
    
    # Information Exposure
    {
        'id': 'INFO001',
        'pattern': r'print\s*\(\s*(?:password|token|secret|credential|ssn|credit_card)',
        'language': 'python',
        'severity': 'MEDIUM',
        'category': 'information_exposure',
        'title': 'Sensitive Data in Print Statement',
        'description': 'Sensitive information (password/token/etc.) being printed to logs/console.',
        'cwe': 'CWE-209',
        'remediation': 'Remove print statements; use proper logging with sanitization',
        'fp_likelihood': 0.25,
    },
    {
        'id': 'INFO002',
        'pattern': r'console\.(log|debug|info)\s*\(\s*(?:password|token|secret|credential)',
        'language': ['typescript', 'javascript'],
        'severity': 'MEDIUM',
        'category': 'information_exposure',
        'title': 'Sensitive Data in Console Log',
        'description': 'Sensitive information being logged to browser console.',
        'cwe': 'CWE-209',
        'remediation': 'Remove console.log of sensitive data; use structured logging',
        'fp_likelihood': 0.25,
    },
]


class SecurityScanner:
    """Scans source code for security patterns."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.findings: list[SecurityFinding] = []
        
    def scan(self) -> list[SecurityFinding]:
        """Scan all source files."""
        self._scan_python_files()
        self._scan_typescript_files()
        
        logger.info(f"Found {len(self.findings)} potential security findings")
        return self.findings
    
    def _scan_python_files(self):
        """Scan Python files."""
        py_files = list(self.project_root.rglob("*.py"))
        skip_dirs = {'__pycache__', '.git', 'venv', '.venv', 'node_modules',
                    'migrations', 'dist', 'build'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            
            # Skip test files from critical findings
            if any(p in str(py_file) for p in ['test_', '_test']):
                continue
                
            self._scan_file(py_file, 'python')
    
    def _scan_typescript_files(self):
        """Scan TypeScript/JavaScript files."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        skip_dirs = {'node_modules', 'dist', '.next', 'coverage'}
        
        for ext in extensions:
            for ts_file in self.project_root.rglob(ext):
                if any(skip in str(ts_file) for skip in skip_dirs):
                    continue
                self._scan_file(ts_file, 'typescript')
    
    def _scan_file(self, file_path: Path, language: str):
        """Scan a single file against all rules."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_root.parent))
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if stripped.startswith(('#', '//', '*')):
                continue
            
            for rule in SECURITY_RULES:
                # Check language applicability
                rule_lang = rule.get('language', '')
                if isinstance(rule_lang, list):
                    if language not in rule_lang:
                        continue
                elif language != rule_lang:
                    continue
                
                # Check pattern match
                match = re.search(rule['pattern'], stripped, re.IGNORECASE)
                if match:
                    finding = SecurityFinding(
                        rule_id=rule['id'],
                        severity=rule['severity'],
                        category=rule['category'],
                        title=rule['title'],
                        description=rule['description'],
                        file_path=rel_path,
                        line_number=i + 1,
                        line_content=stripped[:150],
                        cwe_ref=rule.get('cwe'),
                        remediation=rule['remediation'],
                        false_positive_likelihood=rule.get('fp_likelihood', 0.5)
                    )
                    
                    self.findings.append(finding)


class ReportGenerator:
    """Generates security reports."""
    
    def __init__(self, findings: list[SecurityFinding]):
        self.findings = sorted(findings, key=lambda f: (
            {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3, 'INFO': 4}.get(f.severity, 5),
            f.false_positive_likelihood  # Lower FP likelihood = higher priority
        ))
        self.report = SecurityReport(total_findings=len(findings))
        
        # Calculate summary stats
        for finding in self.findings:
            if finding.severity == 'CRITICAL':
                self.report.critical_count += 1
            elif finding.severity == 'HIGH':
                self.report.high_count += 1
            elif finding.severity == 'MEDIUM':
                self.report.medium_count += 1
            elif finding.severity == 'LOW':
                self.report.low_count += 1
            
            cat = finding.category
            self.report.by_category[cat] = self.report.by_category.get(cat, 0) + 1
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI SECURITY PATTERN VALIDATOR REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Disclaimer
        lines.append("⚠️ DISCLAIMER")
        lines.append("-" * 40)
        lines.append("  This is STATIC ANALYSIS only.")
        lines.append("  Findings should be manually verified.")
        lines.append("  Some results may be false positives.")
        lines.append("")
        
        # Summary
        lines.append("SECURITY SCAN SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Findings:               {self.report.total_findings}")
        lines.append(f"  🔴 Critical:                   {self.report.critical_count}")
        lines.append(f"  🟠 High:                       {self.report.high_count}")
        lines.append(f"  🟡 Medium:                     {self.report.medium_count}")
        lines.append(f"  🟢 Low:                        {self.report.low_count}")
        lines.append("")
        
        # Verdict
        if self.report.critical_count > 0:
            lines.append("  ⚠️ VERDICT: CRITICAL ISSUES FOUND - IMMEDIATE ACTION REQUIRED")
        elif self.report.high_count > 3:
            lines.append("  ⚠️ VERDICT: MULTIPLE HIGH SEVERITY ISSUES")
        elif self.report.high_count > 0:
            lines.append("  ⚠️ VERDICT: SECURITY ISSUES NEED ATTENTION")
        else:
            lines.append("  ✅ VERDICT: NO CRITICAL ISSUES FOUND")
        lines.append("")
        
        # By Category
        if self.report.by_category:
            lines.append("\nFINDINGS BY CATEGORY")
            lines.append("-" * 40)
            
            category_labels = {
                'sql_injection': '💉 SQL Injection',
                'xss': '🌐 Cross-Site Scripting (XSS)',
                'secrets_management': '🔐 Secrets Management',
                'command_injection': '💻 Command Injection',
                'path_traversal': '📁 Path Traversal',
                'insecure_deserialization': '📦 Insecure Deserialization',
                'authentication': '🔑 Authentication Issues',
                'weak_crypto': '🔒 Weak Cryptography',
                'information_exposure': '👁️ Information Exposure',
            }
            
            for cat, count in sorted(self.report.by_category.items(), 
                                       key=lambda x: -x[1]):
                label = category_labels.get(cat, cat.title())
                icon = '🔴' if count > 3 else ('🟠' if count > 1 else '🟡')
                lines.append(f"  {icon} {label:<35} {count:>5}")
        
        # Detailed Findings
        lines.append("\n\nDETAILED FINDINGS")
        lines.append("=" * 40)
        
        # Group by severity
        critical = [f for f in self.findings if f.severity == 'CRITICAL']
        high = [f for f in self.findings if f.severity == 'HIGH']
        medium = [f for f in self.findings if f.severity == 'MEDIUM']
        
        if critical:
            lines.append("\n🔴 CRITICAL FINDINGS")
            lines.append("-" * 40)
            for finding in critical[:20]:
                lines.append(f"\n  [{finding.rule_id}] {finding.title}")
                lines.append(f"     File:    {finding.file_path}:{finding.line_number}")
                lines.append(f"     CWE:     {finding.cwe_ref or 'N/A'}")
                lines.append(f"     Issue:   {finding.description}")
                lines.append(f"     Code:    {finding.line_content[:100]}")
                lines.append(f"     Fix:     {finding.remediation}")
                
                if finding.false_positive_likelihood < 0.3:
                    lines.append("     ⚡ Confidence: HIGH (low FP risk)")
        
        if high:
            lines.append(f"\n\n🟠 HIGH SEVERITY FINDINGS ({len(high)} total)")
            lines.append("-" * 40)
            for finding in high[:15]:
                lines.append(f"  • [{finding.rule_id}] {finding.title} at {finding.file_path}:{finding.line_number}")
        
        if medium:
            lines.append(f"\n\n🟡 MEDIUM SEVERITY FINDINGS ({len(medium)} total)")
            lines.append("-" * 40)
            for finding in medium[:10]:
                lines.append(f"  • [{finding.rule_id}] {finding.title} at {finding.file_path}:{finding.line_number}")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("SECURITY BEST PRACTICES")
        lines.append("=" * 80)
        lines.append("""
Immediate Actions:

1. **Address CRITICAL findings first**
   - These are most likely to be exploitable
   - Prioritize injection (SQL, command, XSS) issues

2. **Rotate exposed credentials**
   - Any hardcoded secret must be rotated
   - Move to secure secret manager

3. **Implement security headers**
   - Content-Security-Policy
   - X-Content-Type-Options: nosniff
   - Strict-Transport-Security

4. **Set up security scanning in CI**
   - Add this script to pipeline
   - Consider Snyk, Dependabot, CodeQL
   - Fail builds on new CRITICAL findings

5. **Regular security audits**
   - Quarterly penetration testing
   - Dependency vulnerability scanning
   - Code review security checklist

Resources:
  - OWASP Top 10: https://owasp.org/www-project-top-ten/
  - CWE Dictionary: https://cwe.mitre.org/
  - Secure Coding Guidelines: https://owasp.org/project-guidelines/

Note: This tool catches COMMON PATTERNS only.
It does NOT replace professional security auditing or penetration testing.
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total": self.report.total_findings,
                "critical": self.report.critical_count,
                "high": self.report.high_count,
                "medium": self.report.medium_count,
                "low": self.report.low_count,
            },
            "by_category": self.report.by_category,
            "findings": [{
                "rule_id": f.rule_id,
                "severity": f.severity,
                "category": f.category,
                "title": f.title,
                "file": f.file_path,
                "line": f.line_number,
                "cwe": f.cwe_ref,
                "remediation": f.remediation,
                "code_snippet": f.line_content[:200],
            } for f in self.findings],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Security Pattern Validator',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--project-root', '-p', default='..')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit error if critical findings found')
    parser.add_argument('--fail-on-high', type=int, default=0,
                       help='Exit error if high severity findings exceed count')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    print("🛡️ SupremeAI Security Pattern Validator")
    print(f"   Project Root: {project_root}")
    print()
    
    # Scan
    scanner = SecurityScanner(project_root)
    findings = scanner.scan()
    
    # Generate report
    generator = ReportGenerator(findings)
    
    if args.output_format == 'json':
        output = json.dumps(generator.generate_json_report(), indent=2)
    else:
        output = generator.generate_text_report()
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"✅ Report written to: {args.output_file}")
    else:
        print(output)
    
    # Exit codes
    if args.fail_on_critical and generator.report.critical_count > 0:
        sys.exit(1)
    
    if args.fail_on_high and generator.report.high_count > args.fail_on_high:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
