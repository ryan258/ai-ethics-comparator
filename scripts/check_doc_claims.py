#!/usr/bin/env python3
"""Fail if the docs state a countable claim that is no longer true.

Two consecutive "align the docs" commits left the docs misaligned, because
alignment was checked by reading rather than by running. The numbers the docs
quote -- test count, scenario count -- are derivable from the repo, so derive
them and diff.

Usage: uv run python scripts/check_doc_claims.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (regex capturing one number, human description). Every occurrence across the
# doc set must equal the derived truth.
CLAIMS = (
    ("tests", r"(\d+)\s+tests?\b", "test count"),
    ("paradoxes", r"(\d+)\s+paradoxes\b", "scenario count"),
    ("paradoxes", r"(\d+)\s+(?:total\s+)?scenarios\b", "scenario count"),
)

DOCS = ("README.md", "HANDBOOK.md", "ROADMAP.md", "COMPLETION_STATE.md", "docs/UPDATE-IDEAS.md")


def actual_test_count() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    match = re.search(r"(\d+)\s+tests? collected", out)
    if not match:
        raise SystemExit("could not determine test count from pytest --collect-only")
    return int(match.group(1))


def actual_paradox_count() -> int:
    data = json.loads((ROOT / "paradoxes.json").read_text())
    return len(data if isinstance(data, list) else data.get("paradoxes", []))


def version_mismatch() -> str | None:
    """The app version lives in two files; they must agree.

    `pyproject.toml` is the package version, `AppConfig.VERSION` is what `/health`
    and the `X-App-Version` header report. Nothing linked them.
    """
    import tomllib

    from lib.config import AppConfig

    packaged = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    served = AppConfig.model_fields["VERSION"].default
    if packaged != served:
        return (
            f"version mismatch: pyproject.toml says {packaged}, "
            f"lib/config.py AppConfig.VERSION says {served}"
        )
    return None


def main() -> int:
    from lib.config import AppConfig

    truth = {"tests": actual_test_count(), "paradoxes": actual_paradox_count()}
    failures: list[str] = []

    mismatch = version_mismatch()
    if mismatch:
        failures.append(mismatch)

    for doc in DOCS:
        path = ROOT / doc
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for key, pattern, label in CLAIMS:
                for match in re.finditer(pattern, line):
                    claimed = int(match.group(1))
                    if claimed != truth[key]:
                        failures.append(
                            f"{doc}:{lineno}: claims {claimed} for {label}, "
                            f"actual is {truth[key]}\n    {line.strip()}"
                        )

    if failures:
        print("Documentation drift detected:\n")
        print("\n".join(failures))
        print(f"\n{len(failures)} stale claim(s). Update the docs or the code.")
        return 1

    print(
        f"Doc claims OK -- {truth['tests']} tests, {truth['paradoxes']} scenarios, "
        f"version {AppConfig.model_fields['VERSION'].default}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
