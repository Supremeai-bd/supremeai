from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api.dependencies import get_tenant_db
from api.deps import get_current_user_token
from context_engine import ContextBlock, ContextEngine, Section
from context_engine.budget import context_engine_enabled
from core.cache.multi_layer_cache import multi_layer_cache
from core.i18n.language_directive import (
    build_language_directive,
    language_loop_enabled,
    resolve_preferred_language,
)
from core.llm.llm_gateway import llm_gateway
from core.llm.llm_gateway.context import InferenceContext
from core.logging_config import logger
from core.orchestration.conversation_orchestrator import (
    ConversationCommand,
    get_conversation_orchestrator,
)
from core.resilience.circuit_breaker import RedisCircuitBreaker


# ROOT-CAUSE FIX (#2726): derive task_type from prompt complexity instead of
# hardcoding "chat". The routing layer (routing.py:161-165) checks task_type
# keywords to pick the model chain: "reasoning"/"math"/"code" -> hard chain
# (llama-3.3-70b + gemini-2.5-pro), "agent"/"analysis" -> medium chain,
# everything else -> easy chain (flash + instant). With task_type="chat"
# hardcoded, even "design a distributed rate limiter" went to the easy chain.
def _derive_task_type(prompt: str) -> str:
    """বাংলা: প্রম্পট বিশ্লেষণ করে task_type নির্ধারণ — routing layer সঠিক
    model chain বাছাই করতে পারে। Hardcoded 'chat' এর বদলে dynamic classification।"""
    p = (prompt or "").lower()
    # Hard: reasoning + math + code patterns
    hard_keywords = (
        "reasoning",
        "math",
        "code",
        "coding",
        "algorithm",
        "design",
        "architect",
        "implement",
        "debug",
        "refactor",
        "optimize",
        "analyze",
        "synthesize",
        "compare",
        "evaluate",
        "step by step",
    )
    if any(kw in p for kw in hard_keywords):
        return "reasoning"
    # Medium: agent + analysis patterns
    medium_keywords = (
        "agent",
        "analysis",
        "summarize",
        "explain",
        "describe",
        "research",
        "investigate",
        "review",
    )
    if any(kw in p for kw in medium_keywords):
        return "analysis"
    return "chat"


# Global circuit breaker instance
main_llm_circuit = RedisCircuitBreaker(
    name="llm_gateway", failure_threshold=3, recovery_timeout=30.0
)

router = APIRouter(
    prefix="/api/chat", tags=["AI-Orchestration"], dependencies=[Depends(get_current_user_token)]
)


# ROOT-CAUSE FIX (#2728): versioned system persona registry — previously
# chat.py had no Section.SYSTEM persona block (only a language directive).
# Now: task_type-based persona injected as the first SYSTEM context block.
_SYSTEM_PERSONA_VERSION = "1.0"
_SYSTEM_PERSONAS = {
    "chat": (
        "You are SupremeAI, an intelligent AI assistant. "
        "Provide clear, accurate, and helpful responses. "
        "If you're unsure, say so honestly rather than fabricating. "
        "Format code blocks with proper language tags. "
        "Cite sources when referencing external information."
    ),
    "reasoning": (
        "You are SupremeAI, an expert reasoning engine. "
        "Think step-by-step before answering. "
        "For code: provide complete, runnable examples with type hints. "
        "For architecture: explain trade-offs, not just solutions. "
        "If a request is ambiguous, state your assumptions before proceeding."
    ),
    "analysis": (
        "You are SupremeAI, an analytical assistant. "
        "Summarize concisely, highlight key insights, and flag uncertainties. "
        "Structure responses with clear headings when appropriate."
    ),
}


def _derive_task_type(prompt: str) -> str:
    """ROOT-CAUSE FIX (#2726 + #2728): derive task_type from prompt keywords."""
    p = (prompt or "").lower()
    hard_kw = (
        "reasoning",
        "math",
        "code",
        "coding",
        "algorithm",
        "design",
        "architect",
        "implement",
        "debug",
        "refactor",
        "optimize",
        "analyze",
        "synthesize",
        "compare",
        "evaluate",
        "step by step",
    )
    if any(kw in p for kw in hard_kw):
        return "reasoning"
    medium_kw = (
        "agent",
        "analysis",
        "summarize",
        "explain",
        "describe",
        "research",
        "investigate",
        "review",
    )
    if any(kw in p for kw in medium_kw):
        return "analysis"
    return "chat"


