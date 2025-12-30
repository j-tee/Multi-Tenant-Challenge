"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = "Invoice Reconciliation API"
    debug: bool = False

    # Database settings
    database_url: str = "sqlite:///./reconciliation.db"

    # AI settings
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: float = 10.0
    ai_enabled: bool = True
    use_mock_ai: bool = False  # Use mock AI client for testing

    # Reconciliation settings
    reconciliation_date_tolerance_days: int = 3
    reconciliation_amount_tolerance_percent: float = 0.01  # 1%
    reconciliation_min_text_similarity: float = 0.3


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
