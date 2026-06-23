# Recent Code Changes 3 (Semantic Cache, GSM & Frontend Autopsy)


## File: backend\core\semantic_cache.py

`python

import os
import math
import google.generativeai as genai
from google.cloud import firestore
from loguru import logger
from typing import Optional, List

class VectorSemanticCache:
    """
    Enterprise Vector Semantic Cache Engine.
    Saves up to 90% of AI Token costs by matching prompt meanings instead of exact strings.
    """
    def __init__(self):
        self.db = firestore.Client()
        self.collection = self.db.collection("supreme_semantic_cache")
        # Gemini API Config
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """à¦¦à§à¦Ÿà¦¿ à¦­à§‡à¦•à§à¦Ÿà¦°à§‡à¦° à¦®à¦§à§à¦¯à§‡ à¦¸à¦¿à¦®à¦¿à¦²à¦¾à¦°à¦¿à¦Ÿà¦¿ à¦¸à§à¦•à§‹à¦° à¦ªà¦°à¦¿à¦®à¦¾à¦ª à¦•à¦°à¦¾à¦° à¦¬à¦¿à¦¶à§à¦¦à§à¦§ à¦—à¦¾à¦£à¦¿à¦¤à¦¿à¦• à¦²à¦œà¦¿à¦• (Zero Dependencies)"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        if not magnitude1 or not magnitude2:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    async def get_cached_inference(self, prompt: str, model_name: str, threshold: float = 0.95) -> Optional[str]:
        """à¦ªà§à¦°à¦®à§à¦ªà¦Ÿà§‡à¦° à¦…à¦°à§à¦¥ à¦¬à¦¿à¦¶à§à¦²à§‡à¦·à¦£ à¦•à¦°à§‡ à§¯à§«% à¦®à§à¦¯à¦¾à¦šà¦¿à¦‚ à¦ªà§‡à¦²à§‡ à¦•à§à¦¯à¦¾à¦¶à¦¡ à¦°à§‡à¦¸à¦ªà¦¨à§à¦¸ à¦°à¦¿à¦Ÿà¦¾à¦°à§à¦¨ à¦•à¦°à§‡"""
        try:
            # à§§. Gemini Embedding API à¦¦à¦¿à§Ÿà§‡ à¦ªà§à¦°à¦®à§à¦ªà¦Ÿà§‡à¦° à¦­à§‡à¦•à§à¦Ÿà¦° à¦œà§‡à¦¨à¦¾à¦°à§‡à¦Ÿ à¦•à¦°à¦¾ (Lightweight & High-Accuracy)
            response = genai.embed_content(
                model="models/text-embedding-004",
                content=prompt,
                task_type="retrieval_document"
            )
            query_vector = response.get('embedding')
            if not query_vector: return None

            # à§¨. à¦«à¦¾à§Ÿà¦¾à¦°à¦¸à§à¦Ÿà§‹à¦° à¦¥à§‡à¦•à§‡ à¦“à¦‡ à¦¨à¦¿à¦°à§à¦¦à¦¿à¦·à§à¦Ÿ à¦®à¦¡à§‡à¦²à§‡à¦° à¦•à§à¦¯à¦¾à¦¶à¦¡ à¦¡à¦¾à¦Ÿà¦¾ à¦°à¦¿à¦¡ à¦•à¦°à¦¾
            cache_docs = self.collection.where("model", "==", model_name).stream()
            
            for doc in cache_docs:
                data = doc.to_dict()
                cached_vector = data.get("embedding")
                
                if cached_vector:
                    # à§©. à¦•à¦¸à¦¾à¦‡à¦¨ à¦¸à¦¿à¦®à¦¿à¦²à¦¾à¦°à¦¿à¦Ÿà¦¿ à¦•à§à¦¯à¦¾à¦²à¦•à§à¦²à§‡à¦Ÿ à¦•à¦°à¦¾
                    score = self._cosine_similarity(query_vector, cached_vector)
                    if score >= threshold:
                        logger.info(f"âš¡ [SEMANTIC CACHE HIT] Score: {score:.4f}. Token saved for model {model_name}!")
                        return data.get("response_text")
                        
            return None
        except Exception as e:
            logger.error(f"âš ï¸ Semantic cache lookup failed silently: {str(e)}")
            return None

    async def set_cache_inference(self, prompt: str, model_name: str, response_text: str):
        """à¦­à¦¬à¦¿à¦·à§à¦¯à¦¤à§‡à¦° à¦®à§à¦¯à¦¾à¦šà¦¿à¦‚à§Ÿà§‡à¦° à¦œà¦¨à§à¦¯ à¦°à§‡à¦¸à¦ªà¦¨à§à¦¸ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦­à§‡à¦•à§à¦Ÿà¦°à¦¸à¦¹ à¦¸à§‡à¦­ à¦•à¦°à§‡ à¦°à¦¾à¦–à¦¾"""
        try:
            response = genai.embed_content(
                model="models/text-embedding-004",
                content=prompt,
                task_type="retrieval_document"
            )
            embedding = response.get('embedding')
            if not embedding: return

            self.collection.add({
                "prompt_example": prompt,
                "model": model_name,
                "embedding": embedding,
                "response_text": response_text,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"ðŸ’¾ Successfully vectorized and cached new semantic context for {model_name}.")
        except Exception as e:
            logger.error(f"âŒ Failed to write vector semantic cache to Firestore: {str(e)}")

``n

## File: backend\core\secret_vault.py

`python

