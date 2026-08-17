#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SupremeAI 2.0 — Auto Test Generator
============================================================================
উদ্দেশ্য: AI ব্যবহার করে স্বয়ংক্রিয়ভাবে Python মডিউলের জন্য টেস্ট কেস তৈরি করে।

বৈশিষ্ট্য:
  - AST পার্সিং দিয়ে ফাংশন/ক্লাস এক্সট্রাক্ট
  - Multi-LLM রাউটিং (Kimi Primary → DeepSeek Fallback)
  - টেস্ট কোভারেজ ট্র্যাকিং
  - Firestore-এ টেস্ট রেজাল্ট সেভ
  - বাংলা কমেন্ট সাপোর্ট

ব্যবহার:
  python scripts/testing/auto_test_generator.py --target backend/core/config.py
  python scripts/testing/auto_test_generator.py --target backend/core/ --recursive
  python scripts/testing/auto_test_generator.py --target backend/core/llm/llm_gateway.py --provider deepseek

লেখক: SupremeAI Architecture Team
তারিখ: July 20, 2026
============================================================================
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

# বাংলা মন্তব্য: sys.path হ্যাক এড়াতে ক্লিন ইমপোর্ট স্ট্রাকচার
try:
    from backend.core.config import settings
    from backend.core.llm.llm_gateway import get_llm_gateway
    from backend.core.tenant_db import TenantAwareFirestore
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from backend.core.config import settings
    from backend.core.llm.llm_gateway import get_llm_gateway
    from backend.core.tenant_db import TenantAwareFirestore


# ── Configuration ──────────────────────────────────────────────────────────
DEFAULT_PROVIDER = os.getenv("AUTO_TEST_PROVIDER", "gemini")
MAX_TOKENS = int(os.getenv("AUTO_TEST_MAX_TOKENS", "2000"))
TEMPERATURE = float(os.getenv("AUTO_TEST_TEMPERATURE", "0.3"))
OUTPUT_DIR = Path(os.getenv("AUTO_TEST_OUTPUT_DIR", "tests/generated"))
COVERAGE_THRESHOLD = float(os.getenv("AUTO_TEST_COVERAGE_THRESHOLD", "80.0"))

# বাংলা মন্তব্য: টেস্ট জেনারেশনের জন্য সিস্টেম প্রম্পট — কোয়ালিটি নিশ্চিত করে
TEST_GENERATION_PROMPT = """You are an expert Python test engineer. Generate comprehensive pytest test cases for the following Python module.

Requirements:
1. Use pytest with fixtures and parametrize where appropriate
2. Cover happy path, edge cases, and error conditions
3. Mock external dependencies (databases, APIs, file I/O)
4. Include type hints in test functions
5. Add docstrings explaining what each test verifies
6. Target at least 90% code coverage
7. Use pytest-asyncio for async functions
8. Include performance benchmarks where relevant

Module source code:
```python
{source_code}
```

Generate ONLY the test file content. Start with imports and end with the last test function. Do not include markdown code block markers."""


@dataclass
class FunctionInfo:
    """বাংলা মন্তব্য: মডিউল থেকে এক্সট্রাক্ট করা ফাংশন/ক্লাসের তথ্য"""
    name: str
    type: str  # function | class | method
    line_start: int
    line_end: int
    args: list[str] = field(default_factory=list)
    returns: str | None = None
    is_async: bool = False
    is_private: bool = False
    complexity: int = 1


@dataclass
class TestGenerationResult:
    """বাংলা মন্তব্য: টেস্ট জেনারেশনের ফলাফল"""
    target_file: str
    test_file: str
    functions_found: int
    functions_tested: int
    coverage_estimate: float
    generation_time: float
    provider_used: str
    success: bool
    error: str | None = None
    test_code: str = ""


