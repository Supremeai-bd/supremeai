import os
import httpx
from typing import Any, Dict, Optional, Tuple
from loguru import logger


from brain.model_registry import ModelRegistry
from tools.cot_reasoner import ChainOfThoughtReasoner
from core.input_sanitizer import InputSanitizer


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
        self._registry = ModelRegistry()
        self._local_rag = None

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
        prompt_len = len(prompt)
        if max_cost >= 0.25 or "MATH" in upper_task or "REASONING" in upper_task or prompt_len > 2000:
            return "phd_math"
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

        if complexity == "phd_math":
            target_tier = 1
        elif complexity == "code":
            target_tier = 2
        elif task_type in ("translation", "sentiment", "summaries") or complexity == "search":
            target_tier = 5
        else:
            target_tier = 5

        return self._select_model_by_tier(target_tier)

    def route_and_generate(
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

        provider, model = self._pick_provider(task_type, prompt, max_cost)
        try:
            result = self._call(provider, model, enriched_prompt)
            # Add self-verification for CoT tasks
            if ("MATH" in upper_task or "REASONING" in upper_task) and result.get("success"):
                parsed = self.cot_reasoner.parse(result.get("text", ""))
                verification = self.cot_reasoner.verify(parsed.get("final_answer", ""))
                result["reasoning"] = parsed
                result["cot_verification"] = verification
            return result
        except Exception as exc:
            logger.error(f"Provider {provider} failed: {exc}")
            return self._fallback(prompt, provider, exc)

    def _call(self, provider: str, model: str, prompt: str) -> Dict[str, Any]:
        if provider == "openrouter":
            return self._call_openrouter(prompt, model)
        if provider == "huggingface":
            return self._call_huggingface(prompt, model)
        if provider == "gemini":
            return self._call_gemini(prompt, model)
        if provider == "deepseek":
            return self._call_deepseek(prompt, model)
        if provider == "groq":
            return self._call_groq(prompt, model)
        if provider == "nvidia":
            return self._call_nvidia(prompt, model)
        return self._call_ollama(prompt, model)

    def _fallback(self, prompt: str, failed: str, exc: Exception):
        from config import settings
        is_production = settings.env.lower() == "production"

        remaining = ["openrouter", "gemini", "deepseek", "groq", "nvidia", "huggingface", "ollama"]
        if is_production and "ollama" in remaining:
            remaining.remove("ollama")

        if failed in remaining:
            remaining.remove(failed)

        for prov in remaining:
            model = self._model_for(prov)
            try:
                return self._call(prov, model, prompt)
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

    def _call_openrouter(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.openrouter_api_key)
        if not keys:
            raise ValueError("No OpenRouter API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://supremeai.local",
                    "X-Title": "SupremeAI 2.0",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"]
                return {"success": True, "provider": "openrouter", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"OpenRouter key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("OpenRouter API call failed.")

    def _call_gemini(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.gemini_api_key)
        if not keys:
            raise ValueError("No Gemini API keys configured.")

        last_exc = None
        for key in keys:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(url, json=payload)
                    res.raise_for_status()
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"success": True, "provider": "gemini", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"Gemini key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("Gemini API call failed.")

    def _call_deepseek(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.deepseek_api_key)
        if not keys:
            raise ValueError("No DeepSeek API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(
                        "https://api.deepseek.com/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"]
                return {"success": True, "provider": "deepseek", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"DeepSeek key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("DeepSeek API call failed.")

    def _call_groq(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.groq_api_key)
        if not keys:
            raise ValueError("No Groq API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"]
                return {"success": True, "provider": "groq", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"Groq key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("Groq API call failed.")

    def _call_nvidia(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.nvidia_api_key)
        if not keys:
            raise ValueError("No Nvidia API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                with httpx.Client(timeout=30.0) as client:
                    res = client.post(
                        "https://integrate.api.nvidia.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    res.raise_for_status()
                data = res.json()
                text = data["choices"][0]["message"]["content"]
                return {"success": True, "provider": "nvidia", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"Nvidia key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("Nvidia API call failed.")

    def _call_huggingface(self, prompt: str, model: str) -> Dict[str, Any]:
        keys = self._get_keys(self.hf_api_key)
        if not keys:
            raise ValueError("No HuggingFace API keys configured.")

        last_exc = None
        for key in keys:
            try:
                headers = {"Authorization": f"Bearer {key}"}
                url = f"https://api-inference.huggingface.co/models/{model}"
                with httpx.Client(timeout=20.0) as client:
                    res = client.post(url, headers=headers, json={"inputs": prompt})
                    res.raise_for_status()
                data = res.json()
                text = data[0].get("generated_text", str(data)) if isinstance(data, list) else str(data)
                return {"success": True, "provider": "huggingface", "model": model, "text": text, "cost": 0.0}
            except Exception as e:
                logger.warning(f"HuggingFace key failed: {e}")
                last_exc = e
        raise last_exc or ValueError("HuggingFace API call failed.")

    def _call_ollama(self, prompt: str, model: str) -> Dict[str, Any]:
        url = f"{self.ollama_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        with httpx.Client(timeout=10.0) as client:
            res = client.post(url, json=payload)
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
        provider, model = self._pick_provider(task_type, prompt, max_cost)
        logger.info(f"Streaming from provider={provider}, model={model}")
        try:
            if provider == "openrouter" and self.openrouter_api_key:
                yield from self._stream_openai_compatible("https://openrouter.ai/api/v1/chat/completions", self._get_keys(self.openrouter_api_key)[0], model, prompt)
            elif provider == "deepseek" and self.deepseek_api_key:
                yield from self._stream_openai_compatible("https://api.deepseek.com/chat/completions", self._get_keys(self.deepseek_api_key)[0], model, prompt)
            elif provider == "groq" and self.groq_api_key:
                yield from self._stream_openai_compatible("https://api.groq.com/openai/v1/chat/completions", self._get_keys(self.groq_api_key)[0], model, prompt)
            elif provider == "nvidia" and self.nvidia_api_key:
                yield from self._stream_openai_compatible("https://integrate.api.nvidia.com/v1/chat/completions", self._get_keys(self.nvidia_api_key)[0], model, prompt)
            elif provider == "gemini" and self.gemini_api_key:
                yield from self._stream_gemini(prompt, model)
            elif provider == "ollama":
                yield from self._stream_ollama(prompt, model)
            else:
                res = self._call(provider, model, prompt)
                yield res.get("text", "")
        except Exception as exc:
            logger.error(f"Streaming failed for {provider}: {exc}")
            yield f"Error during streaming: {exc}"

    def _stream_openai_compatible(self, url: str, key: str, model: str, prompt: str):
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
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
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

    def _stream_gemini(self, prompt: str, model: str):
        keys = self._get_keys(self.gemini_api_key)
        if not keys:
            raise ValueError("No Gemini API keys configured.")
        key = keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        import json
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass

    def _stream_ollama(self, prompt: str, model: str):
        url = f"{self.ollama_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": True}
        import json
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("response", "")
                            if chunk:
                                yield chunk
                        except Exception:
                            pass