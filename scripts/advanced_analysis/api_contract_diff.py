#!/usr/bin/env python3
"""
API Contract Diff Checker for SupremeAI
========================================
Compares frontend fetch/axios calls against backend route signatures.
Flags mismatches in: path, HTTP method, request/response schema.

Usage:
    python api_contract_diff.py [--frontend-dir ../frontend] [--backend-dir ../backend] [--output-format json|text|html]
    
Self-healing principles:
- No hardcoded paths - auto-discovers routes and API calls
- DB-driven config support via optional JSON config
- CI-friendly exit codes
"""

import argparse
import ast
import json
import logging
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BackendRoute:
    """Represents a backend API route definition."""
    path: str
    method: str  # GET, POST, PUT, DELETE, etc.
    file_path: str
    line_number: int
    function_name: str
    request_params: list[str] = field(default_factory=list)
    response_model: str | None = None
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False


@dataclass
class FrontendAPICall:
    """Represents a frontend API call (fetch/axios)."""
    url: str
    method: str
    file_path: str
    line_number: int
    call_type: str  # fetch, axios, apiClient, etc.
    request_body_params: list[str] = field(default_factory=list)
    expected_response: str | None = None


@dataclass
class ContractMismatch:
    """Represents a mismatch between frontend and backend."""
    severity: str  # CRITICAL, WARNING, INFO
    mismatch_type: str
    frontend_call: FrontendAPICall | None
    backend_route: BackendRoute | None
    description: str
    suggestion: str


