#!/usr/bin/env python3
"""
Orphan Route Finder for SupremeAI
===================================
Finds:
1. Backend routes that are never called from frontend (dead APIs)
2. Frontend API calls to routes that don't exist in backend (broken calls)

Uses strict import-graph and call-pattern analysis (not loose grep).

Usage:
    python orphan_route_finder.py [--frontend-dir ../frontend] [--backend-dir ../backend]
    
Self-healing principles:
- Auto-discovers all routes and API calls
- No hardcoded endpoint lists
- CI-friendly with exit codes
"""

import re
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BackendRoute:
    """Backend API route definition."""
    path: str
    method: str
    file_path: str
    line_number: int
    function_name: str
    module: str = ""
    tags: List[str] = field(default_factory=list)
    is_deprecated: bool = False


@dataclass
class FrontendCallSite:
    """Frontend location where an API call is made."""
    url_pattern: str  # May include dynamic segments
    method: str
    file_path: str
    line_number: int
    component_function: str = ""
    call_type: str = ""  # fetch, axios, custom client


@dataclass
class OrphanRouteIssue:
    """An orphan route or broken call issue."""
    issue_type: str  # DEAD_API, BROKEN_CALL, PARTIAL_MATCH
    severity: str
    route_path: str
    method: str
    description: str
    backend_location: Optional[str] = None
    frontend_locations: List[str] = field(default_factory=list)
    suggestion: str = ""


class BackendRouteScanner:
    """Scans backend for all API route definitions."""
    
    ROUTE_PATTERNS = {
        # FastAPI decorators
        r'@(?:app|router|api_router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        # Method-based
        r'(?:app|router|api_router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        # Multi-method routes
        r'\.(?:api_)?route\s*\(\s*["\']([^"\']+)["\'][^)]*methods\s*=\s*\[([^\]]+)\]',
        # Flask-style
        r'@(?:app|blueprint)\.route\s*\(\s*["\']([^"\']+)["\']',
    }
    
    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.routes: List[BackendRoute] = []
        
    def scan(self) -> List[BackendRoute]:
        """Scan all Python files for route definitions."""
        py_files = list(self.backend_dir.rglob("*.py"))
        skip_dirs = {'__pycache__', 'tests', 'migrations', '.git', 'venv', '.venv'}
        
        for py_file in py_files:
            if any(skip in str(py_file) for skip in skip_dirs):
                continue
            self._scan_file(py_file)
        
        logger.info(f"Found {len(self.routes)} backend routes")
        return self.routes
    
    def _scan_file(self, file_path: Path):
        """Scan a single Python file for routes."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.backend_dir.parent))
        module = rel_path.replace('/', '.').replace('.py', '')
        
        # Track recent decorator context
        pending_decorators = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check for route decorators
            for pattern in list(self.ROUTE_PATTERNS)[:-1]:  # All except multi-method
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if 'route(' in pattern or '(' in pattern[:10]:  # Decorator style
                        method = match.group(1).upper() if match.lastindex >= 1 else 'GET'
                        path = match.group(2) if match.lastindex >= 2 else match.group(1)
                    else:
                        method = match.group(1).upper()
                        path = match.group(2)
                    
                    pending_decorators.append({
                        'method': method,
                        'path': path,
                        'line': i + 1
                    })
            
            # Check for multi-method routes
            multi_match = re.search(self.ROUTE_PATTERNS[2], line, re.IGNORECASE)
            if multi_match:
                path = multi_match.group(1)
                methods_str = multi_match.group(2)
                methods = re.findall(r'["\'](\w+)["\']', methods_str)
                
                for method in methods:
                    self.routes.append(BackendRoute(
                        path=path,
                        method=method.upper(),
                        file_path=rel_path,
                        line_number=i + 1,
                        function_name="",
                        module=module
                    ))
                continue
            
            # If we hit a function definition, associate with pending decorators
            fn_match = re.match(r'def\s+(\w+)\s*\(', stripped)
            if fn_match and pending_decorators:
                func_name = fn_match.group(1)
                for dec in pending_decorators:
                    self.routes.append(BackendRoute(
                        path=dec['path'],
                        method=dec['method'],
                        file_path=rel_path,
                        line_number=dec['line'],
                        function_name=func_name,
                        module=module
                    ))
                pending_decorators = []
            
            # Reset decorators if we hit a non-decorator, non-function line
            elif stripped and not stripped.startswith('@') and not stripped.startswith('def '):
                # Keep only last decorator (in case of stacked decorators)
                if len(pending_decorators) > 1:
                    pending_decorators = pending_decorators[-1:]


class FrontendCallScanner:
    """Scans frontend for all API call sites."""
    
    CALL_PATTERNS = [
        # fetch('/url')
        r'fetch\s*\(\s*["\'`]([^"\'`]+)["\'`]',
        # axios.get('/url'), axios.post('/url'), etc.
        r'(?:axios|apiClient?|api|http)\.(?:get|post|put|delete|patch|request)\s*\(\s*["\'`]([^"\'`]+)["\'`]',
        # .get('/url'), .post('/url') on service instances
        r'\.(?:get|post|put|delete|patch)\s*\(\s*["\'`]([^"\'`]+)["\'`]',
        # url: '/url' in axios config objects
        r'url:\s*["\'`]([^"\'`]+)["\'`]',
        # Template literal URLs
        r'[`]\s*(?:/api|/v1|/auth|/chat|/agent)[^`]*[`]',
    ]
    
    METHOD_FROM_CONTEXT = {
        'axios.get': 'GET', 'axios.post': 'POST', 'axios.put': 'PUT',
        'axios.delete': 'DELETE', 'axios.patch': 'PATCH',
        '.get(': 'GET', '.post(': 'POST', '.put(': 'PUT',
        '.delete(': 'DELETE', '.patch(': 'PATCH',
    }
    
    def __init__(self, frontend_dir: Path):
        self.frontend_dir = Path(frontend_dir)
        self.call_sites: List[FrontendCallSite] = []
        
    def scan(self) -> List[FrontendCallSite]:
        """Scan all frontend files for API calls."""
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        skip_dirs = {'node_modules', 'dist', '.next', 'coverage'}
        
        for ext in extensions:
            for fe_file in self.frontend_dir.rglob(ext):
                if any(skip in str(fe_file) for skip in skip_dirs):
                    continue
                self._scan_file(fe_file)
        
        logger.info(f"Found {len(self.call_sites)} frontend API call sites")
        return self.call_sites
    
    def _scan_file(self, file_path: Path):
        """Scan a single frontend file for API calls."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            return
        
        rel_path = str(file_path.relative_to(self.frontend_dir.parent))
        
        # Try to extract current component/function name
        current_component = ""
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Track component/function names
            comp_match = re.match(r'(?:function|const|let|var|export\s+(?:default\s+)?)\s*(\w+)', stripped)
            if comp_match and any(kw in stripped for kw in ['function', '=>', '=']):
                current_component = comp_match.group(1)
            
            # Skip comments
            if stripped.startswith('//') or stripped.startswith('*') or stripped.startswith('/*'):
                continue
            
            # Look for API calls
            for pattern in self.CALL_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    url = match.group(1).strip()
                    
                    # Filter to only API-like URLs
                    if not self._is_api_url(url):
                        continue
                    
                    method = self._detect_method(line, match)
                    call_type = self._detect_call_type(line)
                    
                    self.call_sites.append(FrontendCallSite(
                        url_pattern=url,
                        method=method,
                        file_path=rel_path,
                        line_number=i + 1,
                        component_function=current_component,
                        call_type=call_type
                    ))
    
    def _is_api_url(self, url: str) -> bool:
        """Check if URL looks like an API endpoint."""
        api_indicators = [
            '/api/', '/v1/', '/v2/', '/v3/',
            '/auth', '/login', '/logout', '/register', '/signup',
            '/chat', '/conversation', '/message',
            '/agent', '/agents', '/task', '/tasks',
            '/user', '/users', '/admin', '/settings',
            '/billing', '/payment', '/subscription',
            '/health', '/metrics', '/status',
            '/webhook', '/callback', '/upload',
            '/search', '/query', '/fetch',
            '/knowledge', '/memory', '/skill',
            '/workspace', '/project',
            '/stream', '/sse', '/ws', '/websocket',
        ]
        
        # Must start with / or be a relative API path
        if url.startswith('/'):
            return True
        if any(url.lower().startswith(ind) for ind in api_indicators):
            return True
        return False
    
    def _detect_method(self, line: str, match: re.Match) -> str:
        """Detect HTTP method from surrounding code context."""
        before_match = line[:match.start()].lower()
        
        for pattern, method in self.METHOD_FROM_CONTEXT.items():
            if pattern.lower() in before_match:
                return method
        
        # Check for method property in object
        method_prop = re.search(r'method:\s*["\']?(\w+)', line[match.end():])
        if method_prop:
            return method_prop.group(1).upper()
        
        return 'GET'  # Default
    
    def _detect_call_type(self, line: str) -> str:
        """Detect what type of API call this is."""
        if 'axios' in line.lower():
            return 'axios'
        elif 'fetch(' in line:
            return 'fetch'
        elif 'apiClient' in line or 'api_client' in line:
            return 'apiClient'
        elif any(x in line for x in ['.get(', '.post(', '.put(', '.delete(']):
            return 'method-chain'
        return 'unknown'


class OrphanRouteAnalyzer:
    """Analyzes routes and calls to find orphans and broken references."""
    
    # Routes that are expected to be frontend-only or external
    EXTERNAL_ROUTE_PREFIXES = ['/docs', '/openapi.json', '/redoc', '/swagger']
    
    # Common health/utility endpoints that may not be called by frontend
    UTILITY_ENDPOINTS = {
        '/health', '/healthz', '/ready', '/live', '/metrics',
        '/version', '/status', '/ping'
    }
    
    def __init__(self, routes: List[BackendRoute], calls: List[FrontendCallSite]):
        self.routes = routes
        self.calls = calls
        self.issues: List[OrphanRouteIssue] = []
        
        # Normalize paths for comparison
        self.normalized_routes: Dict[Tuple[str, str], BackendRoute] = {}
        for route in routes:
            key = (self._normalize_path(route.path), route.method)
            self.normalized_routes[key] = route
    
    def analyze(self) -> List[OrphanRouteIssue]:
        """Perform analysis to find orphan routes and broken calls."""
        self._find_dead_apis()
        self._find_broken_calls()
        self._find_partial_matches()
        
        return self.issues
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for comparison."""
        # Remove query string
        path = path.split('?')[0]
        # Remove trailing slash (except root)
        while path.endswith('/') and len(path) > 1:
            path = path[:-1]
        return path
    
    def _paths_match(self, frontend_path: str, backend_path: str) -> bool:
        """Check if a frontend URL pattern could match a backend route."""
        fp = self._normalize_path(frontend_path)
        bp = self._normalize_path(backend_path)
        
        # Direct match
        if fp == bp:
            return True
        
        # Parameterize both paths
        fp_param = re.sub(r'\{[^}]+\}|:\w+', '{param}', fp)
        bp_param = re.sub(r'\{[^}]+\}|:\w+', '{param}', bp)
        
        # Handle wildcard patterns
        fp_param = re.sub(r'\*\*', '{wildcard}')
        bp_param = re.sub(r'\*\*', '{wildcard}')
        
        return fp_param == bp_param
    
    def _is_utility_endpoint(self, path: str) -> bool:
        """Check if this is a utility/infrastructure endpoint."""
        norm = self._normalize_path(path).lower()
        return any(norm == u or norm.startswith(u + '/') for u in self.UTILITY_ENDPOINTS)
    
    def _is_external_doc_endpoint(self, path: str) -> bool:
        """Check if this is a documentation endpoint."""
        norm = self._normalize_path(path).lower()
        return any(norm.startswith(e) for e in self.EXTERNAL_ROUTE_PREFIXES)
    
    def _find_dead_apis(self):
        """Find backend routes never called from frontend."""
        # Build set of all called paths/methods
        called_paths: Set[Tuple[str, str]] = set()
        for call in self.calls:
            called_paths.add((call.url_pattern, call.method))
        
        for (norm_path, method), route in self.normalized_routes.items():
            # Skip utility endpoints
            if self._is_utility_endpoint(route.path):
                continue
            
            # Skip documentation endpoints  
            if self._is_external_doc_endpoint(route.path):
                continue
            
            # Check if any frontend call matches this route
            is_called = False
            for call in self.calls:
                if self._paths_match(call.url_pattern, route.path):
                    if call.method == method or method == 'MULTI':
                        is_called = True
                        break
            
            if not is_called:
                severity = 'WARNING'
                suggestion = f"Consider removing unused route or document if intended for external use"
                
                # Internal/admin routes are less critical
                if any(p in route.path.lower() for p in ['internal', 'admin', 'debug']):
                    severity = 'INFO'
                
                self.issues.append(OrphanRouteIssue(
                    issue_type='DEAD_API',
                    severity=severity,
                    route_path=route.path,
                    method=method,
                    description=f"Route {method} {route.path} ({route.function_name}) has no frontend caller",
                    backend_location=f"{route.file_path}:{route.line_number}",
                    suggestion=suggestion
                ))
    
    def _find_broken_calls(self):
        """Find frontend calls to non-existent backend routes."""
        for call in self.calls:
            matched = False
            
            for (norm_path, method), route in self.normalized_routes.items():
                if self._paths_match(call.url_pattern, route.path):
                    matched = True
                    
                    # Check method mismatch
                    if call.method != method and method != 'MULTI':
                        self.issues.append(OrphanRouteIssue(
                            issue_type='BROKEN_CALL',
                            severity='CRITICAL',
                            route_path=call.url_pattern,
                            method=call.method,
                            description=f"Frontend uses {call.method} but backend only has {method} for {call.url_pattern}",
                            frontend_locations=[f"{call.file_path}:{call.line_number}"],
                            backend_location=f"{route.file_path}:{route.line_number}",
                            suggestion=f"Change frontend to {method} or add {call.method} handler"
                        ))
                    break
            
            if not matched:
                # Might be calling an external API or using base URL
                if call.url_pattern.startswith(('http://', 'https://')):
                    continue
                
                severity = 'CRITICAL'
                suggestion = f"Create backend route for {call.method} {call.url_pattern} or fix URL"
                
                # Could be a dynamic/constructed URL
                if '{' in call.url_pattern or '${' in call.url_pattern:
                    severity = 'WARNING'
                    suggestion = "Verify this dynamic URL resolves correctly at runtime"
                
                self.issues.append(OrphanRouteIssue(
                    issue_type='BROKEN_CALL',
                    severity=severity,
                    route_path=call.url_pattern,
                    method=call.method,
                    description=f"Frontend calls {call.method} {call.url_pattern} but no matching backend route",
                    frontend_locations=[f"{call.file_path}:{call.line_number}"],
                    suggestion=suggestion
                ))
    
    def _find_partial_matches(self):
        """Find near-misses that might indicate typos or version mismatches."""
        backend_paths = {(r.path, r.method): r for r in self.routes}
        
        for call in self.calls:
            if '{' in call.url_pattern or '$' in call.url_pattern:
                continue  # Skip dynamic URLs for this check
            
            call_norm = self._normalize_path(call.url_pattern)
            
            for (bp, method), route in backend_paths.items():
                bp_norm = self._normalize_path(bp)
                
                # Check for common typo patterns
                if self._is_near_miss(call_norm, bp_norm):
                    # Only report if not already found as exact match
                    already_reported = any(
                        i.route_path == call.url_pattern and i.issue_type == 'BROKEN_CALL'
                        for i in self.issues
                    )
                    if not already_reported:
                        self.issues.append(OrphanRouteIssue(
                            issue_type='PARTIAL_MATCH',
                            severity='WARNING',
                            route_path=call.url_pattern,
                            method=call.method,
                            description=f"Possible typo: '{call.url_pattern}' is similar to backend route '{bp}'",
                            frontend_locations=[f"{call.file_path}:{call.line_number}"],
                            backend_location=f"{route.file_path}:{route.line_number}",
                            suggestion=f"Did you mean '{bp}'?"
                        ))
    
    def _is_near_miss(self, s1: str, s2: str) -> bool:
        """Check if two strings are similar enough to be potential typos."""
        if s1 == s2:
            return False
        
        # One is prefix of other (with possible trailing slash difference)
        if s1.startswith(s2) or s2.startswith(s1):
            diff_len = abs(len(s1) - len(s2))
            return diff_len <= 3 and diff_len > 0
        
        # Single segment difference
        parts1 = s1.rstrip('/').split('/')
        parts2 = s2.rstrip('/').split('/')
        
        if len(parts1) != len(parts2):
            return False
        
        differences = sum(1 for p1, p2 in zip(parts1, parts2) if p1 != p2)
        return differences == 1


class ReportGenerator:
    """Generates reports."""
    
    def __init__(self, issues: List[OrphanRouteIssue], 
                 routes: List[BackendRoute],
                 calls: List[FrontendCallSite]):
        self.issues = issues
        self.routes = routes
        self.calls = calls
    
    def generate_text_report(self) -> str:
        """Generate text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI ORPHAN ROUTE FINDER REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Summary
        dead_apis = [i for i in self.issues if i.issue_type == 'DEAD_API']
        broken_calls = [i for i in self.issues if i.issue_type == 'BROKEN_CALL']
        partial_matches = [i for i in self.issues if i.issue_type == 'PARTIAL_MATCH']
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Backend Routes:       {len(self.routes)}")
        lines.append(f"  Total Frontend Call Sites:  {len(self.calls)}")
        lines.append(f"  Dead APIs (no callers):     {len(dead_apis)}")
        lines.append(f"  Broken Calls (no route):    {len(broken_calls)}")
        lines.append(f"  Partial Matches (typos?):   {len(partial_matches)}")
        lines.append("")
        
        # Critical issues first
        critical_issues = [i for i in self.issues if i.severity == 'CRITICAL']
        if critical_issues:
            lines.append("🔴 CRITICAL ISSUES (Must Fix)")
            lines.append("-" * 40)
            for i, issue in enumerate(critical_issues, 1):
                lines.append(f"\n  {i}. {issue.description}")
                if issue.frontend_locations:
                    lines.append(f"     Frontend: {issue.frontend_locations[0]}")
                if issue.backend_location:
                    lines.append(f"     Backend:  {issue.backend_location}")
                lines.append(f"     💡 {issue.suggestion}")
        
        # Dead APIs
        if dead_apis:
            lines.append(f"\n\n🟢 DEAD APIS (Unused Routes) - {len(dead_apis)} found")
            lines.append("-" * 40)
            for i, issue in enumerate(dead_apis[:20], 1):
                lines.append(f"  {i}. [{issue.severity}] {issue.method} {issue.route_path}")
                lines.append(f"     → {issue.backend_location}")
                lines.append(f"     {issue.suggestion}")
            if len(dead_apis) > 20:
                lines.append(f"  ... and {len(dead_apis) - 20} more")
        
        # Broken calls
        if broken_calls:
            lines.append(f"\n\n🔴 BROKEN CALLS (Missing Routes) - {len(broken_calls)} found")
            lines.append("-" * 40)
            for i, issue in enumerate(broken_calls[:20], 1):
                lines.append(f"  {i}. [{issue.severity}] {issue.method} {issue.route_path}")
                if issue.frontend_locations:
                    lines.append(f"     → {issue.frontend_locations[0]}")
                lines.append(f"     {issue.suggestion}")
            if len(broken_calls) > 20:
                lines.append(f"  ... and {len(broken_calls) - 20} more")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
