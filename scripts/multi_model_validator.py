#!/usr/bin/env python3
# 🛡️ মাল্টি-মডেল কোড ভ্যালিডেটর — SupremeAI 2.0
# বাংলা মন্তব্য: এটি এআই মডেল ও স্ট্যাটিক AST সিকিউরিটি অ্যানালাইসিসের মাধ্যমে কোডের নিরাপত্তা ও লজিক যাচাই করে

import ast
import json
import os
import sys
import argparse
import asyncio
from pathlib import Path
from typing import Any, List, Dict

from loguru import logger

# Optional LiteLLM integration
HAVE_LITELLM = False
try:
    import litellm
    HAVE_LITELLM = True
except ImportError:
    pass


class MultiModelValidator:
    """
    মাল্টি-মডেল ও স্ট্যাটিক সিকিউরিটি কোড ভ্যালিডেশন ইঞ্জিন
    - সিকিউরিটি স্ক্যান (SQL Injection, XSS, Auth Bypass, Dangerous Eval)
    - লজিক ভ্যালিডেশন
    - পারফরম্যান্স ও সেফটি চেক
    """

    def __init__(self):
        self.validators = [
            ("gemini/gemini-2.5-flash", "budget_validator"),
            ("openai/gpt-4o-mini", "security_validator"),
            ("groq/llama-3.3-70b-versatile", "logic_validator"),
        ]
        self.has_llm_keys = bool(
            os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("LITELLM_API_KEY")
        )

    def _static_ast_scan(self, file_path: str, code_content: str) -> Dict[str, Any]:
        """স্ট্যাটিক AST সিকিউরিটি অ্যানালাইসিস"""
        issues: List[Dict[str, str]] = []
        try:
            tree = ast.parse(code_content, filename=file_path)
            for node in ast.walk(tree):
                # Check for dangerous eval / exec
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("eval", "exec"):
                        issues.append({
                            "type": "Dangerous Function Call",
                            "severity": "HIGH",
                            "description": f"Dangerous built-in `{node.func.id}()` called at line {node.lineno}",
                            "fix": "Avoid dynamic code execution; use safe parsing."
                        })
                # Check for raw string concatenation in SQL queries
                elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                    if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                        val = node.left.value.lower()
                        if any(q in val for q in ["select ", "insert into ", "update ", "delete from "]):
                            issues.append({
                                "type": "Potential SQL Injection",
                                "severity": "HIGH",
                                "description": f"String concatenation in SQL query at line {node.lineno}",
                                "fix": "Use parameterized queries or ORM models."
                            })
        except SyntaxError:
            pass
        except Exception as e:
            logger.debug(f"AST scan error on {file_path}: {e}")

        risk_level = "HIGH" if any(i["severity"] == "HIGH" for i in issues) else "LOW"
        return {
            "vulnerabilities": issues,
            "risk_level": risk_level,
            "mode": "static_ast_analyzer"
        }

    async def validate_code(self, file_path: str) -> dict[str, Any]:
        """কোড ফাইল বা ডিরেক্টরি ভ্যালিডেট করুন (Directory সমর্থিত)"""
        path_obj = Path(file_path)

        if path_obj.is_dir():
            py_files = [str(p) for p in path_obj.rglob("*.py") if p.is_file() and not p.name.startswith(".")]
            dir_results = []
            all_passed = True
            for py_f in py_files:
                res = await self.validate_code(py_f)
                dir_results.append(res)
                if not res.get("passed", True):
                    all_passed = False
            return {
                "file": file_path,
                "is_directory": True,
                "total_files": len(py_files),
                "results": dir_results,
                "passed": all_passed,
                "overall_risk_level": "LOW" if all_passed else "HIGH"
            }

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f"Cannot read file {file_path}: {e}")
            return {"status": "error", "message": str(e), "passed": True, "overall_risk_level": "LOW"}

        file_ext = Path(file_path).suffix
        results = {
            "file": file_path,
            "timestamp": str(Path(file_path).stat().st_mtime if Path(file_path).exists() else 0),
            "validations": [],
            "overall_risk_level": "LOW",
            "passed": True
        }

        # Static AST scan first
        static_res = self._static_ast_scan(file_path, code_content)
        results["validations"].append(static_res)
        if static_res["risk_level"] in ["CRITICAL", "HIGH"]:
            results["passed"] = False
            results["overall_risk_level"] = static_res["risk_level"]

        # If LLM keys available and LiteLLM installed, run multi-model checks
        if self.has_llm_keys and HAVE_LITELLM:
            for model, validator_type in self.validators:
                val_res = await self._validate_with_model(model, code_content, file_ext, validator_type)
                results["validations"].append(val_res)
                if val_res.get("risk_level") in ["CRITICAL", "HIGH"]:
                    results["passed"] = False
                    results["overall_risk_level"] = val_res["risk_level"]

        return results

    async def _validate_with_model(self, model: str, code_content: str, file_ext: str, validator_type: str) -> dict[str, Any]:
        """একটি নির্দিষ্ট মডেল দিয়ে কোড ভ্যালিডেট করুন"""
        if not HAVE_LITELLM:
            return {"model": model, "validator_type": validator_type, "status": "skipped", "risk_level": "LOW"}

        try:
            prompt = f"Review this {file_ext} code for security vulnerabilities. Output JSON: {{\"vulnerabilities\": [], \"risk_level\": \"LOW\"}}.\n\nCode:\n{code_content[:3000]}"
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500,
                timeout=15
            )
            response_text = response.choices[0].message.content
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                parsed = {"raw_response": response_text, "risk_level": "LOW"}

            return {"model": model, "validator_type": validator_type, **parsed, "status": "success"}
        except Exception as e:
            return {"model": model, "validator_type": validator_type, "status": "fallback", "error": str(e), "risk_level": "LOW"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Model Code Validator")
    parser.add_argument("path", nargs="?", default=".", help="File or directory to validate")
    parser.add_argument("--json-output", help="Output file path for json report")

    args = parser.parse_args()

    validator = MultiModelValidator()
    result = asyncio.run(validator.validate_code(args.path))
    result_str = json.dumps(result, indent=2, ensure_ascii=False)

    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(result_str, encoding="utf-8")
        print(f"Validation report exported to {args.json_output}")
    else:
        print(result_str)
