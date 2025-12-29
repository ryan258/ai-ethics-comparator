"""
Paradoxes - Arsenal Module
Centralized paradox loading and validation.
Copy-paste ready, zero dependencies on project.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict


class ParadoxBase(TypedDict):
    id: str
    title: str
    promptTemplate: str
    group1Default: str
    group2Default: str


class Paradox(ParadoxBase, total=False):
    type: str
    category: str


_REQUIRED_KEYS: Tuple[str, ...] = (
    "id",
    "title",
    "promptTemplate",
    "group1Default",
    "group2Default",
)


def _normalize_paradox(item: object) -> Optional[Paradox]:
    if not isinstance(item, dict):
        return None

    values: Dict[str, str] = {}
    for key in _REQUIRED_KEYS:
        value = item.get(key)
        if not isinstance(value, str):
            return None
        values[key] = value

    result: Paradox = {
        "id": values["id"],
        "title": values["title"],
        "promptTemplate": values["promptTemplate"],
        "group1Default": values["group1Default"],
        "group2Default": values["group2Default"],
    }

    type_value = item.get("type")
    if isinstance(type_value, str):
        result["type"] = type_value

    category_value = item.get("category")
    if isinstance(category_value, str):
        result["category"] = category_value

    return result


@lru_cache(maxsize=1)
def _load_paradoxes_cached(paradoxes_path: str) -> Tuple[Paradox, ...]:
    with open(paradoxes_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Paradoxes JSON must be a list.")

    normalized: List[Paradox] = []
    for item in data:
        paradox = _normalize_paradox(item)
        if paradox is None:
            raise ValueError("Invalid paradox entry in JSON.")
        normalized.append(paradox)

    return tuple(normalized)


def load_paradoxes(paradoxes_path: Path) -> List[Paradox]:
    """Load and return validated paradoxes from JSON file."""
    return list(_load_paradoxes_cached(str(paradoxes_path)))


def clear_paradox_cache() -> None:
    """Clear the LRU cache for paradox loading (dev utility)."""
    _load_paradoxes_cached.cache_clear()


def get_paradox_by_id(paradoxes: List[Paradox], paradox_id: str) -> Optional[Paradox]:
    """Safely find paradox by ID."""
    for paradox in paradoxes:
        if paradox["id"] == paradox_id:
            return paradox
    return None


def extract_scenario_text(prompt_template: str) -> str:
    """Safely extract scenario text before Instructions."""
    if not prompt_template:
        return ""

    parts = prompt_template.split("**Instructions**")
    return parts[0].strip() if parts else prompt_template.strip()
