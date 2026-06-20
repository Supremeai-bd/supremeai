import os
import asyncio
import hashlib
import time
from functools import wraps
import httpx
from typing import Any, Dict, Optional, Tuple
from loguru import logger


from brain.model_registry import ModelRegistry
from tools.cot_reasoner import ChainOfThoughtReasoner
from core.input_sanitizer import InputSanitizer
from core.audit_logger import AuditLogger
from memory.long_term_memory import LongTermMemory
from core.language_router import LanguageRouter
from core.circuit_breaker import CircuitBreaker


def run_async_as_sync(coro):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def run_async_gen_as_sync(async_gen):
    import asyncio
    import queue
    import threading

    q = queue.Queue()
    done_sentinel = object()

    async def producer():
        try:
            async for item in async_gen:
                q.put(item)
        except Exception as e:
            q.put(e)
        finally:
            q.put(done_sentinel)

    def run_loop():
        asyncio.run(producer())

    t = threading.Thread(target=run_loop)
    t.start()

    while True:
        item = q.get()
        if item is done_sentinel:
            break
        if isinstance(item, Exception):
            raise item
        yield item
    t.join()


async def _await_maybe(val_or_coro):
    import inspect
    if inspect.isawaitable(val_or_coro):
        return await val_or_coro
    return val_or_coro


