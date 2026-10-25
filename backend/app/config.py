import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# Resolve .env location explicitly so the app works from any CWD
# (backend/, repo root, or inside /app container). First existing wins.
_ENV_CANDIDATES = [
    p for p in (
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),      # backend/.env
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")), # repo /.env
    )
    if os.path.exists(p)
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_CANDIDATES or (".env",),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables
    )

    APP_NAME: str = "ERP SOLUTION System"
    APP_VERSION: str = "1.8.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database (explicit psycopg2 driver to match SQLAlchemy sync engine)
    DATABASE_URL: str = "postgresql+psycopg2://erp_user:erp_password@localhost:5432/erp_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @field_validator("SECRET_KEY")
    @classmethod
    def _reject_default_secret_in_prod(cls, v: str) -> str:
        if os.getenv("ENVIRONMENT", "development").lower() == "production" and \
           v == "your-super-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be overridden via environment when ENVIRONMENT=production"
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

    # Frontend URL
    FRONTEND_URL: str = "http://localhost:3000"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

