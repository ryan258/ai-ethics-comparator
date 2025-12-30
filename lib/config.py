"""
Configuration - Arsenal Module
Typed configuration management using Pydantic Settings
"""

import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field

# Strict Candlelight Palette (Reference)
# Background: #121212
# Text: #EBD2BE
# Accents: #A6ACCD, #98C379, #E06C75

class ModelConfig(BaseModel):
    id: str
    name: str

class AppConfig(BaseModel):
    # App Identity
    APP_NAME: str = "AI Ethics Comparator"
    VERSION: str = "6.0.0"

    # AI Service Config
    AI_CONCURRENCY_LIMIT: int = 2
    AI_MAX_RETRIES: int = 5
    AI_RETRY_DELAY: int = 2
    
    # Limits
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "20"))

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
    def results_path(self) -> "Path":
        from pathlib import Path
        return Path(__file__).parent.parent / "results"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from environment and files."""
        # Initialize with env vars
        config = cls()
        
        # Load models from file if env not set
        _models_json = os.getenv("AVAILABLE_MODELS_JSON")
        if _models_json:
            try:
                data = json.loads(_models_json)
                config.AVAILABLE_MODELS = [ModelConfig(**m) for m in data]
            except Exception:
                pass
        else:
            # Load from models.json
            try:
                from pathlib import Path
                models_path = Path(__file__).parent.parent / "models.json"
                if models_path.exists():
                     with open(models_path, 'r') as f:
                         data = json.load(f)
                         config.AVAILABLE_MODELS = [ModelConfig(**m) for m in data]
            except Exception:
                pass

        # Smart defaults for models
        if not config.ANALYST_MODEL and config.AVAILABLE_MODELS:
            config.ANALYST_MODEL = config.AVAILABLE_MODELS[0].id
        
        if not config.DEFAULT_MODEL and config.AVAILABLE_MODELS:
            config.DEFAULT_MODEL = config.AVAILABLE_MODELS[0].id
            
        return config
