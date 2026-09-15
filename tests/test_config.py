from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

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
    monkeypatch.setenv("REPORT_THEME", "light")

    cfg = AppConfig()

    assert cfg.REPORT_THEME == "light"


def test_report_pdf_theme_env_invalid_raises(monkeypatch) -> None:
    monkeypatch.setenv("REPORT_THEME", "sepia")

    with pytest.raises(ValueError, match="REPORT_THEME"):
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
    with open(models_path, encoding="utf-8") as f:
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


def test_max_iterations_is_read_from_the_environment(monkeypatch) -> None:
    """Regression: MAX_ITERATIONS used a class-body default evaluated at import.

    lib.config is imported before load_dotenv() runs, so the .env value was
    silently ignored and the hardcoded 50 always won.
    """
    monkeypatch.setenv("MAX_ITERATIONS", "7")
    assert AppConfig.load().MAX_ITERATIONS == 7

    monkeypatch.delenv("MAX_ITERATIONS", raising=False)
    assert AppConfig.load().MAX_ITERATIONS == 50


def test_out_of_range_limits_are_rejected(monkeypatch) -> None:
    """Semaphore(0) hangs every run silently, so 0 must fail at startup."""
    monkeypatch.setenv("AI_CONCURRENCY_LIMIT", "0")
    with pytest.raises(ValueError, match="AI_CONCURRENCY_LIMIT must be >= 1"):
        AppConfig()

    monkeypatch.delenv("AI_CONCURRENCY_LIMIT")
    monkeypatch.setenv("MAX_ITERATIONS", "0")
    with pytest.raises(ValueError, match="MAX_ITERATIONS must be >= 1"):
        AppConfig()


def test_non_integer_limits_fail_with_an_actionable_message(monkeypatch) -> None:
    monkeypatch.setenv("MAX_ITERATIONS", "not-a-number")
    with pytest.raises(ValueError, match="MAX_ITERATIONS must be an integer"):
        AppConfig.load()
