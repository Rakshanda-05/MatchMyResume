"""
Configuration & Environment Variables
--------------------------------------
All secrets and config values are loaded from environment variables.
Copy .env.example to .env and fill in your values before running.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ─── Anthropic / Claude ───────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str                          # Your Anthropic API key

    # ─── Twilio WhatsApp ──────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str                         # Twilio Account SID
    TWILIO_AUTH_TOKEN: str                          # Twilio Auth Token
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"  # Twilio sandbox or your number

    # ─── App Settings ─────────────────────────────────────────────────────────
    BASE_URL: str = "http://localhost:8000"         # Public URL for file downloads
    MAX_FILE_SIZE_MB: int = 10                      # Max resume upload size
    SESSION_TTL_MINUTES: int = 60                   # How long to keep conversation state
    LOG_LEVEL: str = "INFO"

    # ─── Claude Model ─────────────────────────────────────────────────────────
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"  # Model to use for evaluations

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance (loaded once at startup)."""
    return Settings()
