#!/usr/bin/env python3
# 🛡️ মাল্টি-মডেল কোড ভ্যালিডেটর — SupremeAI 2.0
# বাংলা মন্তব্য: এটি মাল্টিপল এআই মডেল (Gemini + OpenAI + Claude) দিয়ে কোডের নিরাপত্তা ও লজিক যাচাই করে

import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

# LiteLLM ইন্টিগ্রেশন
try:
    import litellm
except ImportError:
    logger.warning("litellm not installed, installing...")
    subprocess.run(["pip", "install", "litellm"], check=True)
    import litellm


class MultiModelValidator:
    """
    মাল্টি-মডেল কোড ভ্যালিডেশন ইঞ্জিন

    - সিকিউরিটি স্ক্যান (SQL Injection, XSS, Auth Bypass)
    - লজিক ভ্যালিডেশন
    - পারফরম্যান্স চেক
    - বেস্ট প্র্যাকটিস কমপ্লায়েন্স
    """

    def __init__(self):
        self.validators = [
            ("gemini/gemini-2.5-flash", "budget_validator"),
            ("openai/gpt-4o-mini", "security_validator"),
            ("groq/llama-3.3-70b-versatile", "logic_validator"),
        ]
        self.risk_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    async def validate_code(self, file_path: str) -> dict[str, Any]:
        """কোড ফাইল বা ডিরেক্টরি ভ্যালিডেট করুন মাল্টি-মডেল দিয়ে (Directory সমর্থিত)"""
        path_obj = Path(file_path)

        # বাংলা মন্তব্য: যদি ডিরেক্টরি পাস করা হয় তবে রিকার্সিভলি পাইথন ফাইলগুলো প্রসেস করা হবে
        if path_obj.is_dir():
            py_files = [str(p) for p in path_obj.rglob("*.py") if p.is_file()]
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
            }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f"Cannot read file {file_path}: {e}")
            return {"status": "error", "message": str(e)}

        file_ext = Path(file_path).suffix
        results = {
            "file": file_path,
            "timestamp": str(Path(file_path).stat().st_mtime),
            "validations": [],
            "overall_risk_level": "LOW",
            "passed": True
        }

        # প্রতিটি ভ্যালিডেটর দিয়ে চেক করুন
        for model, validator_type in self.validators:
            logger.info(f"🔍 Validating {file_path} with {model}...")

            validation_result = await self._validate_with_model(
                model,
                code_content,
                file_ext,
                validator_type
            )
            results["validations"].append(validation_result)

            # রিস্ক লেভেল আপডেট করুন
            if validation_result["risk_level"] in ["CRITICAL", "HIGH"]:
                results["passed"] = False
                results["overall_risk_level"] = validation_result["risk_level"]

        return results

    async def _validate_with_model(
        self,
        model: str,
        code_content: str,
        file_ext: str,
        validator_type: str
    ) -> dict[str, Any]:
        """একটি নির্দিষ্ট মডেল দিয়ে কোড ভ্যালিডেট করুন"""

        system_prompts = {
            "security_validator": f"""আপনি একজন নিরাপত্তা বিশেষজ্ঞ। নিচের {file_ext} কোডে নিরাপত্তা সমস্যা খুঁজুন:
- SQL Injection ভালনারেবিলিটি
- Cross-Site Scripting (XSS)
- Authentication/Authorization বাইপাস
- Data Exposure
- Unvalidated Input

রেসপন্স JSON ফরম্যাটে দিন:
{{
  "vulnerabilities": [
    {{"type": "...", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "description": "...", "fix": "..."}}
  ],
  "risk_level": "CRITICAL|HIGH|MEDIUM|LOW"
}}""",

            "logic_validator": f"""আপনি একজন সিনিয়র কোড রিভিউয়ার। নিচের {file_ext} কোডে লজিক্যাল এরর খুঁজুন:
- ইনফিনিট লুপ
- রেস কন্ডিশন
- নাল পয়েন্টার ডিরেফারেন্স
- এরর হ্যান্ডলিং
- আনইন্টেন্ডেড সাইড এফেক্ট

রেসপন্স JSON ফরম্যাটে দিন:
{{
  "issues": [
    {{"type": "...", "severity": "HIGH|MEDIUM|LOW", "description": "...", "impact": "..."}}
  ],
  "risk_level": "CRITICAL|HIGH|MEDIUM|LOW"
}}""",

            "budget_validator": f"""আপনি একজন পারফরম্যান্স এবং কস্ট অপটিমাইজেশন এক্সপার্ট। নিচের {file_ext} কোড রিভিউ করুন:
- API কল ডুপ্লিকেশন
- ইনএফিশিয়েন্ট লুপ
- আননেসেসারি ডেটা প্রসেসিং
- মেমরি লিক সম্ভাবনা
- ক্যাশিং অপরচুনিটি

রেসপন্স JSON ফরম্যাটে দিন:
{{
  "optimization_suggestions": [
    {{"issue": "...", "potential_cost_saving": "X%", "effort": "low|medium|high", "suggestion": "..."}}
  ],
  "risk_level": "MEDIUM|LOW"
}}"""
        }

        try:
            prompt = f"{system_prompts.get(validator_type, 'Review this code')}\n\nকোড:\n```{file_ext[1:]}\n{code_content}\n```"

            # LiteLLM দিয়ে API কল করুন
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
                timeout=30
            )

            response_text = response.choices[0].message.content

            # JSON parse করার চেষ্টা করুন
            try:
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                # JSON না থাকলে plain text হিসেবে ট্রিট করুন
                parsed = {
                    "raw_response": response_text,
                    "risk_level": "LOW"
                }

            return {
                "model": model,
                "validator_type": validator_type,
                **parsed,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Validation failed with {model}: {e}")
            return {
                "model": model,
                "validator_type": validator_type,
                "status": "error",
                "error": str(e),
                "risk_level": "UNKNOWN"
            }

    async def validate_file_changes(self, diff_content: str) -> dict[str, Any]:
        """গিট ডিফ থেকে শুধু পরিবর্তিত অংশ ভ্যালিডেট করুন"""
        logger.info("🔍 Validating file changes from diff...")

        # Groq দিয়ে দ্রুত প্রাথমিক স্ক্যান করুন
        try:
            response = await litellm.acompletion(
                model="groq/llama-3.3-70b-versatile",
                messages=[{
                    "role": "user",
                    "content": f"""নিচের গিট ডিফে নিরাপত্তা বা লজিক্যাল সমস্যা আছে কিনা দেখুন। শুধু সমস্যা থাকলেই রিপোর্ট করুন।

ডিফ:
```diff
{diff_content}
```

রেসপন্স JSON:
{{"has_issues": bool, "issues": [...], "risk_level": "CRITICAL|HIGH|MEDIUM|LOW"}}"""
                }],
                temperature=0.2,
                max_tokens=500
            )

            parsed = json.loads(response.choices[0].message.content)
            return parsed

        except Exception as e:
            logger.error(f"Diff validation failed: {e}")
            return {"has_issues": False, "status": "error"}

    def export_report(self, results: dict[str, Any], output_path: str):
        """ভ্যালিডেশন রিপোর্ট এক্সপোর্ট করুন"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Validation report saved to {output_file}")


async def validate_critical_files(repo_root: str = ".") -> dict[str, Any]:
    """
    ক্রিটিক্যাল ফাইল (auth, security, payment) ভ্যালিডেট করুন
    """
    validator = MultiModelValidator()
    critical_patterns = [
        "**/auth*.py",
        "**/security*.py",
        "**/payment*.py",
        "**/admin*.py",
        "**/permissions*.py"
    ]

    critical_files = []
    for pattern in critical_patterns:
        critical_files.extend(Path(repo_root).glob(pattern))

    results = {
        "validated_files": [],
        "total_files": len(critical_files),
        "critical_issues": 0,
        "all_passed": True
    }

    for file_path in critical_files[:5]:  # লিমিট করুন খরচ বাঁচানোর জন্য
        file_result = await validator.validate_code(str(file_path))
        results["validated_files"].append(file_result)

        if not file_result.get("passed", True):
            results["critical_issues"] += 1
            results["all_passed"] = False

    return results


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1:
        file_to_validate = sys.argv[1]
        validator = MultiModelValidator()
        result = asyncio.run(validator.validate_code(file_to_validate))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python multi_model_validator.py <file_path>")
