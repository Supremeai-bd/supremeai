#!/usr/bin/env python3
"""
Bengali i18n Completeness Checker for SupremeAI
=================================================
Scans all UI string keys in the codebase and checks which ones
have Bengali translations missing.

This extends the existing rtl_support_checker.py to specifically focus on
Bengali translation completeness for SupremeAI's Bangla user base.

Features:
- Extracts all user-facing strings from frontend code
- Checks against i18n/translation files
- Reports missing Bengali translations
- Identifies hardcoded strings that should be internationalized

Usage:
    python bengali_i18n_completeness_checker.py [--frontend-dir ../frontend] [--output-format text|json]
    
Self-healing principles:
- Auto-discovers i18n files and patterns
- No hardcoded key lists - fully dynamic
- CI-friendly output
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class StringKey:
    """An i18n string key."""
    key: str  # e.g., 'common.save', 'auth.login.title'
    file_path: str
    line_number: int
    context: str  # Where it's used (component name, etc.)
    is_used: bool = True


@dataclass 
class TranslationEntry:
    """A translation entry from i18n file."""
    key: str
    english: str = ""
    bengali: str = ""
    has_bengali: bool = False
    source_file: str = ""


@dataclass 
class MissingTranslation:
    """A missing or incomplete translation."""
    key: string
    english_text: str
    location: str  # Where the key is used
    severity: str  # 'CRITICAL' (common UI), 'HIGH', 'MEDIUM'
    suggestion: str = ""


@dataclass
class I18nReport:
    """Summary of i18n analysis."""
    total_keys_found: int = 0
    keys_with_bengali: int = 0
    keys_missing_bengali: int = 0
    completion_percent: float = 0.0
    critical_missing: int = 0
    hardcoded_strings_found: int = 0
    by_section: dict[str, dict[str, int]] = field(default_factory=dict)


# Patterns for i18n function calls in React/TypeScript
I18N_USAGE_PATTERNS = [
    # Common i18n libraries
    r't\(\s*["\']([^"\']+)["\']',  # t('key')
    r'i18n\.t\(\s*["\']([^"\']+)["\']',
    r'useTranslation\(\)\.t\(\s*["\']([^"\']+)["\']',
    r'intl\.formatMessage\(\s*\{[^}]*id:\s*["\']([^"\']+)["\']',
    
    # Custom implementations
    r'translate\(\s*["\']([^"\']+)["\']',
    r'\$t\(\s*["\']([^"\']+)["\']',
    r'_\(\s*["\']([^"\']+)["\']',
]

# Patterns that suggest a string is user-facing (should be translated)
USER_FACING_PATTERNS = [
    r'(?:placeholder|title|label|alt|aria-label)\s*=\s*["\']([^"\']{3,})["\']',
    r'>\s*[A-Z][^<]{10,100}\s*<',  # Text content in JSX
    r'\{[^}]*"[^"]{10,}"[^}]*\}',  # Strings in JSX expressions
    r'toast?\(\s*["\']([^"\']+)["\']',
    r'alert\(\s*["\']([^"\']+)["\']',
    r'confirm\(\s*["\']([^"\']+)["\']',
]

# Sections/prefixes that are critical for UX
CRITICAL_SECTIONS = [
    'common', 'nav', 'menu', 'button', 'action',
    'error', 'warning', 'success', 'info',
    'auth', 'login', 'register', 'logout',
    'validation', 'required', 'format',
]


class I18nKeyExtractor:
    """Extracts i18n string keys from frontend code."""
    
    def __init__(self, frontend_dir: Path):
        self.frontend_dir = Path(frontend_dir)
        self.keys: dict[str, StringKey] = {}
        self.hardcoded_strings: list[dict[str, Any]] = []
        
    def extract(self) -> tuple[dict[str, StringKey], list[dict]]:
        """Extract all i18n keys and hardcoded strings."""
        self._scan_typescript_files()
        return self.keys, self.hardcoded_strings
    
    def _scan_typescript_files(self):
        """Scan TypeScript/JavaScript files."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        skip_dirs = {'node_modules', 'dist', '.next', 'coverage'}
        
        for ext in extensions:
            for ts_file in self.frontend_dir.rglob(ext):
                if any(skip in str(ts_file) for skip in skip_dirs):
                    continue
                self._scan_file(ts_file)
    
    def _scan_file(self, file_path: Path):
        """Scan a single file for i18n usage."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.frontend_dir.parent))
        
        # Extract component/function name for context
        current_context = Path(file_path).stem
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments
            if stripped.startswith(('//', '*', '/*')):
                continue
            
            # Look for i18n function calls
            for pattern in I18N_USAGE_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    key = match.group(1)
                    
                    if key and len(key) > 1:  # Skip empty/single-char keys
                        self.keys[key] = StringKey(
                            key=key,
                            file_path=rel_path,
                            line_number=i + 1,
                            context=current_context
                        )
            
            # Look for potentially hardcoded strings
            for pattern in USER_FACING_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    text = match.group(1) if match.lastindex >= 1 else ""
                    
                    # Filter out URLs, CSS classes, etc.
                    if text and self._is_user_facing_text(text):
                        self.hardcoded_strings.append({
                            'text': text[:100],
                            'file': rel_path,
                            'line': i + 1,
                            'pattern': pattern.split('(')[0] if '(' in pattern else pattern
                        })
            
            # Update context when we see component definitions
            comp_match = re.match(r'(?:function|const|export\s+(?:default\s+)?)\s*(\w+)', stripped)
            if comp_match and any(kw in stripped for kw in ['=>', '=']):
                current_context = comp_match.group(1)
    
    def _is_user_facing_text(self, text: str) -> bool:
        """Check if text looks like user-facing content that should be translated."""
        # Skip if it looks like code
        if any(c in text for c in ['{', '}', '$(', '${', '<', '>', '=', '/']):
            return False
        
        # Skip URLs
        if text.startswith(('http://', 'https://', '/', '#')):
            return False
        
        # Skip very short strings
        if len(text) < 3:
            return False
        
        # Skip if all uppercase (likely constant/acronym)
        if text.isupper() and len(text) > 2:
            return False
        
        # Check if it contains letters (user-facing text usually does)
        has_letters = any(c.isalpha() for c in text)
        
        return has_letters and len(text) > 3


class TranslationFileParser:
    """Parses i18n/translation files."""
    
    def __init__(self, frontend_dir: Path):
        self.frontend_dir = Path(frontend_dir)
        self.translations: dict[str, TranslationEntry] = {}
        
    def parse(self) -> dict[str, TranslationEntry]:
        """Parse all translation files."""
        self._find_and_parse_translation_files()
        logger.info(f"Found {len(self.translations)} translation keys")
        return self.translations
    
    def _find_and_parse_translation_files(self):
        """Find and parse translation/i18n files."""
        # Common locations for i18n files
        i18n_patterns = [
            'src/i18n/**/*.json',
            'src/i18n/**/*.ts',
            'src/locales/**/*',
            'src/lang/**/*',
            '**/translations.*',
            '**/i18n.*',
            '**/locale*/**/*.json',
        ]
        
        # Specific known files for SupremeAI
        known_files = [
            'frontend/src/i18n/translations.ts',
            'frontend/src/i18n/config.ts',
        ]
        
        for pattern in known_files:
            file_path = self.frontend_dir.parent / pattern
            if file_path.exists():
                self._parse_file(file_path)
        
        # Also search broadly
        for pattern in i18n_patterns:
            for i18n_file in self.frontend_dir.glob(pattern):
                if '__pycache__' in str(i18n_file):
                    continue
                self._parse_file(i18n_file)
    
    def _parse_file(self, file_path: Path):
        """Parse a single translation file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.frontend_dir.parent))
        
        # Try JSON first
        if file_path.suffix == '.json':
            try:
                data = json.loads(content)
                self._extract_from_json(data, rel_path)
                return
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"Silenced error: {e}")
        
        # Try TypeScript/JavaScript exports
        if file_path.suffix in ['.ts', '.tsx', '.js']:
            self._extract_from_ts(content, rel_path)
    
    def _extract_from_json(self, data: Any, source_file: str, prefix: str = ""):
        """Recursively extract translations from JSON structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, str):
                    # This is a translation value
                    if full_key not in self.translations:
                        entry = TranslationEntry(key=full_key, source_file=source_file)
                        self.translations[full_key] = entry
                    
                    # Check if this looks like Bengali text
                    if self._is_bengali(value):
                        self.translations[full_key].bengali = value
                        self.translations[full_key].has_bengali = True
                    elif not self.translations[full_key].english:
                        self.translations[full_key].english = value
                        
                elif isinstance(value, dict):
                    # Nested object - recurse
                    self._extract_from_json(value, source_file, full_key)
                    
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._extract_from_json(item, source_file, prefix)
    
    def _extract_from_ts(self, content: str, source_file: str):
        """Extract translations from TypeScript file."""
        # Look for common export patterns
        patterns = [
            # Object literal exports
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(\{[^;]+\})',
            # Nested objects
            r'["\']([\w.]+)["\']:\s*["\']([^"\']*)["\']',
        ]
        
        # Find translation objects
        obj_matches = re.finditer(patterns[0], content, re.DOTALL)
        for match in obj_matches:
            match.group(1)
            obj_content = match.group(2)
            
            # Parse key-value pairs from object
            kv_pairs = re.finditer(r'["\']([\w.]+)["\']:\s*["\']([^"\']*)["\']', obj_content)
            for kv in kv_pairs:
                key = kv.group(1)
                value = kv.group(2)
                
                entry = TranslationEntry(key=key, source_file=source_file)
                
                if self._is_bengali(value):
                    entry.bengali = value
                    entry.has_bengali = True
                else:
                    entry.english = value
                
                self.translations[key] = entry
    
    @staticmethod
    def _is_bengali(text: str) -> bool:
        """Check if text contains Bengali characters."""
        # Bengali Unicode range: U+0980 to U+09FF
        bengali_chars = sum(1 for c in text if '\u0980' <= c <= '\u09FF')
        
        # If more than 30% of alphabetic chars are Bengali, consider it Bengali text
        alpha_chars = sum(1 for c in text if c.isalpha())
        
        if alpha_chars > 0 and (bengali_chars / alpha_chars) > 0.3:
            return True
        
        # Also check for common Bengali words
        common_bn_words = ['সবই', 'হয়', 'না', 'কি', 'এই', 'আছে', 'দিন', 'সময']
        return bool(any(word in text for word in common_bn_words))


class CompletenessChecker:
    """Checks translation completeness."""
    
    def __init__(self, keys: dict[str, StringKey], 
                 translations: dict[str, TranslationEntry]):
        self.keys = keys
        self.translations = translations
        self.missing: list[MissingTranslation] = []
        self.report = I18nReport(total_keys_found=len(keys))
    
    def check(self) -> tuple[list[MissingTranslation], I18nReport]:
        """Check for missing translations."""
        for key, string_key in self.keys.items():
            # Check if we have a translation for this key
            trans_entry = self.translations.get(key)
            
            if trans_entry:
                if trans_entry.has_bengali:
                    self.report.keys_with_bengali += 1
                else:
                    self.report.keys_missing_bengali += 1
                    
                    # Determine severity
                    severity = self._assess_severity(key)
                    
                    self.missing.append(MissingTranslation(
                        key=key,
                        english_text=trans_entry.english or "(unknown)",
                        location=f"{string_key.file_path}:{string_key.line_number}",
                        severity=severity,
                        suggestion=self._generate_suggestion(key, severity)
                    ))
            else:
                # Key not found in any translation file
                self.report.keys_missing_bengali += 1
                
                severity = self._assess_severity(key)
                if severity == 'CRITICAL':
                    self.report.critical_missing += 1
                
                self.missing.append(MissingTranslation(
                    key=key,
                    english_text="(not in translation file)",
                    location=f"{string_key.file_path}:{string_key.line_number}",
                    severity=severity,
                    suggestion=f"Add key '{key}' to translation files"
                ))
        
        # Calculate completion percentage
        total = self.report.total_keys_found
        if total > 0:
            self.report.completion_percent = (self.report.keys_with_bengali / total) * 100
        
        self.report.hardcoded_strings_found = len([])  # Would be passed separately
        
        # Categorize by section
        sections = defaultdict(lambda: {'total': 0, 'translated': 0})
        for key in self.keys:
            section = key.split('.')[0] if '.' in key in key else 'other'
            sections[section]['total'] += 1
            
            if key in self.translations and self.translations[key].has_bengali:
                sections[section]['translated'] += 1
        
        self.report.by_section = dict(sections)
        
        return self.missing, self.report
    
    def _assess_severity(self, key: str) -> str:
        """Assess severity of missing translation."""
        key_lower = key.lower()
        
        # Critical sections
        for section in CRITICAL_SECTIONS:
            if key_lower.startswith(section):
                return 'CRITICAL'
        
        # High visibility items
        if any(kw in key_lower for kw in ['title', 'header', 'nav', 'menu', 'button']):
            return 'HIGH'
        
        # Error/success messages are important
        if any(kw in key_lower for kw in ['error', 'success', 'warning', 'confirm']):
            return 'HIGH'
        
        return 'MEDIUM'
    
    def _generate_suggestion(self, key: str, severity: str) -> str:
        """Generate suggestion for fixing missing translation."""
        base = f"Add Bengali translation for '{key}'"
        
        if severity == 'CRITICAL':
            base += " - This is visible to users, priority fix needed."
        elif severity == 'HIGH':
            base += " - Important for good UX."
        
        return base


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, missing: list[MissingTranslation], report: I18nReport,
                 keys: dict[str, StringKey], hardcoded: list[dict]):
        self.missing = sorted(missing, key=lambda m: (
            {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}.get(m.severity, 3),
            m.key
        ))
        self.report = report
        self.keys = keys
        self.hardcoded = hardcoded
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI BENGALI i18n COMPLETENESS CHECKER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total i18n Keys Found:         {self.report.total_keys_found}")
        lines.append(f"  With Bengali Translation:      {self.report.keys_with_bengali}")
        lines.append(f"  Missing Bengali Translation:   {self.report.keys_missing_bengali}")
        lines.append(f"  Completion Rate:               {self.report.completion_percent:.1f}%")
        lines.append(f"  Critical Missing:              {self.report.critical_missing}")
        lines.append("")
        
        # Completion gauge
        pct = self.report.completion_percent
        if pct >= 90:
            gauge = "✅ Excellent"
        elif pct >= 70:
            gauge = "🟡 Good"
        elif pct >= 50:
            gauge = "🟠 Needs Work"
        else:
            gauge = "🔴 Poor"
        lines.append(f"  Status: {gauge}")
        lines.append("")
        
        # By Section breakdown
        if self.report.by_section:
            lines.append("\nCOMPLETION BY SECTION")
            lines.append("-" * 40)
            lines.append(f"  {'Section':<20} {'Total':>8} {'Translated':>12} {'Rate':>8}")
            
            for section, stats in sorted(self.report.by_section.items()):
                rate = (stats['translated'] / stats['total'] * 100) if stats['total'] else 0
                icon = "✅" if rate >= 90 else ("🟡" if rate >= 70 else "🔴")
                lines.append(f"  {icon} {section:<19} {stats['total']:>7} {stats['translated']:>11} {rate:>7.0f}%")
        
        # Missing Translations
        if self.missing:
            lines.append("\n\n🔴 MISSING BENGALI TRANSLATIONS")
            lines.append("=" * 40)
            
            critical = [m for m in self.missing if m.severity == 'CRITICAL']
            high = [m for m in self.missing if m.severity == 'HIGH']
            medium = [m for m in self.missing if m.severity == 'MEDIUM']
            
            if critical:
                lines.append(f"\n  🚨 CRITICAL ({len(critical)}):")
                for miss in critical[:15]:
                    lines.append(f"     • {miss.key}")
                    lines.append(f"       {miss.location}")
                    lines.append(f"       EN: {miss.english_text[:60]}")
            
            if high:
                lines.append(f"\n  ⚠️ HIGH PRIORITY ({len(high)}):")
                for miss in high[:10]:
                    lines.append(f"     • {miss.key} ({miss.location})")
            
            if medium:
                lines.append(f"\n  🟡 MEDIUM ({len(medium)}):")
                lines.append(f"     ...and {len(medium)} more medium priority items")
        
        # Hardcoded strings warning
        if self.hardcoded:
            lines.append("\n\n⚠️ POTENTIAL HARDCODED STRINGS FOUND")
            lines.append("-" * 40)
            lines.append(f"  Found {len(self.hardcoded)} strings that might need i18n:")
            
            for hc in self.hardcoded[:10]:
                lines.append(f"     • \"{hc['text'][:50]}\" at {hc['file']}:{hc['line']}")
            
            if len(self.hardcoded) > 10:
                lines.append(f"     ...and {len(self.hardcoded) - 10} more")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS FOR BENGALI i18n")
        lines.append("=" * 80)
        lines.append("""
