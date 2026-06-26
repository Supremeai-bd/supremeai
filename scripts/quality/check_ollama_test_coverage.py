#!/usr/bin/env python3
"""
Ollama Test-Coverage Auto-Generator — বাস্তবায়ন পরীক্ষা
========================================================
এই স্ক্রিপ্ট紀হ internship actual忈tatc Ollama (qwen2.5:0.5b / llama3.2:latest)
দিয়ে backend-er Bash a上_file generate test files try করবে।

সｔｅｐｓ:
  1. Pick a real backend source file (concrete Python module)
  2. Build a structured prompt for test-generation
  3. Call Ollama /api/generate directamente (bypass ModelRouter)
  4. Save the generated test file
  5. Run pytest on that file with pytest-cov
  6. Show coverage result
  7. সিদ্ধান্ত: Ollama এই job টি করতে পারে কিনা?

ব্যবহার:
  python scripts/check_ollama_test_coverage.py [source_file_path] [ollama_model]

Example:
  python scripts/check_ollama_test_coverage.py backend/core/circuit_breaker.py qwen2.5:0.5b
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── কনফিগ ────────────────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
VENV_PYTHON = str(Path(__file__).resolve().parents[2] / "backend" / ".venv" / "Scripts" / "python.exe")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def bprint(msg: str, color: str = "") -> None:
    print(f"{color}{msg}{RESET}")


# ── প্রম্পট বিল্ডার ───────────────────────────────────────────────────────────
def build_generation_prompt(source_code: str, file_path: str, stack: str = "python") -> str:
    return f"""You are a senior Python QA engineer. Generate ONLY the test file. No markdown, no explanation.

REQUIREMENTS:
- Use pytest + pytest-asyncio.
- Mock all external dependencies (network, redis, file I/O).
- Test every public method in every class.
- Include edge cases: empty inputs, None values, boundary values, concurrent calls.
- Use descriptive names: test_<method>_<scenario>.
- Coverage target: 90%+.

SOURCE FILE: {file_path}

SOURCE CODE:
```python
{source_code[:8000]}
```