import os
from loguru import logger

try:
    from google.cloud import secretmanager
except ImportError:
    secretmanager = None

class ProductionSecretVault:
    """
    Enterprise Cloud Secret Vault.
    Fetches production API keys and database strings directly into memory from Google Secret Manager.
    Removes the need for plaintext .env files in cloud instances.
    """
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.env = os.getenv("ENV", "local").lower()
        self.client = None

        if secretmanager and self.env == "production":
            try:
                # Cloud Run-à¦à¦° à¦¡à¦¿à¦«à¦²à§à¦Ÿ à¦¸à¦¾à¦°à§à¦­à¦¿à¦¸ à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ à¦…à¦Ÿà§‹à¦®à§‡à¦Ÿà¦¿à¦•à§à¦¯à¦¾à¦²à¦¿ à¦…à¦¥à§‹à¦°à¦¾à¦‡à¦œà¦¡ à¦¹à¦¬à§‡
                self.client = secretmanager.SecretManagerServiceClient()
                logger.info(f"ðŸ”’ Production Secret Vault hooked into GCP Project: {self.project_id}")
            except Exception as e:
                logger.warning(f"Failed to bind Secret Manager Service Client: {str(e)}. Falling back to raw env.")
        else:
            logger.info("âš™ï¸ Local/Dev mode active or library missing. Bypassing Google Secret Manager.")

    def fetch_secret(self, secret_id: str, default_fallback: str = "") -> str:
        """à¦—à§à¦—à¦² à¦¸à¦¿à¦•à§à¦°à§‡à¦Ÿ à¦®à§à¦¯à¦¾à¦¨à§‡à¦œà¦¾à¦° à¦¥à§‡à¦•à§‡ à¦°à¦¿à§Ÿà¦¾à¦²-à¦Ÿà¦¾à¦‡à¦®à§‡ à¦¸à¦¿à¦•à§à¦°à§‡à¦Ÿ à¦­à§à¦¯à¦¾à¦²à§ à¦°à¦¿à¦¡ à¦•à¦°à¦¾à¦° à¦®à§‡à¦•à¦¾à¦¨à¦¿à¦œà¦®"""
        # à¦²à§‹à¦•à¦¾à¦² à¦®à§‹à¦¡ à¦¬à¦¾ à¦•à§à¦²à¦¾à¦‰à¦¡ à¦°à¦¾à¦¨ à¦à¦¨à¦­à¦¾à§Ÿà¦°à¦¨à¦®à§‡à¦¨à§à¦Ÿ à¦­à§à¦¯à¦¾à¦°à¦¿à§Ÿà§‡à¦¬à¦² à¦¬à§à¦¯à¦¾à¦•à¦†à¦ª à¦šà§‡à¦•
        env_fallback = os.getenv(secret_id)
        if env_fallback:
            return env_fallback

        if not self.client or not self.project_id:
            return default_fallback

        try:
            # GCP Secret Manager Standard Resource Path
            name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            payload = response.payload.data.decode("UTF-8")
            return payload.strip()
        except Exception as e:
            logger.error(f"âŒ Failed to fetch secret [{secret_id}] from GSM: {str(e)}. Using fallback.")
            return default_fallback

