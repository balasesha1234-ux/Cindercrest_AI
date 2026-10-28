"""Application configuration using Pydantic Settings."""

import secrets
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and defaults."""

    # Server binding (localhost only)
    HOST: str = Field(default="127.0.0.1", description="Host to bind to. Must be localhost.")
    PORT: int = Field(default=8000, description="Port to bind the server.")
    DEBUG: bool = Field(default=False, description="Debug mode flag.")

    # CORS Whitelist
    CORS_ORIGINS: list[str] | str = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origins for the frontend.",
    )

    # Authentication
    SESSION_TOKEN: str = Field(
        default="",
        description="Ephemeral per-launch session token. Generated automatically if empty.",
    )

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./data/cindercrest.db",
        description="Database URL for SQLite WAL storage.",
    )

    # Model providers
    OLLAMA_BASE_URL: str = Field(
        default="http://127.0.0.1:11434",
        description="Base URL for local Ollama service.",
    )
    OLLAMA_MODEL: str = Field(
        default="qwen3:8b",
        description="Default local model identifier.",
    )
    GROQ_API_KEY: str | None = Field(
        default=None,
        description="Groq API key for ultra-fast cloud model fallback.",
    )
    GROQ_MODEL: str = Field(
        default="qwen/qwen3.8-27b",
        description="Default Groq model identifier.",
    )

    # Voice pipeline settings
    VOICE_SAMPLE_RATE: int = Field(default=16000, description="Audio sample rate in Hz.")
    VOICE_VAD_THRESHOLD: float = Field(default=0.5, description="VAD confidence threshold.")
    VOICE_DEFAULT_SYNTHESIZER: str = Field(
        default="onecore",
        description="Speech synthesis engine ('onecore' or 'sapi').",
    )

    # Approved filesystem roots for safe read-only intelligence
    APPROVED_DIRECTORIES: list[str] | str = Field(
        default_factory=lambda: ["docs"],
        description="Explicit list of approved directory paths for read-only filesystem intelligence.",
    )

    # Privacy Mode
    PRIVACY_MODE: bool = Field(
        default=False,
        description="Default system privacy mode flag. When true, memory writes and retrievals are disabled.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CINDERCREST_",
        extra="ignore",
    )

    @field_validator("HOST")
    @classmethod
    def validate_localhost_only(cls, v: str) -> str:
        """Enforce localhost binding only."""
        if v not in ("127.0.0.1", "localhost"):
            raise ValueError(
                f"Security violation: Cindercrest can only bind to 127.0.0.1 or localhost, received '{v}'"
            )
        return v

    @field_validator("SESSION_TOKEN")
    @classmethod
    def ensure_session_token(cls, v: str) -> str:
        """Generate a random 32-byte hex token if none provided."""
        if not v or not v.strip():
            return secrets.token_hex(32)
        return v.strip()

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Support comma-separated strings or lists for CORS origins."""
        if isinstance(v, str):
            return [orig.strip() for orig in v.split(",") if orig.strip()]
        return v

    @field_validator("APPROVED_DIRECTORIES", mode="before")
    @classmethod
    def parse_approved_directories(cls, v: str | list[str]) -> list[str]:
        """Support comma-separated strings or lists for approved directories."""
        if isinstance(v, str):
            return [d.strip() for d in v.split(",") if d.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
