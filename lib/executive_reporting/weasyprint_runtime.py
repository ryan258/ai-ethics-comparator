"""
Shared WeasyPrint runtime loading helpers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _candidate_macos_library_dirs() -> list[str]:
    return [
        str(path)
        for path in (Path("/opt/homebrew/lib"), Path("/usr/local/lib"))
        if path.exists()
    ]


def ensure_weasyprint_runtime_environment() -> None:
    """Help CFFI find Homebrew GTK/Pango libraries on macOS."""
    if sys.platform != "darwin":
        return

    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    search_paths = [segment for segment in existing.split(":") if segment]

    for candidate in reversed(_candidate_macos_library_dirs()):
        if candidate not in search_paths:
            search_paths.insert(0, candidate)

    if search_paths:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(search_paths)


def load_weasyprint_html() -> tuple[Any | None, Exception | None]:
    """Import WeasyPrint's HTML class after preparing the runtime environment."""
    ensure_weasyprint_runtime_environment()
    try:
        from weasyprint import HTML as weasyprint_html
    except (ModuleNotFoundError, OSError) as exc:  # pragma: no cover - optional dependency guard
        return None, exc
    return weasyprint_html, None
