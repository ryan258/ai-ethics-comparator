"""
JSON Extraction - Arsenal Module
Recovers a JSON object from model output that may be fenced, prefixed with
prose, or wrapped in commentary.
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(response_text: str) -> dict[str, Any] | None:
    """Extract and parse the first usable JSON object from raw model text.

    Candidates are tried most-likely-first: the whole string, a fenced block,
    the outermost brace span, then a scan for the first decodable object.
    """
    if not isinstance(response_text, str):
        return None

    text = response_text.strip()
    candidates: list[str] = [text]

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1).strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    # Fallback: scan for the first decodable JSON object in mixed content.
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
