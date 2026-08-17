"""
Unit tests for configuration module.
"""
import pytest
from app.config import Settings, get_settings


class TestSettings:
    """Test Settings class functionality."""

    def test_default_app_name(self):
        """Test default application name."""
        settings = Settings()
        assert settings.APP_NAME == "ERP SOLUTION System"

    def test_default_app_version(self):
        """Test default application version."""
        settings = Settings()
        assert settings.APP_VERSION == "1.8.0"

    def test_default_debug_false(self):
        """Test debug is False by default."""
        settings = Settings()
        assert settings.DEBUG is False

    def test_default_database_url(self):
        """Test default database URL."""
        settings = Settings()
        assert "postgresql" in settings.DATABASE_URL
        assert "erp_db" in settings.DATABASE_URL

    def test_default_redis_url(self):
        """Test default Redis URL."""
        settings = Settings()
        assert settings.REDIS_URL == "redis://localhost:6379/0"

    def test_default_algorithm(self):
        """Test default JWT algorithm."""
        settings = Settings()
        assert settings.ALGORITHM == "HS256"

    def test_default_token_expiry(self):
        """Test default token expiry time (24 hours)."""
        settings = Settings()
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 24

    def test_default_smtp_config(self):
        """Test default SMTP configuration."""
        settings = Settings()
        assert settings.SMTP_HOST == "smtp.gmail.com"
        assert settings.SMTP_PORT == 587

    def test_default_ollama_config(self):
        """Test default Ollama configuration."""
        settings = Settings()
        assert settings.OLLAMA_BASE_URL == "http://localhost:11434"
        assert settings.OLLAMA_MODEL == "llama3.1"

    def test_upload_dir_default(self):
        """Test default upload directory."""
        settings = Settings()
        assert settings.UPLOAD_DIR == "./uploads"

    def test_max_upload_size(self):
        """Test maximum upload size (50MB)."""
        settings = Settings()
        assert settings.MAX_UPLOAD_SIZE == 50 * 1024 * 1024

    def test_websocket_heartbeat_interval(self):
        """Test WebSocket heartbeat interval."""
        settings = Settings()
        assert settings.WS_HEARTBEAT_INTERVAL == 30


class TestGetSettings:
    """Test get_settings function with LRU cache."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test that get_settings uses LRU cache."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_settings_singleton(self):
        """Test that settings object is a singleton via LRU cache."""
        settings = get_settings()
        cached_settings = get_settings()
        assert id(settings) == id(cached_settings)


class TestSettingsCustomValues:
    """Test Settings with custom values."""

    def test_custom_app_name(self):
        """Test setting custom app name."""
        settings = Settings(APP_NAME="Custom ERP")
        assert settings.APP_NAME == "Custom ERP"

    def test_custom_debug_true(self):
        """Test setting debug to True."""
        settings = Settings(DEBUG=True)
        assert settings.DEBUG is True

    def test_custom_database_url(self):
        """Test setting custom database URL."""
        custom_url = "postgresql://user:pass@host:5432/customdb"
        settings = Settings(DATABASE_URL=custom_url)
        assert settings.DATABASE_URL == custom_url

    def test_custom_secret_key(self):
        """Test setting custom secret key."""
        settings = Settings(SECRET_KEY="my-super-secret-key")
        assert settings.SECRET_KEY == "my-super-secret-key"

    def test_custom_ollama_model(self):
        """Test setting custom Ollama model."""
        settings = Settings(OLLAMA_MODEL="mistral")
        assert settings.OLLAMA_MODEL == "mistral"

    def test_custom_stripe_keys(self):
        """Test setting custom Stripe keys."""
        settings = Settings(
            STRIPE_SECRET_KEY="sk_test_123",
            STRIPE_PUBLISHABLE_KEY="pk_test_456"
        )
        assert settings.STRIPE_SECRET_KEY == "sk_test_123"
        assert settings.STRIPE_PUBLISHABLE_KEY == "pk_test_456"
