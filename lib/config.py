"""
Configuration - Arsenal Module
Typed configuration management using Pydantic Settings
"""

import os
import json
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

# Strict Candlelight Palette (Reference)
# Background: #121212
# Text: #EBD2BE
# Accents: #A6ACCD, #98C379, #E06C75

class ModelConfig(BaseModel):
    id: str
    name: str


def _normalize_model_entries(entries: object, source_name: str) -> List[ModelConfig]:
    """Normalize model entries to typed ModelConfig objects."""
    if not isinstance(entries, list):
        raise ValueError(f"{source_name} must contain a JSON array.")

    models: List[ModelConfig] = []
    for idx, entry in enumerate(entries):
        if isinstance(entry, str):
            model_id = entry.strip()
            if not model_id:
                raise ValueError(f"{source_name} contains an empty model ID at index {idx}.")
            models.append(ModelConfig(id=model_id, name=model_id))
            continue

        if isinstance(entry, dict):
            try:
                models.append(ModelConfig(**entry))
            except ValidationError as exc:
                raise ValueError(f"Invalid model entry in {source_name} at index {idx}.") from exc
            continue

        raise ValueError(
            f"{source_name} entries must be strings or objects with 'id' and 'name'."
        )

    return models


def _parse_models_env_var(env_name: str) -> Optional[List[ModelConfig]]:
    """Parse model list from a JSON-array env var."""
    raw = os.getenv(env_name)
    if raw is None:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_name} must be valid JSON.") from exc

    return _normalize_model_entries(parsed, env_name)


def _env_bool(name: str, default: bool) -> bool:
    """Parse common boolean env formats with a strict fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be one of: true/false, 1/0, yes/no, on/off"
    )


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    """Parse a constrained string env var."""
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in allowed:
        return normalized

    allowed_values = ", ".join(sorted(allowed))
    raise ValueError(f"{name} must be one of: {allowed_values}")


class AppConfig(BaseModel):
    # App Identity
    APP_NAME: str = "AI Ethics Comparator"
    VERSION: str = "6.0.0"

    # AI Service Config
    AI_CONCURRENCY_LIMIT: int = Field(default_factory=lambda: int(os.getenv("AI_CONCURRENCY_LIMIT", "2")))
    AI_MAX_RETRIES: int = Field(default_factory=lambda: int(os.getenv("AI_MAX_RETRIES", "5")))
    AI_RETRY_DELAY: int = Field(default_factory=lambda: int(os.getenv("AI_RETRY_DELAY", "2")))
    AI_CHOICE_INFERENCE_ENABLED: bool = Field(
        default_factory=lambda: _env_bool("AI_CHOICE_INFERENCE_ENABLED", True)
    )
    REPORT_PDF_THEME: Literal["dark", "light"] = Field(
        default_factory=lambda: _env_choice("REPORT_PDF_THEME", "dark", {"dark", "light"})
    )
    
    # Limits
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "50"))

    # URLs (required - no hardcoded defaults)
    APP_BASE_URL: Optional[str] = Field(default_factory=lambda: os.getenv("APP_BASE_URL"))
    OPENROUTER_BASE_URL: Optional[str] = Field(default_factory=lambda: os.getenv("OPENROUTER_BASE_URL"))

    # Secrets
    OPENROUTER_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY"))

    def validate_secrets(self) -> None:
        """Validate that required environment variables are present."""
        if not self.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY not found in environment. "
                "Please create a .env file with: OPENROUTER_API_KEY=sk-or-your-key"
            )

        if not self.APP_BASE_URL:
            raise ValueError(
                "APP_BASE_URL not found in environment. "
                "Please add to .env: APP_BASE_URL=http://localhost:8000"
            )

        if not self.OPENROUTER_BASE_URL:
            raise ValueError(
                "OPENROUTER_BASE_URL not found in environment. "
                "Please add to .env: OPENROUTER_BASE_URL=https://openrouter.ai/api/v1"
            )
    
    # Models (Loaded from env JSON or file)
    AVAILABLE_MODELS: List[ModelConfig] = Field(default_factory=list)
    ANALYST_MODEL: Optional[str] = Field(default_factory=lambda: os.getenv("ANALYST_MODEL"))
    DEFAULT_MODEL: Optional[str] = Field(default_factory=lambda: os.getenv("DEFAULT_MODEL"))

    @property
    def results_path(self) -> Path:
        return Path(__file__).parent.parent / "results"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from environment and files."""
        # Initialize with env vars
        config = cls()

        # Model source priority:
        # 1) models.json (repo source of truth)
        # 2) OPENROUTER_MODELS (env fallback)
        # 3) AVAILABLE_MODELS_JSON (legacy env fallback)
        models_path = Path(__file__).parent.parent / "models.json"
        if models_path.exists():
            try:
                with open(models_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config.AVAILABLE_MODELS = _normalize_model_entries(data, models_path.name)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {models_path.name}.") from exc
        else:
            openrouter_models = _parse_models_env_var("OPENROUTER_MODELS")
            if openrouter_models is not None:
                config.AVAILABLE_MODELS = openrouter_models
            else:
                available_models_json = _parse_models_env_var("AVAILABLE_MODELS_JSON")
                if available_models_json is not None:
                    config.AVAILABLE_MODELS = available_models_json

        # Smart defaults for models
        if not config.ANALYST_MODEL and config.AVAILABLE_MODELS:
            config.ANALYST_MODEL = config.AVAILABLE_MODELS[0].id
        
        if not config.DEFAULT_MODEL and config.AVAILABLE_MODELS:
            config.DEFAULT_MODEL = config.AVAILABLE_MODELS[0].id
            
        return config
