from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "SupremeAI 2.0"
    API_V1_STR: str = "/api/v1"
    
    app_name: str = "SupremeAI 2.0"
    env: str = "local"
    debug: bool = True

    port: int = 8000
    host: str = "0.0.0.0"
    supremeai_admin_password_hash: str | None = None

    openrouter_api_key: str = ""
    hf_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""
    groq_api_key: str = ""
    nvidia_api_key: str = ""
    firecrawl_api_key: str = ""
    sentry_dsn: str = ""
    ollama_url: str = "http://localhost:11434"

    max_cost_per_task: float = 0.01
    admin_rules_db: str = "data/constitutional_rules.db"
    memory_db_dir: str = "data/memory"
    skill_registry_path: str = "data/skill_registry.json"

settings = Settings()