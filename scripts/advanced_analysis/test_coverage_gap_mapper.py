#!/usr/bin/env python3
"""
Test Coverage Gap Mapper for SupremeAI
=======================================
Analyzes which modules have tests and which don't, with risk-weighted
prioritization. Critical path modules (auth, payment, etc.) get higher
priority when missing tests.

Features:
- Maps source modules to their corresponding test files
- Identifies untested modules
- Risk-weighted scoring based on module importance
- Tracks coverage trends over time (with baseline)

Usage:
    python test_coverage_gap_mapper.py [--backend-dir ../backend] [--output-format text|json]
    
Self-healing principles:
- Auto-discovers test files by naming convention
- No hardcoded module lists - uses heuristics for importance
- CI-friendly output with exit codes
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SourceModule:
    """A source code module."""
    name: str
    file_path: str
    relative_path: str
    line_count: int = 0
    function_count: int = 0
    class_count: int = 0
    complexity_score: float = 0.0  # Estimated complexity
    importance_score: float = 0.0  # Business criticality


@dataclass
class TestFile:
    """A test file."""
    name: str
    file_path: str
    relative_path: str
    tested_module: str | None = None  # Which module it tests
    test_function_count: int = 0
    test_class_count: int = 0
    has_integration_tests: bool = False
    has_unit_tests: bool = False


@dataclass
class CoverageGap:
    """Represents a coverage gap (untested or undertested module)."""
    module: SourceModule
    has_test_file: bool = False
    test_coverage_estimate: float = 0.0  # 0.0 - 1.0 estimated
    risk_score: float = 0.0  # Importance × (1 - coverage)
    priority: str = ""  # CRITICAL, HIGH, MEDIUM, LOW
    suggested_test_name: str = ""
    reason: str = ""


@dataclass
class CoverageReport:
    """Summary of coverage analysis."""
    total_source_modules: int = 0
    modules_with_tests: int = 0
    modules_without_tests: int = 0
    overall_coverage_percent: float = 0.0
    critical_gaps: int = 0
    high_risk_gaps: int = 0
    medium_risk_gaps: int = 0
    low_risk_gaps: int = 0
    average_importance_of_untested: float = 0.0


# Patterns indicating business-critical modules
CRITICAL_PATTERNS = [
    r'auth', r'login', r'password', r'session', r'token', r'jwt',
    r'payment', r'billing', r'subscription', r'invoice', r'stripe',
    r'user', r'account', r'profile', r'permission', r'role', r'rbac',
    r'api_?key', r'secret', r'credential', r'encrypt', r'decrypt',
    r'email', r'notify', r'webhook', r'callback',
]

HIGH_IMPORTANCE_PATTERNS = [
    r'agent', r'task', r'job', r'queue', r'worker',
    r'chat', r'message', r'conversation',
    r'file', r'upload', r'download', r'storage',
    r'integration', r'webhook', r'event',
    r'cache', r'redis', r'database', r'model',
    r'router', r'route', r'endpoint', r'handler',
    r'config', r'setting', r'environment',
]

# Test file naming conventions to check
TEST_NAMING_CONVENTIONS = [
    # Standard pytest convention: test_<module>.py
    lambda src: f"test_{src}",
    # Alternative: <module>_test.py  
    lambda src: f"{src}_test",
    # In tests/ subdirectory: tests/test_<module>.py
    lambda src: f"tests/test_{src}",
    # In tests/ with same structure
    lambda src: f"tests/{src.replace('/', '/')}/test_{src.rsplit('/', 1)[-1] if '/' in src else f'test_{src}'}",
]


class SourceModuleScanner:
    """Scans for source modules."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.modules: dict[str, SourceModule] = {}
        
    def scan(self) -> dict[str, SourceModule]:
        """Scan for all source modules."""
        py_files = self._find_source_files()
        
        for py_file in py_files:
            module = self._analyze_file(py_file)
            if module:
                self.modules[module.name] = module
                self._calculate_importance(module)
        
        logger.info(f"Found {len(self.modules)} source modules")
        return self.modules
    
    def _find_source_files(self) -> list[Path]:
        """Find source Python files (excluding tests)."""
        skip_dirs = {
            '__pycache__', '.git', 'venv', '.venv', 'dist', 
            'build', '.tox', 'node_modules', 'migrations',  # Skip migration files
        }
        
        # Also skip directories that are clearly test directories
        test_indicators = {'test', 'tests', 'spec', 'specs'}
        
        py_files = []
        for py_file in self.project_dir.rglob("*.py"):
            rel_str = str(py_file.relative_to(self.project_dir))
            
            if any(skip in rel_str for skip in skip_dirs):
                continue
            
            # Skip test files
            parts = Path(rel_str).parts
            if any(p.startswith('test_') or p.endswith('_test') for p in parts):
                continue
            if any(p in test_indicators for p in parts[:-1]):  # Not the file itself
                continue
                
            py_files.append(py_file)
        
        return py_files
    
    def _analyze_file(self, file_path: Path) -> SourceModule | None:
        """Analyze a single source file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return None
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        module_name = rel_path.replace('/', '.').replace('.py', '')
        
        # Count functions and classes (basic heuristic)
        func_count = len(re.findall(r'^\s*def\s+\w+', content, re.MULTILINE))
        async_func_count = len(re.findall(r'^\s*async\s+def\s+\w+', content, re.MULTILINE))
        class_count = len(re.findall(r'^\s*class\s+\w+', content, re.MULTILINE))
        
        # Rough complexity estimate
        complexity = (
            func_count * 2 + 
            async_func_count * 3 +
            class_count * 5 +
            len(re.findall(r'\b(if|for|while|try|except)\b', content)) * 0.5
        )
        
        return SourceModule(
            name=module_name,
            file_path=str(file_path),
            relative_path=rel_path,
            line_count=len(lines),
            function_count=func_count + async_func_count,
            class_count=class_count,
            complexity_score=complexity
        )
    
    def _calculate_importance(self, module: SourceModule):
        """Calculate business importance score for a module."""
        score = 0.0
        
        # Check filename and path against patterns
        check_string = f"{module.name} {module.relative_path}".lower()
        
        # Critical patterns (higher weight)
        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, check_string):
                score += 10.0
        
        # High importance patterns
        for pattern in HIGH_IMPORTANCE_PATTERNS:
            if re.search(pattern, check_string):
                score += 5.0
        
        # Base importance from complexity
        score += min(module.complexity_score / 10, 5.0)
        
        # Bonus for being directly in api/ routes
        if '/api/' in module.relative_path.lower() or '/routes/' in module.relative_path.lower():
            score += 3.0
        
        # Bonus for core/ directory
        if '/core/' in module.relative_path.lower():
            score += 2.0
        
        module.importance_score = score


class TestFileScanner:
    """Scans for test files."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.test_files: dict[str, TestFile] = {}
        self.module_to_test_map: dict[str, str] = {}  # module_name -> test_file_name
        
    def scan(self) -> dict[str, TestFile]:
        """Scan for all test files."""
        test_files = self._find_test_files()
        
        for tf in test_files:
            test_info = self._analyze_test_file(tf)
            if test_info:
                self.test_files[test_info.name] = test_info
                
                # Try to map to source module
                source_module = self._guess_source_module(test_info)
                if source_module:
                    self.module_to_test_map[source_module] = test_info.name
        
        logger.info(f"Found {len(self.test_files)} test files")
        return self.test_files
    
    def _find_test_files(self) -> list[Path]:
        """Find test files using common conventions."""
        test_files = []
        
        # Common test directory names
        test_dirs = {'tests', 'test', 'spec', 'specs'}
        
        for py_file in self.project_dir.rglob("*.py"):
            filename = py_file.name
            
            # Check if it looks like a test file
            is_test = (
                filename.startswith('test_') or filename.endswith(('_test.py', '_spec.py')) or any(td in str(py_file) for td in test_dirs)
            )
            
            if is_test:
                test_files.append(py_file)
        
        return test_files
    
    def _analyze_test_file(self, file_path: Path) -> TestFile | None:
        """Analyze a test file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return None
        
        rel_path = str(file_path.relative_to(self.project_dir.parent))
        
        # Count test functions/classes
        test_funcs = len(re.findall(r'^\s*def\s+test_\w+', content, re.MULTILINE))
        test_classes = len(re.findall(r'^\s*class\s+\w*Test\w*', content, re.MULTILINE))
        
        # Detect test types
        has_integration = bool(re.search(r'(integration|e2e|end.?to.?end)', content, re.IGNORECASE))
        has_unit = not has_integration or test_funcs > 0
        
        return TestFile(
            name=file_path.stem,
            file_path=str(file_path),
            relative_path=rel_path,
            test_function_count=test_funcs,
            test_class_count=test_classes,
            has_integration_tests=has_integration,
            has_unit_tests=has_unit
        )
    
    def _guess_source_module(self, test: TestFile) -> str | None:
        """Guess which source module this test file tests."""
        test_name = Path(test.relative_path).stem
        
        # Remove test prefixes/suffixes
        source_name_candidates = []
        
        if test_name.startswith('test_'):
            source_name_candidates.append(test_name[5:])
        if test_name.endswith('_test'):
            source_name_candidates.append(test_name[:-5])
        if test_name.endswith('_spec'):
            source_name_candidates.append(test_name[:-5])
        
        # Try to find matching source module
        for candidate in source_name_candidates:
            # Look for various path variations
            test_dir = Path(test.relative_path).parent
            
            possible_paths = [
                candidate,
                f"{test_dir}/{candidate}".replace('tests/', '').replace('test/', ''),
                f"{candidate.replace('_', '/')}",  # Handle nested modules
            ]
            
            for path in possible_paths:
                normalized = path.replace('/', '.')
                return normalized
        
        return None


class CoverageGapAnalyzer:
    """Analyzes coverage gaps between source and tests."""
    
    def __init__(self, modules: dict[str, SourceModule], 
                 test_files: dict[str, TestFile],
                 module_to_test_map: dict[str, str]):
        self.modules = modules
        self.test_files = test_files
        self.module_to_test_map = module_to_test_map
        self.gaps: list[CoverageGap] = []
        self.report = CoverageReport()
    
    def analyze(self) -> tuple[list[CoverageGap], CoverageReport]:
        """Perform coverage gap analysis."""
        for module in self.modules.values():
            gap = self._analyze_module(module)
            self.gaps.append(gap)
        
        # Sort by risk score descending
        self.gaps.sort(key=lambda g: -g.risk_score)
        
        # Generate summary report
        self._generate_summary()
        
        return self.gaps, self.report
    
    def _analyze_module(self, module: SourceModule) -> CoverageGap:
        """Analyze coverage for a single module."""
        has_test = module.name in self.module_to_test_map
        
        # Estimate coverage (very rough heuristic)
        if has_test:
            test_name = self.module_to_test_map[module.name]
            test_file = self.test_files.get(test_name)
            
            if test_file:
                # Estimate based on test count vs function count
                if module.function_count > 0:
                    ratio = min(test_file.test_function_count / module.function_count, 1.0)
                    coverage = 0.4 + (ratio * 0.6)  # Base 40% + up to 60% more
                else:
                    coverage = 0.7  # Has some tests at least
            else:
                coverage = 0.5  # Unknown test file details
        else:
            coverage = 0.0
        
        # Calculate risk score
        risk = module.importance_score * (1.0 - coverage)
        
        # Determine priority
        if risk >= 15 or (not has_test and module.importance_score >= 10):
            priority = "CRITICAL"
        elif risk >= 8 or (not has_test and module.importance_score >= 5):
            priority = "HIGH"
        elif risk >= 3 or not has_test:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # Suggest test file name
        module_filename = Path(module.relative_path).stem
        suggested_test = f"test_{module_filename}.py"
        
        # Reason for gap
        if not has_test:
            reason = "No test file found"
        elif coverage < 0.5:
            reason = f"Low test coverage (~{coverage:.0%})"
        else:
            reason = f"Partial coverage (~{coverage:.0%})"
        
        return CoverageGap(
            module=module,
            has_test_file=has_test,
            test_coverage_estimate=coverage,
            risk_score=risk,
            priority=priority,
            suggested_test_name=suggested_test,
            reason=reason
        )
    
    def _generate_summary(self):
        """Generate summary statistics."""
        total = len(self.gaps)
        with_tests = sum(1 for g in self.gaps if g.has_test_file)
        without_tests = total - with_tests
        
        avg_coverage = sum(g.test_coverage_estimate for g in self.gaps) / max(total, 1)
        
        critical = sum(1 for g in self.gaps if g.priority == "CRITICAL")
        high = sum(1 for g in self.gaps if g.priority == "HIGH")
        medium = sum(1 for g in self.gaps if g.priority == "MEDIUM")
        low = sum(1 for g in self.gaps if g.priority == "LOW")
        
        avg_importance_untested = (
            sum(g.module.importance_score for g in self.gaps if not g.has_test_file) / 
            max(without_tests, 1)
        )
        
        self.report = CoverageReport(
            total_source_modules=total,
            modules_with_tests=with_tests,
            modules_without_tests=without_tests,
            overall_coverage_percent=avg_coverage * 100,
            critical_gaps=critical,
            high_risk_gaps=high,
            medium_risk_gaps=medium,
            low_risk_gaps=low,
            average_importance_of_untested=avg_importance_untested
        )


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, gaps: list[CoverageGap], report: CoverageReport,
                 modules: dict[str, SourceModule]):
        self.gaps = gaps
        self.report = report
        self.modules = modules
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI TEST COVERAGE GAP MAPPER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Source Modules:         {self.report.total_source_modules}")
        lines.append(f"  Modules With Tests:           {self.report.modules_with_tests}")
        lines.append(f"  Modules Without Tests:        {self.report.modules_without_tests}")
        lines.append(f"  Est. Overall Coverage:        {self.report.overall_coverage_percent:.1f}%")
        lines.append("")
        lines.append("  GAPS BY PRIORITY:")
        lines.append(f"    🔴 CRITICAL:               {self.report.critical_gaps}")
        lines.append(f"    🟠 HIGH:                   {self.report.high_risk_gaps}")
        lines.append(f"    🟡 MEDIUM:                 {self.report.medium_risk_gaps}")
        lines.append(f"    🟢 LOW:                    {self.report.low_risk_gaps}")
        lines.append("")
        
        # Critical gaps first
        critical_gaps = [g for g in self.gaps if g.priority == "CRITICAL"]
        if critical_gaps:
            lines.append("\n🔴 CRITICAL GAPS (Untested Important Modules)")
            lines.append("=" * 40)
            
            for i, gap in enumerate(critical_gaps[:20], 1):
                m = gap.module
                lines.append(f"\n  {i}. [{gap.priority}] Risk: {gap.risk_score:.1f}")
                lines.append(f"     Module: {m.name}")
                lines.append(f"     File:   {m.relative_path}")
                lines.append(f"     Size:   {m.line_count} lines, {m.function_count} funcs")
                lines.append(f"     Import: {m.importance_score:.1f}/10")
                lines.append(f"     Issue:  {gap.reason}")
                lines.append(f"     💡 Create: {gap.suggested_test_name}")
            
            if len(critical_gaps) > 20:
                lines.append(f"\n  ... and {len(critical_gaps) - 20} more critical gaps")
        
        # High priority gaps
        high_gaps = [g for g in self.gaps if g.priority == "HIGH"]
        if high_gaps:
            lines.append(f"\n\n🟠 HIGH PRIORITY GAPS: {len(high_gaps)} modules")
            lines.append("-" * 40)
            
            for gap in high_gaps[:15]:
                m = gap.module
                lines.append(f"  • {m.name} ({m.line_count} lines, imp:{m.importance_score:.1f})")
            
            if len(high_gaps) > 15:
                lines.append(f"  ... and {len(high_gaps) - 15} more")
        
        # Untested modules summary
        untested = [g for g in self.gaps if not g.has_test_file]
        if untested:
            lines.append(f"\n\n📋 ALL UNTESTED MODULES: {len(untested)} total")
            lines.append("-" * 40)
            
            # Group by directory
            by_dir = defaultdict(list)
            for gap in untested:
                dir_path = str(Path(gap.module.relative_path).parent)
                by_dir[dir_path].append(gap)
            
            for directory, gaps_in_dir in sorted(by_dir.items()):
                lines.append(f"\n  {directory}/ ({len(gaps_in_dir)} untested)")
                for gap in sorted(gaps_in_dir, key=lambda g: -g.module.importance_score)[:5]:
                    lines.append(f"    - {Path(gap.module.relative_path).stem} "
                               f"(imp:{gap.module.importance_score:.1f})")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
Priority Testing Plan:

Phase 1 (This Sprint) - Critical Modules:
  • Focus on auth, payment, user management tests
  • These have highest risk if they fail in production

Phase 2 (Next Sprint) - High Priority:
  • Core API routes and handlers
  • Agent/task orchestration

Phase 3 (Ongoing) - Medium/Low Priority:
  • Utility and helper modules
  • Less critical features

Testing Strategy Recommendations:
  • Use pytest with fixtures for setup
  • Mock external dependencies (API calls, DB)
  • Aim for 80%+ coverage on critical paths
  • Add integration tests for key workflows

CI Integration:
  • Set minimum coverage threshold (e.g., 70%)
  • Fail build if coverage drops
  • Run this script weekly to track progress
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": asdict(self.report),
            "gaps": [{
                "module": gap.module.name,
                "file": gap.module.relative_path,
                "has_test": gap.has_test_file,
                "coverage_est": round(gap.test_coverage_estimate, 2),
                "risk_score": round(gap.risk_score, 2),
                "priority": gap.priority,
                "importance": round(gap.module.importance_score, 2),
                "suggested_test": gap.suggested_test_name,
                "reason": gap.reason
            } for gap in self.gaps],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Test Coverage Gap Mapper - Risk-weighted coverage analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', type=int, default=0,
                       help='Fail if critical gaps exceed this count')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print("🧪 SupremeAI Test Coverage Gap Mapper")
    print(f"   Backend: {backend_dir}")
    print()
    
    # Scan source modules
    src_scanner = SourceModuleScanner(backend_dir)
    modules = src_scanner.scan()
    
    # Scan test files
    test_scanner = TestFileScanner(backend_dir)
    test_files = test_scanner.scan()
    
    # Analyze gaps
    analyzer = CoverageGapAnalyzer(modules, test_files, test_scanner.module_to_test_map)
    gaps, report = analyzer.analyze()
    
    # Generate report
    generator = ReportGenerator(gaps, report, modules)
    
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
    
    # Exit code for CI
    if args.fail_on_critical and report.critical_gaps > args.fail_on_critical:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
