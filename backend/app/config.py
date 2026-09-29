from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Placeholder values that must never be used in production
_INSECURE_SECRET_KEYS = {"", "your-super-secret-key-change-in-production", "change-me"}
_INSECURE_DATABASE_URLS = {"postgresql://erp_user:erp_password@localhost:5432/erp_db"}


class Settings(BaseSettings):
    APP_NAME: str = "ERP SOLUTION System"
    APP_VERSION: str = "1.8.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # Database
    DATABASE_URL: str = "postgresql://erp_user:erp_password@localhost:5432/erp_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if v.strip() in _INSECURE_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is not configured. Generate one with `openssl rand -hex 32` "
                "and provide it via environment variable or .env file."
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_not_be_default_in_production(cls, v: str, info) -> str:
        env = (info.data.get("ENVIRONMENT") or "development").lower()
        if env == "production" and v in _INSECURE_DATABASE_URLS:
            raise ValueError(
                "DATABASE_URL still uses the insecure default credentials in production. "
                "Set a real DATABASE_URL (or DB_USER/DB_PASSWORD/DB_NAME) before deploying."
            )
        return v

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@erp_solution.local"

    # AI / Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # OpenAI (optional — required only for GPT-4 features; never hardcode)
    OPENAI_API_KEY: str = ""

    # CORS (comma-separated list of allowed origins)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Monitoring (optional)
    SENTRY_DSN: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

