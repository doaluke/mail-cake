from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql://mailcake:mailcake_password@localhost:5432/mailcake"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # LiteLLM Proxy
    litellm_proxy_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-mailcake-master-key"

    # Gmail OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/gmail/callback"

    # Email (Digest 發送)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # 預設 LLM 模型
    default_model: str = "claude-haiku"
    default_summary_style: str = "bullet_points"

    # 費用控制
    max_tokens_per_email: int = 1000
    max_summaries_per_day: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