Generate the complete test file now. Do NOT add explanations or markdown fences."""


# ── OLLAMA কল (সিঙ্ক,流式) ──────────────────────────────────────────────────
def call_ollama(model: str, prompt: str, temperature: float = 0.2) -> str:
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 4096,
        },
    }
    with httpx.Client(timeout=600.0) as client:
        resp = client.post(url, json=payload, timeout=600.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")


# ── প্রম্পট সেভ ও রান টেস্ট ──────────────────────────────────────────────────
def run_pytest_on_file(test_file_path: str) -> dict[str, Any]:
    cmd = [
        VENV_PYTHON,
        "-m",
        "pytest",
        test_file_path,
        "-v",
        "--tb=short",
        f"--cov={test_file_path.replace(os.sep, '.').replace('_test.py','').replace('test_','')}",
        "--cov-report=term-missing",
        "--cov-report=xml:" + str(Path(test_file_path).parent / "coverage_generated.xml"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "passed": proc.returncode == 0,
        }
    except Exception as exc:
        return {"returncode": -1, "passed": False, "error": str(exc)}


def parse_coverage_from_xml(xml_path: str) -> tuple[float, int, int]:
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        line_rate = float(root.attrib.get("line-rate", 0))
        lines_covered = int(root.attrib.get("lines-covered", 0))
        lines_valid = int(root.attrib.get("lines-valid", 0))
        pct = round(line_rate * 100, 1)
        return pct, lines_covered, lines_valid
    except Exception:
        return 0.0, 0, 0


# ── মেইন ─────────────────────────────────────────────────────────────────────
async def main_async() -> int:
    parser = argparse.ArgumentParser(
        description="Ollama দিয়ে test coverage જનറেশন চেক করে"
    )
    parser.add_argument("source_file", nargs="?", default="backend/core/circuit_breaker.py")
    parser.add_argument("model", nargs="?", default="llama3.2:latest")
    parser.add_argument("--dry-run", action="store_true", help="Only generate, not run tests")
    args = parser.parse_args()

    source_path = Path(args.source_file)
    if not source_path.exists():
        bprint(f"❌ Source file not found: {source_path}", RED)
        return 1

    source_code = source_path.read_text(encoding="utf-8")
    module_name = source_path.stem.replace("_", "")
    test_file_name = f"test_{source_path.stem}_ollama_gen.py"
    test_file_path = source_path.parent / test_file_name

    bprint("=" * 60, CYAN)
    bprint("  Ollama Test-Coverage Generator (বাংলা explain)", CYAN)
    bprint("=" * 60, CYAN)
    bprint(f"সোর্স ফাইল : {source_path}", CYAN)
    bprint(f"মডেল       : {args.model}", CYAN)
    bprint(f"টেস্ট ফাইল  : {test_file_path}", CYAN)
    bprint(f"Dry-run     : {args.dry_run}", CYAN)
    bprint("", CYAN)

    # ── Step 1: Server health ──────────────────────────────────────────────
    bprint("🔍 [ধাপ 1] Ollama সার্ভার চেক...", CYAN)
    try:
        health = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        if health.status_code == 200:
            bprint("  ✅ সার্ভার চলছে", GREEN)
        else:
            bprint(f"  ❌ সার্ভার status={health.status_code}", RED)
            return 1
    except Exception as exc:
        bprint(f"  ❌ সার্ভারে কানেক্ট hologram না: {exc}", RED)
        bprint("  🔧 `ollama serve` চালু করুন", YELLOW)
        return 1

    # ── Step 2: Generation ────────────────────────────────────────────────
    bprint("\n📝 [ধাপ 2] Ollama দিয়ে টেস্ট জেনারেট করা হচ্ছে...", CYAN)
    prompt = build_generation_prompt(source_code, str(source_path))
    try:
        generated_code = call_ollama(args.model, prompt)
        if not generated_code or not generated_code.strip():
            bprint("  ❌ Ollama খালি রেসপন্স দিল।", RED)
            return 1
        bprint(f"  ✅ জেনারেশন সম্পূর্ণ! ({len(generated_code)} অক্ষর)", GREEN)
    except httpx.HTTPStatusError as exc:
        bprint(f"  ❌ HTTP এরর: {exc.response.status_code}", RED)
        return 1
    except httpx.TimeoutException:
        bprint("  ❌ request টাইমআউট (120s)", RED)
        return 1
    except Exception as exc:
        bprint(f"  ❌ এরর: {exc}", RED)
        return 1

    # Clean markdown fences if any
    lines = generated_code.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    cleaned_code = "\n".join(lines).strip()

    # ── Step 3: Save ──────────────────────────────────────────────────────
    bprint(f"\n💾 [ধাপ 3] টেস্ট ফাইল সেভ হচ্ছে: {test_file_name}", CYAN)
    test_file_path.write_text(cleaned_code, encoding="utf-8")
    bprint(f"  ✅ সেভ সম্পূর্ণ!", GREEN)

    # Print a preview
    preview = cleaned_code[:600].replace("\n", "\n     ")
    bprint(f"\n📄 Preview:\n     {preview}...", YELLOW)

    if args.dry_run:
        bprint("\n🏁 Dry-run — test skipped.", YELLOW)
        return 0

    # ── Step 4: Run tests ─────────────────────────────────────────────────
    bprint(f"\n🧪 [ধাপ 4] pytest চালানো হচ্ছে...", CYAN)
    run_result = run_pytest_on_file(str(test_file_path))

    bprint(f"  Return code : {run_result['returncode']}")
    bprint(f"  Passed       : {run_result.get('passed')}", GREEN if run_result.get("passed") else RED)

    if run_result.get("stderr"):
        err_preview = run_result["stderr"][:800]
        bprint(f"  Stderr preview:\n     {err_preview}", YELLOW)

    # ── Step 5: Coverage ──────────────────────────────────────────────────
    cov_xml = test_file_path.parent / "coverage_generated.xml"
    if cov_xml.exists() and run_result.get("passed"):
        pct, covered, valid = parse_coverage_from_xml(str(cov_xml))
        bprint(f"\n📊 [ধাপ 5] Coverage রিপোর্ট:", CYAN)
        bprint(f"  Coverage       : {pct}%", GREEN if pct >= 70 else YELLOW)
        bprint(f"  Lines covered  : {covered} / {valid}")
        if pct >= 70:
            bprint("\n🎉 cukup সুন্দর! Ollama এই job টি করতে পারে।", GREEN)
            return 0
        elif pct >= 40:
            bprint("\n⚠️  coverage মাঝারি — কিছু lacking আছে, কিন্তু কাজ করছে।", YELLOW)
            return 0
        else:
            bprint("\n⚠️  coverage কম আছে — টেস্ট meaningful但可能 নয়।", YELLOW)
            return 1
    else:
        if not run_result.get("passed"):
            bprint("\n⚠️  টেস্ট ফলন Honors দিল, combine করবে না। served track করে দেখুন।", RED)
        if not cov_xml.exists():
            bprint("\n⚠️  coverage.xml generate হল ná, প্যাচেজ Χ مشکل হossible।", RED)
        return 1


def main() -> int:
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        bprint("\n⏹ interrupted.", YELLOW)
        return 130


if __name__ == "__main__":
    sys.exit(main())