def _get_system_persona(task_type: str) -> str:
    """ROOT-CAUSE FIX (#2728): return the versioned system persona for a task_type."""
    return _SYSTEM_PERSONAS.get(task_type, _SYSTEM_PERSONAS["chat"])


class ChatPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    model_name: str = "gemini-2.5-pro"
    # ROOT-CAUSE FIX (#2725): conversation history — previously missing from
    # ChatPayload, so the non-streaming /api/chat endpoint also had single-turn
    # amnesia. Frontend now sends history tail (last 20 messages).
    messages: list[dict] | None = Field(
        default=None, description="Conversation history for multi-turn context"
    )


class OrchestratedChatPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    project_id: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=2048)
    title: str | None = Field(default=None, max_length=256)
    artifact_type: str | None = Field(default=None, max_length=32)
    content: str | None = Field(default=None, max_length=500_000)
    confirmation: bool = False


@router.post("/orchestrate")
async def orchestrate_chat(
    payload: OrchestratedChatPayload,
    user: dict = Depends(get_current_user_token),
):
    """Canonical governed hub for conversational capability dispatch."""
    principal = user.get("tenant_id")
    if not principal:
        raise HTTPException(status_code=401, detail="Authenticated tenant claim required")
    result = await get_conversation_orchestrator().dispatch(
        ConversationCommand(
            prompt=payload.prompt,
            user_id=str(user.get("sub") or principal),
            tenant_id=str(principal),
            role=str(user.get("role", "user")),
            project_id=payload.project_id,
            conversation_id=payload.conversation_id,
            confirmation=payload.confirmation,
            metadata={
                "session_id": payload.session_id,
                "url": payload.url,
                "title": payload.title,
                "artifact_type": payload.artifact_type,
                "content": payload.content,
            },
        )
    )
    status_code = 202 if result.status == "confirmation_required" else 200
    if result.status == "denied":
        status_code = 403
    return JSONResponse(
        status_code=status_code,
        content={
            "success": result.status == "completed",
            "status": result.status,
            "correlation_id": result.correlation_id,
            "capability": result.capability,
            "response": result.response,
            "requires_confirmation": result.requires_confirmation,
            "error": result.error,
            "events": result.events,
        },
    )


@router.get("/capabilities")
async def list_chat_capabilities():
    """Discover connected spokes without exposing implementation details."""
    return {"success": True, "capabilities": get_conversation_orchestrator().capabilities()}


@router.get("/tasks/{task_id}")
async def get_chat_task(task_id: str, user: dict = Depends(get_current_user_token)):
    """Read durable task state through Chat with strict tenant ownership checks."""
    from adaptive_engine.task_engine import TaskEngine

    tenant_id = user.get("tenant_id") or user.get("sub")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Authenticated tenant required")
    task = TaskEngine().get(task_id)
    if not task or task.tenant_id != str(tenant_id) or task.created_by != str(user.get("sub")):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": task.model_dump(mode="json")}