# Global Vault Singleton Instance
secret_vault = ProductionSecretVault()

``n

## File: backend\core\config.py

`python


import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from loguru import logger
from core.secret_vault import secret_vault


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if "pytest" in sys.modules else ["../.env", ".env"],
        extra="ignore",
    )

    PROJECT_NAME: str = "SupremeAI 2.0"
    API_V1_STR: str = "/api/v1"

    app_name: str = "SupremeAI 2.0"
    env: str = "local"
    debug: bool = True
    docs_auth_enabled: bool = False
    docs_username: str = "admin"
    docs_password: str = ""

    port: int = 8000
    host: str = "0.0.0.0"
    supremeai_admin_password_hash: str | None = None

    cors_origins: list[str] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "https://supremeai-a.web.app",
        "https://supremeai-a.firebaseapp.com",
        "https://supremeai-admin.web.app",
        "https://supremeai-admin.firebaseapp.com",
    ]

    jwt_secret: str = secret_vault.fetch_secret("JWT_SECRET", "np97Qpdqi9VdRyiANqjfKZn8/u7s/WCjtG8UsjbhhS0=")
    
    # âš¡ à¦¡à¦¾à¦‡à¦¨à¦¾à¦®à¦¿à¦•à¦²à¦¿ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦•à§à¦²à¦¾à¦‰à¦¡ à¦®à§‡à¦®à¦°à¦¿ à¦¥à§‡à¦•à§‡ à¦¸à¦¿à¦•à§à¦°à§‡à¦Ÿ à¦°à¦¿à¦¡ à¦•à¦°à¦¾ à¦¹à¦šà§à¦›à§‡
    # à¦¡à¦¿à¦¸à§à¦•à§‡ à¦•à§‹à¦¨à§‹ .env à¦«à¦¾à¦‡à¦² à¦¨à¦¾ à¦¥à¦¾à¦•à¦²à§‡à¦“ à¦ªà§à¦°à§‹à¦¡à¦¾à¦•à¦¶à¦¨ à¦à¦ªà¦¿à¦†à¦‡ à§§à§¦à§¦% à¦¸à§à¦®à§à¦¥à¦²à¦¿ à¦šà¦²à¦¬à§‡
    supabase_database_url: str = secret_vault.fetch_secret(
        "SUPABASE_DATABASE_URL_POOLER", 
        "postgresql://localhost:5432/postgres"
    )

    openrouter_api_key: str = secret_vault.fetch_secret("OPENROUTER_API_KEY", "")
    hf_api_key: str = secret_vault.fetch_secret("HF_API_KEY", "")
    gemini_api_key: str = secret_vault.fetch_secret("GEMINI_API_KEY", "")
    deepseek_api_key: str = secret_vault.fetch_secret("DEEPSEEK_API_KEY", "")
    groq_api_key: str = secret_vault.fetch_secret("GROQ_API_KEY", "")
    nvidia_api_key: str = secret_vault.fetch_secret("NVIDIA_API_KEY", "")
    firecrawl_api_key: str = secret_vault.fetch_secret("FIRECRAWL_API_KEY", "")

    claude_openrouter_model: str = "anthropic/claude-3.5-haiku:free"

    gemini_rpm_limit: int = 9
    gemini_tpm_limit: int = 240_000
    gemini_rpd_limit: int = 475
    groq_rpm_limit: int = 28
    groq_tpm_limit: int = 28_500
    groq_rpd_limit: int = 13_680
    openrouter_rpm_limit: int = 19
    openrouter_rpd_limit: int = 45
    cloudflare_rpd_limit: int = 9_000
    nvidia_rpm_limit: int = 38
    nvidia_tpm_limit: int = 38_000
    huggingface_rpm_limit: int = 18
    huggingface_rpd_limit: int = 950

    max_prompt_tokens: int = 4_000
    max_response_tokens: int = 1_500
    enable_token_compression: bool = True
    sentry_dsn: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    gcp_project_id: str = "supremeai-a"
    gcp_region: str = "us-central1"

    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""

    max_cost_per_task: float = 0.01
    admin_rules_db: str = "data/constitutional_rules.db"
    memory_db_dir: str = "data/memory"
    skill_registry_path: str = "data/skill_registry.json"

    @field_validator("env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        allowed = {"local", "staging", "production", "test"}
        if value.lower() not in allowed:
            raise ValueError(f"env must be one of {allowed}")
        return value.lower()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        import json
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def validate_config(self) -> None:
        if self.env.lower() == "production":
            missing = []
            if not self.openrouter_api_key:
                missing.append("openrouter_api_key")
            if not self.gemini_api_key:
                missing.append("gemini_api_key")
            if not self.sentry_dsn:
                logger.warning("Sentry DSN is not configured (strongly recommended)")
            if not self.jwt_secret:
                missing.append("secure JWT_SECRET")
            if missing:
                raise RuntimeError(f"Missing required configurations for production: {', '.join(missing)}")


settings = Settings()

``n

## File: apps\studio-client\src\App.tsx

`python

