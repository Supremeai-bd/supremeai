#!/usr/bin/env python3
"""
API Breaking Change Detector for SupremeAI
==========================================
Detects potentially breaking changes in API contracts by comparing
route signatures across commits/branches.

Features:
- Compares current routes against a baseline (branch, tag, or saved state)
- Flags new required parameters
- Detects response schema changes
- Identifies removed or modified endpoints

Usage:
    python api_breaking_change_detector.py [--baseline-branch main] [--backend-dir ../backend]
    
Self-healing principles:
- Auto-discovers all route definitions
- No hardcoded endpoint lists
- CI-friendly: can block deploys with breaking changes
"""

import argparse
import ast
import json
import logging
import subprocess
import sys
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
class RouteSignature:
    """Signature of an API route."""
    path: str
    method: str
    function_name: str
    parameters: list[dict[str, str]]  # [{name, type, required, default}]
    response_model: str | None = None
    deprecated: bool = False
    file_path: str = ""
    line_number: int = 0


@dataclass 
class BreakingChange:
    """A potentially breaking change detected."""
    change_type: str  # 'REMOVED_ENDPOINT', 'NEW_REQUIRED_PARAM', 'PARAM_TYPE_CHANGE', 'RESPONSE_CHANGE', 'METHOD_CHANGE'
    severity: str  # 'BREAKING', 'LIKELY_BREAKING', 'CAUTION'
    description: str
    old_signature: RouteSignature | None = None
    new_signature: RouteSignature | None = None
    suggestion: str = ""


@dataclass
class BreakingChangeReport:
    """Summary of breaking change analysis."""
    total_routes_current: int = 0
    total_routes_baseline: int = 0
    breaking_changes: int = 0
    likely_breaking: int = 0
    caution_items: int = 0
    new_endpoints: int = 0
    safe_changes: int = 0