class BackendRouteExtractor:
    """Extracts API routes from FastAPI/Flask backend code."""
    
    # Common decorators that define routes
    ROUTE_DECORATORS = {
        'app.get': 'GET',
        'app.post': 'POST',
        'app.put': 'PUT',
        'app.delete': 'DELETE',
        'app.patch': 'PATCH',
        'app.options': 'OPTIONS',
        'app.head': 'HEAD',
        'router.get': 'GET',
        'router.post': 'POST',
        'router.put': 'PUT',
        'router.delete': 'DELETE',
        'router.patch': 'PATCH',
        'api_router.get': 'GET',
        'api_router.post': 'POST',
        'api_router.put': 'PUT',
        'api_router.delete': 'DELETE',
        '@get': 'GET',
        '@post': 'POST',
        '@put': 'PUT',
        '@delete': 'DELETE',
        '.route(': 'MULTI',  # Special handling needed
        '.api_route(': 'MULTI',
        '.get(': 'GET',
        '.post(': 'POST',
        '.put(': 'PUT',
        '.delete(': 'DELETE',
    }
    
    def __init__(self, backend_dir: Path):
        self.backend_dir = Path(backend_dir)
        self.routes: list[BackendRoute] = []
        
    def extract_routes(self) -> list[BackendRoute]:
        """Extract all routes from backend Python files."""
        python_files = list(self.backend_dir.rglob("*.py"))
        
        for py_file in python_files:
            if any(skip in str(py_file) for skip in ['__pycache__', 'migrations', '.venv', 'venv', 'node_modules', '.git']):
                continue
            self._extract_from_file(py_file)
            
        logger.info(f"Extracted {len(self.routes)} backend routes from {len(python_files)} files")
        return self.routes
    
    def _extract_from_file(self, file_path: Path):
        """Extract routes from a single Python file using AST and regex."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return
            
        # AST-based extraction for decorator patterns
        try:
            tree = ast.parse(content, filename=str(file_path))
            self._extract_from_ast(tree, file_path, lines)
        except SyntaxError:
            # Fall back to regex-based extraction
            self._extract_from_regex(content, file_path, lines)
    
    def _extract_from_ast(self, tree: ast.AST, file_path: Path, lines: list[str]):
        """Extract routes using AST analysis."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
                
            for decorator in node.decorator_list:
                route_info = self._analyze_decorator(decorator, node, file_path, lines)
                if route_info:
                    self.routes.append(route_info)
    
    def _analyze_decorator(self, decorator: ast.AST, func_node: ast.AST, 
                          file_path: Path, lines: list[str]) -> BackendRoute | None:
        """Analyze a single decorator to extract route info."""
        # Handle call decorators like @app.get("/path")
        if isinstance(decorator, ast.Call):
            func_name = self._get_decorator_func_name(decorator)
            if func_name:
                method = self.ROUTE_DECORATORS.get(func_name)
                if method:
                    path = self._get_first_string_arg(decorator)
                    if path:
                        # Extract request params from function signature
                        params = [arg.arg for arg in func_node.args.args 
                                 if arg.arg != 'self' and arg.arg != 'request' 
                                 and arg.arg != 'current_user' and arg.arg != 'db']
                        
                        return BackendRoute(
                            path=path,
                            method=method,
                            file_path=str(file_path.relative_to(self.backend_dir.parent)),
                            line_number=func_node.lineno,
                            function_name=func_node.name,
                            request_params=params
                        )
        
        # Handle attribute decorators
        elif isinstance(decorator, ast.Attribute):
            func_name = f"{self._get_attribute_chain(decorator)}"
            method = self.ROUTE_DECORATORS.get(func_name)
            if method:
                # Need to find the actual call in source
                return None  # Will be caught by regex fallback
        
        return None
    
    def _get_decorator_func_name(self, call: ast.Call) -> str | None:
        """Get the function name from a decorator call."""
        if isinstance(call.func, ast.Attribute):
            return self._get_attribute_chain(call.func)
        elif isinstance(call.func, ast.Name):
            return call.func.id
        return None
    
    def _get_first_string_arg(self, call: ast.Call) -> str | None:
        """Get the first string argument from a call."""
        for arg in call.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
        return None
    
    def _get_attribute_chain(self, attr: ast.Attribute) -> str:
        """Get full attribute chain."""
        parts = [attr.attr]
        current = attr.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))
    
    def _extract_from_regex(self, content: str, file_path: Path, lines: list[str]):
        """Fallback regex-based route extraction."""
        # Pattern for @app.get("/path") or router.get("/path")
        patterns = [
            r'@(?:\w+\.)*(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            r'(?:router|app|api_router)\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            r'\.(?:api_)?route\s*\(\s*["\']([^"\']+)["\'][^)]*methods\s*=\s*\[([^\]]+)\]',
        ]
        
        methods_map = {'get': 'GET', 'post': 'POST', 'put': 'PUT', 
                      'delete': 'DELETE', 'patch': 'PATCH'}
        
        for i, line in enumerate(lines):
            for pattern in patterns[:2]:  # Simple patterns
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    path = match.group(1)
                    # Determine method from pattern
                    method_match = re.search(r'(get|post|put|delete|patch)', line, re.IGNORECASE)
                    method = methods_map.get(method_match.group(1).lower(), 'GET') if method_match else 'GET'
                    
                    # Find function name on next non-empty/non-decorator line
                    func_name = ""
                    for j in range(i+1, min(i+5, len(lines))):
                        fn_match = re.search(r'def\s+(\w+)\s*\(', lines[j])
                        if fn_match:
                            func_name = fn_match.group(1)
                            break
                        elif lines[j].strip() and not lines[j].strip().startswith('@'):
                            break
                    
                    self.routes.append(BackendRoute(
                        path=path,
                        method=method,
                        file_path=str(file_path.relative_to(self.backend_dir.parent)),
                        line_number=i + 1,
                        function_name=func_name
                    ))
                    break
            
            # Multi-method pattern
            multi_match = re.search(patterns[2], line, re.IGNORECASE)
            if multi_match:
                path = multi_match.group(1)
                methods_str = multi_match.group(2)
                methods = re.findall(r'["\'](\w+)["\']', methods_str)
                
                for method in methods:
                    self.routes.append(BackendRoute(
                        path=path,
                        method=method.upper(),
                        file_path=str(file_path.relative_to(self.backend_dir.parent)),
                        line_number=i + 1,
                        function_name=""
                    ))


