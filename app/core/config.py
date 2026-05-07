from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "InnerCircle AGI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///C:/tmp/innercircle.db"

    # ── Security ──────────────────────────────────────────────
    SECRET_KEY: str = "changeme-super-secret-key-min-32-chars!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ── Rate Limiting ────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60

    # ── OpenAI (LLM) ─────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 120  # seconds
    OPENAI_MAX_TOKENS: int = 4096

    # ── ChromaDB (Vector Memory) ─────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # ── Redis / Celery ───────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # ── Insight Generation ───────────────────────────────────
    INSIGHT_GENERATION_INTERVAL_HOURS: int = 6
    MAX_INSIGHTS_PER_AGENT: int = 3

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"   # System env vars must not break startup



@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()