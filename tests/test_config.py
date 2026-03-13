from __future__ import annotations

import io
import json
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


def test_report_pdf_theme_env_parses_to_light(monkeypatch) -> None:
    monkeypatch.setenv("REPORT_PDF_THEME", "light")

    cfg = AppConfig()

    assert cfg.REPORT_PDF_THEME == "light"


def test_report_pdf_theme_env_invalid_raises(monkeypatch) -> None:
    monkeypatch.setenv("REPORT_PDF_THEME", "sepia")

    with pytest.raises(ValueError, match="REPORT_PDF_THEME"):
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
    models_path = Path(__file__).resolve().parent.parent / "models.json"
    with open(models_path, "r", encoding="utf-8") as f:
        expected_models = json.load(f)

    assert cfg.AVAILABLE_MODELS
    assert [model.id for model in cfg.AVAILABLE_MODELS] == [
        entry["id"] if isinstance(entry, dict) else entry for entry in expected_models
    ]


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
