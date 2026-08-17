"""Standalone smoke test for the SupremeAI IDE Trio Pipeline adapters.

Run from the repo root:
    python tests/test_ide_trio_smoke.py
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

# Ensure Unicode output works even on cp1252 Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load_adapters():
    """Load trio_adapters.py directly via importlib, bypassing the heavy
    `agents/__init__.py` (which pulls in loguru / litellm / pandas chains)."""
    candidates = [
        Path(r"F:\supremeai backup\.kilo\worktrees\dirt-octopus\backend\agents\ide\trio_adapters.py"),
        Path(r"F:\supremeai backup\backend\agents\ide\trio_adapters.py"),
    ]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        raise RuntimeError("trio_adapters.py not found")

    spec = importlib.util.spec_from_file_location("trio_adapters_standalone", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["trio_adapters_standalone"] = mod
    spec.loader.exec_module(mod)
    return mod


ASYNCIO_RUN = False


async def main() -> None:
    results = []
    adapters = _load_adapters()
    KiloReviewer = adapters.KiloReviewer
    ClineChecker = adapters.ClineChecker
    TrioAgentResult = adapters.TrioAgentResult

    # ── Test 1: Basic review (KiloReviewer._basic_review) ─────────────
    print("\n=== Test 1: KiloReviewer basic review ===")
    try:
        reviewer = KiloReviewer()
        sample = (
            "def api():\n"
            "    secret = 'abc123'  # bad\n"
            "    print('debug')\n"
            "    eval(input())\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            "        pass\n"
            "    # TODO fix\n"
        )
        result = await reviewer.run(sample, language="python")
        assert isinstance(result, TrioAgentResult)
        assert result.role == "reviewer"
        assert result.agent == "kilo"
        types = {i["type"] for i in result.issues}
        print(f"  issues found: {[i['type'] for i in result.issues]}")
        assert "hardcoded_secret" in types, "should flag hardcoded secret"
        assert "eval_usage" in types, "should flag eval()"
        assert "bare_except" in types, "should flag bare except"
        assert "debug_statement" in types, "should flag print()"
        print("  ✅ PASSED")
    except Exception as exc:
        print(f"  ❌ FAILED: {exc}")
        results.append("KiloReviewer.basic_review")

    # ── Test 2: ClineChecker local production checks ───────────────────
    print("\n=== Test 2: ClineChecker local checks ===")
    try:
        checker = ClineChecker()
        good_code = (
            "def add(a: int, b: int) -> int:\n"
            "    try:\n"
            "        return a + b\n"
            "    except TypeError as e:\n"
            "        return 0\n"
        )
        local = await checker._run_local_checks(good_code, "python", "")
        result_map = {k: v["passed"] for k, v in local.items()}
        print(f"  checks: {result_map}")
        assert local["no_debug_statements"]["passed"] is True
        assert local["error_handling"]["passed"] is True
        assert local["type_hints"]["passed"] is True
        assert local["no_hardcoded_secrets"]["passed"] is True
        print("  ✅ PASSED")
    except Exception as exc:
        print(f"  ❌ FAILED: {exc}")
        results.append("ClineChecker.local_checks")

    # ── Test 3: TrioAgentResult serialization ──
    print("\n=== Test 3: TrioAgentResult.to_dict ===")
    try:
        r = TrioAgentResult(role="writer", agent="gemini", output="code", confidence=0.9)
        d = r.to_dict()
        assert d["role"] == "writer" and d["agent"] == "gemini"
        assert d["timestamp"], "timestamp should be auto-filled"
        assert isinstance(d["issues"], list)
        print("  ✅ PASSED")
    except Exception as exc:
        print(f"  ❌ FAILED: {exc}")
        results.append("TrioAgentResult.to_dict")

    # ── Test 4: Pipeline result shape exercised through reviewer → checker
    print("\n=== Test 4: end-to-end reviewer + checker chain ===")
    try:
        reviewer = KiloReviewer()
        checker = ClineChecker()
        code = (
            "def handler(req_id: int) -> str:\n"
            "    try:\n"
            "        return f'ok:{req_id}'\n"
            "    except Exception:\n"
            "        return 'err'\n"
        )
        rv = await reviewer.run(code, language="python", filepath="app.py")
        ck = await checker.run(code, language="python", filepath="app.py", reviewer_result=rv)
        assert rv.agent == "kilo" and ck.agent == "cline"
        assert ck.metadata.get("ready_for_production") is not None
        print(f"  reviewer issues: {len(rv.issues)}, checker ready: {ck.metadata['ready_for_production']}")
        print("  ✅ PASSED")
    except Exception as exc:
        print(f"  ❌ FAILED: {exc}")
        results.append("e2e_chain")

    # ── Summary ──
    print("\n=======================")
    if results:
        print(f"❌ {len(results)} test(s) FAILED: {results}")
        sys.exit(1)
    print("✅ ALL SMOKE TESTS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())