# ⚡ ১. Fully Async Standard Completion with Multi-Layer Caching
@router.post("/get_completion")
async def get_completion(request: Request, payload: ChatPayload, db=Depends(get_tenant_db)):
    """Non-blocking Async LLM Completion with 5-Layer Caching"""
    logger.info(f"⚡ Async API Hit: Generating completion for tenant: {db.tenant_id}")

    # Extract session ID from headers for session-based caching
    session_id = request.headers.get("X-Session-ID")

    # Check multi-layer cache first
    cached_result = await multi_layer_cache.get(
        prompt=payload.prompt,
        model_name=payload.model_name,
        session_id=session_id,
        user_id=db.tenant_id,  # AUD-5.6: user-scoped cache keys
    )

    if cached_result:
        logger.info(f"🚀 CACHE HIT: {cached_result['source']}")
        return {
            "success": True,
            "response": cached_result["response"],
            "cached": True,
            "cache_source": cached_result["source"],
            "latency_ms": cached_result.get("latency_ms", 0),
        }

    # Cache miss - generate response from AI model with memory context
    logger.info("❌ CACHE MISS: Generating new response from AI model with memory recall")
    try:
        # M2 Context Engine: memory/RAG ফ্যাক্ট এখন budgeted block হিসেবে যোগ হয়
        # (আগে অবাধ্য concatenation হতো — ERR-F03 context bloat)
        # ROOT-CAUSE FIX (#2728): system persona block — previously the only
        # Section.SYSTEM was the language directive. No behavioral contract existed.
        # Now: a task_type-based persona is injected as the FIRST SYSTEM block.
        _derived_task = _derive_task_type(payload.prompt)
        context_blocks: list[ContextBlock] = [
            ContextBlock(
                section=Section.SYSTEM,
                text=_get_system_persona(_derived_task),
                priority=0,
                block_id="system-persona",
            ),  # #2728
            ContextBlock(section=Section.USER, text=payload.prompt, priority=0, block_id="user"),
        ]

        # (#1834) মৃত LTM no-op block মুছে ফেলা হয়েছে (instance-local facts কখনো persist হতো না)
        # build_context()
        # সবসময় "No memory available." ফেরত দিত, আর প্রতি cache-miss চ্যাটে
        # অপ্রয়োজনীয় একটি Supabase client তৈরি হতো। আসল recall নিচের
        # recall_memories (pgvector ai_memory) — সেটিই একমাত্র memory path।

        # Retrieve System Knowledge Base (Cold-Start RAG)
        try:
            from services.memory_service import recall_memories

            rag_results = await recall_memories(
                task_description=payload.prompt,
                limit=3,
                threshold=0.55,
                user_id=db.tenant_id,  # AUD-5.1: only the caller's memories
            )
            if rag_results:
                rag_facts = []
                for r in rag_results:
                    metadata = r.get("metadata", {})
                    content = metadata.get("content", r.get("summary", ""))
                    if content:
                        rag_facts.append(f"- {content}")
                for idx, fact in enumerate(rag_facts):
                    context_blocks.append(
                        ContextBlock(
                            section=Section.KNOWLEDGE,
                            text=fact,
                            priority=idx,
                            block_id=f"kb:{idx}",
                        )
                    )
        except Exception as rag_err:
            logger.debug(f"RAG Retrieval bypassed: {rag_err}")

        # M19 P-C: ভাষা-লুপ বন্ধ — সংরক্ষিত preferred_language এখন মডেলের কাছে
        # পৌঁছায় (system-directive block)। পছন্দ-অনুপস্থিত/en → কোনো block নেই
        # (আজকের আচরণ)। kill-switch SUPREMEAI_LANGUAGE_LOOP=off।
        if language_loop_enabled():
            _lang_directive = build_language_directive(
                await resolve_preferred_language(db.tenant_id)
            )
            if _lang_directive:
                context_blocks.append(
                    ContextBlock(
                        section=Section.SYSTEM,
                        text=_lang_directive,
                        priority=0,
                        block_id="lang-directive",
                    )
                )

        # Governed Intelligence Routing check
        from core.intelligence import IntelligenceRouter, VerificationEngine, synaptic_memory

        router = IntelligenceRouter()
        routing_decision = router.route(payload.prompt)
        logger.info(
            f"🧠 Governed Chat Route: tier={routing_decision.tier.value} "
            f"classification={routing_decision.classification.value} "
            f"audit_id={routing_decision.audit_id}"
        )

        if routing_decision.budget.requires_approval:
            from core.intelligence import manual_tasks

            task = manual_tasks.create(
                category="chat_governance",
                title=f"Review sensitive chat operation: {payload.prompt[:40]}...",
                steps=[
                    "Review prompt intent",
                    "Confirm authorization",
                    "Approve execution via release workflow",
                ],
                evidence_required=["operator identity", "approval timestamp"],
            )
            return {
                "success": False,
                "status": "approval_required",
                "requires_approval": True,
                "manual_task": task.model_dump(),
                "response": "এই কাজটি সংবেদনশীল বা অপরিবর্তনীয় হওয়ায় হিউম্যান রিভিউয়ের জন্য ম্যানুয়াল টাস্ক রেজিস্ট্রিভুক্ত করা হয়েছে।",
                "cached": False,
                "governance": routing_decision.model_dump(mode="json"),
            }

        # M2 Context Engine: budgeted, smallest-sufficient-context prompt
        # বাংলা (M07 P-F): kill-switch SUPREMEAI_CONTEXT_ENGINE=off → raw-prompt
        # passthrough (budget ছাড়া) — লাউড-লগ, নীরব ভাব নয়।
        if context_engine_enabled():
            assembled = ContextEngine().assemble(context_blocks)
            enriched_prompt = assembled.prompt
            logger.info(
                f"🧩 Context Engine: {assembled.report.total_tokens}/{assembled.report.budget} tokens, "
                f"kept={len(assembled.report.kept)}, dropped={len(assembled.report.dropped)}"
            )
        else:
            enriched_prompt = payload.prompt
            logger.info(
                "🧩 Context Engine OFF (SUPREMEAI_CONTEXT_ENGINE=off) — "
                "raw prompt passthrough; budget assembly skipped"
            )

        if await main_llm_circuit.should_attempt_external():
            try:
                # বাংলা মন্তব্য: সরাসরি গুগল নেটিভ ক্লায়েন্ট কল না করে ইউনিভার্সাল llm_gateway ব্যবহার করে এপিআই কল করা হচ্ছে
                # M16 P-A: tenant_id propagate — এই পথ যেন CostGuard-এর একই
                # spend feed-এ ভিড়ে যায় (আগে এটি metering-bypass ছিল; ড্যাশবোর্ডে
                # খরচ অদৃশ্য থাকত)।
                response = await llm_gateway.acompletion(
                    prompt=enriched_prompt,
                    # M03 P0-পূর্ণাংশ: InferenceContext বাধ্যতামূলক — টেন্যান্ট/
                    # টাস্ক অ্যাট্রিবিউশন এক-কাঠামোয় (M16 P-A spend feed এই পথেই)।
                    # ROOT-CAUSE FIX (#2726): task_type derived from prompt complexity
                    # instead of hardcoded "chat" — so "design a distributed rate limiter"
                    # routes to the hard model chain (llama-3.3-70b + gemini-2.5-pro),
                    # not the easy flash chain.
                    # Also honor user's model_name as the model override (previously
                    # it was only used as a cache key, never reached the gateway).
                    model=payload.model_name if payload.model_name != "gemini-2.5-pro" else None,
                    context=InferenceContext(
                        tenant_id=str(db.tenant_id) if db.tenant_id else "anonymous",
                        task_type=_derive_task_type(payload.prompt),
                        stream=False,
                    ),
                )
                await main_llm_circuit.record_success()
                response_text = (
                    response.get("text", "") if isinstance(response, dict) else str(response)
                )

                # Synaptic memory safe ingestion in memory layer
                synaptic_memory.remember(
                    block_id=f"chat_{db.tenant_id}_{routing_decision.audit_id}",
                    payload={"prompt": payload.prompt, "response": response_text[:200]},
                    importance=0.4 if routing_decision.tier.value == "fast" else 0.8,
                )

                # Store response in multi-layer cache for future requests
                await multi_layer_cache.set(
                    prompt=payload.prompt,
                    response=response_text,
                    model_name=payload.model_name,
                    session_id=session_id,
                    user_id=db.tenant_id,  # AUD-5.6: user-scoped cache keys
                )

                return {
                    "success": True,
                    "response": response_text,
                    "cached": False,
                    "cache_source": "L5_AI_MODEL",
                    "source": "external",
                }
            except Exception as e:
                logger.warning(f"External LLM API fail: {e!s} — falling back")
                await main_llm_circuit.record_failure()
                # Fall through to fallback logic

        # --- Fallback Path ---
        try:
            from services.memory_service import recall_memories

            fallback_results = await recall_memories(
                task_description=payload.prompt, limit=1, threshold=0.75
            )
            if fallback_results:
                best = fallback_results[0]
                metadata = best.get("metadata", {})
                answer = metadata.get("content", best.get("summary", ""))

                similarity = best.get("similarity", 0.8)
                disclaimer = " (এই উত্তরটি সম্পূর্ণ নিশ্চিত নাও হতে পারে।)" if similarity < 0.8 else ""

                response_text = answer + disclaimer
                return {
                    "success": True,
                    "response": response_text,
                    "cached": False,
                    "cache_source": "KNOWLEDGE_BASE_FALLBACK",
                    "source": "knowledge_base",
                }
        except Exception as e:
            logger.exception(f"Knowledge base fallback query failed: {e}")

        return {
            "success": True,
            "response": "দুঃখিত, এই মুহূর্তে আপনার প্রশ্নের উত্তর দিতে পারছি না। একটু পরে আবার চেষ্টা করুন।",
            "cached": False,
            "cache_source": "FALLBACK_NO_MATCH",
            "source": "no_match",
        }
    except Exception as e:
        logger.error(f"Async LLM Error: {e!s}")
        raise HTTPException(status_code=500, detail="AI Gateway Timeout.") from e