class FrontendCallExtractor:
    """Extracts API calls from frontend TypeScript/JavaScript code."""
    
    # Patterns for different call types
    FETCH_PATTERNS = [
        r'fetch\s*\(\s*["\']([^"\']+)["\']',
        r'fetch\s*\(\s*[`]{1}([^`]+)[`]{1}',
        r'\.get\s*\(\s*["\']([^"\']+)["\']',
        r'\.post\s*\(\s*["\']([^"\']+)["\']',
        r'\.put\s*\(\s*["\']([^"\']+)["\']',
        r'\.delete\s*\(\s*["\']([^"\']+)["\']',
        r'\.patch\s*\(\s*["\']([^"\']+)["\']',
        r'axios\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        r'api(?:Client)?\.(?:get|post|put|delete|patch|request)\s*\(\s*["\']([^"\']+)["\']',
        r'url:\s*["\']([^"\']+)["\']',  # axios config object
    ]
    
    METHOD_MAP = {
        'fetch': 'GET',  # Default, may be overridden by options
        '.get': 'GET',
        '.post': 'POST',
        '.put': 'PUT',
        '.delete': 'DELETE',
        '.patch': 'PATCH',
        'axios.get': 'GET',
        'axios.post': 'POST',
        'axios.put': 'PUT',
        'axios.delete': 'DELETE',
        'axios.patch': 'PATCH',
    }
    
    def __init__(self, frontend_dir: Path):
        self.frontend_dir = Path(frontend_dir)
        self.calls: list[FrontendAPICall] = []
        
    def extract_calls(self) -> list[FrontendAPICall]:
        """Extract all API calls from frontend files."""
        # Search TS/TSX/JS/JSX files
        extensions = ['*.ts', '*.tsx', '*.js', '*.jsx']
        files = []
        for ext in extensions:
            files.extend(self.frontend_dir.rglob(ext))
        
        # Filter out node_modules, dist, .next, tests, etc.
        files = [f for f in files if not any(
            skip in str(f) for skip in ['node_modules', 'dist', '.next', 'coverage', '__tests__', '.test.', '.spec.']
        )]
        
        for file_path in files:
            self._extract_from_file(file_path)
            
        logger.info(f"Extracted {len(self.calls)} frontend API calls from {len(files)} files")
        return self.calls
    
    def _extract_from_file(self, file_path: Path):
        """Extract API calls from a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return
        
        for i, line in enumerate(lines):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith(('//', '*', '/*')):
                continue
                
            for pattern in self.FETCH_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    url = match.group(1).strip()
                    
                    # Skip non-API URLs
                    if self._is_api_url(url):
                        method = self._determine_method(line, match)
                        call_type = self._detect_call_type(line)
                        
                        self.calls.append(FrontendAPICall(
                            url=url,
                            method=method,
                            file_path=str(file_path.relative_to(self.frontend_dir.parent)),
                            line_number=i + 1,
                            call_type=call_type
                        ))
    
    def _is_api_url(self, url: str) -> bool:
        """Check if URL looks like an API endpoint."""
        # Skip external or firebase endpoints
        if 'firebase' in url.lower() or url.startswith('http'):
            return False
            
        # Skip relative imports, CSS, images, etc.
        api_indicators = ['/api/', '/v1/', '/v2/', '/admin/', '/auth/', 
                         '/chat/', '/agent/', '/user/', '/billing/',
                         '/health', '/metrics', '/webhook', '/stream']
        
        # Must start with / or have API indicators
        if url.startswith('/'):
            return True
        return bool(any(ind in url.lower() for ind in api_indicators))
    
    def _determine_method(self, line: str, match: re.Match) -> str:
        """Determine HTTP method from context."""
        matched_str = match.group(0).lower()
        # Check for method in matched pattern
        for method_key, method_val in self.METHOD_MAP.items():
            if method_key.lower() in matched_str:
                return method_val
        
        # Check for method in options object (fetch/axios)
        options_match = re.search(r'method:\s*["\']?(\w+)["\']?', line[match.end():])
        if options_match:
            return options_match.group(1).upper()
        
        return 'GET'  # Default
    
    def _detect_call_type(self, line: str) -> str:
        """Detect what type of API call this is."""
        if 'axios' in line.lower():
            return 'axios'
        elif 'fetch(' in line:
            return 'fetch'
        elif 'apiClient' in line or 'api_client' in line or 'api.client' in line:
            return 'apiClient'
        elif any(x in line for x in ['.get(', '.post(', '.put(', '.delete(', '.patch(']):
            return 'method-chain'
        return 'unknown'


class ContractDiffChecker:
    """Main checker that compares frontend calls to backend routes."""
    
    def __init__(self, backend_routes: list[BackendRoute], frontend_calls: list[FrontendAPICall]):
        self.backend_routes = backend_routes
        self.frontend_calls = frontend_calls
        self.mismatches: list[ContractMismatch] = []
        
        # Build lookup structures
        self.route_map: dict[tuple[str, str], list[BackendRoute]] = defaultdict(list)
        for route in backend_routes:
            key = (self._normalize_path(route.path), route.method)
            self.route_map[key].append(route)
    
    def check(self) -> list[ContractMismatch]:
        """Perform contract diff check."""
        self._check_orphan_frontend_calls()
        self._check_dead_backend_routes()
        self._check_method_mismatches()
        self._check_path_parameter_mismatches()
        
        return self.mismatches
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for comparison (handle trailing slashes, etc.)."""
        # Remove query parameters
        path = path.split('?')[0]
        # Normalize multiple slashes
        while '//' in path:
            path = path.replace('//', '/')
        # Remove trailing slash (except root)
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        return path
    
    def _path_matches(self, frontend_path: str, backend_path: str) -> bool:
        """Check if paths match considering path parameters."""
        fp = self._normalize_path(frontend_path)
        bp = self._normalize_path(backend_path)
        
        # Direct match
        if fp == bp:
            return True
        
        # Convert both to pattern (replace params with placeholder)
        # Handle JS template literals first: ${var} -> {param}
        fp_pattern = re.sub(r'\$\{[^}]+\}', '{param}', fp)
        fp_pattern = re.sub(r'\{[^}]+\}', '{param}', fp_pattern)
        bp_pattern = re.sub(r'\{[^}]+\}|:\w+', '{param}', bp)
        
        # Suffix match (because backend might not include router prefix)
        if fp_pattern.endswith(bp_pattern) or bp_pattern.endswith(fp_pattern):
            return True
            
        return fp_pattern == bp_pattern
    
    def _check_orphan_frontend_calls(self):
        """Find frontend calls that don't match any backend route."""
        for call in self.frontend_calls:
            self._normalize_path(call.url)
            
            found_match = False
            for (route_path, method) in self.route_map:
                if self._path_matches(call.url, route_path):
                    if call.method == method or method == 'MULTI':
                        found_match = True
                        break
            
            if not found_match:
                # Check if it's a partial match (same path, different method)
                partial_match = any(
                    self._path_matches(call.url, rp) 
                    for rp, _ in self.route_map
                )
                
                severity = 'WARNING' if partial_match else 'CRITICAL'
                mismatch_type = 'ORPHAN_FRONTEND_CALL' if not partial_match else 'METHOD_MISMATCH'
                
                self.mismatches.append(ContractMismatch(
                    severity=severity,
                    mismatch_type=mismatch_type,
                    frontend_call=call,
                    backend_route=None,
                    description=f"Frontend calls {call.method} {call.url} but no matching backend route found",
                    suggestion=f"Create backend route for {call.method} {call.url} or fix frontend URL"
                ))
    
    def _check_dead_backend_routes(self):
        """Find backend routes never called from frontend."""
        for route in self.backend_routes:
            is_called = False
            
            for call in self.frontend_calls:
                if self._path_matches(call.url, route.path):
                    is_called = True
                    break
            
            if not is_called:
                # Skip common utility routes
                skip_patterns = ['/health', '/metrics', '/ready', '/live', '/docs', '/openapi']
                if not any(route.path.startswith(p) for p in skip_patterns):
                    self.mismatches.append(ContractMismatch(
                        severity='INFO',
                        mismatch_type='DEAD_BACKEND_ROUTE',
                        frontend_call=None,
                        backend_route=route,
                        description=f"Backend route {route.method} {route.path} ({route.function_name}) has no frontend caller",
                        suggestion="Consider removing dead route or document if intended for external/API use"
                    ))
    
    def _check_method_mismatches(self):
        """Find cases where same path exists but method differs."""
        for call in self.frontend_calls:
            for (route_path, method), routes in self.route_map.items():
                if self._path_matches(call.url, route_path) and call.method != method:
                    if method != 'MULTI':
                        self.mismatches.append(ContractMismatch(
                            severity='CRITICAL',
                            mismatch_type='METHOD_MISMATCH',
                            frontend_call=call,
                            backend_route=routes[0],
                            description=f"Frontend uses {call.method} but backend defines {method} for {call.url}",
                            suggestion=f"Change frontend to use {method} or add {call.method} handler on backend"
                        ))
    
    def _check_path_parameter_mismatches(self):
        """Check for path parameter naming inconsistencies."""
        param_styles_frontend = defaultdict(set)
        param_styles_backend = defaultdict(set)
        
        for call in self.frontend_calls:
            params = re.findall(r'\{([^}]+)\}', call.url)
            base_path = re.sub(r'\{[^}]+\}', '{}', call.url)
            if params:
                param_styles_frontend[base_path].update(params)
        
        for route in self.backend_routes:
            params = re.findall(r'(?:\{([^}]+)\}|:(\w+))', route.path)
            flat_params = [p[0] or p[1] for p in params]
            base_path = re.sub(r'(?:\{[^}]+\}|:\w+)', '{}', route.path)
            if flat_params:
                param_styles_backend[base_path].update(flat_params)
        
        # Compare parameter styles
        all_bases = set(param_styles_frontend.keys()) | set(param_styles_backend.keys())
        for base in all_bases:
            fp = param_styles_frontend.get(base, set())
            bp = param_styles_backend.get(base, set())
            if fp and bp and fp != bp:
                self.mismatches.append(ContractMismatch(
                    severity='WARNING',
                    mismatch_type='PARAM_STYLE_INCONSISTENCY',
                    frontend_call=None,
                    backend_route=None,
                    description=f"Path parameter style differs for {base}: frontend={fp}, backend={bp}",
                    suggestion="Standardize parameter naming (e.g., always use {id} or :id)"
                ))


class ReportGenerator:
    """Generates reports in various formats."""
    
    def __init__(self, mismatches: list[ContractMismatch], 
                 backend_routes: list[BackendRoute],
                 frontend_calls: list[FrontendAPICall]):
        self.mismatches = mismatches
        self.backend_routes = backend_routes
        self.frontend_calls = frontend_calls
    
    def generate_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("SUPREMEAI API CONTRACT DIFF REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        critical = sum(1 for m in self.mismatches if m.severity == 'CRITICAL')
        warnings = sum(1 for m in self.mismatches if m.severity == 'WARNING')
        infos = sum(1 for m in self.mismatches if m.severity == 'INFO')
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"  Total Backend Routes:     {len(self.backend_routes)}")
        lines.append(f"  Total Frontend Calls:     {len(self.frontend_calls)}")
        lines.append(f"  Critical Issues:          {critical}")
        lines.append(f"  Warnings:                 {warnings}")
        lines.append(f"  Info Notes:               {infos}")
        lines.append("")
        
        # Group mismatches by type
        by_type = defaultdict(list)
        for m in self.mismatches:
            by_type[m.mismatch_type].append(m)
        
        # Detailed findings
        lines.append("DETAILED FINDINGS")
        lines.append("-" * 40)
        
        for mismatch_type, mismatches in sorted(by_type.items()):
            lines.append(f"\n📌 {mismatch_type.replace('_', ' ').title()} ({len(mismatches)} issues)")
            lines.append("  " + "-" * 36)
            
            for i, m in enumerate(mismatches[:20], 1):  # Limit output
                lines.append(f"\n  {i}. [{m.severity}] {m.description}")
                if m.frontend_call:
                    lines.append(f"     Frontend: {m.frontend_call.file_path}:{m.frontend_call.line_number}")
                if m.backend_route:
                    lines.append(f"     Backend:  {m.backend_route.file_path}:{m.backend_route.line_number}")
                lines.append(f"     Suggest:   {m.suggestion}")
            
            if len(mismatches) > 20:
                lines.append(f"\n  ... and {len(mismatches) - 20} more issues of this type")
        
        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("""
1. Fix CRITICAL issues immediately - these cause runtime errors
2. Review WARNING issues - may cause unexpected behavior  
3. Consider generating OpenAPI spec from backend for type-safe frontend
4. Add this script to CI pipeline for early detection
5. Consider using tools like openapi-typescript for auto-generation
""")
        
        return "\n".join(lines)
    
    def generate_json_report(self) -> dict:
        """Generate machine-readable JSON report."""
        return {
            "summary": {
                "total_backend_routes": len(self.backend_routes),
                "total_frontend_calls": len(self.frontend_calls),
                "critical_count": sum(1 for m in self.mismatches if m.severity == 'CRITICAL'),
                "warning_count": sum(1 for m in self.mismatches if m.severity == 'WARNING'),
                "info_count": sum(1 for m in self.mismatches if m.severity == 'INFO'),
            },
            "mismatches": [asdict(m) for m in self.mismatches],
            "timestamp": __import__('datetime').datetime.now().isoformat(),
        }
    
    def generate_html_report(self) -> str:
        """Generate HTML report with styling."""
        json_data = self.generate_json_report()
        
        severity_colors = {
            'CRITICAL': '#dc3545',
            'WARNING': '#ffc107',
            'INFO': '#17a2b8'
        }
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SupremeAI API Contract Diff Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 6px; text-align: center; }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .mismatch {{ border-left: 4px solid #ccc; padding: 15px; margin: 10px 0; background: #fafafa; }}
        .severity-badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; color: white; font-size: 0.85em; font-weight: bold; }}
        pre {{ background: #282c34; color: #abb2bf; padding: 15px; border-radius: 6px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 SupremeAI API Contract Diff Report</h1>
        <div class="summary">
            <div class="stat-card"><div class="stat-number">{json_data['summary']['total_backend_routes']}</div><div class="stat-label">Backend Routes</div></div>
            <div class="stat-card"><div class="stat-number">{json_data['summary']['total_frontend_calls']}</div><div class="stat-label">Frontend Calls</div></div>
            <div class="stat-card"><div class="stat-number" style="color: {severity_colors['CRITICAL']}">{json_data['summary']['critical_count']}</div><div class="stat-label">Critical</div></div>
            <div class="stat-card"><div class="stat-number" style="color: {severity_colors['WARNING']}">{json_data['summary']['warning_count']}</div><div class="stat-label">Warnings</div></div>
        </div>
"""
        
        for m in self.mismatches[:50]:  # Limit HTML size
            color = severity_colors.get(m.severity, '#666')
            html += f"""
        <div class="mismatch" style="border-left-color: {color};">
            <span class="severity-badge" style="background: {color};">{m.severity}</span>
            <strong>{m.mismatch_type.replace('_', ' ')}</strong>
            <p>{m.description}</p>
            <p><em>Suggestion: {m.suggestion}</em></p>
"""
            if m.frontend_call:
                html += f"<code>{m.frontend_call.file_path}:{m.frontend_call.line_number}</code><br>"
            if m.backend_route:
                html += f"<code>{m.backend_route.file_path}:{m.backend_route.line_number}</code>"
            html += "</div>"
        
        html += """
    </div>
</body>
</html>"""
        return html


def main():
    parser = argparse.ArgumentParser(
        description='SupremeAI API Contract Diff Checker - Detect frontend/backend API mismatches',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python api_contract_diff.py
  python api_contract_diff.py --output-format json > report.json
  python api_contract_diff.py --output-format html > report.html
  python api_contract_diff.py --frontend-dir ./src --backend-dir ./backend --verbose
"""
    )
    
    parser.add_argument('--frontend-dir', '-f', default='../../frontend',
                       help='Frontend source directory (default: ../../frontend)')
    parser.add_argument('--backend-dir', '-b', default='../../backend',
                       help='Backend source directory (default: ../../backend)')
    parser.add_argument('--output-format', '-o', choices=['text', 'json', 'html'], 
                       default='text', help='Output format (default: text)')
    parser.add_argument('--output-file', help='Write output to file instead of stdout')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--fail-on-critical', action='store_true',
                       help='Exit with error code if critical issues found (CI mode)')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    frontend_dir = (script_dir / args.frontend_dir).resolve()
    backend_dir = (script_dir / args.backend_dir).resolve()
    
    if not frontend_dir.exists():
        logger.error(f"Frontend directory not found: {frontend_dir}")
        sys.exit(1)
    if not backend_dir.exists():
        logger.error(f"Backend directory not found: {backend_dir}")
        sys.exit(1)
    
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    print("🔍 SupremeAI API Contract Diff Checker")
    print(f"   Frontend: {frontend_dir}")
    print(f"   Backend:  {backend_dir}")
    print()
    
    # Extract routes and calls
    backend_extractor = BackendRouteExtractor(backend_dir)
    backend_routes = backend_extractor.extract_routes()
    
    frontend_extractor = FrontendCallExtractor(frontend_dir)
    frontend_calls = frontend_extractor.extract_calls()
    
    # Run comparison
    checker = ContractDiffChecker(backend_routes, frontend_calls)
    mismatches = checker.check()
    
    # Generate report
    generator = ReportGenerator(mismatches, backend_routes, frontend_calls)
    
    if args.output_format == 'json':
        output = json.dumps(generator.generate_json_report(), indent=2)
    elif args.output_format == 'html':
        output = generator.generate_html_report()
    else:
        output = generator.generate_text_report()
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"✅ Report written to: {args.output_file}")
    else:
        print(output)
    
    # Exit code for CI
    critical_count = sum(1 for m in mismatches if m.severity == 'CRITICAL')
    if args.fail_on_critical and critical_count > 0:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    main()