import React, { useEffect, useState } from "react";

// Pro Tip: à¦—à§à¦²à§‹à¦¬à¦¾à¦² à¦¬à§à¦¯à¦¾à¦•à¦à¦¨à§à¦¡ URL à¦®à§à¦¯à¦¾à¦ª
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

export const App: React.FC = () => {
  const [isServerOnline, setIsServerOnline] = useState<boolean>(false);
  const [streamLogs, setStreamLogs] = useState<string[]>([]);

  useEffect(() => {
    // âš¡ à§§. à¦†à¦²à¦¾à¦¦à¦¾ /health à¦ªà§‹à¦²à¦¿à¦‚ à¦¸à¦®à§à¦ªà§‚à¦°à§à¦£ à¦¡à¦¿à¦²à¦¿à¦Ÿ à¦•à¦°à§‡ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦®à§‡à¦‡à¦¨ SSE à¦¸à§à¦Ÿà§à¦°à¦¿à¦®à§‡ à¦•à¦¾à¦¨à§‡à¦•à§à¦Ÿ à¦•à¦°à¦¾ à¦¹à¦šà§à¦›à§‡
    // à¦†à¦ªà¦¨à¦¾à¦° à¦ªà§à¦°à¦œà§‡à¦•à§à¦Ÿà§‡à¦° à¦à¦•à¦šà§à¦¯à¦¼à¦¾à¦² à¦¸à§à¦Ÿà§à¦°à¦¿à¦®à¦¿à¦‚ à¦à¦¨à§à¦¡à¦ªà¦¯à¦¼à§‡à¦¨à§à¦Ÿ (à¦¯à§‡à¦®à¦¨: /api/task/stream) à¦à¦–à¦¾à¦¨à§‡ à¦¬à¦¸à¦¾à¦¬à§‡à¦¨
    const sseEndpoint = `${API_BASE_URL}/api/task/stream`;
    
    console.log("ðŸ”Œ Initializing SupremeAI Unified Lifespan SSE Stream...");
    const eventSource = new EventSource(sseEndpoint);

    // ðŸŸ¢ à§¨. SSE à¦•à¦¾à¦¨à§‡à¦•à¦¶à¦¨ à¦¸à¦¾à¦•à¦¸à§‡à¦¸à¦«à§à¦²à¦¿ à¦“à¦ªà§‡à¦¨ à¦¹à¦²à§‡ à¦¸à§à¦Ÿà§‡à¦Ÿ à¦šà§‡à¦žà§à¦œ (Zero Network Cost Health Check)
    eventSource.onopen = () => {
      console.log("ðŸŸ¢ [SYSTEM ON] SupremeAI Backend Core is ONLINE. SSE Stream active.");
      setIsServerOnline(true);
    };

    // à§©. à¦°à¦¿à¦¯à¦¼à§‡à¦²-à¦Ÿà¦¾à¦‡à¦® à¦²à¦¾à¦‡à¦­ à¦®à§‡à¦¸à§‡à¦œ à¦¬à¦¾ à¦Ÿà¦¾à¦¸à§à¦• à¦²à¦— à¦°à¦¿à¦¸à¦¿à¦­ à¦•à¦°à¦¾à¦° à¦²à¦œà¦¿à¦•
    eventSource.onmessage = (event) => {
      try {
        const parsedData = JSON.parse(event.data);
        if (parsedData.log) {
          setStreamLogs((prev) => [...prev, parsedData.log]);
        }
      } catch (err) {
        // à¦ªà§à¦²à§‡à¦‡à¦¨ à¦Ÿà§‡à¦•à§à¦¸à¦Ÿ à¦¡à¦¾à¦Ÿà¦¾ à¦†à¦¸à¦²à§‡ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦¹à§à¦¯à¦¾à¦¨à§à¦¡à§‡à¦² à¦•à¦°à¦¬à§‡
        setStreamLogs((prev) => [...prev, event.data]);
      }
    };

    // ðŸ”´ à§ª. à¦¸à¦¾à¦°à§à¦­à¦¾à¦° à¦¡à¦¾à¦‰à¦¨ à¦¹à¦²à§‡ à¦¬à¦¾ à¦•à¦¨à§à¦Ÿà§‡à¦‡à¦¨à¦¾à¦° à¦¸à§à¦²à¦¿à¦ªà§‡ à¦—à§‡à¦²à§‡ à¦¸à§à¦¬à§Ÿà¦‚à¦•à§à¦°à¦¿à§Ÿà¦­à¦¾à¦¬à§‡ à¦…à¦«à¦²à¦¾à¦‡à¦¨ à¦¸à§à¦Ÿà§‡à¦Ÿ à¦Ÿà¦—à¦²
    // EventSource à¦¨à¦¿à¦œà§‡ à¦¥à§‡à¦•à§‡à¦‡ à¦¬à§à¦¯à¦¾à¦•à¦—à§à¦°à¦¾à¦‰à¦¨à§à¦¡à§‡ à¦°à¦¿-à¦•à¦¾à¦¨à§‡à¦•à§à¦Ÿ à¦Ÿà§à¦°à¦¾à¦‡ à¦•à¦°à¦¤à§‡ à¦¥à¦¾à¦•à¦¬à§‡, à¦•à§‹à¦¨à§‹ setInterval à¦²à¦¾à¦—à¦¬à§‡ à¦¨à¦¾
    eventSource.onerror = (error) => {
      console.error("ðŸ”´ [SYSTEM CRITICAL] SSE Stream severed. SupremeAI Server is OFFLINE.");
      setIsServerOnline(false);
    };

    // ðŸ§¹ à§«. à¦•à¦®à§à¦ªà§‹à¦¨à§‡à¦¨à§à¦Ÿ à¦†à¦¨à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦¬à¦¾ à¦°à¦¿à¦²à¦¿à¦œ à¦¹à§à¦¯à¦¾à¦¨à§à¦¡à¦²à¦¾à¦° (Zombie Tab & Memory Leak Prevention)
    return () => {
      console.warn("ðŸ”Œ Disconnecting active SSE stream context wrapper.");
      eventSource.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 relative">
      {/* ðŸ›¡ï¸ à¦—à¦¡-à¦Ÿà¦¿à¦¯à¦¼à¦¾à¦° à¦°à¦¿à¦¯à¦¼à§‡à¦²-à¦Ÿà¦¾à¦‡à¦® à¦²à¦¾à¦‡à¦­ à¦¹à§‡à¦²à¦¥ à¦‡à¦¨à§à¦¡à¦¿à¦•à§‡à¦Ÿà¦° à¦¬à§à¦¯à¦¾à¦œ */}
      <div className="absolute top-4 right-4 flex items-center gap-2 bg-slate-900/80 border border-slate-800 px-3 py-1.5 rounded-full shadow-lg backdrop-blur-md">
        <span className={`h-2.5 w-2.5 rounded-full ${isServerOnline ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
        <span className="text-xs font-mono tracking-wider font-bold text-slate-300">
          {isServerOnline ? "SUPREME_CORE: ACTIVE" : "SUPREME_CORE: OFFLINE"}
        </span>
      </div>

      {/* à¦¡à§à¦¯à¦¾à¦¶à¦¬à§‹à¦°à§à¦¡à§‡à¦° à¦¬à¦¾à¦•à¦¿ UI à¦¸à§‡à¦•à¦¶à¦¨ à¦à¦–à¦¾à¦¨à§‡ à¦¬à¦¸à¦¬à§‡ */}
      <main className="mt-12">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
          SupremeAI Dashboard Console
        </h1>
        
        {/* à¦²à¦¾à¦‡à¦­ à¦²à¦— à¦®à¦¨à¦¿à¦Ÿà¦° à¦¸à§à¦•à§à¦°à¦¿à¦¨ */}
        <div className="mt-6 p-4 bg-slate-900 border border-slate-800 rounded-xl font-mono text-xs max-h-60 overflow-y-auto">
          <p className="text-slate-500">// Live Infrastructure Logs:</p>
          {streamLogs.map((log, index) => (
            <p key={index} className="text-cyan-400 mt-1">{log}</p>
          ))}
        </div>
      </main>
    </div>
  );
};

``n

## File: tools\vscode-extension\test\__mocks__\vscode.ts

`python

// tools/vscode-extension/test/__mocks__/vscode.ts
// Type-safe VS Code Mock Engine to eliminate dead-code and false positives.

export class Position {
    constructor(public readonly line: number, public readonly character: number) {}

    isBefore(other: Position): boolean {
        if (this.line < other.line) return true;
        if (this.line > other.line) return false;
        return this.character < other.character;
    }

    isAfter(other: Position): boolean {
        if (this.line > other.line) return true;
        if (this.line < other.line) return false;
        return this.character > other.character;
    }

    isEqual(other: Position): boolean {
        return this.line === other.line && this.character === other.character;
    }
}

export class Range {
    public readonly start: Position;
    public readonly end: Position;

    constructor(start: Position, end: Position);
    constructor(startLine: number, startCharacter: number, endLine: number, endCharacter: number);
    constructor(startOrLine: Position | number, endOrChar: Position | number, endLine?: number, endCharacter?: number) {
        if (typeof startOrLine === "number" && typeof endOrChar === "number" && typeof endLine === "number" && typeof endCharacter === "number") {
            this.start = new Position(startOrLine, endOrChar);
            this.end = new Position(endLine, endCharacter);
        } else if (startOrLine instanceof Position && endOrChar instanceof Position) {
            this.start = startOrLine;
            this.end = endOrChar;
        } else {
            throw new Error("Invalid Range constructor parameters");
        }
    }

    get isEmpty(): boolean {
        return this.start.isEqual(this.end);
    }
}

export class Selection extends Range {
    public readonly anchor: Position;
    public readonly active: Position;

    constructor(anchor: Position, active: Position) {
        super(anchor, active);
        this.anchor = anchor;
        this.active = active;
    }

    get isReversed(): boolean {
        return this.active.isBefore(this.anchor);
    }
}

// âš¡ Active Functional Namespaces using Jest Spies with proper type structures
export const window = {
    showInformationMessage: jest.fn().mockResolvedValue(undefined),
    showErrorMessage: jest.fn().mockResolvedValue(undefined),
    showWarningMessage: jest.fn().mockResolvedValue(undefined),
    activeTextEditor: undefined,
    visibleTextEditors: [],
    createStatusBarItem: jest.fn().mockReturnValue({
        command: undefined,
        text: "",
        show: jest.fn(),
        hide: jest.fn(),
        dispose: jest.fn()
    })
};

export const workspace = {
    getConfiguration: jest.fn().mockReturnValue({
        get: jest.fn(),
        update: jest.fn(),
        has: jest.fn()
    }),
    textDocuments: [],
    onDidChangeTextDocument: jest.fn().mockReturnValue({ dispose: jest.fn() }),
    onDidSaveTextDocument: jest.fn().mockReturnValue({ dispose: jest.fn() })
};

export const commands = {
    registerCommand: jest.fn().mockReturnValue({ dispose: jest.fn() }),
    executeCommand: jest.fn().mockResolvedValue(undefined)
};

export enum StatusBarAlignment {
    Left = 1,
    Right = 2
}

export enum OverviewRulerLane {
    Left = 1,
    Center = 2,
    Right = 4,
    Full = 7
}

export const ExtensionContext = jest.fn().mockImplementation(() => ({
    subscriptions: [],
    workspaceState: { get: jest.fn(), update: jest.fn() },
    globalState: { get: jest.fn(), update: jest.fn(), setKeysForSync: jest.fn() },
    extensionPath: "/mock/extension/path",
    storagePath: "/mock/storage/path",
    globalStoragePath: "/mock/global/storage/path",
    logPath: "/mock/log/path"
}));

``n

## File: apps\studio-client\src\store\useStore.ts

`python

import { create } from "zustand";

// ðŸ›¡ï¸ à¦Ÿà¦¾à¦‡à¦ª-à¦¸à§‡à¦« à¦¸à§à¦Ÿà§à¦¯à¦¾à¦Ÿà¦¾à¦¸ à¦à¦¬à¦‚ à¦®à§‡à¦¸à§‡à¦œ à¦‡à¦¨à§à¦Ÿà¦¾à¦°à¦«à§‡à¦¸ à¦¡à§‡à¦«à¦¿à¦¨à¦¿à¦¶à¦¨
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

interface SupremeState {
  // Core Infrastructure States (BFF Architecture Ready)
  isServerOnline: boolean;
  sessionId: string | null;
  currentIdempotencyKey: string | null;
  isOrchestrating: boolean;
  
  // Clean Orchestration Context (No Plaintext API Keys!)
  chatHistory: ChatMessage[];
  activeTaskType: string;
  executionError: string | null;

  // Actions / Mutators
  setServerStatus: (online: boolean) => void;
  initializeSession: (id: string) => void;
  generateIdempotencyKey: () => string;
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearHistory: () => void;
  triggerOrchestration: (active: boolean, error?: string | null) => void;
}

export const useStore = create<SupremeState>((set) => ({
  // â”€â”€ ðŸ“¦ Core Infrastructure Default States â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  isServerOnline: false,
  sessionId: null,
  currentIdempotencyKey: null,
  isOrchestrating: false,
  chatHistory: [],
  activeTaskType: "general",
  executionError: null,

  // â”€â”€ âš¡ Actions & Mutators (Zero Ghost State Architecture) â”€â”€â”€â”€â”€â”€â”€â”€â”€
  
  setServerStatus: (online) => set({ isServerOnline: online }),

  initializeSession: (id) => set({ sessionId: id }),

  generateIdempotencyKey: () => {
    // ðŸ”’ à¦¡à¦¾à¦¬à¦²-à¦¬à¦¿à¦²à¦¿à¦‚ à¦à¦¬à¦‚ à¦°à§‡à¦¸ à¦•à¦¨à§à¦¡à¦¿à¦¶à¦¨ à¦ à§‡à¦•à¦¾à¦¤à§‡ à¦ªà§à¦°à¦¤à¦¿ à¦•à§à¦²à¦¿à¦•à§‡à¦° à¦œà¦¨à§à¦¯ à¦‡à¦‰à¦¨à¦¿à¦• UUIDv4 à¦œà§‡à¦¨à¦¾à¦°à§‡à¦Ÿà¦°
    const uniqueKey = crypto.randomUUID();
    set({ currentIdempotencyKey: uniqueKey });
    return uniqueKey;
  },

  addMessage: (message) => set((state) => ({
    chatHistory: [
      ...state.chatHistory,
      {
        ...message,
        id: crypto.randomUUID(),
        timestamp: Date.now()
      }
    ]
  })),

  clearHistory: () => set({ chatHistory: [], executionError: null }),

  triggerOrchestration: (active, error = null) => set({ 
    isOrchestrating: active, 
    executionError: error 
  })
}));

``n

## File: backend\core\prompt_helpers.py

`python

from typing import List, Dict

def format_unified_chat_prompt(message: str, history: List[Dict[str, str]] = None) -> str:
    """
    Centralized prompt builder for unifying chat history with the current task.
    Prevents context loss and DRY violations across multiple routers.
    """
    if not history:
        return message

    formatted_prompt = ""
    for msg in history:
        role = "User" if msg.get("role") == "user" else "Assistant"
        formatted_prompt += f"{role}: {msg.get('content', '')}\n"
    formatted_prompt += f"User: {message}\nAssistant:"
    return formatted_prompt

``n

