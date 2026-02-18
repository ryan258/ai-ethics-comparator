from __future__ import annotations

import io
import pytest
from pathlib import Path

from lib.config import AppConfig


def test_choice_inference_env_false_parses_to_false(monkeypatch) -> None:
    monkeypatch.setenv("AI_CHOICE_INFERENCE_ENABLED", "false")

    cfg = AppConfig()

    assert cfg.AI_CHOICE_INFERENCE_ENABLED is False


def test_choice_inference_env_invalid_raises(monkeypatch) -> None:
    monkeypatch.setenv("AI_CHOICE_INFERENCE_ENABLED", "maybe")

    with pytest.raises(ValueError, match="AI_CHOICE_INFERENCE_ENABLED"):
        AppConfig()


def test_models_json_is_primary_source(monkeypatch) -> None:
    monkeypatch.setenv(
        "OPENROUTER_MODELS",
        '["nvidia/nemotron-3-nano-30b-a3b:free","openai/gpt-4o-mini"]',
    )
    monkeypatch.delenv("AVAILABLE_MODELS_JSON", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("ANALYST_MODEL", raising=False)

    cfg = AppConfig.load()

    assert cfg.AVAILABLE_MODELS
    assert cfg.AVAILABLE_MODELS[0].id == "openrouter/aurora-alpha"


def test_openrouter_models_env_used_when_models_json_missing(monkeypatch) -> None:
    monkeypatch.setenv(
        "OPENROUTER_MODELS",
        '["nvidia/nemotron-3-nano-30b-a3b:free","openai/gpt-4o-mini"]',
    )
    monkeypatch.delenv("AVAILABLE_MODELS_JSON", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("ANALYST_MODEL", raising=False)

    original_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if self.name == "models.json":
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    cfg = AppConfig.load()

    assert [model.id for model in cfg.AVAILABLE_MODELS] == [
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "openai/gpt-4o-mini",
    ]
    assert cfg.DEFAULT_MODEL == "nvidia/nemotron-3-nano-30b-a3b:free"
    assert cfg.ANALYST_MODEL == "nvidia/nemotron-3-nano-30b-a3b:free"


def test_openrouter_models_env_invalid_json_raises_when_models_json_missing(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_MODELS", "not-json")
    monkeypatch.delenv("AVAILABLE_MODELS_JSON", raising=False)

    original_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if self.name == "models.json":
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)

    with pytest.raises(ValueError, match="OPENROUTER_MODELS must be valid JSON"):
        AppConfig.load()


def test_empty_models_json_loads_as_empty_model_list(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("AVAILABLE_MODELS_JSON", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("ANALYST_MODEL", raising=False)

    original_exists = Path.exists

    def fake_exists(self: Path) -> bool:
        if self.name == "models.json":
            return True
        return original_exists(self)

    original_open = open

    def fake_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if Path(path).name == "models.json":
            return io.StringIO("[]")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr("builtins.open", fake_open)

    cfg = AppConfig.load()

    assert cfg.AVAILABLE_MODELS == []
    assert cfg.DEFAULT_MODEL is None
    assert cfg.ANALYST_MODEL is None