Priority Actions:

1. **Fix Critical Missing Translations First**
   - Focus on nav, buttons, errors, auth flows
   - These are most visible to users

2. **Use Professional Translation**
   - Consider native speaker review
   - Maintain consistent terminology
   - Use formal/polite register appropriately

3. **Handle Plurals/Gender Properly**
   - Bengali has different forms for formality levels
   - Implement pluralization rules
   - Consider gender-neutral language where appropriate

4. **Test RTL Layout**
   - Run existing rtl_support_checker.py too
   - Ensure text renders correctly
   - Test font rendering

5. **Automate Detection**
   - Add this script to CI pipeline
   - Fail build if completion drops below threshold
   - Alert on new untranslated keys

Resources:
   - Google Translate API for initial drafts
   - Native speaker review process
   - Bengali glossary for technical terms
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total_keys": self.report.total_keys_found,
                "with_bengali": self.report.keys_with_bengali,
                "missing_bengali": self.report.keys_missing_bengali,
                "completion_percent": round(self.report.completion_percent, 2),
                "critical_missing": self.report.critical_missing,
            },
            "by_section": self.report.by_section,
            "missing_translations": [{
                "key": m.key,
                "english": m.english_text,
                "location": m.location,
                "severity": m.severity,
                "suggestion": m.suggestion
            } for m in self.missing[:100]],
            "hardcoded_strings_count": len(self.hardcoded),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Bengali i18n Completeness Checker',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--frontend-dir', '-f', default='../frontend')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-below', type=float, default=0,
                       help='Fail if completion below this percent')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    frontend_dir = (script_dir / args.frontend_dir).resolve()
    
    print("🔤 SupremeAI Bengali i18n Completeness Checker")
    print(f"   Frontend Dir: {frontend_dir}")
    print()
    
    # Extract i18n keys
    extractor = I18nKeyExtractor(frontend_dir)
    keys, hardcoded = extractor.extract()
    
    # Parse translation files
    parser_obj = TranslationFileParser(frontend_dir)
    translations = parser_obj.parse()
    
    # Check completeness
    checker = CompletenessChecker(keys, translations)
    missing, report = checker.check()
    
    # Generate report
    generator = ReportGenerator(missing, report, keys, hardcoded)
    
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
    
    # Exit code
    if args.fail_below > 0 and report.completion_percent < args.fail_below:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
