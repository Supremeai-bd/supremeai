"""core.agent_chat_loop — Autonomous ReAct chat engine (M09 P-C).

বাংলা: ধাপ ১ (governed tool surface — ``core.agent_tool_policy``,
``core.agent_tool_specs``, ``/api/agent/tools`` + ``/api/agent/tool-calls`` এবং
গেটওয়ে প্রক্সি) ইতিমধ্যে main-এ আছে। এই মডিউল তার উপরে দাঁড়িয়ে চ্যাট-পথের
অসম্পূর্ণ অর্ধেকটি সম্পূর্ণ করে: একটি বহু-পদক্ষেপ ReAct লুপ যা ইউজারের কথাকে
টুল-সিদ্ধান্তে রূপ দেয়, গভর্নড গেট দিয়ে সত্যিই নির্বাহ করে এবং
পর্যবেক্ষণের ভিত্তিতে চূড়ান্ত উত্তর টোকেন-স্ট্রিম করে।

স্তর-চুক্তি (কে কী করে — DRY, কোনো গেট ডুপ্লিকেট নয়):

* **টেন্যান্ট-দৃশ্যমানতা**: ``core.agent_tool_policy.tenant_tool_view`` —
  flag → allowlist → policy। flag-off মানে সাদামাটা চ্যাট মোড (সৎ, কোনো
  সিদ্ধান্ত-থিয়েটার নয়);
* **সিদ্ধান্ত**: ``ReasoningOrchestrator.decide`` — LLM ReAct JSON +
  deterministic fallback, ``source``-এ সৎ উৎস;
* **নির্বাহ**: ``core.tool_loop.execute_tool_decision`` — flag → রেজিস্ট্রি →
  MCP পলিসি; এই তিন গেট এখানে কখনো কপি হয় না;
* **সংশ্লেষণ**: ``LLMGateway.acompletion`` (stream) — বাধ্যতামূলক
  ``InferenceContext`` attribution (scripts/ci/check_gateway_context.py চুক্তি)।

ইভেন্ট-চুক্তি (``run_stream`` যা yield করে):

* ``{"type": "meta", ...}`` — লুপ-শুরুর প্রসঙ্গ (toolsEnabled, availableTools, maxSteps);
* ``{"type": "thought", ...}`` — সিদ্ধান্ত-পর্বের চিন্তা + সৎ source;
* ``{"type": "tool_call", ...}`` — মডেল টুল বেছে নিয়েছে;
* ``{"type": "tool_result", ...}`` — গেট-পরবর্তী সত্য ফল (executed/status/observation/reason);
* ``{"type": "content_delta", ...}`` — চূড়ান্ত উত্তরের টোকেন-খণ্ড;
* ``{"type": "final", ...}`` — পূর্ণ উত্তর + পদক্ষেপ-হিসাব (boundedStop সহ);
* ``{"type": "error", ...}`` — সৎ ব্যর্থতা (কখনো ভান নয়)।

নিরাপত্তা: ``max_steps`` বাউন্ডেড (ডিফল্ট ৫, সর্বোচ্চ ৮) — অসীম ReAct
পুনরাবৃত্তি কাঠামোগতভাবে অসম্ভব। টেন্যান্ট-allowlist-এর বাইরের টুল এখানেও
নির্বাহ হয় না (``tenant_blocked`` — রাউটারের 403-চুক্তির লুপ-রূপ);
policy_blocked/ব্যর্থতা পর্যবেক্ষণ হয়ে মডেলের কাছে ফেরত যায় — নীরবে হজম নয়।
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from core.agent_tool_policy import tenant_tool_view
from core.monitoring.logging_config import logger

#: লুপ-বাউন্ড: ডিফল্ট পদক্ষেপ-সীমা ও কাঠামোগত সর্বোচ্চ।
DEFAULT_MAX_STEPS = 5
HARD_MAX_STEPS = 8

#: প্রতি-পদক্ষেপ পর্যবেক্ষণ-দৈর্ঘ্য সীমা — প্রম্পট-বিস্ফোরণ ঠেকাতে।
MAX_OBSERVATION_CHARS = 4000

#: সংশ্লেষণ-প্রম্পটের স্থির অংশ — সততা ও ভাষা-মিররিং এখানেই শেখানো হয়।
_SYNTHESIS_PREAMBLE = (
    "You are SupremeAI, the user's personal executive agent.\n"
    "Answer the user's latest request using ONLY the conversation and the REAL "
    "tool observations below.\n"
    "Rules:\n"
    "1. Ground every factual claim in the observations. If a tool was refused, "
    "blocked or failed, or data is missing, say so honestly — never invent results.\n"
    "2. Reply in the same language the user wrote in (বাংলা প্রশ্ন → খাঁটি বাংলা "
    "উত্তর; English question → professional English).\n"
    "3. Be concise and actionable.\n"
)

_BUDGET_NOTE = (
    "NOTE: the tool-execution budget was exhausted before the model finished "
    "working. Answer from the observations already collected and state plainly "
    "what could not be checked.\n"
)


def _truncate(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + f" …[truncated {len(cleaned) - limit} chars]"


class AgentChatLoop:
    """এক চ্যাট-টার্নের বহু-পদক্ষেপ ReAct অর্কেস্ট্রেটর।

    ``decider`` ও ``llm`` ইনজেক্টযোগ্য — টেস্ট অফলাইনে ফেক দেয়; প্রোডাকশনে
    ডিফল্ট lazy-লোড হয় (ReasoningOrchestrator ও LLMGateway)।
    """

    def __init__(
        self,
        decider: Any | None = None,
        llm: Any | None = None,
    ) -> None:
        self._decider = decider
        self._llm = llm

    # ── collaborators (lazy — টেস্ট ফেক ইনজেক্ট করতে পারে) ────────────────────

    async def _decide(
        self,
        task: str,
        context: dict[str, Any] | None,
        tools: list[str],
    ) -> dict[str, Any]:
        if self._decider is None:
            from core.brain.reasoning_orchestrator import ReasoningOrchestrator

            self._decider = ReasoningOrchestrator.get_instance()
        return await self._decider.decide(task, context=context, tools=tools)

    def _gateway(self) -> Any:
        if self._llm is None:
            from core.llm.llm_gateway import get_llm_gateway

            self._llm = get_llm_gateway()
        return self._llm

    async def _execute(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """গভর্নড নির্বাহ — গেটগুলো core.tool_loop-এ, এখানে শুধু আহ্বান।"""
        from core.tool_loop import execute_tool_decision

        return await execute_tool_decision(
            {"tool": tool, "args": args or {}, "source": "agent_chat_loop"}
        )

    # ── main entry ───────────────────────────────────────────────────────────

    async def run_stream(
        self,
        messages: list[dict[str, Any]],
        tenant_id: str = "*",
        model: str = "auto",
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> AsyncIterator[dict[str, Any]]:
        """Full ReAct turn as an event stream (see module docstring contract)."""
        tenant = (tenant_id or "").strip() or "*"
        steps_limit = max(1, min(int(max_steps or DEFAULT_MAX_STEPS), HARD_MAX_STEPS))

        convo = [
            {"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")}
            for m in (messages or [])
            if isinstance(m, dict)
        ]
        if not convo:
            yield {"type": "error", "message": "messages must contain at least one message"}
            yield {"type": "final", "answer": "", "stepsUsed": 0, "toolCalls": [], "boundedStop": False}
            return
        task = next(
            (m["content"] for m in reversed(convo) if m["role"] == "user"),
            convo[-1]["content"],
        )

        view = tenant_tool_view(tenant)
        available = view.available_names() if view.enabled else []
        meta: dict[str, Any] = {
            "type": "meta",
            "tenantId": tenant,
            "toolsEnabled": bool(view.enabled),
            "allowlistSource": view.allowlist_source,
            "availableTools": available,
            "maxSteps": steps_limit,
        }
        if view.allowlist_error:
            meta["allowlistError"] = view.allowlist_error
        yield meta

        history: list[dict[str, str]] = list(convo)
        tool_records: list[dict[str, Any]] = []
        bounded_stop = False

        for step in range(1, steps_limit + 1):
            if not available:
                break  # সাদামাটা চ্যাট মোড — সৎ, সিদ্ধান্ত-থিয়েটার নয়

            decision = await self._decide(
                task, context={"history": history[-8:]}, tools=available
            )
            chosen = str((decision or {}).get("tool") or "done")
            yield {
                "type": "thought",
                "step": step,
                "thought": str((decision or {}).get("thought") or ""),
                "reasoning": str((decision or {}).get("reasoning") or ""),
                "source": str((decision or {}).get("source") or "unknown"),
            }
            if chosen == "done":
                break

            args = (decision or {}).get("args") or {}
            if chosen not in available:
                # টেন্যান্ট-সীমা লুপ-স্তরেও কঠোর — নির্বাহ হবে না; সত্য
                # প্রত্যাখ্যান পর্যবেক্ষণ হয়ে মডেলের কাছে ফেরত যাবে।
                # দুই রকম সৎ প্রত্যাখ্যান:
                #   * declared কিন্তু policy-unavailable → "policy_blocked"
                #     (ম্যানিফেস্টের নিজস্ব reason — অনুমোদন লাগবে);
                #   * টেন্যান্টের জন্য ডিক্লেয়ার্ডই নয় → "tenant_blocked"।
                declared = {t["function"]["name"]: t for t in view.tools}
                if chosen in declared:
                    agent_meta = declared[chosen].get("agent") or {}
                    status = "policy_blocked"
                    risk = agent_meta.get("risk")
                    reason = (
                        f"tool '{chosen}' refused: "
                        f"{agent_meta.get('reason') or 'policy requires human approval'}"
                    )
                else:
                    status = "tenant_blocked"
                    risk = None
                    reason = (
                        f"tool '{chosen}' refused: not declared for this tenant "
                        f"(allowlist source={view.allowlist_source}) — choose another tool or 'done'"
                    )
                logger.warning(f"[agent_chat_loop] {status} tool={chosen} tenant={tenant}")
                yield {
                    "type": "tool_result",
                    "step": step,
                    "tool": chosen,
                    "executed": False,
                    "status": status,
                    "risk": risk,
                    "reason": reason,
                }
                tool_records.append({"step": step, "tool": chosen, "status": status, "executed": False})
                history.append({"role": "assistant", "content": f"[tool:{chosen} blocked] {reason}"})
                continue

            yield {"type": "tool_call", "step": step, "tool": chosen, "args": args}
            result = await self._execute(chosen, args)
            executed = bool(result.get("executed"))
            observation = str(result.get("observation")) if executed else str(
                result.get("reason") or result.get("error") or "tool did not execute"
            )
            event: dict[str, Any] = {
                "type": "tool_result",
                "step": step,
                "tool": chosen,
                "executed": executed,
                "status": result.get("status"),
                "risk": result.get("risk"),
            }
            if executed:
                event["observation"] = _truncate(observation)
            else:
                event["reason"] = _truncate(observation, 800)
            yield event
            tool_records.append(
                {"step": step, "tool": chosen, "status": result.get("status"), "executed": executed}
            )
            history.append(
                {"role": "assistant", "content": f"[tool:{chosen} status={result.get('status')}] {_truncate(observation)}"}
            )
        else:
            bounded_stop = True  # বাজেট শেষ — সৎভাবে স্বীকার করা হবে

        # ── চূড়ান্ত সংশ্লেষণ (সবসময় — টুল থাকুক বা না থাকুক) ─────────────────
        answer_parts: list[str] = []
        failure: str | None = None
        try:
            stream = await self._synthesize_stream(history, tenant, model, bounded_stop)
            if isinstance(stream, dict):
                # Tier-0 deterministic bypass ইত্যাদি — non-streamed dict ফল।
                text = str(stream.get("text") or "")
                if text:
                    answer_parts.append(text)
                    yield {"type": "content_delta", "delta": text}
            else:
                async for chunk in stream:
                    delta = str(chunk) if not isinstance(chunk, str) else chunk
                    if delta:
                        answer_parts.append(delta)
                        yield {"type": "content_delta", "delta": delta}
        except Exception as exc:
            logger.error(f"[agent_chat_loop] synthesis failed: {type(exc).__name__}: {exc}")
            failure = f"final synthesis failed ({type(exc).__name__})"
            yield {"type": "error", "message": failure}

        if failure is not None or not "".join(answer_parts).strip():
            # সৎ দ্বিতীয় প্রচেষ্টা: non-streaming এক-কল ফলব্যাক।
            try:
                res = await self._synthesize_once(history, tenant, model, bounded_stop)
                text = str((res or {}).get("text") or "")
                if text:
                    answer_parts = [text]
                    yield {"type": "content_delta", "delta": text}
                    failure = None
            except Exception as exc:
                logger.error(f"[agent_chat_loop] synthesis fallback failed: {type(exc).__name__}")
                if failure is None:
                    failure = f"final synthesis failed ({type(exc).__name__})"
                    yield {"type": "error", "message": failure}

        answer = "".join(answer_parts)
        yield {
            "type": "final",
            "answer": answer,
            "stepsUsed": len(tool_records),
            "toolCalls": tool_records,
            "boundedStop": bounded_stop,
            "toolsEnabled": bool(view.enabled),
        }

    async def run(
        self,
        messages: list[dict[str, Any]],
        tenant_id: str = "*",
        model: str = "auto",
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> dict[str, Any]:
        """Non-streaming convenience: এক টার্ন চালিয়ে পূর্ণ ফল ফেরত দেয়।"""
        answer_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        errors: list[str] = []
        meta: dict[str, Any] = {}
        steps_used = 0
        bounded_stop = False
        async for event in self.run_stream(
            messages=messages, tenant_id=tenant_id, model=model, max_steps=max_steps
        ):
            etype = event.get("type")
            if etype == "meta":
                meta = event
            elif etype == "tool_call":
                tool_calls.append(event)
            elif etype == "content_delta":
                answer_parts.append(str(event.get("delta") or ""))
            elif etype == "error":
                errors.append(str(event.get("message") or ""))
            elif etype == "final":
                steps_used = int(event.get("stepsUsed") or 0)
                bounded_stop = bool(event.get("boundedStop"))
        return {
            "answer": "".join(answer_parts),
            "toolCalls": tool_calls,
            "meta": meta,
            "stepsUsed": steps_used,
            "boundedStop": bounded_stop,
            "errors": errors,
        }

    # ── synthesis internals ──────────────────────────────────────────────────

    def _synthesis_prompt(
        self,
        history: list[dict[str, str]],
        bounded_stop: bool,
    ) -> str:
        convo_lines = [f"{m['role']}: {m['content']}" for m in history]
        parts = [
            _SYNTHESIS_PREAMBLE,
            "Conversation:\n" + "\n".join(convo_lines) + "\n",
        ]
        if bounded_stop:
            parts.append(_BUDGET_NOTE)
        return "\n".join(parts)

    async def _synthesize_stream(
        self,
        history: list[dict[str, str]],
        tenant_id: str,
        model: str,
        bounded_stop: bool,
    ) -> Any:
        from core.llm.llm_gateway.context import InferenceContext

        model_arg = None if model in (None, "", "auto") else model
        return await self._gateway().acompletion(
            prompt=self._synthesis_prompt(history, bounded_stop),
            context=InferenceContext(
                tenant_id=tenant_id or "anonymous",
                task_type="chat",
                stream=True,
            ),
            model=model_arg,
        )

    async def _synthesize_once(
        self,
        history: list[dict[str, str]],
        tenant_id: str,
        model: str,
        bounded_stop: bool,
    ) -> dict[str, Any]:
        from core.llm.llm_gateway.context import InferenceContext

        model_arg = None if model in (None, "", "auto") else model
        res = await self._gateway().acompletion(
            prompt=self._synthesis_prompt(history, bounded_stop),
            context=InferenceContext(
                tenant_id=tenant_id or "anonymous",
                task_type="chat",
                stream=False,
            ),
            model=model_arg,
        )
        return res if isinstance(res, dict) else {}


def agent_chat_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    """HTTP payload for ``POST /api/agent/chat`` — the run() dict, JSON-safe."""
    payload = dict(result)
    meta = payload.get("meta")
    if isinstance(meta, dict):
        payload["meta"] = json.loads(json.dumps(meta, ensure_ascii=False, default=str))
    return payload
