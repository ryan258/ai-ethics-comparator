"""Regression tests for D-05: the scenario library needs a controlled vocabulary.

`category` is free-text provenance -- 47 of 197 scenarios had none, and 77
distinct values covered 197 items, so nothing could be grouped by the ethical
tension a scenario actually stresses. `dimensions` is the closed vocabulary that
fixes it, and membership is enforced at load so a typo cannot silently create an
eighth dimension nothing aggregates on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.paradoxes import (
    ETHICAL_DIMENSIONS,
    clear_paradox_cache,
    load_paradoxes,
)

PARADOXES_PATH = Path(__file__).resolve().parent.parent / "paradoxes.json"


def _valid_paradox(**overrides) -> dict:
    base = {
        "id": "dim_test",
        "title": "Dimension Test",
        "type": "trolley",
        "promptTemplate": "Choose.\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "a"},
            {"id": 2, "label": "B", "description": "b"},
        ],
    }
    base.update(overrides)
    return base


def _write(tmp_path: Path, paradoxes: list[dict]) -> Path:
    path = tmp_path / "paradoxes.json"
    path.write_text(json.dumps(paradoxes))
    clear_paradox_cache()
    return path


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_paradox_cache()
    yield
    clear_paradox_cache()


# --- validation ----------------------------------------------------------


def test_valid_dimensions_are_loaded(tmp_path: Path) -> None:
    path = _write(tmp_path, [_valid_paradox(dimensions=["Duty", "Consequence"])])
    assert load_paradoxes(path)[0]["dimensions"] == ["Duty", "Consequence"]


def test_unknown_dimension_fails_at_load(tmp_path: Path) -> None:
    """A typo must fail loudly, not create a dimension nothing aggregates on."""
    path = _write(tmp_path, [_valid_paradox(dimensions=["Duty", "Utilitarianism"])])

    with pytest.raises(ValueError, match="unknown dimension"):
        load_paradoxes(path)


def test_empty_dimensions_list_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, [_valid_paradox(dimensions=[])])

    with pytest.raises(ValueError, match="non-empty list"):
        load_paradoxes(path)


def test_dimensions_are_deduplicated_preserving_order(tmp_path: Path) -> None:
    path = _write(tmp_path, [_valid_paradox(dimensions=["Duty", "Consequence", "Duty"])])
    assert load_paradoxes(path)[0]["dimensions"] == ["Duty", "Consequence"]


def test_dimensions_remain_optional(tmp_path: Path) -> None:
    """Scenarios authored before the vocabulary must still load."""
    path = _write(tmp_path, [_valid_paradox()])
    assert "dimensions" not in load_paradoxes(path)[0]


# --- the shipped library -------------------------------------------------


def test_every_shipped_scenario_carries_dimensions() -> None:
    paradoxes = load_paradoxes(PARADOXES_PATH)

    missing = [p["id"] for p in paradoxes if not p.get("dimensions")]
    assert not missing, f"{len(missing)} scenarios have no dimensions: {missing[:5]}"


def test_shipped_dimensions_are_all_in_the_vocabulary() -> None:
    paradoxes = load_paradoxes(PARADOXES_PATH)

    used = {d for p in paradoxes for d in p.get("dimensions", [])}
    assert used <= set(ETHICAL_DIMENSIONS)


def test_no_dimension_saturates_the_library() -> None:
    """A dimension on nearly every scenario cannot stratify anything.

    This is the same failure D-02 fixed in the fingerprint: a metric pinned near
    its ceiling looks confident and discriminates nothing. Pinning it here stops
    a future lexicon edit from quietly reintroducing it.
    """
    paradoxes = load_paradoxes(PARADOXES_PATH)
    total = len(paradoxes)

    for dimension in ETHICAL_DIMENSIONS:
        share = sum(1 for p in paradoxes if dimension in p.get("dimensions", [])) / total
        assert share < 0.85, (
            f"{dimension} covers {share:.0%} of the library -- too broad to "
            "stratify by. Tighten its lexicon in scripts/backfill_dimensions.py."
        )


def test_every_dimension_is_represented() -> None:
    """An unused dimension is a gap in the corpus worth knowing about."""
    paradoxes = load_paradoxes(PARADOXES_PATH)
    used = {d for p in paradoxes for d in p.get("dimensions", [])}

    assert set(ETHICAL_DIMENSIONS) - used == set()


def test_dimension_vocabulary_matches_the_analyst_prompt() -> None:
    """The point of reusing the analyst's labels is direct comparability.

    If the prompt's allowed labels drift from ETHICAL_DIMENSIONS, scenario
    design and fingerprint output stop lining up and cross-referencing them
    becomes meaningless.
    """
    prompt = (Path(__file__).resolve().parent.parent / "templates" / "analysis_prompt.txt").read_text()

    for dimension in ETHICAL_DIMENSIONS:
        assert dimension in prompt, (
            f"{dimension!r} is in ETHICAL_DIMENSIONS but not offered to the analyst"
        )
