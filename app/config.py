"""
config.py - Application configuration using Pydantic Settings.
Reads variables strictly from environment/.env at runtime without hardcoded providers or secrets.
"""

from typing import Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Settings (Read strictly from environment/.env, no hardcoded provider/model)
    GROQ_API_KEY: Optional[str] = Field(default=None, description="API key for LLM provider")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="OpenAI-compatible base URL")
    LLM_MODEL: Optional[str] = Field(default=None, description="Model identifier for the provider")
    LLM_TIMEOUT_SECONDS: float = Field(default=10.0, description="Request timeout in seconds")
    LLM_TEMPERATURE: float = Field(default=0.2, description="Sampling temperature")

    # ML Classifier & Routing Settings
    # If None, the classifier uses the cross-validation tuned threshold from training set
    CONFIDENCE_THRESHOLD: Optional[float] = Field(
        default=None,
        description="Confidence threshold for automatic routing vs needs_review. If None, uses CV-tuned value."
    )
    EMBEDDING_MODEL_NAME: str = Field(default="all-MiniLM-L6-v2", description="SentenceTransformers model")

    # Persistence
    DATABASE_URL: str = Field(default="sqlite:///./tickets.db", description="Database connection URL")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Log level")

    # Team Routing Table
    TEAM_ROUTING: Dict[str, str] = Field(
        default_factory=lambda: {
            "Billing": "Finance Support",
            "Technical": "Engineering Support",
            "Access": "IT Security / Identity",
            "General": "Customer Care",
        },
        description="Mapping from category to designated support team",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def safe_summary(self) -> Dict[str, object]:
        """Return safe configuration representation without exposing any secret keys."""
        return {
            "llm_configured": bool(self.GROQ_API_KEY),
            "llm_base_url": self.LLM_BASE_URL if self.LLM_BASE_URL else "(not set)",
            "llm_model": self.LLM_MODEL if self.LLM_MODEL else "(not set)",
            "llm_timeout_seconds": self.LLM_TIMEOUT_SECONDS,
            "llm_temperature": self.LLM_TEMPERATURE,
            "confidence_threshold": self.CONFIDENCE_THRESHOLD if self.CONFIDENCE_THRESHOLD is not None else "(auto CV-tuned)",
            "embedding_model": self.EMBEDDING_MODEL_NAME,
            "database_url": self.DATABASE_URL.split("?")[0],
        }


settings = Settings()
