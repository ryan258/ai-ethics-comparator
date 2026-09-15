"""
Prompt Template Loading - Arsenal Module
Single cached reader for the on-disk prompt templates.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def read_prompt_template(path: str) -> str | None:
    """Read a prompt template once per process.

    These files do not change at runtime, and re-reading them inside an async
    request handler put blocking disk I/O on the event loop on every call.

    Returns None when the file is unreadable so callers keep their graceful
    fallback rather than failing the request.
    """
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - any read failure degrades the same
        logger.error("Failed to load prompt template (%s): %s", path, exc)
        return None


def clear_prompt_template_cache() -> None:
    """Drop cached templates (dev utility; mirrors clear_paradox_cache)."""
    read_prompt_template.cache_clear()