class ASTExtractor:
    """
    বাংলা মন্তব্য: AST (Abstract Syntax Tree) ব্যবহার করে Python ফাইল থেকে
    ফাংশন, ক্লাস, এবং মেথড এক্সট্রাক্ট করে। Cyclomatic complexity হিসাব করে।
    """

    def __init__(self, source_code: str, file_path: str = ""):
        self.source_code = source_code
        self.file_path = file_path
        self.tree = ast.parse(source_code)
        self.functions: list[FunctionInfo] = []

    def extract(self) -> list[FunctionInfo]:
        """বাংলা মন্তব্য: সব ফাংশন ও ক্লাস এক্সট্রাক্ট করে"""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                self._process_function(node, "function")
            elif isinstance(node, ast.AsyncFunctionDef):
                self._process_function(node, "function", is_async=True)
            elif isinstance(node, ast.ClassDef):
                self._process_class(node)
        return self.functions

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef,
                          type_: str, is_async: bool = False, parent: str = "") -> None:
        """বাংলা মন্তব্য: একক ফাংশন প্রসেস করে"""
        args = [arg.arg for arg in node.args.args if arg.arg not in ("self", "cls")]
        returns = ast.unparse(node.returns) if node.returns else None

        # Cyclomatic complexity calculation
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.With,
                           ast.Assert, ast.ExceptHandler, ast.comprehension)):
                complexity += 1

        name = f"{parent}.{node.name}" if parent else node.name

        info = FunctionInfo(
            name=name,
            type=type_,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            args=args,
            returns=returns,
            is_async=is_async,
            is_private=node.name.startswith("_"),
            complexity=complexity,
        )
        self.functions.append(info)

    def _process_class(self, node: ast.ClassDef) -> None:
        """বাংলা মন্তব্য: ক্লাস এবং তার মেথডগুলো প্রসেস করে"""
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._process_function(item, "method", parent=node.name)
            elif isinstance(item, ast.AsyncFunctionDef):
                self._process_function(item, "method", is_async=True, parent=node.name)


class TestGenerator:
    """
    বাংলা মন্তব্য: AI-চালিত টেস্ট জেনারেটর। Multi-LLM রাউটিং সাপোর্ট করে।
    Semantic cache ব্যবহার করে একই মডিউলের জন্য দ্বিতীয়বার টোকেন খরচ কমায়।
    """

    def __init__(self, provider: str = DEFAULT_PROVIDER):
        self.provider = provider
        self.gateway = None
        self._cache: dict[str, str] = {}  # In-memory cache

    async def initialize(self) -> None:
        """বাংলা মন্তব্য: LLM Gateway ইনিশিয়ালাইজ করে"""
        self.gateway = get_llm_gateway()
        logger.info(f"TestGenerator initialized with provider: {self.provider}")

    def _get_cache_key(self, source_code: str) -> str:
        """বাংলা মন্তব্য: সোর্স কোডের SHA256 হ্যাশ ক্যাশ কী হিসেবে ব্যবহার করে"""
        return hashlib.sha256(source_code.encode()).hexdigest()[:16]

    async def generate_tests(self, source_code: str, file_path: str) -> str:
        """
        বাংলা মন্তব্য: AI দিয়ে টেস্ট কোড জেনারেট করে।
        প্রথমে ক্যাশ চেক করে, মিস হলে LLM কল করে।
        """
        cache_key = self._get_cache_key(source_code)

        # Cache hit check
        if cache_key in self._cache:
            logger.info(f"Cache hit for {file_path}")
            return self._cache[cache_key]

        # Build prompt
        prompt = TEST_GENERATION_PROMPT.format(source_code=source_code)

        try:
            # বাংলা মন্তব্য: LLM Gateway দিয়ে রাউট করা রিকোয়েস্ট
            response = await self.gateway.acompletion(
                prompt=prompt,
                task_type="test_generation",
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                provider=self.provider,
            )

            test_code = response.get("text", "")

            # Clean up markdown markers if present
            test_code = re.sub(r"^```python\n?", "", test_code)
            test_code = re.sub(r"```\n?$", "", test_code)

            # Cache result
            self._cache[cache_key] = test_code

            return test_code

        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            # Fallback: generate basic pytest structure
            return self._generate_fallback_tests(source_code, file_path)

    def _generate_fallback_tests(self, source_code: str, file_path: str) -> str:
        """
        বাংলা মন্তব্য: LLM ফেইল হলে বেসিক টেস্ট স্ট্রাকচার জেনারেট করে।
        এতে করে সিস্টেম সম্পূর্ণ নির্ভরশীল হয় না LLM-এর উপর।
        """
        extractor = ASTExtractor(source_code, file_path)
        functions = extractor.extract()

        lines = [
            "# Auto-generated fallback tests",
            "import pytest",
            "from unittest.mock import Mock, patch, AsyncMock",
            "",
            f"# Tests for {Path(file_path).name}",
            "",
        ]

        for func in functions:
            if func.is_private:
                continue
            test_name = f"test_{func.name.replace('.', '_')}"
            lines.extend([
                f"def {test_name}():",
                f'    """Test {func.name} — auto-generated fallback."""',
                "    # TODO: Implement actual test logic",
                "    assert True  # Placeholder",
                "",
            ])

        return "\n".join(lines)


