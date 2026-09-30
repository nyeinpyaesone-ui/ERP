import os

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Placeholder values that must never be used in production
_INSECURE_SECRET_KEYS = {
    "",
    "change-me",
    "secret-key",
    "your-secret-key",
    "your-secret-key-here",
    "your-secret-key-change-in-production",
    "your-super-secret-key",
    "your-super-secret-key-change-in-production",
}
_INSECURE_DATABASE_URLS = {"postgresql://erp_user:erp_password@localhost:5432/erp_db"}

# Deterministic development-only key (documented in .env.example as dev fallback).
_DEV_SECRET_KEY = "dev-only-insecure-secret-key-0123456789abcdef"


def _load_test_env_defaults() -> None:
    """Provide safe defaults for the automated test environment only.

    Production/staging deployments must still configure real secrets; this
    branch is reachable exclusively when pytest is the running process, so it
    can never weaken a real deployment.
    """
    if "PYTEST_CURRENT_TEST" not in os.environ and "pytest" not in os.sys.argv[0]:
        return
    # Keep tests hermetic: never read a developer's local .env file.
    os.environ.setdefault("ENV_FILE_DISABLED", "1")
    os.environ.setdefault("SECRET_KEY", _DEV_SECRET_KEY)
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")


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
    # Env key used across .env / docker-compose / setup scripts is JWT_ALGORITHM.
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        lowered = v.strip().lower()
        if (
            lowered in _INSECURE_SECRET_KEYS
            or "change" in lowered
            or "replace" in lowered
            or "your-" in lowered
            or "xxx" in lowered
            or len(lowered) < 32
        ):
            raise ValueError(
                "SECRET_KEY is not configured. Generate one with `openssl rand -hex 32` "
                "and provide it via environment variable or .env file."
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def database_url_must_not_be_default_in_production(cls, v: str, info) -> str:
        env = (info.data.get("ENVIRONMENT") or "development").lower()
        if env == "production" and ("erp_user:erp_password" in v or v in _INSECURE_DATABASE_URLS):
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

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_algorithm_alias(cls, values):
        """Accept the legacy ALGORITHM init key as an alias of JWT_ALGORITHM.

        The canonical configuration key everywhere (.env templates,
        docker-compose, docs) is JWT_ALGORITHM; older programmatic callers
        may still pass ALGORITHM. Env vars are read natively by
        pydantic-settings via the JWT_ALGORITHM field.
        """
        if isinstance(values, dict):
            for key in ("ALGORITHM", "algorithm"):
                if key in values and not values.get("JWT_ALGORITHM"):
                    values["JWT_ALGORITHM"] = values.pop(key)
        return values

def _is_test_run() -> bool:
    """True when executing under pytest (used to keep tests hermetic)."""
    import sys
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.path.basename(sys.argv[0])


def _engine_kwargs(url: str) -> dict:
    """Pool options that are valid for the configured dialect.

    SQLite (tests / lightweight local dev) does not support pool_size/
    max_overflow; Postgres keeps the tuned production pool.
    """
    kwargs = {"pool_pre_ping": True}
    if not url.startswith("sqlite"):
        kwargs.update(pool_size=20, max_overflow=30)
    return kwargs

_load_test_env_defaults()

@lru_cache()
def get_settings() -> Settings:
    # Under pytest, ignore a developer's local .env so tests are reproducible.
    return Settings(_env_file=None if _is_test_run() else ".env")

settings = get_settings()

