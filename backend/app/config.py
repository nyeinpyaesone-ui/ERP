import json
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ERP SOLUTION System"
    APP_VERSION: str = "1.8.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["dev", "test", "prod"] = "dev"

    # Database
    DATABASE_URL: str = "postgresql://erp_user:erp_password@localhost:5432/erp_db"

    # SQLAlchemy pool (honored by app.database.get_engine)
    POOL_SIZE: int = 10
    POOL_MAX_OVERFLOW: int = 20
    POOL_RECYCLE: int = 1800

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security: SecretStr so the value never leaks via repr/logs.
    # Dev/test default is intentionally weak but flagged; prod refuses to boot
    # with it (see model validator below) — Twelve-Factor III, fail-closed.
    SECRET_KEY: SecretStr = SecretStr("your-super-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS: plain string in env (comma-separated or JSON array) so that
    # pydantic-settings never attempts JSON decoding at the source layer.
    # Use cors_origins_list to get the parsed list.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS as a JSON array, a comma-separated string,
        or a single origin. Never raises: falls back to splitting on commas.
        Empty input falls back to local-dev defaults so allow_credentials
        does not block every origin.
        """
        default = ["http://localhost:3000", "http://localhost:5173"]
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return default
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                items = [str(item).strip() for item in parsed if str(item).strip()]
                if items:
                    return items
                return ["http://localhost:3000", "http://localhost:5173"]
        parsed = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return parsed or ["http://localhost:3000", "http://localhost:5173"]

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@erp_solution.local"

    # AI / Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    @model_validator(mode="after")
    def _fail_closed_in_prod(self) -> "Settings":
        """Prod must boot with real secrets — refuse the well-known defaults."""
        if self.ENVIRONMENT == "prod":
            placeholder = "your-super-secret-key-change-in-production"
            if self.SECRET_KEY.get_secret_value() == placeholder:
                raise ValueError(
                    "SECRET_KEY must be set to a unique value when ENVIRONMENT=prod"
                )
            if len(self.SECRET_KEY.get_secret_value()) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in prod")
            if self.DATABASE_URL.startswith("postgresql://erp_user:erp_password"):
                raise ValueError("DATABASE_URL must not use the example credentials")
        return self

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def _positive_ttl(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