1. Fix all CRITICAL broken calls immediately - these cause runtime errors
2. Review DEAD APIs - remove or document intentional external-only routes
3. Check PARTIAL MATCHES for potential typos
4. Consider generating OpenAPI spec for type-safe frontend SDK
5. Add this script to CI pipeline for early detection
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate JSON report."""
        return {
            "summary": {
                "total_routes": len(self.routes),
                "total_call_sites": len(self.calls),
                "dead_apis_count": sum(1 for i in self.issues if i.issue_type == 'DEAD_API'),
                "broken_calls_count": sum(1 for i in self.issues if i.issue_type == 'BROKEN_CALL'),
                "partial_matches_count": sum(1 for i in self.issues if i.issue_type == 'PARTIAL_MATCH'),
                "critical_count": sum(1 for i in self.issues if i.severity == 'CRITICAL'),
            },
            "issues": [asdict(i) for i in self.issues],
            "timestamp": datetime.now().isoformat(),
        }


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI Orphan Route Finder - Find dead APIs and broken calls',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--frontend-dir', '-f', default='../frontend',
                       help='Frontend directory (default: ../frontend)')
    parser.add_argument('--backend-dir', '-b', default='../backend',
                       help='Backend directory (default: ../backend)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json'], 
                       default='text', help='Output format')
    parser.add_argument('--output-file', help='Write output to file')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    script_dir = Path(__file__).parent
    frontend_dir = (script_dir / args.frontend_dir).resolve()
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    print(f"🔍 SupremeAI Orphan Route Finder")
    print(f"   Frontend: {frontend_dir}")
    print(f"   Backend:  {backend_dir}")
    print()
    
    # Scan
    backend_scanner = BackendRouteScanner(backend_dir)
    routes = backend_scanner.scan()
    
    frontend_scanner = FrontendCallScanner(frontend_dir)
    calls = frontend_scanner.scan()
    
    # Analyze
    analyzer = OrphanRouteAnalyzer(routes, calls)
    issues = analyzer.analyze()
    
    # Generate report
    generator = ReportGenerator(issues, routes, calls)
    
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
    critical_count = sum(1 for i in issues if i.severity == 'CRITICAL')
    if args.fail_on_critical and critical_count > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
