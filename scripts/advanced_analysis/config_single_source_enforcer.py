#!/usr/bin/env python3
"""
Config Single Source Enforcer for SupremeAI
==============================================
Finds hardcoded literals (timeouts, max_tokens, rate-limits, etc.)
scattered across codebase and generates HARDCODED_AUDIT.md report.

This automates what was previously a manual audit process.

Detects:
- Numeric magic numbers that look like configuration
- String literals that should be constants
- Duplicate values across files (should be centralized)
- Configuration-like patterns outside config files

Usage:
    python config_single_source_enforcer.py [--project-root ../] [--output-format text|json|markdown]
    
Self-healing principles:
- Fully dynamic detection (no hardcoded watchlist)
- Pattern-based heuristics to identify config-like values
- CI-friendly: can fail build on new hardcodes
- Generates actionable report with file:line references
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from re import Pattern

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class HardcodedFinding:
    """Represents a potential hardcoded value that should be configured."""
    value: str  # The actual hardcoded value
    value_type: str  # 'numeric', 'string', 'boolean', 'url', 'timeout', etc.
    file_path: str
    line_number: int
    line_content: str
    context: str  # Variable name or surrounding context
    category: str  # timeout, limit, url, key, threshold, etc.
    confidence: float  # 0.0 - 1.0 how likely this is truly problematic
    suggestion: str = ""
    similar_findings: list[str] = field(default_factory=list)  # References to same value elsewhere


@dataclass
class ConfigFileReference:
    """Reference to where this should ideally be configured."""
    suggested_location: str  # e.g., "settings.py", "config.yaml", "env var TIMEOUT"
    existing_config: bool = False  # Does this config already exist somewhere?
    config_key: str = ""  # If exists, what's the key name?


@dataclass
class AuditSummary:
    """Summary of the hardcoded audit."""
    total_findings: int = 0
    high_confidence: int = 0  # confidence > 0.8
    medium_confidence: int = 0  # confidence > 0.5
    categories: dict[str, int] = field(default_factory=dict)
    most_common_values: list[tuple[str, int]] = field(default_factory=list)
    files_affected: int = 0
    new_since_last_audit: int = 0  # If baseline provided


# Patterns that suggest a numeric literal is configuration-related
CONFIG_NUMERIC_PATTERNS: list[tuple[Pattern[str], str, float]] = [
    # Timeouts (seconds, milliseconds)
    (re.compile(r'(?:timeout|time_out|wait|delay|sleep|interval|ttl)\s*[=:]\s*(\d+(?:\.\d+)?)', re.IGNORECASE), 
     'timeout', 0.9),
    (re.compile(r'\b(\d{1,4}(?:\.\d+)?)\s*(?:#\s*.*(?:timeout|sec|ms))'),
     'timeout', 0.7),
    
    # Rate limits
    (re.compile(r'(?:rate.?limit|max.?req|requests?|throttle|rps|qps)\s*[=:]\s*(\d+)', re.IGNORECASE),
     'rate_limit', 0.95),
    (re.compile(r'(?:per_?(?:second|minute|hour)|/(?:s|min|h))\s*[:=]\s*(\d+)', re.IGNORECASE),
     'rate_limit', 0.85),
    
    # Token/size limits
    (re.compile(r'(?:max_?(?:token|char|length|size)|limit|(?:token|char|length|size)_?limit)\s*[=:]\s*(\d+)', re.IGNORECASE),
     'size_limit', 0.9),
    (re.compile(r'max_tokens?\s*=\s*(\d+)', re.IGNORECASE),
     'max_tokens', 0.95),
    (re.compile(r'context_window\s*=\s*(\d+)', re.IGNORECASE),
     'context_limit', 0.9),
    
    # Retries
    (re.compile(r'(?:max_?retries?|retry_?(?:count|max|attempts))\s*[=:]\s*(\d+)', re.IGNORECASE),
     'retry_count', 0.92),
    (re.compile(r'retry_?(?:backoff|delay|wait)\s*[=:]\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
     'retry_delay', 0.88),
    
    # Batch/pagination sizes
    (re.compile(r'(?:batch_?size|page_?size|chunk_?size|buffer_?size|pool_?size)\s*[=:]\s*(\d+)', re.IGNORECASE),
     'batch_size', 0.85),
    (re.compile(r'(?:limit|per_page|page_size|offset)\s*=\s*(\d+)', re.IGNORECASE),
     'pagination', 0.75),
    
    # Port numbers
    (re.compile(r'(?:port)\s*[=:]\s*(\d{2,5})', re.IGNORECASE),
     'port', 0.9),
    
    # Percentages/thresholds
    (re.compile(r'(?:threshold|cutoff|ratio|percent(?:age)?)\s*[=:]\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
     'threshold', 0.8),
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:#\s*.*)?$'),
     'percentage', 0.6),
    
    # Memory sizes
    (re.compile(r'(?:max_?)?(?:memory|ram|heap)\s*[=:]\s*(\d+[kKmMgGtT]?)', re.IGNORECASE),
     'memory_size', 0.85),
    
    # Expiration times
    (re.compile(r'(?:expire|expiry|expires_in|valid_for|lifetime|age|max_age)\s*[=:]\s*(\d+)', re.IGNORECASE),
     'expiration', 0.87),
]

# Patterns for string literals that should be constants
CONFIG_STRING_PATTERNS: list[tuple[Pattern[str], str, float]] = [
    # URLs
    (re.compile(r'[\'"](https?://[^\s"\']+)[\'"]', re.IGNORECASE),
     'url', 0.7),
    
    # Service names/endpoints
    (re.compile(r'(?:service|host|endpoint|url|base_url|api_url)\s*[=:]\s*[\'"]([^"\']+)["\']', re.IGNORECASE),
     'service_url', 0.92),
    
    # Feature flags / mode strings
    (re.compile(r'(?:mode|environment|env|stage)\s*[=:]\s*[\'"](\w+)["\']', re.IGNORECASE),
     'mode_string', 0.75),
    
    # Header names
    (re.compile(r'(?:header|content.?type|accept)\s*[=:]\s*[\'"]([^"\']+)["\']', re.IGNORECASE),
     'header_value', 0.7),
    
    # Error messages (these might be intentional, lower confidence)
    (re.compile(r'raise\s+\w+Error\s*\(\s*[\'"]([^"\']{20,})["\']', re.IGNORECASE),
     'error_message', 0.4),
]

# File patterns to skip (these are expected to have literals)
SKIP_FILES = {
    'migrations/', '__pycache__/', 'test_', '_test.', '.test.',
    'node_modules/', 'dist/', '.next/', 'coverage/',
    'package-lock.json', 'yarn.lock',
    'requirements.txt', 'setup.py', 'pyproject.toml',
    '.env', '.env.',
    'LICENSE', 'CHANGELOG', 'README',
}

# Directories that are config files (values here are OK)
CONFIG_DIRECTORIES = {'config/', 'configs/', '.config/'}
CONFIG_FILES = {'settings.py', 'config.py', 'constants.py', 'conf.py',
                'settings.ts', 'config.ts', 'constants.ts',
                'config.yaml', 'config.yml', 'config.json',
                '.env.example', 'env.example'}


class HardcodedScanner:
    """Scans source code for hardcoded configuration values."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.findings: list[HardcodedFinding] = []
        self.value_occurrences: Counter = Counter()  # Track duplicate values
        
    def scan(self) -> list[HardcodedFinding]:
        """Scan all source files for hardcoded values."""
        self._scan_python_files()
        self._scan_typescript_files()
        self._scan_shell_files()
        
        # Post-process: find duplicate values across files
        self._find_duplicates()
        
        logger.info(f"Found {len(self.findings)} potential hardcoded values")
        return self.findings
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        rel_str = str(file_path.relative_to(self.project_root))
        
        # Skip specific patterns
        for pattern in SKIP_FILES:
            if pattern in rel_str:
                return True
        
        # Don't skip config files entirely, but mark findings as lower confidence
        filename = file_path.name
        if filename in CONFIG_FILES:
            return False  # Still scan but will adjust confidence
        
        return False
    
    def _is_config_file(self, file_path: Path) -> bool:
        """Check if this is a designated config file."""
        rel_str = str(file_path.relative_to(self.project_root))
        
        for cfg_dir in CONFIG_DIRECTORIES:
            if cfg_dir in rel_str:
                return True
        
        return file_path.name in CONFIG_FILES
    
    def _scan_python_files(self):
        """Scan Python files."""
        py_files = list(self.project_root.rglob("*.py"))
        
        for py_file in py_files:
            if self._should_skip_file(py_file):
                continue
            
            is_config = self._is_config_file(py_file)
            self._scan_py_file(py_file, is_config)
    
    def _scan_py_file(self, file_path: Path, is_config: bool):
        """Scan a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and docstrings (basic check)
            if stripped.startswith('#') or '"""' in stripped or "'''" in stripped:
                continue
            
            # Check numeric patterns
            for pattern, category, base_confidence in CONFIG_NUMERIC_PATTERNS:
                matches = pattern.finditer(line)
                for match in matches:
                    value = match.group(1) if match.lastindex and match.group(1) else match.group(0)
                    
                    # Adjust confidence based on context
                    confidence = base_confidence
                    if is_config:
                        confidence *= 0.3  # Much lower confidence in config files
                    
                    # Extract context (variable name being assigned)
                    context = self._extract_assignment_context(line)
                    
                    finding = HardcodedFinding(
                        value=value,
                        value_type='numeric',
                        file_path=rel_path,
                        line_number=i + 1,
                        line_content=stripped[:120],
                        context=context,
                        category=category,
                        confidence=confidence,
                        suggestion=self._suggest_config_location(category, value)
                    )
                    
                    self.findings.append(finding)
                    self.value_occurrences[value] += 1
            
            # Check string patterns
            for pattern, category, base_confidence in CONFIG_STRING_PATTERNS:
                matches = pattern.finditer(line)
                for match in matches:
                    value = match.group(1) if match.lastindex >= 1 else match.group(0)
                    
                    # Skip very short strings
                    if len(value) < 3:
                        continue
                    
                    confidence = base_confidence
                    if is_config:
                        confidence *= 0.3
                    
                    context = self._extract_assignment_context(line)
                    
                    finding = HardcodedFinding(
                        value=value,
                        value_type='string',
                        file_path=rel_path,
                        line_number=i + 1,
                        line_content=stripped[:120],
                        context=context,
                        category=category,
                        confidence=confidence,
                        suggestion=self._suggest_config_location(category, value)
                    )
                    
                    self.findings.append(finding)
                    self.value_occurrences[value] += 1
    
    def _scan_typescript_files(self):
        """Scan TypeScript/JavaScript files."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        
        for ext in extensions:
            for ts_file in self.project_root.rglob(ext):
                if self._should_skip_file(ts_file):
                    continue
                
                is_config = self._is_config_file(ts_file)
                self._scan_ts_file(ts_file, is_config)
    
    def _scan_ts_file(self, file_path: Path, is_config: bool):
        """Scan a single TypeScript/JavaScript file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        # Similar patterns but adapted for JS/TS syntax
        js_patterns = [
            # Timeout patterns
            (r'(?:timeout|timeOut|wait|delay|interval)\s*[:=]\s*(\d+(?:\.\d+)?)', 'timeout', 0.9),
            # Rate limits
            (r'(?:rateLimit|maxRequests?|throttle)\s*[:=]\s*(\d+)', 'rate_limit', 0.93),
            # Max tokens/sizes
            (r'(?:maxTokens?|maxLength|tokenLimit|contextWindow)\s*[:=]\s*(\d+)', 'size_limit', 0.94),
            # Retries
            (r'(?:maxRetries?|retryCount|retryAttempts)\s*[:=]\s*(\d+)', 'retry_count', 0.91),
            # URLs
            (r['"(https?://[^"]+)"'], 'url', 0.72),
            (r"'(https?://[^']+)'", 'url', 0.72),
            (r'`(https?://[^`]+)`', 'url', 0.72),
        ]
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith(('//', '*', '/*')):
                continue
            
            for pattern, category, base_confidence in js_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    value = match.group(1) if match.lastindex >= 1 else match.group(0)
                    
                    confidence = base_confidence
                    if is_config:
                        confidence *= 0.3
                    
                    context = self._extract_assignment_context(line)
                    
                    finding = HardcodedFinding(
                        value=value,
                        value_type='numeric' if value.replace('.','').isdigit() else 'string',
                        file_path=rel_path,
                        line_number=i + 1,
                        line_content=stripped[:120],
                        context=context,
                        category=category,
                        confidence=confidence,
                        suggestion=self._suggest_config_location(category, value)
                    )
                    
                    self.findings.append(finding)
                    self.value_occurrences[value] += 1
    
    def _scan_shell_files(self):
        """Scan shell scripts."""
        shell_files = list(self.project_root.rglob("*.sh"))
        
        for sh_file in shell_files:
            if self._should_skip_file(sh_file):
                continue
            
            self._scan_sh_file(sh_file)
    
    def _scan_sh_file(self, file_path: Path):
        """Scan a single shell script."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return
        
        rel_path = str(file_path.relative_to(self.project_root))
        
        # Shell-specific patterns
        shell_patterns = [
            (r'(?:TIMEOUT|WAIT|DELAY|SLEEP|INTERVAL)=(\d+)', 'timeout', 0.88),
            (r'(?:RETRIES?|MAX_RETRIES?)=(\d+)', 'retry_count', 0.9),
            (r'(?:BATCH|PAGE|CHUNK)_?SIZE=(\d+)', 'batch_size', 0.86),
        ]
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if stripped.startswith('#'):
                continue
            
            for pattern, category, base_confidence in shell_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    
                    finding = HardcodedFinding(
                        value=value,
                        value_type='numeric',
                        file_path=rel_path,
                        line_number=i + 1,
                        line_content=stripped[:120],
                        context=line.split('=')[0] if '=' in line else '',
                        category=category,
                        confidence=base_confidence,
                        suggestion="Export as environment variable or add to .env"
                    )
                    
                    self.findings.append(finding)
                    self.value_occurrences[value] += 1
    
    def _extract_assignment_context(self, line: str) -> str:
        """Extract variable name or context from assignment line."""
        # Python-style: VAR = value
        assign_match = re.match(r'^(\w[\w.]*)\s*=', line.strip())
        if assign_match:
            return assign_match.group(1)
        
        # JS/TS-style: const VAR =, let VAR =, VAR:
        js_match = re.match(r'^(?:const|let|var)\s+(\w[\w]*)', line.strip())
        if js_match:
            return js_match.group(1)
        
        prop_match = re.match(r'^(\w[\w]*)\s*:', line.strip())
        if prop_match:
            return prop_match.group(1)
        
        return ""
    
    def _find_duplicates(self):
        """Find values that appear multiple times (strong signal for centralization)."""
        # Group findings by normalized value
        by_value: dict[str, list[HardcodedFinding]] = defaultdict(list)
        
        for finding in self.findings:
            key = f"{finding.category}:{finding.value}"
            by_value[key].append(finding)
        
        # Mark duplicates
        for key, findings in by_value.items():
            if len(findings) > 1:
                locations = [f"{f.file_path}:{f.line_number}" for f in findings]
                for finding in findings:
                    finding.similar_findings = [l for l in locations if l != f"{finding.file_path}:{finding.line_number}"]
                    # Boost confidence for duplicates
                    if len(findings) >= 3:
                        finding.confidence = min(finding.confidence * 1.2, 1.0)
    
    @staticmethod
    def _suggest_config_location(category: str, value: str) -> str:
        """Suggest where this value should be configured."""
        suggestions = {
            'timeout': "Move to settings.TIMEOUT or env var APP_TIMEOUT",
            'rate_limit': "Move to settings.RATE_LIMIT or use a rate limiter config",
            'max_tokens': "Move to model config or settings.MAX_TOKENS",
            'size_limit': "Move to settings with appropriate naming",
            'retry_count': "Move to settings.RETRY_COUNT",
            'retry_delay': "Move to settings.RETRY_DELAY",
            'batch_size': "Move to settings.BATCH_SIZE",
            'pagination': "Move to settings.DEFAULT_PAGE_SIZE",
            'port': "Move to settings.PORT or env var PORT",
            'threshold': "Move to settings.THRESHOLDS dict",
            'memory_size': "Move to settings.MEMORY_LIMIT",
            'expiration': "Move to settings.EXPIRY/TTL config",
            'url': "Move to settings.BASE_URL or env var",
            'service_url': "Move to service registry or settings.SERVICES",
            'mode_string': "Move to settings.MODE or env var APP_ENV",
            'header_value': "Consider constant or settings.HEADERS",
        }
        
        base_suggestion = suggestions.get(category, "Consider moving to centralized config")
        
        # Add specific suggestions for common values
        common_configs = {
            '30': " (30 seconds timeout)",
            '60': " (1 minute)",
            '300': " (5 minutes)",
            '3600': " (1 hour)",
            '100': " (common batch/page size)",
            '1000': " (common limit)",
            '2048': " (token limit)",
            '4096': " (token limit)",
            '8192': " (large token limit)",
        }
        
        extra = common_configs.get(value, "")
        
        return f"{base_suggestion}{extra}"


class BaselineComparator:
    """Compares current findings against a previous baseline."""
    
    def __init__(self, baseline_file: Path):
        self.baseline_file = baseline_file
        self.baseline_findings: set[str] = set()
        
    def load_baseline(self) -> bool:
        """Load previous baseline if it exists."""
        if not self.baseline_file.exists():
            return False
        
        try:
            with open(self.baseline_file, 'r') as f:
                data = json.load(f)
            
            # Create set of unique identifiers from baseline
            for finding in data.get('findings', []):
                key = f"{finding['file_path']}:{finding['line_number']}:{finding['value']}"
                self.baseline_findings.add(key)
            
            return True
        except Exception as e:
            logger.warning(f"Could not load baseline: {e}")
            return False
    
    def find_new_findings(self, current_findings: list[HardcodedFinding]) -> list[HardcodedFinding]:
        """Find findings that are new since baseline."""
        new_findings = []
        
        for finding in current_findings:
            key = f"{finding.file_path}:{finding.line_number}:{finding.value}"
            if key not in self.baseline_findings:
                finding.suggestion += " [NEW SINCE LAST AUDIT]"
                new_findings.append(finding)
        
        return new_findings


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, findings: list[HardcodedFinding]):
        self.findings = sorted(findings, key=lambda x: (-x.confidence, x.file_path, x.line_number))
        
        # Calculate summary stats
        high_conf = sum(1 for f in self.findings if f.confidence >= 0.8)
        med_conf = sum(1 for f in self.findings if 0.5 <= f.confidence < 0.8)
        
        categories = Counter(f.category for f in self.findings)
        value_counts = Counter(f.value for f in self.findings).most_common(10)
        affected_files = len({f.file_path for f in self.findings})
        
        self.summary = AuditSummary(
            total_findings=len(self.findings),
            high_confidence=high_conf,
            medium_confidence=med_conf,
            categories=dict(categories),
            most_common_values=value_counts,
            files_affected=affected_files
        )
    
    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI HARDCODED VALUE AUDIT REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Findings:              {self.summary.total_findings}")
        lines.append(f"  High Confidence (>80%):      {self.summary.high_confidence}")
        lines.append(f"  Medium Confidence (50-80%):  {self.summary.medium_confidence}")
        lines.append(f"  Files Affected:              {self.summary.files_affected}")
        lines.append("")
        
        lines.append("  BY CATEGORY:")
        for cat, count in sorted(self.summary.categories.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"    {cat:<25} {count:>5}")
        
        lines.append("\n  MOST COMMON VALUES:")
        for val, count in self.summary.most_common_values[:10]:
            lines.append(f"    {val:<25} appears {count}x")
        
        # High Confidence Findings
        high_conf_findings = [f for f in self.findings if f.confidence >= 0.8]
        if high_conf_findings:
            lines.append("\n\n🔴 HIGH CONFIDENCE FINDINGS (Should Fix)")
            lines.append("=" * 40)
            
            for i, finding in enumerate(high_conf_findings[:50], 1):  # Limit output
                dup_marker = f" [{len(finding.similar_findings)+1}x]" if finding.similar_findings else ""
                lines.append(f"\n  {i}. [{finding.category}]{dup_marker} ({finding.confidence:.0%})")
                lines.append(f"     Value:   {finding.value}")
                lines.append(f"     File:    {finding.file_path}:{finding.line_number}")
                lines.append(f"     Context: {finding.context}")
                lines.append(f"     Code:    {finding.line_content}")
                lines.append(f"     💡 {finding.suggestion}")
                
                if finding.similar_findings:
                    lines.append(f"     Also at: {', '.join(finding.similar_findings[:3])}")
            
            if len(high_conf_findings) > 50:
                lines.append(f"\n  ... and {len(high_conf_findings) - 50} more high-confidence findings")
        
        # Medium Confidence Findings (summary only)
        med_conf_findings = [f for f in self.findings if 0.5 <= f.confidence < 0.8]
        if med_conf_findings:
            lines.append(f"\n\n⚠️ MEDIUM CONFIDENCE FINDINGS: {len(med_conf_findings)} items")
            lines.append("(Review these - some may be legitimate inline values)")
            
            # Show unique categories
            med_categories = {f.category for f in med_conf_findings}
            lines.append(f"   Categories: {', '.join(sorted(med_categories))}")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Immediate Actions:
1. Move all HIGH CONFIDENCE findings to centralized config
2. For duplicate values, create shared constants
3. Add environment variables for deployment-specific values

Prevention:
1. Run this script in CI pipeline
2. Fail builds if NEW high-confidence findings appear
3. Add to code review checklist: "no new magic numbers"
4. Consider using linter rules (e.g., flake8-magic-numbers)

Config Centralization Strategy:
- App-level defaults → settings.py / config.ts
- Deployment-specific → Environment variables (.env, render.yaml)
- Feature flags → Feature flag service / config
- Service endpoints → Service registry / discovery

To save baseline for future comparisons:
  python config_single_source_enforcer.py --save-baseline
""")
        
        return "\n".join(lines)
    
    def generate_markdown_report(self) -> str:
        """Generate GitHub-flavored markdown report."""
        self.generate_text_report()
        
        # Convert to markdown format
        md_lines = ["# SupremeAI Hardcoded Value Audit Report", ""]
        md_lines.append(f"**Generated:** {datetime.now().isoformat()}")
        md_lines.append("")
        
        ## Summary Table
        md_lines.append("## Summary")
        md_lines.append("")
        md_lines.append("| Metric | Count |")
        md_lines.append("|--------|-------|")
        md_lines.append(f"| Total Findings | {self.summary.total_findings} |")
        md_lines.append(f"| High Confidence (≥80%) | {self.summary.high_confidence} |")
        md_lines.append(f"| Medium Confidence (50-79%) | {self.summary.medium_confidence} |")
        md_lines.append(f"| Files Affected | {self.summary.files_affected} |")
        md_lines.append("")
        
        ## Category Breakdown
        md_lines.append("### By Category")
        md_lines.append("")
        md_lines.append("| Category | Count |")
        md_lines.append("|----------|-------|")
        for cat, count in sorted(self.summary.categories.items(), key=lambda x: -x[1]):
            md_lines.append(f"| {cat} | {count} |")
        md_lines.append("")
        
        ## High Confidence Details
        high_conf = [f for f in self.findings if f.confidence >= 0.8]
        if high_conf:
            md_lines.append("## 🔴 High Confidence Findings")
            md_lines.append("")
            md_lines.append("| # | Category | Value | Location | Suggestion |")
            md_lines.append("---|----------|-------|----------|------------|")
            
            for i, finding in enumerate(high_conf[:50], 1):
                location = f"`{finding.file_path}:{finding.line_number}`"
                suggestion = finding.suggestion.replace('|', '\\|')[:80]
                md_lines.append(f"| {i} | {finding.category} | `{finding.value}` | {location} | {suggestion} |")
            
            if len(high_conf) > 50:
                md_lines.append(f"\n*... and {len(high_conf) - 50} more findings*")
        
        return '\n'.join(md_lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report for machine consumption."""
        return {
            "summary": asdict(self.summary),
            "findings": [asdict(f) for f in self.findings],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Config Single Source Enforcer - Find hardcoded values',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python config_single_source_enforcer.py
  python config_single_source_enforcer.py --output-format markdown > HARDCODED_AUDIT.md
  python config_single_source_enforcer.py --output-format json --output-file audit.json
  python config_single_source_enforcer.py --fail-on-new  # CI mode: fail on new issues
"""
    )
    
    parser.add_argument('--project-root', '-p', default='..',
                       help='Project root directory')
    parser.add_argument('--output-format', '-o', choices=['text', 'json', 'markdown'], 
                       default='text', help='Output format')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--save-baseline', action='store_true',
                       help='Save current findings as baseline for future comparison')
    parser.add_argument('--baseline-file', default='.hardcoded_baseline.json',
                       help='Baseline file path')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--min-confidence', type=float, default=0.5,
                       help='Minimum confidence to include in report (0.0-1.0)')
    parser.add_argument('--fail-on-new', action='store_true',
                       help='Exit with error if new findings since baseline')
    parser.add_argument('--fail-on-high-count', type=int, default=0,
                       help='Exit error if high-confidence findings exceed this count')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    project_root = (script_dir / args.project_root).resolve()
    
    print("🔧 SupremeAI Config Single Source Enforcer")
    print(f"   Project Root: {project_root}")
    print()
    
    # Scan for hardcoded values
    scanner = HardcodedScanner(project_root)
    findings = scanner.scan()
    
    # Filter by minimum confidence
    filtered_findings = [f for f in findings if f.confidence >= args.minconfidence]
    
    # Compare against baseline if needed
    new_count = 0
    if args.fail_on_new or args.save_baseline:
        comparator = BaselineComparator(script_dir / args.baseline_file)
        if comparator.load_baseline():
            new_findings = comparator.find_new_findings(filtered_findings)
            new_count = len(new_findings)
    
    # Save baseline if requested
    if args.save_baseline:
        baseline_data = {"findings": [asdict(f) for f in filtered_findings], 
                        "timestamp": datetime.now().isoformat()}
        with open(script_dir / args.baseline_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)
        print(f"✅ Baseline saved to: {args.baseline_file}")
    
    # Generate report
    generator = ReportGenerator(filtered_findings)
    
    if args.output_format == 'json':
        output = json.dumps(generator.generate_json_report(), indent=2)
    elif args.output_format == 'markdown':
        output = generator.generate_markdown_report()
    else:
        output = generator.generate_text_report()
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"✅ Report written to: {args.output_file}")
    else:
        print(output)
    
    # Exit codes for CI
    high_conf_count = generator.summary.high_confidence
    
    if args.fail_on_new and new_count > 0:
        print(f"\n❌ Found {new_count} new hardcoded values since last audit!", file=sys.stderr)
        sys.exit(1)
    
    if args.fail_on_high_count and high_conf_count > args.fail_on_high_count:
        print(f"\n❌ High-confidence findings ({high_conf_count}) exceed threshold ({args.fail_on_high_count})!", 
              file=sys.stderr)
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