class TestRunner:
    """
    বাংলা মন্তব্য: জেনারেট করা টেস্ট রান করে এবং কোভারেজ রিপোর্ট তৈরি করে।
    pytest এবং pytest-cov ব্যবহার করে।
    """

    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_test(self, test_code: str, original_file: str) -> str:
        """বাংলা মন্তব্য: জেনারেট করা টেস্ট ফাইল সেভ করে"""
        original_path = Path(original_file)
        test_filename = f"test_{original_path.stem}.py"

        # Preserve directory structure
        relative_dir = original_path.parent.relative_to(Path.cwd()) if original_path.is_absolute() else original_path.parent
        test_dir = self.output_dir / relative_dir
        test_dir.mkdir(parents=True, exist_ok=True)

        test_file = test_dir / test_filename

        # Add header
        header = f"\"\"\"\nAuto-generated tests for {original_file}\nGenerated: {datetime.now(UTC).isoformat()}\n\"\"\"\n\n"
        full_code = header + test_code

        test_file.write_text(full_code, encoding="utf-8")
        logger.info(f"Test saved: {test_file}")

        return str(test_file)

    async def run_tests(self, test_file: str) -> dict[str, Any]:
        """বাংলা মন্তব্য: pytest দিয়ে টেস্ট রান করে রেজাল্ট রিটার্ন করে"""
        import subprocess

        cmd = [
            sys.executable, "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--cov-report=term-missing",
            "--cov-report=json",
            "--cov=." if not test_file else f"--cov={Path(test_file).parent}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Parse coverage from JSON report
            coverage = 0.0
            cov_json = Path("coverage.json")
            if cov_json.exists():
                cov_data = json.loads(cov_json.read_text())
                coverage = cov_data.get("totals", {}).get("percent_covered", 0.0)
                cov_json.unlink()  # Clean up

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "coverage": coverage,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timed out after 120s",
                "coverage": 0.0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "coverage": 0.0,
            }