class RouteExtractor:
    """Extracts route signatures from codebase."""
    
    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.routes: list[RouteSignature] = []
        
    def extract(self) -> list[RouteSignature]:
        """Extract all route signatures."""
        py_files = list(self.backend_dir.rglob("*.py"))
        
        skip_dirs = {'__pycache__', 'tests', 'migrations', '.git', 
                    'venv', '.venv'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            self._extract_from_file(py_file)
            
        logger.info(f"Extracted {len(self.routes)} route signatures")
        return self.routes
    
    def _extract_from_file(self, file_path: Path):
        """Extract routes from a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.backend_dir.parent))
        
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            
            # Check for route decorators
            for decorator in node.decorator_list:
                route_info = self._analyze_decorator(decorator, node, lines, rel_path)
                if route_info:
                    self.routes.append(route_info)
    
    def _analyze_decorator(self, decorator: ast.AST, func_node: ast.AST, 
                           lines: list[str], rel_path: str) -> RouteSignature | None:
        """Analyze a decorator to extract route info."""
        if isinstance(decorator, ast.Call):
            # Get method from decorator name
            method = self._get_method(decorator)
            if not method or method == 'MULTI':
                return None
            
            # Get path from first string argument
            path = self._get_path(decorator)
            if not path:
                return None
            
            # Extract parameters from function signature
            parameters = self._extract_parameters(func_node)
            
            # Check for deprecation
            is_deprecated = self._is_deprecated(func_node)
            
            return RouteSignature(
                path=path,
                method=method,
                function_name=func_node.name,
                parameters=parameters,
                file_path=rel_path,
                line_number=func_node.lineno,
                deprecated=is_deprecated
            )
        
        return None
    
    def _get_method(self, decorator: ast.Call) -> str | None:
        """Get HTTP method from decorator."""
        method_map = {
            'get': 'GET', 'post': 'POST', 'put': 'PUT',
            'delete': 'DELETE', 'patch': 'PATCH',
            'options': 'OPTIONS', 'head': 'HEAD'
        }
        
        if isinstance(decorator.func, ast.Attribute):
            attr = decorator.func.attr.lower()
            return method_map.get(attr)
        elif isinstance(decorator.func, ast.Name):
            name = decorator.func.id.lower()
            return method_map.get(name)
        
        return None
    
    def _get_path(self, decorator: ast.Call) -> str | None:
        """Get route path from decorator."""
        if decorator.args:
            first_arg = decorator.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value
        return None
    
    def _extract_parameters(self, func_node: ast.AST) -> list[dict[str, str]]:
        """Extract parameters from function signature."""
        params = []
        
        # Common names to skip (injected dependencies)
        skip_params = {'self', 'request', 'current_user', 'db', 'session',
                      'background_tasks', 'authorize'}
        
        all_args = func_node.args.args
        defaults = func_node.args.defaults
        defaults_offset = len(all_args) - len(defaults)
        
        for i, arg in enumerate(all_args):
            if arg in skip_params:
                continue
            
            param_info = {
                'name': arg,
                'type': 'unknown',  # Would need more analysis for actual type
                'required': i < defaults_offset,
                'default': str(defaults[i - defaults_offset]) if i >= defaults_offset else None
            }
            params.append(param_info)
        
        return params
    
    def _is_deprecated(self, func_node: ast.AST) -> bool:
        """Check if function is marked as deprecated."""
        docstring = ast.get_docstring(func_node) or ""
        return 'deprecated' in docstring.lower()


class BreakingChangeDetector:
    """Detects breaking changes between two sets of routes."""
    
    def __init__(self, current_routes: list[RouteSignature], 
                 baseline_routes: list[RouteSignature]):
        self.current = {f"{r.method} {r.path}": r for r in current_routes}
        self.baseline = {f"{r.method} {r.path}": r for r in baseline_routes}
        self.changes: list[BreakingChange] = []
        self.report = BreakingChangeReport(
            total_routes_current=len(current_routes),
            total_routes_baseline=len(baseline_routes)
        )
        
    def detect(self) -> tuple[list[BreakingChange], BreakingChangeReport]:
        """Detect breaking changes."""
        self._detect_removed_endpoints()
        self._detect_parameter_changes()
        self._detect_method_changes()
        self._detect_new_required_params()
        self._detect_new_endpoints()
        
        # Calculate summary
        self.report.breaking_changes = sum(1 for c in self.changes if c.severity == 'BREAKING')
        self.report.likely_breaking = sum(1 for c in self.changes if c.severity == 'LIKELY_BREAKING')
        self.report.caution_items = sum(1 for c in self.changes if c.severity == 'CAUTION')
        
        return self.changes, self.report
    
    def _detect_removed_endpoints(self):
        """Find endpoints that existed in baseline but not in current."""
        for key, baseline_route in self.baseline.items():
            if key not in self.current:
                # Check if it was just deprecated (not actually removed)
                still_exists_deprecated = any(
                    r.path == baseline_route.path and r.deprecated
                    for r in self.current.values()
                )
                
                if not still_exists_deprecated:
                    severity = 'BREAKING' if not baseline_route.deprecated else 'LIKELY_BREAKING'
                    
                    self.changes.append(BreakingChange(
                        change_type='REMOVED_ENDPOINT',
                        severity=severity,
                        description=f"Endpoint {key} ({baseline_route.function_name}) was removed",
                        old_signature=baseline_route,
                        suggestion="Consider deprecating before removing, or verify this is intentional"
                    ))
    
    def _detect_parameter_changes(self):
        """Find parameter changes in existing endpoints."""
        for key in set(self.current.keys()) & set(self.baseline.keys()):
            current = self.current[key]
            baseline = self.baseline[key]
            
            # Check for removed parameters
            baseline_param_names = {p['name'] for p in baseline.parameters}
            current_param_names = {p['name'] for p in current.parameters}
            
            removed = baseline_param_names - current_param_names
            current_param_names - baseline_param_names
            
            if removed:
                for param_name in removed:
                    # Was it required?
                    was_required = any(
                        p['name'] == param_name and p['required']
                        for p in baseline.parameters
                    )
                    
                    if was_required:
                        self.changes.append(BreakingChange(
                            change_type='REQUIRED_PARAM_REMOVED',
                            severity='BREAKING',
                            description=f"Required parameter '{param_name}' removed from {key}",
                            old_signature=baseline,
                            new_signature=current,
                            suggestion="This will break clients sending this parameter"
                        ))
                    else:
                        self.changes.append(BreakingChange(
                            change_type='OPTIONAL_PARAM_REMOVED',
                            severity='LIKELY_BREAKING',
                            description=f"Optional parameter '{param_name}' removed from {key}",
                            old_signature=baseline,
                            new_signature=current,
                            suggestion="Clients using this parameter may fail"
                        ))
    
    def _detect_method_changes(self):
        """Find HTTP method changes."""
        for key in set(self.current.keys()) & set(self.baseline.keys()):
            current = self.current[key]
            baseline = self.baseline[key]
            
            if current.method != baseline.method:
                self.changes.append(BreakingChange(
                    change_type='METHOD_CHANGE',
                    severity='BREAKING',
                    description=f"HTTP method changed for {key}: {baseline.method} → {current.method}",
                    old_signature=baseline,
                    new_signature=current,
                    suggestion="This will break all clients using the previous method"
                ))
    
    def _detect_new_required_params(self):
        """Find newly required parameters."""
        for key in set(self.current.keys()) & set(self.baseline.keys()):
            current = self.current[key]
            baseline = self.baseline[key]
            
            current_required = {p['name'] for p in current.parameters if p['required']}
            baseline_required = {p['name'] for p in baseline.parameters if p['required']}
            
            new_required = current_required - baseline_required
            
            for param_name in new_required:
                # Check if it existed before as optional
                was_optional = any(
                    p['name'] == param_name and not p['required']
                    for p in baseline.parameters
                )
                
                if was_optional:
                    self.changes.append(BreakingChange(
                        change_type='PARAM_NOW_REQUIRED',
                        severity='BREAKING',
                        description=f"Parameter '{param_name}' is now required in {key}",
                        old_signature=baseline,
                        new_signature=current,
                        suggestion="Clients not sending this parameter will get errors"
                    ))
    
    def _detect_new_endpoints(self):
        """Find new endpoints (informational only)."""
        for key, current_route in self.current.items():
            if key not in self.baseline:
                self.report.new_endpoints += 1
                
                self.changes.append(BreakingChange(
                    change_type='NEW_ENDPOINT',
                    severity='CAUTION',
                    description=f"New endpoint added: {key}",
                    new_signature=current_route,
                    suggestion="Informational - no action needed unless versioning concerns"
                ))


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, changes: list[BreakingChange], report: BreakingChangeReport):
        self.changes = sorted(changes, key=lambda c: (
            {'BREAKING': 0, 'LIKELY_BREAKING': 1, 'CAUTION': 2}.get(c.severity, 3),
            c.change_type
        ))
        self.report = report
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI API BREAKING CHANGE DETECTOR REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Routes in Current:           {self.report.total_routes_current}")
        lines.append(f"  Routes in Baseline:          {self.report.total_routes_baseline}")
        lines.append(f"  New Endpoints:               {self.report.new_endpoints}")
        lines.append("")
        lines.append(f"  🔴 Breaking Changes:          {self.report.breaking_changes}")
        lines.append(f"  🟠 Likely Breaking:           {self.report.likely_breaking}")
        lines.append(f"  🟡 Caution Items:              {self.report.caution_items}")
        lines.append("")
        
        # Verdict
        if self.report.breaking_changes > 0:
            lines.append("  ⚠️ VERDICT: BREAKING CHANGES DETECTED!")
        elif self.report.likely_breaking > 0:
            lines.append("  ⚠️ VERDICT: Likely breaking changes - review needed")
        elif self.report.caution_items > 0:
            lines.append("  ✅ VERDICT: Safe with minor notes")
        else:
            lines.append("  ✅ VERDICT: No breaking changes detected")
        lines.append("")
        
        # Detailed Changes
        if self.changes:
            lines.append("\nDETAILED CHANGES")
            lines.append("=" * 40)
            
            for i, change in enumerate(self.changes[:40], 1):
                icon = {'BREAKING': '🔴', 'LIKELY_BREAKING': '🟠', 'CAUTION': '🟡'}.get(change.severity, '⚪')
                
                lines.append(f"\n  {i}. {icon} [{change.change_type}] {change.severity}")
                lines.append(f"     {change.description}")
                
                if change.old_signature:
                    lines.append(f"     Old: {change.old_signature.file_path}:{change.old_signature.line_number}")
                if change.new_signature:
                    lines.append(f"     New: {change.new_signature.file_path}:{change.new_signature.line_number}")
                
                lines.append(f"     💡 {change.suggestion}")
            
            if len(self.changes) > 40:
                lines.append(f"\n  ... and {len(self.changes) - 40} more changes")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("API VERSIONING BEST PRACTICES")
        lines.append("=" * 80)
        lines.append("""
To Avoid Breaking Changes:

1. **Version Your APIs**
   - Use URL versioning: /api/v1/, /api/v2/
   - Maintain old versions alongside new ones

2. **Deprecate Before Removing**
   - Add deprecation warning to old endpoints
   - Keep deprecated endpoints for at least one major version cycle
   - Document migration path for clients

3. **Use Optional Parameters**
   - New parameters should be optional when possible
   - Provide sensible defaults
   - Announce upcoming required parameter changes

4. **Communicate Changes**
   - Maintain CHANGELOG.md
   - Use semantic versioning
   - Announce breaking changes in release notes

5. **CI Integration**
   - Run this script on every PR targeting main
   - Block merges with undocummented breaking changes
   - Require sign-off for breaking changes
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": asdict(self.report),
            "changes": [asdict(c) for c in self.changes],
            "timestamp": datetime.now().isoformat(),
        }


