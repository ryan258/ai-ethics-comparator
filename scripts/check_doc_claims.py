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
    ("tests", r"(\d+)\s+(?:passing\s+)?tests?\b", "test count"),
    ("paradoxes", r"(\d+)\s+paradoxes\b", "scenario count"),
    ("paradoxes", r"(\d+)\s+(?:total\s+)?scenarios\b", "scenario count"),
)

DOCS = ("README.md", "HANDBOOK.md", "ROADMAP.md", "COMPLETION_STATE.md", "paradoxes.md", "docs/UPDATE-IDEAS.md", "docs/101-ways-to-use-this-project-for-fun-and-profit.md")


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
            if line.startswith("Historical:"):
                continue
            if "--host 0.0.0.0" in line or "scripts/pdf_gen_smoke.py" in line:
                failures.append(f"{doc}:{lineno}: retired or unsafe operating recipe")
            for key, pattern, label in CLAIMS:
                for match in re.finditer(pattern, line):
                    claimed = int(match.group(1))
                    if claimed != truth[key]:
                        failures.append(
                            f"{doc}:{lineno}: claims {claimed} for {label}, "
                            f"actual is {truth[key]}\n    {line.strip()}"
                        )

    # Current scenario data must not carry the old output protocol.
    corpus = json.loads((ROOT / "paradoxes.json").read_text())
    from lib.paradoxes import load_paradoxes
    from lib.query_processor import render_options_template
    normalized = load_paradoxes(ROOT / "paradoxes.json")
    for scenario in normalized:
        prompt, _ = render_options_template(scenario)
        if "exactly five lines" in prompt or prompt.count("**Output Contract (Strict):**") != 1:
            failures.append(f"Scenario {scenario['id']} has competing output instructions")
    titles = [item["title"] for item in corpus]
    if len(titles) != len(set(titles)):
        failures.append("Scenario titles must be disambiguated")
    if any(not item.get("category") for item in corpus):
        failures.append("Scenario category missing")

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