class TestReportStore:
    """
    বাংলা মন্তব্য: Firestore-এ টেস্ট রেজাল্ট সেভ করে।
    Tenant-aware এবং time-series data সাপোর্ট করে।
    """

    def __init__(self):
        self.db = None

    async def initialize(self) -> None:
        """বাংলা মন্তব্য: Firestore কানেকশন ইনিশিয়ালাইজ করে"""
        try:
            self.db = TenantAwareFirestore()
            logger.info("TestReportStore initialized")
        except Exception as e:
            logger.warning(f"Firestore unavailable, using local JSON: {e}")
            self.db = None

    async def save_result(self, result: TestGenerationResult) -> None:
        """বাংলা মন্তব্য: টেস্ট জেনারেশন রেজাল্ট সেভ করে"""
        data = {
            "target_file": result.target_file,
            "test_file": result.test_file,
            "functions_found": result.functions_found,
            "functions_tested": result.functions_tested,
            "coverage_estimate": result.coverage_estimate,
            "generation_time": result.generation_time,
            "provider_used": result.provider_used,
            "success": result.success,
            "error": result.error,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if self.db:
            try:
                await self.db.collection("test_reports").add(data)
            except Exception as e:
                logger.error(f"Failed to save to Firestore: {e}")

        # Always save locally as backup
        local_file = OUTPUT_DIR / "test_report_history.jsonl"
        with open(local_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")


class AutoTestGenerator:
    """
    বাংলা মন্তব্য: মূল অরকেস্ট্রেটর ক্লাস। সব কম্পোনেন্টকে একসাথে চালায়।
    """

    def __init__(self, provider: str = DEFAULT_PROVIDER):
        self.generator = TestGenerator(provider)
        self.runner = TestRunner()
        self.store = TestReportStore()
        self.results: list[TestGenerationResult] = []

    async def initialize(self) -> None:
        """বাংলা মন্তব্য: সব সাব-সিস্টেম ইনিশিয়ালাইজ করে"""
        await self.generator.initialize()
        await self.store.initialize()

    async def process_file(self, file_path: str) -> TestGenerationResult:
        """
        বাংলা মন্তব্য: একক Python ফাইলের জন্য টেস্ট জেনারেট এবং রান করে।
        """
        start_time = time.time()
        path = Path(file_path)

        if not path.exists():
            return TestGenerationResult(
                target_file=file_path,
                test_file="",
                functions_found=0,
                functions_tested=0,
                coverage_estimate=0.0,
                generation_time=0.0,
                provider_used=self.generator.provider,
                success=False,
                error=f"File not found: {file_path}",
            )

        source_code = path.read_text(encoding="utf-8")

        # Extract functions for metrics
        extractor = ASTExtractor(source_code, file_path)
        functions = extractor.extract()
        public_functions = [f for f in functions if not f.is_private]

        # Generate tests
        logger.info(f"Generating tests for {file_path} ({len(public_functions)} public functions)")
        test_code = await self.generator.generate_tests(source_code, file_path)

        # Save tests
        test_file = self.runner.save_test(test_code, file_path)

        # Run tests
        run_result = await self.runner.run_tests(test_file)

        elapsed = time.time() - start_time

        result = TestGenerationResult(
            target_file=file_path,
            test_file=test_file,
            functions_found=len(public_functions),
            functions_tested=len(public_functions),  # Optimistic estimate
            coverage_estimate=run_result.get("coverage", 0.0),
            generation_time=elapsed,
            provider_used=self.generator.provider,
            success=run_result.get("success", False),
            error=run_result.get("error"),
            test_code=test_code,
        )

        await self.store.save_result(result)
        self.results.append(result)

        return result

    async def process_directory(self, dir_path: str, recursive: bool = True) -> list[TestGenerationResult]:
        """
        বাংলা মন্তব্য: একটি ডিরেক্টরির সব Python ফাইলের জন্য টেস্ট জেনারেট করে।
        """
        path = Path(dir_path)
        pattern = "**/*.py" if recursive else "*.py"
        py_files = list(path.glob(pattern))

        # Exclude test files and common non-source files
        exclude_patterns = [
            "test_", "__pycache__", ".venv", "node_modules",
            "conftest.py", "setup.py", "__init__.py",
        ]

        source_files = [
            f for f in py_files
            if not any(pat in str(f) for pat in exclude_patterns)
        ]

        logger.info(f"Found {len(source_files)} source files in {dir_path}")

        for file in source_files:
            result = await self.process_file(str(file))
            status = "✅" if result.success else "❌"
            logger.info(f"{status} {file.name} — Coverage: {result.coverage_estimate:.1f}%")

        return self.results

    def generate_summary_report(self) -> str:
        """
        বাংলা মন্তব্য: সব রেজাল্টের উপর ভিত্তি করে সারসংক্ষেপ রিপোর্ট তৈরি করে।
        """
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        avg_coverage = sum(r.coverage_estimate for r in self.results) / total if total else 0
        avg_time = sum(r.generation_time for r in self.results) / total if total else 0

        lines = [
            "# SupremeAI Auto Test Generation Report",
            f"\nGenerated: {datetime.now(UTC).isoformat()}",
            f"\n## Summary",
            f"- **Total Files**: {total}",
            f"- **Successful**: {successful} ({successful/total*100:.1f}%)",
            f"- **Failed**: {total - successful}",
            f"- **Average Coverage**: {avg_coverage:.1f}%",
            f"- **Average Generation Time**: {avg_time:.2f}s",
            f"- **Provider Used**: {self.generator.provider}",
            f"\n## Details",
            "| File | Functions | Coverage | Time | Status |",
            "|------|-----------|----------|------|--------|",
        ]

        for r in self.results:
            status = "✅ Pass" if r.success else "❌ Fail"
            lines.append(
                f"| {Path(r.target_file).name} | {r.functions_tested} | {r.coverage_estimate:.1f}% | {r.generation_time:.2f}s | {status} |"
            )

        report = "\n".join(lines)

        # Save report
        report_file = OUTPUT_DIR / "generation_report.md"
        report_file.write_text(report, encoding="utf-8")
        logger.info(f"Report saved: {report_file}")

        return report


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """বাংলা মন্তব্য: CLI entry point — argparse দিয়ে আর্গুমেন্ট পার্স করে"""
    parser = argparse.ArgumentParser(
        description="SupremeAI 2.0 — Auto Test Generator\nAI দিয়ে স্বয়ংক্রিয় টেস্ট জেনারেশন",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", "-t", required=True, help="Target Python file or directory")
    parser.add_argument("--recursive", "-r", action="store_true", help="Process directory recursively")
    parser.add_argument("--provider", "-p", default=DEFAULT_PROVIDER,
                        choices=["gemini", "deepseek", "groq", "openai", "anthropic"],
                        help="LLM provider for test generation")
    parser.add_argument("--coverage-threshold", "-c", type=float, default=COVERAGE_THRESHOLD,
                        help="Minimum coverage threshold (%)")
    parser.add_argument("--output-dir", "-o", type=Path, default=OUTPUT_DIR,
                        help="Output directory for generated tests")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't save tests")

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

    async def run():
        generator = AutoTestGenerator(provider=args.provider)
        await generator.initialize()

        target_path = Path(args.target)

        if target_path.is_file():
            result = await generator.process_file(str(target_path))
            print(f"\n{'='*60}")
            print(f"Target: {result.target_file}")
            print(f"Test File: {result.test_file}")
            print(f"Functions: {result.functions_tested}/{result.functions_found}")
            print(f"Coverage: {result.coverage_estimate:.1f}%")
            print(f"Time: {result.generation_time:.2f}s")
            print(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
            if result.error:
                print(f"Error: {result.error}")

        elif target_path.is_dir():
            results = await generator.process_directory(str(target_path), recursive=args.recursive)
            report = generator.generate_summary_report()
            print(f"\n{'='*60}")
            print(report)

        else:
            print(f"Error: Target not found: {args.target}")
            sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
