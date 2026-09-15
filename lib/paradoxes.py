"""
Paradoxes - Arsenal Module
Centralized paradox loading and validation.
Copy-paste ready, zero dependencies on project.
"""
import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class OptionDict(TypedDict):
    """Single option in N-way paradox"""
    id: int
    label: str
    description: str


class ParadoxBase(TypedDict):
    """N-way paradox schema"""
    id: str
    title: str
    promptTemplate: str
    options: list[OptionDict]


class Paradox(ParadoxBase, total=False):
    type: str
    category: str
    dimensions: list[str]
    rubric: list[str]


# Closed vocabulary for `dimensions` -- the ethical tension a scenario puts
# under load. Deliberately the SAME seven labels the analyst prompt scores
# (templates/analysis_prompt.txt), so scenario design and fingerprint output
# are directly comparable: you can ask "how does this model handle the
# scenarios built to stress Duty?" and compare it against the model's measured
# Duty dominance.
#
# `category` remains free-text provenance ("Aesop", "Authored: Epistemic
# Ethics"); it is NOT a grouping key and never was one -- 47 of 197 scenarios
# had none at all, and 77 distinct values covered 197 items.
ETHICAL_DIMENSIONS: tuple[str, ...] = (
    "Duty",
    "Consequence",
    "Purity",
    "Authority",
    "Compassion",
    "Risk-aversion",
    "Legalism",
)


_REQUIRED_KEYS: tuple[str, ...] = (
    "id",
    "title",
    "promptTemplate",
    "options",
)


def _normalize_paradox(item: object) -> Paradox | None:
    """Validate and normalize paradox (supports both binary and N-way schemas)"""
    if not isinstance(item, dict):
        return None

    # Validate required string fields
    id_val = item.get("id")
    title_val = item.get("title")
    prompt_val = item.get("promptTemplate")

    if not isinstance(id_val, str) or not isinstance(title_val, str) or not isinstance(prompt_val, str):
        return None

    validated_options: list[OptionDict] = []

    # Check for N-way schema (new format with options[] array)
    options_val = item.get("options")
    if options_val is not None:
        # N-way schema validation
        if not isinstance(options_val, list) or len(options_val) < 2 or len(options_val) > 4:
            return None

        # Validate each option structure
        for opt in options_val:
            if not isinstance(opt, dict):
                return None

            opt_id = opt.get("id")
            opt_label = opt.get("label")
            opt_desc = opt.get("description")

            if type(opt_id) is not int or not isinstance(opt_label, str) or not isinstance(opt_desc, str):
                return None

            if opt_id < 1 or opt_id > 4:
                return None

            validated_options.append({
                "id": opt_id,
                "label": opt_label,
                "description": opt_desc
            })
    else:
        # Binary schema fallback (old format with group1Default/group2Default)
        group1 = item.get("group1Default")
        group2 = item.get("group2Default")

        if not isinstance(group1, str) or not isinstance(group2, str):
            return None

        # Convert binary to N-way format
        validated_options = [
            {"id": 1, "label": "Option 1", "description": group1},
            {"id": 2, "label": "Option 2", "description": group2}
        ]

    if sorted(o["id"] for o in validated_options) != list(range(1, len(validated_options) + 1)):
        return None

    result: Paradox = {
        "id": id_val,
        "title": title_val,
        "promptTemplate": prompt_val,
        "options": validated_options,
    }

    # Optional fields
    type_value = item.get("type")
    if isinstance(type_value, str):
        result["type"] = type_value

    category_value = item.get("category")
    if isinstance(category_value, str):
        result["category"] = category_value

    # Membership is enforced, not coerced: a typo must fail loudly at load
    # rather than silently creating an eighth dimension nothing aggregates on.
    dimensions_value = item.get("dimensions")
    if dimensions_value is not None:
        if not isinstance(dimensions_value, list) or not dimensions_value:
            raise ValueError(
                f"Paradox {id_val!r}: 'dimensions' must be a non-empty list"
            )
        unknown = [d for d in dimensions_value if d not in ETHICAL_DIMENSIONS]
        if unknown:
            raise ValueError(
                f"Paradox {id_val!r}: unknown dimension(s) {unknown}. "
                f"Allowed: {', '.join(ETHICAL_DIMENSIONS)}"
            )
        # De-duplicate while preserving the authored order.
        result["dimensions"] = list(dict.fromkeys(dimensions_value))

    rubric_value = item.get("rubric")
    if isinstance(rubric_value, list):
        result["rubric"] = [str(r) for r in rubric_value]

    return result


@lru_cache(maxsize=1)
def _load_paradoxes_cached(paradoxes_path: str) -> tuple[Paradox, ...]:
    with open(paradoxes_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Paradoxes JSON must be a list.")

    normalized: list[Paradox] = []
    for item in data:
        paradox = _normalize_paradox(item)
        if paradox is None:
            raise ValueError("Invalid paradox entry in JSON.")
        if any(p["id"] == paradox["id"] for p in normalized):
            raise ValueError(f"Duplicate paradox ID: {paradox['id']}")
        normalized.append(paradox)

    return tuple(normalized)


def load_paradoxes(paradoxes_path: Path) -> list[Paradox]:
    """Load and return validated paradoxes from JSON file.

    Returns a deep copy: the cache is process-wide, so handing out the cached
    dicts would let any caller mutating a paradox poison every later request.
    """
    return copy.deepcopy(list(_load_paradoxes_cached(str(paradoxes_path))))


def clear_paradox_cache() -> None:
    """Clear the LRU cache for paradox loading (dev utility)."""
    _load_paradoxes_cached.cache_clear()


def get_paradox_by_id(paradoxes: list[Paradox], paradox_id: str) -> Paradox | None:
    """Safely find paradox by ID."""
    for paradox in paradoxes:
        if paradox["id"] == paradox_id:
            return paradox
    return None


def resolve_paradox(
    run_data: dict,
    paradoxes: list[Paradox],
) -> Paradox:
    """Resolve immutable execution evidence; live edits never rewrite history.

    Legacy records are reconstructed from their persisted prompt and options.
    Applying an edited scenario requires a new run, linked by predecessorRunId.
    """
    paradox_id = run_data.get("paradoxId")

    snapshot = run_data.get("paradox")
    if isinstance(snapshot, dict) and snapshot.get("id"):
        return copy.deepcopy(snapshot)  # type: ignore[return-value]

    title = run_data.get("paradoxTitle") or paradox_id or "Unknown Dilemma"
    options = run_data.get("options")
    return {  # type: ignore[return-value]
        "id": str(paradox_id or "unknown"),
        "title": str(title),
        "category": str(run_data.get("paradoxCategory") or "General Ethics"),
        "promptTemplate": str(run_data.get("prompt") or ""),
        "options": copy.deepcopy(options) if isinstance(options, list) else [],
        "type": str(run_data.get("paradoxType") or "trolley"),
    }


def extract_scenario_text(prompt_template: str) -> str:
    """Safely extract scenario text before Instructions."""
    if not prompt_template:
        return ""

    parts = prompt_template.split("**Instructions**")
    return parts[0].strip() if parts else prompt_template.strip()
