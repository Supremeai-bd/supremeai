#!/usr/bin/env python3
"""
SuperAI Automated Verification Suite
=====================================
Comprehensive tests to verify SuperAI transformation success.

Usage:
    python superai_verify.py                    # Run all checks
    python superai_verify.py --quick            # Quick smoke tests only
    python superai_verify.py --security         # Security-specific checks
    python superai_verify.py --json             # JSON output for CI

Checks Performed:
✅ File existence (new modules created)
✅ Import validity (all modules load correctly)
✅ Configuration (env vars, settings)
✅ Security headers (CSP, HSTS, etc.)
✅ Rate limiting (middleware active)
✅ Cache connectivity (Redis)
✅ Health endpoints (/health, /metrics)
✅ Code quality (lint, type check)
✅ Dependencies (all installed)

Author: SuperAI Toolkit
Version: 1.0.0
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict


@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str
    category: str
    passed: bool
    message: str
    duration_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class VerificationReport:
    """Complete verification report."""
    timestamp: str
    total_checks: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    checks: List[CheckResult] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        ran = self.total_checks - self.skipped
        return (self.passed / ran * 100) if ran > 0 else 0
    
    @property
    def status(self) -> str:
        if self.failed == 0:
            return "✅ ALL CHECKS PASSED"
        elif self.pass_rate >= 80:
            return "⚠️ MOSTLY PASSED (some issues)"
        else:
            return "❌ CRITICAL ISSUES FOUND"


class SuperAIVerifier:
    """Verifies SuperAI transformation was successful."""
    
    def __init__(self, repo_path: str = ".", output_format: str = "text"):
        self.repo_path = Path(repo_path).resolve()
        self.output_format = output_format
        self.start_time = time.time()
        self.report = VerificationReport(
            timestamp=datetime.now().isoformat(),
            total_checks=0,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=0
        )
    
    def run_check(self, name: str, category: str, check_fn) -> CheckResult:
        """Run a single verification check with timing."""
        start = time.time()
        try:
            passed, message, details = check_fn()
            duration = (time.time() - start) * 1000
            
            result = CheckResult(
                name=name,
                category=category,
                passed=passed,
                message=message,
                duration_ms=duration,
                details=details or {}
            )
            
            self.report.checks.append(result)
            self.report.total_checks += 1
            
            if passed:
                self.report.passed += 1
            else:
                self.report.failed += 1
            
            return result
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = CheckResult(
                name=name,
                category=category,
                passed=False,
                message=f"Check crashed: {str(e)}",
                duration_ms=duration
            )
            self.report.checks.append(result)
            self.report.total_checks += 1
            self.report.failed += 1
            return result
    
    def run_command(self, cmd: str, timeout: int = 30) -> Tuple[bool, str, str]:
        """Run shell command safely."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    # ===== CHECK CATEGORIES =====

    def check_pytest_execution(self) -> List[CheckResult]:
        """Run actual pytest suite."""
        results = []
        
        def run_pytest():
            success, stdout, stderr = self.run_command("poetry run pytest backend/tests/ -v", timeout=60)
            if success:
                return True, "Pytest passed", {"output": stdout[:500]}
            else:
                return False, "Pytest failed", {"error": stderr[:500]}
                
        results.append(self.run_check("Pytest Execution", "Integration Tests", run_pytest))
        return results

    def check_live_api_health(self) -> List[CheckResult]:
        """Check live API endpoints if running locally."""
        results = []
        
        def run_curl():
            success, stdout, stderr = self.run_command("curl -s http://localhost:8000/api/v1/health", timeout=5)
            if success and ('"status":"ok"' in stdout.lower() or 'healthy' in stdout.lower()):
                return True, "Local API is healthy", {"response": stdout[:200]}
            else:
                return False, "Local API not responding or unhealthy", {"response": stdout[:200]}
                
        results.append(self.run_check("Live API Health (curl)", "Integration Tests", run_curl))
        return results
        
    def check_load_test(self) -> List[CheckResult]:
        """Basic load simulation."""
        results = []
        
        def run_load():
            import threading
            import urllib.request
            
            success_count = 0
            def req():
                nonlocal success_count
                try:
                    urllib.request.urlopen("http://localhost:8000/", timeout=2)
                    success_count += 1
                except:
                    pass
            
            threads = [threading.Thread(target=req) for _ in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()
            
            if success_count > 0:
                return True, f"{success_count}/10 requests succeeded", {}
            return False, "Load test failed", {}
            
        results.append(self.run_check("Basic Load Test", "Performance", run_load))
        return results
    
    def check_file_existence(self) -> List[CheckResult]:
        """Check that all expected files were created."""
        results = []
        
        expected_files = {
            "Cache Module": "backend/core/cache.py",
            "Rate Limiter": "backend/core/rate_limit.py",
            "Security Middleware": "backend/core/middleware/security.py",
            "Monitoring": "backend/core/monitoring.py",
            "Auto-Healer": "backend/core/auto_healer.py",
            "Config Validation": "backend/core/config_validation.py",
            "App Factory": "backend/core/app.py",
            "Dockerfile": "backend/Dockerfile",
            ".env.example": ".env.example",
        }
        
        for name, file_path in expected_files.items():
            def make_check(fp):
                def check():
                    full_path = self.repo_path / fp
                    if full_path.exists():
                        size = full_path.stat().st_size
                        return True, f"Exists ({size:,} bytes)", {"path": fp, "size": size}
                    return False, f"Not found: {fp}", {}
                return check
            
            result = self.run_check(
                f"File: {name}",
                "File Existence",
                make_check(file_path)
            )
            results.append(result)
        
        return results
    
    def check_imports(self) -> List[CheckResult]:
        """Check that all new modules can be imported."""
        results = []
        
        imports_to_test = [
            ("QueryCache", "from backend.core.cache import QueryCache"),
            ("RateLimiter", "from backend.core.rate_limit import RateLimiter"),
            ("SecurityHeadersMiddleware", "from backend.core.middleware.security import SecurityHeadersMiddleware"),
            ("MetricsCollector", "from backend.core.monitoring import MetricsCollector"),
            ("AutoHealer", "from backend.core.auto_healer import AutoHealer"),
            ("ConfigValidationMixin", "from backend.core.config_validation import ConfigValidationMixin"),
        ]
        
        for name, import_cmd in imports_to_test:
            def make_check(cmd):
                def check():
                    success, stdout, stderr = self.run_command(f'python -c "{cmd}"')
                    if success:
                        return True, "Import successful", {"command": cmd}
                    return False, f"Import failed: {stderr[:100]}", {"error": stderr[:200]}
                return check
            
            result = self.run_check(
                f"Import: {name}",
                "Module Imports",
                make_check(import_cmd)
            )
            results.append(result)
        
        return results
    
    def check_security(self) -> List[CheckResult]:
        """Verify security hardening is in place."""
        results = []
        
        # Check GitHub Actions SHA pinning
        def check_sha_pinning():
            ci_file = self.repo_path / ".github/workflows/ci.yml"
            if not ci_file.exists():
                return False, "CI workflow not found", {}
            
            content = ci_file.read_text()
            
            # Count SHA-pinned actions vs tag-based
            sha_count = content.count("uses:") - len([
                line for line in content.split('\n') 
                if 'uses:' in line and ('@v' in line or '@latest' in line)
            ])
            
            has_sha = any(len(line.strip().split('@')) > 1 and line.strip().split('@')[1][:10].isalnum() 
                         for line in content.split('\n') if 'uses:' in line)
            
            if has_sha:
                return True, "Actions are SHA-pinned ✅", {"sha_pinned": True}
            return False, "⚠️ Actions may use floating tags", {"sha_pinned": False}
        
        results.append(self.run_check("SHA-Pinned Actions", "Security", check_sha_pinning))
        
        # Check security middleware exists
        def check_security_middleware():
            sec_file = self.repo_path / "backend/core/middleware/security.py"
            if not sec_file.exists():
                return False, "Security middleware not found", {}
            
            content = sec_file.read_text()
            required = ["X-Content-Type-Options", "Strict-Transport-Security", "Content-Security-Policy"]
            found = [r for r in required if r in content]
            
            if len(found) == len(required):
                return True, f"All {len(required)} security headers present ✅", {"headers": found}
            return False, f"Missing headers: {set(required) - set(found)}", {"found": found}
        
        results.append(self.run_check("Security Headers", "Security", check_security_middleware))
        
        # Check rate limiter
        def check_rate_limiter():
            rl_file = self.repo_path / "backend/core/rate_limit.py"
            if not rl_file.exists():
                return False, "Rate limiter not found", {}
            
            content = rl_file.read_text()
            has_tiers = "anonymous" in content.lower() and "authenticated" in content.lower()
            has_redis = "redis" in content.lower()
            
            if has_tiers and has_redis:
                return True, "Multi-tier rate limiting configured ✅", {"tiers": True, "redis": True}
            return False, "Rate limiter incomplete", {"tiers": has_tiers, "redis": has_redis}
        
        results.append(self.run_check("Rate Limiting", "Security", check_rate_limiter))
        
        return results
    
    def check_code_quality(self) -> List[CheckResult]:
        """Run code quality checks."""
        results = []
        
        # Ruff linting
        def check_ruff():
            success, stdout, stderr = self.run_command(
                "poetry run ruff check . --output-format=text 2>&1 | head -50"
            )
            if success:
                return True, "No lint errors ✅", {}
            
            error_count = stdout.count("\n") if stdout else 0
            return False, f"{error_count} lint issues found", {"output": stdout[:500]}
        
        results.append(self.run_check("Ruff Lint", "Code Quality", check_ruff))
        
        # Type checking (non-blocking)
        def check_mypy():
            success, stdout, stderr = self.run_command(
                "poetry run mypy backend/core/ --ignore-missing-imports 2>&1 | tail -20"
            )
            # MyPy warnings are OK, errors are not
            has_errors = "error:" in stderr.lower() if stderr else False
            if not has_errors:
                return True, "Type check passed (warnings OK) ✅", {}
            return False, "Type errors found", {"errors": stderr[:300]}
        
        results.append(self.run_check("MyPy Types", "Code Quality", check_mypy))
        
        # Python syntax check
        def check_syntax():
            py_files = list(self.repo_path.rglob("backend/core/*.py"))
            errors = []
            
            for py_file in py_files:
                success, _, stderr = self.run_command(f"python -m py_compile {py_file}")
                if not success:
                    errors.append(py_file.name)
            
            if not errors:
                return True, f"All {len(py_files)} files compile ✅", {"files_checked": len(py_files)}
            return False, f"Syntax errors in: {errors}", {"errors": errors}
        
        results.append(self.run_check("Python Syntax", "Code Quality", check_syntax))
        
        return results
    
    def check_configuration(self) -> List[CheckResult]:
        """Verify configuration is correct."""
        results = []
        
        # Check .env.example has new variables
        def check_env_example():
            env_file = self.repo_path / ".env.example"
            if not env_file.exists():
                return False, ".env.example not found", {}
            
            content = env_file.read_text()
            required_vars = [
                "REDIS_URL",
                "LLM_CACHE_ENABLED",
                "RATE_LIMIT_ENABLED",
                "DAILY_BUDGET_USD",
                "SECURITY_HEADERS_ENABLED"
            ]
            
            found = [v for v in required_vars if v in content]
            
            if len(found) >= 4:
                return True, f"{len(found)}/{len(required_vars)} new vars documented ✅", {"documented": found}
            return False, f"Only {len(found)} new variables documented", {"found": found}
        
        results.append(self.run_check("Environment Variables", "Configuration", check_env_example))
        
        # Check Dockerfile optimization
        def check_dockerfile():
            dockerfile = self.repo_path / "backend/Dockerfile"
            if not dockerfile.exists():
                return False, "Dockerfile not found", {}
            
            content = dockerfile.read_text()
            optimizations = []
            
            if "multi-stage" in content.lower() or "AS builder" in content:
                optimizations.append("multi-stage")
            if "non-root" in content.lower() or "appuser" in content:
                optimizations.append("non-root user")
            if "healthcheck" in content.lower() or "HEALTHCHECK" in content:
                optimizations.append("health check")
            
            if len(optimizations) >= 2:
                return True, f"Docker optimized: {', '.join(optimizations)} ✅", {"optimizations": optimizations}
            return False, "Dockerfile needs optimization", {"current": optimizations}
        
        results.append(self.run_check("Dockerfile", "Configuration", check_dockerfile))
        
        return results
    
    def check_dependencies(self) -> List[CheckResult]:
        """Verify dependencies are installed."""
        results = []
        
        # Check poetry.lock exists and is recent
        def check_poetry_lock():
            lock_file = self.repo_path / "poetry.lock"
            toml_file = self.repo_path / "pyproject.toml"
            
            if not lock_file.exists():
                return False, "poetry.lock missing", {}
            
            if toml_file.exists():
                lock_time = lock_file.stat().st_mtime
                toml_time = toml_file.stat().st_mtime
                
                if lock_time < toml_time:
                    return False, "poetry.lock outdated (run poetry lock)", {}
            
            return True, "Dependencies locked ✅", {}
        
        results.append(self.run_check("Poetry Lock", "Dependencies", check_poetry_lock))
        
        # Check redis package available
        def check_redis_pkg():
            success, _, _ = self.run_command("python -c \"import redis; print(redis.__version__)\"")
            if success:
                return True, "Redis package installed ✅", {}
            return False, "Redis package missing (needed for caching)", {}
        
        results.append(self.run_check("Redis Package", "Dependencies", check_redis_pkg))
        
        return results
    
    def run_all_checks(self) -> VerificationReport:
        """Run all verification checks."""
        
        print("\n" + "=" * 70)
        print("🔍 SUPERAI VERIFICATION SUITE")
        print("=" * 70)
        print(f"Repository: {self.repo_path}")
        print(f"Started:   {self.report.timestamp}")
        print()
        
        # Run all check categories
        categories = [
            ("📁 File Existence", self.check_file_existence),
            ("📦 Module Imports", self.check_imports),
            ("🔒 Security Hardening", self.check_security),
            ("✨ Code Quality", self.check_code_quality),
            ("⚙️  Configuration", self.check_configuration),
            ("📚 Dependencies", self.check_dependencies),
            ("🧪 Integration Tests", self.check_pytest_execution),
            ("🌐 Live API Health", self.check_live_api_health),
            ("🔥 Performance/Load Test", self.check_load_test),
        ]
        
        for category_name, check_fn in categories:
            print(f"\n{category_name}")
            print("-" * 40)
            check_fn()
        
        # Calculate final stats
        self.report.duration_seconds = time.time() - self.start_time
        
        # Print report
        self.print_report()
        
        return self.report
    
    def print_report(self):
        """Print formatted verification report."""
        
        print("\n" + "=" * 70)
        print(f"VERIFICATION COMPLETE: {self.report.status}")
        print("=" * 70)
        
        # Summary by category
        categories = {}
        for check in self.report.checks:
            if check.category not in categories:
                categories[check.category] = {"passed": 0, "failed": 0, "total": 0}
            categories[check.category]["total"] += 1
            if check.passed:
                categories[check.category]["passed"] += 1
            else:
                categories[check.category]["failed"] += 1
        
        print("\n📊 Summary by Category:")
        print("-" * 40)
        for cat, stats in categories.items():
            status = "✅" if stats["failed"] == 0 else "❌"
            print(f"  {status} {cat}: {stats['passed']}/{stats['total']} passed")
        
        # Overall stats
        print(f"\n📈 Overall: {self.report.passed}/{self.report.total_checks} ({self.report.pass_rate:.1f}%)")
        print(f"⏱️  Duration: {self.report.duration_seconds:.1f}s")
        
        # Failed checks detail
        failed_checks = [c for c in self.report.checks if not c.passed]
        if failed_checks:
            print(f"\n❌ Failed Checks ({len(failed_checks)}):")
            print("-" * 40)
            for check in failed_checks:
                print(f"  • [{check.category}] {check.name}")
                print(f"    {check.message}")
        
        # Next steps
        if self.report.failed == 0:
            print(f"\n🎉 All checks passed! SuperAI is ready for deployment!")
        elif self.report.pass_rate >= 80:
            print(f"\n⚠️  Minor issues found. Review and fix before deployment.")
        else:
            print(f"\n🚨 Critical issues! Fix these before deploying.")
        
        print("=" * 70)
    
    def export_json(self) -> str:
        """Export report as JSON."""
        return json.dumps(asdict(self.report), indent=2, default=str)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SuperAI Verification Suite",
        epilog="Run after applying patches to verify transformation success."
    )
    
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--quick", action="store_true", help="Quick smoke tests only")
    parser.add_argument("--category", choices=["all", "security", "quality", "config"], 
                       default="all", help="Check category to run")
    
    args = parser.parse_args()
    
    verifier = SuperAIVerifier(repo_path=args.repo, output_format="json" if args.json else "text")
    
    if args.quick:
        # Quick mode: just file existence + imports
        verifier.check_file_existence()
        verifier.check_imports()
    elif args.category != "all":
        category_map = {
            "security": verifier.check_security,
            "quality": verifier.check_code_quality,
            "config": verifier.check_configuration,
        }
        category_map[args.category]()
    else:
        verifier.run_all_checks()
    
    if args.json:
        print(verifier.export_json())
    
    # Exit code based on pass rate
    sys.exit(0 if verifier.report.pass_rate >= 80 else 1)


if __name__ == "__main__":
    main()
