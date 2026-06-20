from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    openrouter_api_key: str = ""
    hf_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    nvidia_api_key: str = ""
    firecrawl_api_key: str = ""
    sentry_dsn: str = ""
    ollama_url: str = "http://localhost:11434"
    gcp_project_id: str = "supremeai-a"
    gcp_region: str = "us-central1"

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

    def validate(self) -> None:
        if self.env.lower() == "production":
            missing = []
            if not self.openrouter_api_key:
                missing.append("openrouter_api_key")
            if not self.gemini_api_key:
                missing.append("gemini_api_key")
            if not self.sentry_dsn:
                missing.append("sentry_dsn (strongly recommended)")
            if missing:
                raise RuntimeError(f"Missing required API keys for production: {', '.join(missing)}")


settings = Settings()
settings.validate()
