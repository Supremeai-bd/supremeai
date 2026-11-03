# backend/tests/core/test_playground_sandboxing.py
"""#2707 (Gap-H) — Real-time Playground Sandboxing পরীক্ষা।

বাংলা মন্তব্য: PlaygroundRunner (N-parallel candidate → আসল execution →
deterministic score → winner), AdvancedReasoningEngine-এর executable
alternatives, এবং dispatcher-এর real sandbox verification — তিনটিরই
regression lock। টেস্ট executor হিসেবে আসল python subprocess ব্যবহার
(docker-নির্ভরতা ছাড়া সত্যিকারের execution)।
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from core.intelligence.playground_runner import (
    PlaygroundCandidate,
    PlaygroundRunner,
)


def _real_python_executor(code: str) -> object:
    """বাংলা মন্তব্য: আসল python subprocess — docker ছাড়াই সত্যিকারের execution।"""

    async def _run() -> dict:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=10)
        return {
            "success": proc.returncode == 0,
            "output": out.decode(errors="replace"),
            "error": err.decode(errors="replace"),
        }

    return _run()


# ═══════════════════════════════════════════════════════════════════════
# ১. PlaygroundRunner — generate_test_select API
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_test_select_picks_winner_by_real_execution():
    """২+ candidate parallel-এ চলে; আসল output-score-ই winner নির্ধারণ করে।"""
    winner_code = (
        "import json\n"
        "conclusion = 'solid conclusion'\n"
        "confidence = 0.95\n"
        "ok = bool(conclusion) and confidence > 0.3\n"
        'print(json.dumps({"ok": True, "confidence": 0.95}))\n'
    )
    loser_code = "import json\nprint(json.dumps({'ok': False, 'confidence': 0.1}))\n"

    runner = PlaygroundRunner(executor=_real_python_executor)
    candidates = [
        PlaygroundCandidate(label="loser", code=loser_code),
        PlaygroundCandidate(label="winner", code=winner_code),
    ]
    result = await runner.generate_test_select(candidates, task="verify repair")

    assert result["winner"] == "winner"
    assert result["verified_in_sandbox"] is True
    assert result["winner_score"] > 50.0
    # উভয় candidate-ই প্রকৃত parallel রানে বিচারিত হয়েছে
    assert len(result["results"]) == 2
    labels = {r["label"] for r in result["results"]}
    assert labels == {"winner", "loser"}


@pytest.mark.asyncio
async def test_generate_test_select_no_candidates_honest():
    runner = PlaygroundRunner(executor=_real_python_executor)
    result = await runner.generate_test_select([], task="t")
    assert result["winner"] is None
    assert result["verified_in_sandbox"] is False
    assert result["reason"] == "no_candidates"


@pytest.mark.asyncio
async def test_generate_test_select_honest_when_sandbox_unavailable():
    """সব candidate-ব্যর্থতায় সৎ False + কারণ — কোনো ভান-winner নয়।"""

    async def broken_executor(code: str) -> dict:
        return {"success": False, "error": "sandbox unavailable: no docker daemon"}

    runner = PlaygroundRunner(executor=broken_executor)
    result = await runner.generate_test_select(
        [PlaygroundCandidate(label="a", code="print(1)")], task="t"
    )
    assert result["winner"] is None
    assert result["verified_in_sandbox"] is False
    assert result["reason"] == "sandbox_unavailable"


@pytest.mark.asyncio
async def test_generate_test_select_isolates_candidate_crash():
    """একটি candidate crash করলেও বাকিরা বিচারিত হয় (parallel isolation)।"""

    async def executor(code: str) -> dict:
        if "BOOM" in code:
            raise RuntimeError("candidate exploded")
        return {"success": True, "output": '{"ok": true, "confidence": 0.8}'}

    runner = PlaygroundRunner(executor=executor)
    result = await runner.generate_test_select(
        [
            PlaygroundCandidate(label="boom", code="BOOM"),
            PlaygroundCandidate(label="fine", code="print('fine')"),
        ],
        task="t",
    )
    assert result["winner"] == "fine"
    assert result["verified_in_sandbox"] is True
    # boom-candidate সৎভাবে failed — তবু বাকি candidate বিচারিত (isolation)
    boom = [r for r in result["results"] if r["label"] == "boom"][0]
    assert boom["executed"] is False and boom["score"] == 0.0
    assert "exploded" in boom["error"]


@pytest.mark.asyncio
async def test_candidate_timeout_is_bounded():
    """ধীর candidate per_candidate_timeout-এ সীমাবদ্ধ — লুপ আটকে থাকে না।"""

    async def slow_executor(code: str) -> dict:
        await asyncio.sleep(5.0)
        return {"success": True, "output": ""}

    runner = PlaygroundRunner(executor=slow_executor, per_candidate_timeout=0.2)
    result = await runner.generate_test_select(
        [PlaygroundCandidate(label="slow", code="print(1)")], task="t"
    )
    assert result["winner"] is None
    assert result["verified_in_sandbox"] is False
    assert "timed out" in result["results"][0]["error"]


# ═══════════════════════════════════════════════════════════════════════
# ২. AdvancedReasoningEngine — executable alternatives
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_executable_alternatives_produces_runnable_code():
    """প্রতিটি alternative এখন executable candidate — কোড প্রকৃত চলে ও verdict দেয়।"""
    from core.advanced_reasoning import AdvancedReasoningEngine

    engine = AdvancedReasoningEngine()
    candidates = await engine.generate_executable_alternatives(
        "Design a token bucket rate limiter", context={}
    )
    assert len(candidates) >= 2, "at least 2 alternative candidates required (#2707)"

    runner = PlaygroundRunner(executor=_real_python_executor)
    result = await runner.generate_test_select(
        [PlaygroundCandidate(label=c["label"], code=c["code"]) for c in candidates],
        task="rate limiter design",
    )
    # প্রতিটি candidate-কোডই valid-executable — winner আসল রান থেকে
    assert len(result["results"]) == len(candidates)
    assert all(r["executed"] for r in result["results"])
    assert result["winner"] is not None
    assert result["verified_in_sandbox"] is True


@pytest.mark.asyncio
async def test_candidate_code_contract_json_verdict():
    """Candidate-চুক্তি: কোড stdout-এ JSON verdict প্রিন্ট করে।"""
    from core.advanced_reasoning import AdvancedReasoningEngine

    engine = AdvancedReasoningEngine()
    candidates = await engine.generate_executable_alternatives("Evaluate caching tradeoffs")
    assert candidates
    code = candidates[0]["code"]
    # কোডটি নিজেই নির্ধারিত চুক্তি মেনে চলে (in-process compile + verdict shape)
    compile(code, "<candidate>", "exec")  # valid Python
    assert '"ok"' in code and '"confidence"' in code


# ═══════════════════════════════════════════════════════════════════════
# ৩. Dispatcher — verified_in_sandbox এখন প্রকৃত স্যান্ডবক্স-ফল থেকে
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_dispatcher_verified_in_sandbox_from_playground(monkeypatch):
    """patch_candidate.verified_in_sandbox প্রকৃত playground-ফল বহন করে।"""
    from core.intelligence import playground_runner as pr_mod
    from core.orchestration.cognitive_pipeline_dispatcher import (
        CognitiveIntent,
        get_master_orchestrator,
    )

    fake_result = {
        "task": "q",
        "winner": "deductive",
        "verified_in_sandbox": True,
        "winner_score": 97.5,
        "results": [{"label": "deductive", "executed": True, "ok": True, "score": 97.5}],
        "reason": "ok",
    }
    fake_pg = type("FakePG", (), {"generate_test_select": AsyncMock(return_value=fake_result)})()
    monkeypatch.setattr(pr_mod, "PlaygroundRunner", lambda per_candidate_timeout=10.0: fake_pg)

    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(
        CognitiveIntent.REPAIR,
        {"error": "TimeoutError", "target_file": "adapters/task_executor.py"},
    )
    assert result.status == "SUCCESS"
    assert result.artifacts["patch_candidate"]["verified_in_sandbox"] is True
    pg = result.artifacts["playground_verification"]
    assert pg["status"] == "executed"
    assert pg["winner"] == "deductive"
    assert pg["candidates_tested"] >= 1


@pytest.mark.asyncio
async def test_dispatcher_honest_when_playground_unavailable(monkeypatch):
    """স্যান্ডবক্স unavailable → verified_in_sandbox সৎ False, পাইপলাইন অক্ষুণ্ণ।"""
    from core.intelligence import playground_runner as pr_mod
    from core.orchestration.cognitive_pipeline_dispatcher import (
        CognitiveIntent,
        get_master_orchestrator,
    )

    fake_result = {
        "task": "q",
        "winner": None,
        "verified_in_sandbox": False,
        "results": [],
        "reason": "sandbox_unavailable",
    }
    fake_pg = type("FakePG", (), {"generate_test_select": AsyncMock(return_value=fake_result)})()
    monkeypatch.setattr(pr_mod, "PlaygroundRunner", lambda per_candidate_timeout=10.0: fake_pg)

    orchestrator = get_master_orchestrator()
    result = await orchestrator.dispatch(
        CognitiveIntent.REPAIR,
        {"error": "TimeoutError", "target_file": "adapters/task_executor.py"},
    )
    assert result.status == "SUCCESS"  # graceful degradation — pipeline বাঁচে
    assert result.artifacts["patch_candidate"]["verified_in_sandbox"] is False
    assert result.artifacts["playground_verification"]["reason"] == "sandbox_unavailable"