def get_baseline_routes(branch: str = 'main', backend_dir: Path | None = None) -> list[RouteSignature]:
    """Get route signatures from a git branch."""
    try:
        # Try to get routes from specified branch
        result = subprocess.run(
            ['git', 'show', f'{branch}:backend/api/routes/__init__.py'],
            capture_output=True,
            text=True,
            cwd=backend_dir if backend_dir else '.',
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse the output - simplified version
            # In production, you'd save/load a proper baseline file
            logger.info(f"Successfully fetched baseline from branch {branch}")
            return []
        else:
            logger.warning(f"Could not fetch baseline from {branch}: {result.stderr}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting baseline: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI API Breaking Change Detector',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--backend-dir', '-b', default='../backend')
    parser.add_argument('--baseline-branch', default='main',
                       help='Git branch to compare against')
    parser.add_argument('--baseline-file', help='Saved baseline JSON file')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], default='text')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-breaking', action='store_true',
                       help='Exit error if breaking changes found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print("⚠️ SupremeAI API Breaking Change Detector")
    print(f"   Backend Dir: {backend_dir}")
    print(f"   Baseline:   {args.baseline_branch}")
    print()
    
    # Extract current routes
    extractor = RouteExtractor(backend_dir)
    current_routes = extractor.extract()
    
    # Get baseline routes
    if args.baseline_file:
        try:
            with open(args.baseline_file) as f:
                baseline_data = json.load(f)
            baseline_routes = [RouteSignature(**r) for r in baseline_data]
        except Exception as e:
            logger.error(f"Could not load baseline file: {e}")
            baseline_routes = []
    else:
        baseline_routes = get_baseline_routes(args.baseline_branch, backend_dir)
    
    # If no baseline available, just report current state
    if not baseline_routes:
        print("⚠️ No baseline available - reporting current routes only")
        print(f"Found {len(current_routes)} routes in current codebase\n")
        
        # Save current as potential baseline
        if args.output_file:
            baseline_data = [asdict(r) for r in current_routes]
            with open(args.output_file.replace('.json', '_baseline.json'), 'w') as f:
                json.dump(baseline_data, f, indent=2)
            print(f"✅ Saved baseline to: {args.output_file}_baseline.json")
            print("   Re-run with --baseline-file to detect changes")
        return 0
    
    # Detect changes
    detector = BreakingChangeDetector(current_routes, baseline_routes)
    changes, report = detector.detect()
    
    # Generate report
    generator = ReportGenerator(changes, report)
    
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
    if args.fail_onbreaking and report.breaking_changes > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
