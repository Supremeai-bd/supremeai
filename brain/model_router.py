import os
import httpx
from typing import Any, Dict, Optional, Tuple
from loguru import logger


from brain.model_registry import ModelRegistry


class ModelRouter:
    """
    Routes tasks to the cheapest capable model with fallbacks.
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

    def route_and_generate(
        self, prompt: str, task_type: str = "general", max_cost: float = 0.01
    ) -> Dict[str, Any]:
        logger.info(
            f"Routing task_type='{task_type}' max_cost={max_cost} "
            f"openrouter={'yes' if self.openrouter_api_key else 'no'}"
        )

        provider, model = self._pick_provider(task_type, max_cost)
        try:
            return self._call(provider, model, prompt)
        except Exception as exc:
            logger.error(f"Provider {provider} failed: {exc}")
            return self._fallback(prompt, provider, exc)

    def _estimate_complexity(self, task_type: str, max_cost: float) -> str:
        upper_prompt = (task_type or "").upper()
        if max_cost >= 0.25 or "MATH" in upper_prompt or "REASONING" in upper_prompt:
            return "phd_math"
        if "CODE" in upper_prompt or "CODING" in upper_prompt:
            return "code"
        if "SEARCH" in upper_prompt or "RAG" in upper_prompt:
            return "search"
        if "OCR" in upper_prompt or "VISION" in upper_prompt:
            return "vision"
        if "VALIDATION" in upper_prompt or "SCHEMA" in upper_prompt:
            return "structured"
        return "general"

    def _pick_provider(self, task_type: str, max_cost: float):
        from config import settings
        is_production = settings.env.lower() == "production"

        complexity = self._estimate_complexity(task_type, max_cost)
        if complexity == "phd_math" and self.openrouter_api_key:
            return "openrouter", "anthropic/claude-3-opus"
        if complexity == "code" and self.openrouter_api_key:
            return "openrouter", "qwen/qwen-2.5-72b-instruct"

        if task_type in ("translation", "sentiment") and self.hf_api_key:
            return "huggingface", "google/flan-t5-base"
        if self.openrouter_api_key:
            return "openrouter", self.default_model
        if self.gemini_api_key:
            return "gemini", "gemini-1.5-flash"
        if self.deepseek_api_key:
            return "deepseek", "deepseek-chat"
        if self.groq_api_key:
            return "groq", "llama3-8b-8192"
        if self.nvidia_api_key:
            return "nvidia", "meta/llama3-8b-instruct"

        if is_production:
            raise RuntimeError("Production mode requires cloud API keys. Ollama is disabled in production.")

        return "ollama", self.local_model

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