# ⚡ ২. Fully Async Streaming Generator
@router.post("/stream_chat")
async def stream_chat(payload: ChatPayload, db=Depends(get_tenant_db)):
    """High-Concurrency Async SSE Streamer."""
    logger.info(f"🌊 SSE Stream Initiated for tenant: {db.tenant_id}")

    # বাংলা (#2259 D1): পুরনো self-sufficiency pre-check বাদ —
    # UnifiedLearningEngine-এ `process_chat_message` মেথডই ছিল না, ফলে
    # প্রতিটি /stream_chat রিকোয়েস্টেই AttributeError → warning log হতো এবং
    # fast-path কখনোই কাজ করত না (dead path)। Semantic recall fast-path
    # canonical Experience store-এর উপর দিয়ে #2259 D2-তে (query verification
    # সহ) ফিরে আসবে।

    async def async_generator():
        try:
            # M2 Context Engine blocks (ERR-F03: budgeted assembly)
            context_blocks: list[ContextBlock] = [
                ContextBlock(section=Section.USER, text=payload.prompt, priority=0, block_id="user")
            ]
            try:
                from services.memory_service import recall_memories

                # BUGFIX: আগে user_id পাঠানো হতো না — ফলে অন্য tenant-এর মেমরিও
                # recall হতো (tenant isolation miss)। এখন db.tenant_id স্কোপড।
                rag_results = await recall_memories(
                    task_description=payload.prompt,
                    limit=3,
                    threshold=0.55,
                    user_id=db.tenant_id,
                )
                if rag_results:
                    rag_facts = []
                    for r in rag_results:
                        metadata = r.get("metadata", {})
                        content = metadata.get("content", r.get("summary", ""))
                        if content:
                            rag_facts.append(f"- {content}")
                    for idx, fact in enumerate(rag_facts):
                        context_blocks.append(
                            ContextBlock(
                                section=Section.KNOWLEDGE,
                                text=fact,
                                priority=idx,
                                block_id=f"kb:{idx}",
                            )
                        )
            except Exception as rag_err:
                logger.debug(f"RAG Retrieval bypassed in stream: {rag_err}")

            # M19 P-C: ভাষা-লুপ বন্ধ (SSE-পথ) — বিস্তারিত উপরের get_completion-এ।
            # বাংলা: এটি নেস্টেড async_generator — identity এখানে db.tenant_id।
            if language_loop_enabled():
                _lang_directive = build_language_directive(
                    await resolve_preferred_language(db.tenant_id)
                )
                if _lang_directive:
                    context_blocks.append(
                        ContextBlock(
                            section=Section.SYSTEM,
                            text=_lang_directive,
                            priority=0,
                            block_id="lang-directive",
                        )
                    )

            # M2 Context Engine: budgeted, smallest-sufficient-context prompt
            # বাংলা (M07 P-F): kill-switch SUPREMEAI_CONTEXT_ENGINE=off → raw-prompt
            # passthrough (budget ছাড়া) — লাউড-লগ, নীরব ভাব নয়।
            if context_engine_enabled():
                assembled = ContextEngine().assemble(context_blocks)
                enriched_prompt = assembled.prompt
                logger.info(
                    f"🧩 Context Engine: {assembled.report.total_tokens}/{assembled.report.budget} tokens, "
                    f"kept={len(assembled.report.kept)}, dropped={len(assembled.report.dropped)}"
                )
            else:
                enriched_prompt = payload.prompt
                logger.info(
                    "🧩 Context Engine OFF (SUPREMEAI_CONTEXT_ENGINE=off) — "
                    "raw prompt passthrough; budget assembly skipped"
                )

            if await main_llm_circuit.should_attempt_external():
                try:
                    # বাংলা: ইউনিভার্সাল llm_gateway ব্যবহার করে স্ট্রিমিং সম্পন্ন করা হচ্ছে
                    # M16 P-A: streaming পথেও tenant_id propagate — non-streaming
                    # পথের সাথে একই metering parity।
                    response_stream = await llm_gateway.acompletion(
                        prompt=enriched_prompt,
                        # M03 P0-পূর্ণাংশ: streaming পথেও context বাধ্যতামূলক —
                        # non-streaming-এর সাথে একই attribution parity।
                        # ROOT-CAUSE FIX (#2726): task_type derived from prompt complexity
                        # + honor user's model_name override (same as non-streaming path).
                        model=payload.model_name
                        if payload.model_name != "gemini-2.5-pro"
                        else None,
                        context=InferenceContext(
                            tenant_id=str(db.tenant_id) if db.tenant_id else "anonymous",
                            task_type=_derive_task_type(
                                payload.prompt
                            ),  # #2726: derived not hardcoded
                            stream=True,
                        ),
                    )

                    import json

                    meta_payload = json.dumps(
                        {"meta": {"provider": "llm_gateway", "status": "streaming"}}
                    )
                    yield f"data: {meta_payload}\n\n"

                    async for chunk in response_stream:
                        if chunk:
                            # SSE (Server-Sent Events) স্ট্যান্ডার্ড ফরম্যাট with JSON chunking
                            chunk_payload = json.dumps({"token": chunk})
                            yield f"data: {chunk_payload}\n\n"

                    yield "data: [DONE]\n\n"
                    await main_llm_circuit.record_success()

                    return

                except Exception as e:
                    logger.warning(f"External LLM API stream fail: {e!s} — falling back")
                    await main_llm_circuit.record_failure()

            # --- Fallback Path ---
            try:
                from services.memory_service import recall_memories

                fallback_results = await recall_memories(
                    task_description=payload.prompt, limit=1, threshold=0.75
                )
                if fallback_results:
                    best = fallback_results[0]
                    metadata = best.get("metadata", {})
                    answer = metadata.get("content", best.get("summary", ""))

                    similarity = best.get("similarity", 0.8)
                    disclaimer = " (এই উত্তরটি সম্পূর্ণ নিশ্চিত নাও হতে পারে।)" if similarity < 0.8 else ""

                    response_text = answer + disclaimer
                    import json

                    chunk_payload = json.dumps({"token": response_text})
                    meta_payload = json.dumps(
                        {"meta": {"provider": "cache_fallback", "status": "completed"}}
                    )
                    yield f"data: {meta_payload}\n\n"
                    yield f"data: {chunk_payload}\n\n"
                    yield "data: [DONE]\n\n"
                    return
            except Exception as e:
                logger.exception(f"Knowledge base stream fallback failed: {e}")

            yield "data: দুঃখিত, এই মুহূর্তে আপনার প্রশ্নের উত্তর দিতে পারছি না। একটু পরে আবার চেষ্টা করুন।\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream broken: {e!s}")
            yield 'data: {"error": "Internal Stream Error"}\n\n'

    # বাংলা: SSE হেডার — proxy/CDN বাফারিং রোধে ক্রিটিক্যাল।
    return StreamingResponse(
        async_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx বাফারিং রোধে
            "Content-Encoding": "identity",  # কম্প্রেশন বন্ধ — SSE-এর জন্য প��রয���োজন
        },
    )


@router.get("/learning/stats")
async def get_learning_stats(db=Depends(get_tenant_db)):
    """Learning telemetry stats from the canonical LearningStore (#2259 D1).

    বাংলা: আগে এটি UnifiedLearningEngine-এর async `get_stats()`-কে await না
    করে coroutine রিটার্ন করত → endpoint কখনোই কাজ করত না। এখন সরাসরি
    durable LearningStore-এর বাস্তব stats।"""
    from core.learning import get_learning_store

    return get_learning_store().get_stats()
