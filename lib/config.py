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
    
    # URLs
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    
    # Secrets
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")

    def __init__(self, **data):
        super().__init__(**data)
        # Validate required environment variables
        if not self.OPENROUTER_API_KEY:
            import sys
            print("ERROR: OPENROUTER_API_KEY not found in environment", file=sys.stderr)
            print("Please create a .env file with: OPENROUTER_API_KEY=sk-or-your-key", file=sys.stderr)
            sys.exit(1)
    
    # Models (Loaded from env JSON or file)
    AVAILABLE_MODELS: List[ModelConfig] = Field(default_factory=list)
    ANALYST_MODEL: Optional[str] = os.getenv("ANALYST_MODEL")
    DEFAULT_MODEL: Optional[str] = os.getenv("DEFAULT_MODEL")

    @property
    def results_path(self):
        from pathlib import Path
        return Path(__file__).parent.parent / "results"

# Singleton
config = AppConfig()

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

# Ensure analyst model has a fallback from available models if possible, but no hardcoded string here
if not config.ANALYST_MODEL and config.AVAILABLE_MODELS:
    config.ANALYST_MODEL = config.AVAILABLE_MODELS[0].id

if not config.DEFAULT_MODEL and config.AVAILABLE_MODELS:
    config.DEFAULT_MODEL = config.AVAILABLE_MODELS[0].id
