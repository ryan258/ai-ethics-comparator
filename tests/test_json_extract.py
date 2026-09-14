"""
Tests for lib.json_extract module.
Verifies JSON recovery from fenced, prefixed, and mixed model outputs.
"""

from __future__ import annotations

from lib.json_extract import extract_json_object


def test_extract_json_object_direct() -> None:
    raw = '{"option_id": 1, "explanation": "Direct JSON"}'
    parsed = extract_json_object(raw)
    assert parsed == {"option_id": 1, "explanation": "Direct JSON"}


def test_extract_json_object_fenced() -> None:
    raw_json_tag = '```json\n{"option_id": 2, "explanation": "Fenced JSON"}\n```'
    assert extract_json_object(raw_json_tag) == {"option_id": 2, "explanation": "Fenced JSON"}

    raw_no_tag = '```\n{"option_id": 3, "explanation": "Plain fence"}\n```'
    assert extract_json_object(raw_no_tag) == {"option_id": 3, "explanation": "Plain fence"}


def test_extract_json_object_surrounding_prose() -> None:
    raw = (
        "Here is my decision on this scenario:\n\n"
        '{"option_id": 4, "explanation": "Wrapped in commentary"}\n\n'
        "I hope this fulfills the requirements."
    )
    assert extract_json_object(raw) == {"option_id": 4, "explanation": "Wrapped in commentary"}


def test_extract_json_object_mixed_and_multiple() -> None:
    raw = 'Some thought prefix {not valid json} but then {"option_id": 1, "valid": true}'
    parsed = extract_json_object(raw)
    assert parsed == {"option_id": 1, "valid": True}


def test_extract_json_object_invalid_inputs() -> None:
    # Non-string input
    assert extract_json_object(None) is None  # type: ignore[arg-type]
    assert extract_json_object(123) is None  # type: ignore[arg-type]

    # Non-JSON prose
    assert extract_json_object("Just plain commentary with no braces.") is None

    # Broken braces
    assert extract_json_object("{unclosed brace") is None

    # Top-level array should not be returned as an object dict
    assert extract_json_object("[1, 2, 3]") is None