class ModelRouter:
    """
    Routes tasks to the cheapest capable model with fallbacks.
    Uses ModelRegistry for tier-based model selection.
    Priority:
      1. OpenRouter (cheap + capable)
      2. Gemini (Google AI Studio - Free Tier)
      3. DeepSeek (Free/Cheap Tier)
      4. Groq (Free Tier)
      5. Nvidia (NIM Free API)
      6. HuggingFace (free tier)
      7. Ollama local (offline fallback, disabled in production)
    """

    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.hf_api_key = os.getenv("HF_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY", "")
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.default_model = os.getenv(
            "DEFAULT_MODEL", "meta-llama/llama-3-8b-instruct:free"
        )
        self.local_model = os.getenv("LOCAL_MODEL", "llama3")
        self.cot_reasoner = ChainOfThoughtReasoner(max_iterations=2)
        self.input_sanitizer = InputSanitizer()
        self.audit_logger = AuditLogger()
        self._registry = ModelRegistry()
        self._local_rag = None
        self.long_term_memory = LongTermMemory()
        self.language_router = LanguageRouter()
        self._breakers = {
            "openrouter": CircuitBreaker("openrouter"),
            "gemini": CircuitBreaker("gemini"),
            "deepseek": CircuitBreaker("deepseek"),
            "groq": CircuitBreaker("groq"),
            "nvidia": CircuitBreaker("nvidia"),
            "huggingface": CircuitBreaker("huggingface"),
            "ollama": CircuitBreaker("ollama"),
        }
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._cache_ttl = 300.0

    def _cache_key(self, prompt: str, task_type: str) -> str:
        return hashlib.md5(f"{prompt}:{task_type}".encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        result, ts = entry
        if time.time() - ts > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return result

    def _put_in_cache(self, key: str, value: Dict[str, Any]) -> None:
        self._cache[key] = (value, time.time())

    def _get_local_rag(self):
        if self._local_rag is None:
            try:
                from tools.local_search_rag import LocalSearchRAG
                self._local_rag = LocalSearchRAG()
            except ImportError:
                self._local_rag = None
        return self._local_rag

    @property
    def local_rag(self):
        return self._get_local_rag()

    def _get_keys(self, raw_str: str) -> list[str]:
        if not raw_str:
            return []
        keys = []
        raw_clean = raw_str.replace("\n", ",").replace(";", ",")
        for part in raw_clean.split(","):
            part_stripped = part.strip()
            if part_stripped:
                keys.append(part_stripped)
        return keys

    def _estimate_complexity(self, task_type: str, prompt: str, max_cost: float) -> str:
        upper_task = (task_type or "").upper()
        upper_prompt = (prompt or "").upper()
        prompt_len = len(prompt)
        
        # Specialized/scientific/medical domains detection
        specialized_keywords = ["MEDICAL", "SCIENCE", "SCIENTIFIC", "CLINICAL", "GENETICS", "PHYSICS", "BIO", "CHEMISTRY"]
        is_specialized = "SPECIALIZED" in upper_task or any(kw in upper_task or kw in upper_prompt for kw in specialized_keywords)

        if max_cost >= 0.25 or "MATH" in upper_task or "REASONING" in upper_task or prompt_len > 2000 or is_specialized:
            return "specialized" if is_specialized else "phd_math"
        if "CODE" in upper_task or "CODING" in upper_task or prompt_len > 1000:
            return "code"
        if "SEARCH" in upper_task or "RAG" in upper_task or "RESEARCH" in upper_task:
            return "search"
        if "OCR" in upper_task or "VISION" in upper_task:
            return "vision"
        if "VALIDATION" in upper_task or "SCHEMA" in upper_task:
            return "structured"
        return "general"

    def _has_key_for_provider(self, provider: str) -> bool:
        if provider == "openai":
            return bool(self.openrouter_api_key)
        if provider == "anthropic":
            return bool(self.openrouter_api_key)
        if provider == "google":
            return bool(self.gemini_api_key) or bool(self.openrouter_api_key)
        if provider == "deepseek":
            return bool(self.deepseek_api_key) or bool(self.openrouter_api_key)
        if provider == "groq":
            return bool(self.groq_api_key) or bool(self.openrouter_api_key)
        if provider == "nvidia":
            return bool(self.nvidia_api_key) or bool(self.openrouter_api_key)
        if provider == "huggingface":
            return bool(self.hf_api_key)
        if provider == "ollama":
            from config import settings
            return settings.env.lower() != "production"
        return False

    def _select_model_by_tier(self, target_tier: int) -> Tuple[str, str]:
        tier_models = []
        for model_id, metadata in self._registry.MODELS.items():
            if metadata.get("tier") == target_tier:
                tier_models.append((model_id, metadata))

        tier_models.sort(key=lambda x: x[1].get("rank", 999))

        for model_id, metadata in tier_models:
            provider = metadata.get("provider")
            if self._has_key_for_provider(provider):
                if provider in ("openai", "anthropic") and self.openrouter_api_key:
                    return "openrouter", metadata.get("openrouter_id")
                if provider == "google":
                    if self.gemini_api_key:
                        return "gemini", "gemini-1.5-flash" if "flash" in model_id else "gemini-pro-1.5"
                    return "openrouter", metadata.get("openrouter_id")
                if provider == "deepseek":
                    if self.deepseek_api_key:
                        return "deepseek", "deepseek-chat"
                    return "openrouter", metadata.get("openrouter_id")
                if provider == "groq":
                    if self.groq_api_key:
                        return "groq", "llama3-8b-8192"
                    return "openrouter", metadata.get("openrouter_id")
                if provider == "nvidia":
                    if self.nvidia_api_key:
                        return "nvidia", "meta/llama3-8b-instruct"
                    return "openrouter", metadata.get("openrouter_id")
                if provider == "huggingface" and self.hf_api_key:
                    return "huggingface", "google/flan-t5-base"
                if provider == "ollama":
                    return "ollama", metadata.get("ollama_id", self.local_model)

        if target_tier == 1:
            return self._select_model_by_tier(2)
        elif target_tier == 2:
            return self._select_model_by_tier(5)
        elif target_tier == 5:
            from config import settings
            if settings.env.lower() != "production":
                return "ollama", self._registry.MODELS.get("local-qwen-0.5b", {}).get("ollama_id", self.local_model)
            else:
                if self.gemini_api_key:
                    return "gemini", "gemini-1.5-flash"
                if self.openrouter_api_key:
                    return "openrouter", self.default_model
                raise RuntimeError("No available LLM providers configured in production.")
        return "ollama", self.local_model

    def _pick_provider(self, task_type: str, prompt: str, max_cost: float) -> Tuple[str, str]:
        from config import settings
        is_production = settings.env.lower() == "production"

        if task_type == "completion":
            if self.gemini_api_key:
                return "gemini", "gemini-1.5-flash"
            if self.openrouter_api_key:
                return "openrouter", "google/gemini-flash-1.5"
            if self.deepseek_api_key:
                return "deepseek", "deepseek-chat"
            if self.groq_api_key:
                return "groq", "llama3-8b-8192"
            if is_production:
                raise RuntimeError("Production mode requires cloud API keys. Ollama is disabled in production.")
            reg_info = self._registry.get_model("local-qwen-0.5b")
            return "ollama", reg_info.get("ollama_id", self.local_model)

        complexity = self._estimate_complexity(task_type, prompt, max_cost)

        if complexity in ("phd_math", "specialized"):
            target_tier = 1
        elif complexity == "code":
            target_tier = 2
        elif task_type in ("translation", "sentiment", "summaries") or complexity == "search":
            target_tier = 5
        else:
            target_tier = 5

        return self._select_model_by_tier(target_tier)

    def _warn_if_low_key_redundancy(self, provider: str) -> None:
        key_map = {
            "openrouter": self.openrouter_api_key,
            "gemini": self.gemini_api_key,
            "deepseek": self.deepseek_api_key,
            "groq": self.groq_api_key,
            "nvidia": self.nvidia_api_key,
            "huggingface": self.hf_api_key,
        }
        raw = key_map.get(provider, "")
        count = len(self._get_keys(raw))
        if count == 1:
            logger.warning(f"Provider '{provider}' has only 1 API key configured. Add fallback keys to improve availability.")

    def route_and_generate(
        self, prompt: str, task_type: str = "general", max_cost: float = 0.01
    ) -> Dict[str, Any]:
        return run_async_as_sync(self.async_route_and_generate(prompt, task_type, max_cost))

    async def async_route_and_generate(
        self, prompt: str, task_type: str = "general", max_cost: float = 0.01
    ) -> Dict[str, Any]:
        logger.info(
            f"Routing task_type='{task_type}' max_cost={max_cost} "
            f"openrouter={'yes' if self.openrouter_api_key else 'no'}"
        )

        # Sanitize input and strip PII
        sanitized = self.input_sanitizer.sanitize(prompt)
        if not sanitized.get("is_valid", True):
            return {
                "success": False,
                "error": f"Input validation/safety block: {sanitized.get('reason')}"
            }
        prompt = sanitized.get("prompt", prompt)

        upper_task = (task_type or "general").upper()

        # Multi-modal routing: Detect image/pdf file paths or vision task type
        if "VISION" in upper_task or any(ext in prompt.lower() for ext in [".png", ".jpg", ".jpeg", ".pdf"]):
            try:
                from tools.vision_agent import VisionAgent
                vision_agent = VisionAgent()
                file_path = ""
                for w in prompt.split():
                    if any(ext in w.lower() for ext in [".png", ".jpg", ".jpeg", ".pdf"]):
                        file_path = w.strip("()[]\"'")
                        break
                if file_path and os.path.exists(file_path):
                    logger.info(f"Vision task detected, routing path: {file_path}")
                    if file_path.lower().endswith(".pdf"):
                        res = vision_agent.analyze_pdf(file_path)
                    elif "chart" in prompt.lower():
                        res = vision_agent.analyze_chart(file_path)
                    else:
                        res = vision_agent.analyze_image(file_path)
                    return {
                        "success": res.get("success", False),
                        "provider": "local_vision",
                        "model": "VisionAgent",
                        "text": res.get("text") or res.get("summary") or res.get("error", "No text found"),
                        "cost": 0.0,
                        "structured": res.get("structured", {})
                    }
            except Exception as e:
                logger.error(f"Failed to run local vision agent: {e}")
        enriched_prompt = prompt

        # Integrate ChainOfThought reasoning for math/reasoning tasks
        if "MATH" in upper_task or "REASONING" in upper_task:
            cot_prompt = self.cot_reasoner.build_prompt(prompt, task_type)
            enriched_prompt = cot_prompt
            logger.info("Using ChainOfThought reasoning for task")

        # Integrate local search RAG for search/research tasks
        if "SEARCH" in upper_task or "RAG" in upper_task or "RESEARCH" in upper_task:
            try:
                rag_result = self.local_rag.semantic_search(prompt)
                if rag_result.get("status") == "ok" and rag_result.get("matches"):
                    sources = []
                    for m in rag_result["matches"]:
                        doc_id = m.get("doc_id")
                        title = m.get("title", "")
                        fields = self.local_rag._index.get(doc_id, [])
                        text = fields[1] if len(fields) > 1 else ""
                        sources.append(f"Source: {title}\n{text}")
                    if sources:
                        enriched_prompt = f"{prompt}\n\nRetrieved context:\n" + "\n\n".join(sources)
            except Exception as exc:
                logger.warning(f"Local RAG search failed: {exc}")

        # Integrate long-term memory context
        memory_context = self.long_term_memory.build_context()
        if memory_context:
            enriched_prompt = f"{enriched_prompt}\n\nLong-term memory context:\n{memory_context}"

        provider, model = self._pick_provider(task_type, prompt, max_cost)

        lang_route = self.language_router.route(prompt, task_type)
        detected_lang = lang_route.get("language", "english")
        lang_provider = lang_route.get("provider", "openrouter")
        if detected_lang != "english":
            provider = lang_provider
            logger.info(f"Language override: detected {detected_lang} => provider {provider}")

        cache_key = self._cache_key(enriched_prompt, task_type)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        self._warn_if_low_key_redundancy(provider)
        try:
            result = await self._call(provider, model, enriched_prompt)
            if result.get("success"):
                self.long_term_memory.remember_fact(
                    content=result.get("text", "")[:200],
                    category="response",
                    source=provider,
                    importance=0.3,
                )
            if ("MATH" in upper_task or "REASONING" in upper_task) and result.get("success"):
                parsed = self.cot_reasoner.parse(result.get("text", ""))
                verification = self.cot_reasoner.verify(parsed.get("final_answer", ""))
                result["reasoning"] = parsed
                result["cot_verification"] = verification
            return result
        except Exception as exc:
            logger.error(f"Provider {provider} failed: {exc}")
            return await self._fallback(prompt, provider, exc)

    async def _call(self, provider: str, model: str, prompt: str) -> Dict[str, Any]:
        retries = 3
        delay = 1.0
        last_exc = None
        for i in range(retries):
            try:
                res = await self._call_with_breaker(provider, model, prompt)
                
                # If rate limited (e.g. rate limit error text or status)
                if not res.get("success") and ("rate limit" in str(res.get("error", "")).lower() or "429" in str(res.get("error", ""))):
                    raise RuntimeError(f"Rate limited: {res.get('error')}")
                    
                return res
            except Exception as exc:
                last_exc = exc
                if i == retries - 1:
                    break
                logger.warning(f"Provider {provider} failed (attempt {i+1}/{retries}). Retrying in {delay}s... Error: {exc}")
                await asyncio.sleep(delay)
                delay *= 2
        raise last_exc or RuntimeError(f"Failed to call provider {provider}")

    async def _call_with_breaker(self, provider: str, model: str, prompt: str) -> Dict[str, Any]:
        breaker = self._breakers.get(provider)
        if not breaker:
            return await self._execute_call(provider, model, prompt)
            
        if not breaker.allow_request():
            raise RuntimeError(f"Circuit breaker {provider} is open")
            
        try:
            res = await self._execute_call(provider, model, prompt)
            breaker.mark_success()
            return res
        except Exception:
            breaker.mark_failure()
            raise

    async def _execute_call(self, provider: str, model: str, prompt: str) -> Dict[str, Any]:
        if provider == "openrouter":
            return await self._call_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions",
                self.openrouter_api_key,
                model,
                prompt,
                provider_name="openrouter",
                extra_headers={
                    "HTTP-Referer": "https://supremeai.local",
                    "X-Title": "SupremeAI 2.0",
                },
            )
        if provider == "huggingface":
            return await self._call_huggingface(prompt, model)
        if provider == "gemini":
            return await self._call_gemini(prompt, model)
        if provider == "deepseek":
            return await self._call_openai_compatible(
                "https://api.deepseek.com/chat/completions",
                self.deepseek_api_key,
                model,
                prompt,
                provider_name="deepseek",
            )
        if provider == "groq":
            return await self._call_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions",
                self.groq_api_key,
                model,
                prompt,
                provider_name="groq",
            )
        if provider == "nvidia":
            return await self._call_openai_compatible(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                self.nvidia_api_key,
                model,
                prompt,
                provider_name="nvidia",
            )
        return await self._call_ollama(prompt, model)

    async def _fallback(self, prompt: str, failed: str, exc: Exception):
        from config import settings
        is_production = settings.env.lower() == "production"

        remaining = ["openrouter", "gemini", "deepseek", "groq", "nvidia", "huggingface", "ollama"]
        if is_production and "ollama" in remaining:
            remaining.remove("ollama")

        if failed in remaining:
            remaining.remove(failed)

        # Log rotation decision for explainable AI governance
        self.audit_logger.log_decision(
            action_type="agent_rotation",
            decision_details=f"Provider rotated from '{failed}' due to failure.",
            reasoning=f"Error: {exc}. Attempting fallback providers: {remaining}"
        )

        for prov in remaining:
            model = self._model_for(prov)
            try:
                return await self._call(prov, model, prompt)
            except Exception as e:
                logger.error(f"Fallback {prov} failed: {e}")
        return {
            "success": False,
            "error": f"All providers failed, last={exc}",
            "text": "All AI providers are unavailable right now.",
        }

    def _model_for(self, provider: str) -> str:
        return {
            "openrouter": self.default_model,
            "huggingface": "google/flan-t5-base",
            "ollama": self.local_model,
            "gemini": "gemini-1.5-flash",
            "deepseek": "deepseek-chat",
            "groq": "llama3-8b-8192",
            "nvidia": "meta/llama3-8b-instruct",
        }[provider]

    async def _call_openai_compatible(
        self,
        base_url: str,
        raw_keys: str,
        model: str,
        prompt: str,
        provider_name: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        keys = self._get_keys(raw_keys)
        if not keys:
            raise ValueError(f"No {provider_name} API keys configured.")

        headers = {
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        last_exc = None
        for key in keys:
            try:
                auth_header = {"Authorization": f"Bearer {key}"}
                res = await self._http_client.post(
                    base_url,
                    headers={**headers, **auth_header},
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"]
                return {"success": True, "provider": provider_name, "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"{provider_name.title()} key failed: {e}")
                last_exc = e
        raise last_exc or ValueError(f"{provider_name} API call failed.")

    async def _call_openrouter(self, prompt: str, model: str) -> Dict[str, Any]:
        return await self._call_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            self.openrouter_api_key,
            model,
            prompt,
            provider_name="openrouter",
            extra_headers={
                "HTTP-Referer": "https://supremeai.local",
                "X-Title": "SupremeAI 2.0",
            },
        )

    async def _call_gemini(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.gemini_api_key)
        if not keys:
            raise ValueError("No Gemini API keys configured.")

        last_exc = None
        for key in keys:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {
                    "x-goog-api-key": key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                res = await self._http_client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"success": True, "provider": "gemini", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"Gemini key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("Gemini API call failed.")

    async def _call_deepseek(self, prompt: str, model: str) -> Dict[str, Any]:
        return await self._call_openai_compatible(
            "https://api.deepseek.com/chat/completions",
            self.deepseek_api_key,
            model,
            prompt,
            provider_name="deepseek",
        )

    async def _call_groq(self, prompt: str, model: str) -> Dict[str, Any]:
        return await self._call_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions",
            self.groq_api_key,
            model,
            prompt,
            provider_name="groq",
        )

    async def _call_nvidia(self, prompt: str, model: str) -> Dict[str, Any]:
        return await self._call_openai_compatible(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            self.nvidia_api_key,
            model,
            prompt,
            provider_name="nvidia",
        )

    async def _call_huggingface(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.hf_api_key)
        if not keys:
            raise ValueError("No HuggingFace API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {"Authorization": f"Bearer {key}"}
                url = f"https://api-inference.huggingface.co/models/{model}"
                res = await self._http_client.post(url, headers=headers, json={"inputs": prompt}, timeout=20.0)
                res.raise_for_status()
                data = res.json()
                text = data[0].get("generated_text", str(data)) if isinstance(data, list) else str(data)
                return {"success": True, "provider": "huggingface", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"HuggingFace key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("HuggingFace API call failed.")

    async def _call_ollama(self, prompt: str, model: str) -> Dict[str, Any]:
        url = f"{self.ollama_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        res = await self._http_client.post(url, json=payload, timeout=10.0)
        res.raise_for_status()
        data = res.json()
        return {"success": True, "provider": "ollama", "model": model, "text": data.get("response", ""), "cost": 0.0}

    def route_and_generate_with_cot(
        self, prompt: str, task_type: str = "general", max_cost: float = 0.01, expected: Optional[str] = None
    ) -> Dict[str, Any]:
        reasoning = self.cot_reasoner.refine_loop(prompt, context=task_type, expected=expected)
        generated = self.route_and_generate(prompt, task_type=task_type, max_cost=max_cost)
        if generated.get("success") and reasoning.get("final_answer"):
            generated["cot_verification"] = self.cot_reasoner.verify(reasoning["final_answer"], expected)
            generated["reasoning"] = reasoning
        return generated

    def query_local_rag(self, query: str) -> Dict[str, Any]:
        try:
            return self.local_rag.semantic_search(query)
        except Exception as exc:
            logger.error(f"Local RAG semantic search failed: {exc}")
            return {"status": "error", "error": str(exc), "query": query, "matches": []}

    def route_and_stream(self, prompt: str, task_type: str = "general", max_cost: float = 0.01):
        return run_async_gen_as_sync(self.async_route_and_stream(prompt, task_type, max_cost))

    async def async_route_and_stream(self, prompt: str, task_type: str = "general", max_cost: float = 0.01):
        provider, model = self._pick_provider(task_type, prompt, max_cost)
        logger.info(f"Streaming from provider={provider}, model={model}")
        try:
            if provider == "openrouter" and self.openrouter_api_key:
                res_stream = self._stream_openai_compatible("https://openrouter.ai/api/v1/chat/completions", self._get_keys(self.openrouter_api_key)[0], model, prompt)
            elif provider == "deepseek" and self.deepseek_api_key:
                res_stream = self._stream_openai_compatible("https://api.deepseek.com/chat/completions", self._get_keys(self.deepseek_api_key)[0], model, prompt)
            elif provider == "groq" and self.groq_api_key:
                res_stream = self._stream_openai_compatible("https://api.groq.com/openai/v1/chat/completions", self._get_keys(self.groq_api_key)[0], model, prompt)
            elif provider == "nvidia" and self.nvidia_api_key:
                res_stream = self._stream_openai_compatible("https://integrate.api.nvidia.com/v1/chat/completions", self._get_keys(self.nvidia_api_key)[0], model, prompt)
            elif provider == "gemini" and self.gemini_api_key:
                res_stream = self._stream_gemini(prompt, model)
            elif provider == "ollama":
                res_stream = self._stream_ollama(prompt, model)
            else:
                res = await self._call(provider, model, prompt)
                yield res.get("text", "")
                return

            if hasattr(res_stream, "__aiter__"):
                async for chunk in res_stream:
                    yield chunk
            else:
                for chunk in res_stream:
                    yield chunk
        except Exception as exc:
            logger.error(f"Streaming failed for {provider}: {exc}")
            yield f"Error during streaming: {exc}"

    async def _stream_openai_compatible(self, url: str, key: str, model: str, prompt: str):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        }
        import json
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            chunk = data["choices"][0]["delta"].get("content", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass

    async def _stream_gemini(self, prompt: str, model: str):
        keys = self._get_keys(self.gemini_api_key)
        if not keys:
            raise ValueError("No Gemini API keys configured.")
        key = keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
        headers = {
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        import json
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass

    async def _stream_ollama(self, prompt: str, model: str):
        url = f"{self.ollama_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}
        import json
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("response", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass