#!/usr/bin/env python3
"""Assign `dimensions` to every scenario in paradoxes.json.

D-05: `category` encodes provenance ("Aesop", "Authored: Epistemic Ethics"),
not ethical content -- 47 of 197 scenarios had none at all and 77 distinct
values covered 197 items, so nothing could be stratified by the tension a
scenario actually puts under load.

`dimensions` fixes that with the closed vocabulary in `lib.paradoxes`. This
script produces the FIRST PASS by scoring each scenario's title and option text
against an explicit lexicon. The lexicon is deliberately visible and editable:
this is a heuristic, and the assignments it produces are meant to be reviewed
and corrected by hand, not trusted blindly.

    uv run python scripts/backfill_dimensions.py --dry-run   # report only
    uv run python scripts/backfill_dimensions.py             # write the file

Re-running is safe: scenarios that already carry `dimensions` are left alone
unless --overwrite is passed, so hand corrections survive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.paradoxes import ETHICAL_DIMENSIONS  # noqa: E402

PARADOXES_PATH = Path(__file__).resolve().parent.parent / "paradoxes.json"

# Marker terms per dimension. Matched as word-prefixes against lowercased text.
LEXICON: dict[str, tuple[str, ...]] = {
    "Duty": (
        "duty", "duties", "obligation", "obliged", "promise", "oath", "pledge",
        "vow", "commitment", "committed", "loyal", "loyalty", "betray", "owe",
        "owed", "responsibility", "responsible", "fiduciary", "steward",
    ),
    "Consequence": (
        "minimize", "minimise", "maximize", "maximise", "outcome", "net",
        "cost-benefit", "utility", "greater good", "aggregate", "casualt",
        "lives saved", "harm reduction", "efficien", "yield", "throughput",
        "total harm", "overall benefit", "payoff", "trade-off", "tradeoff",
    ),
    "Purity": (
        "sacred", "desecrat", "dignity", "taboo", "defil", "sanctity",
        "purity", "contaminat", "corrupt", "unnatural", "natural order",
        "violat", "profane", "untouched", "pristine",
    ),
    "Authority": (
        "authority", "chain of command", "order", "hierarch", "jurisdiction",
        "mandate", "govern", "official", "command", "sovereign", "institution",
        "oversight", "council", "board", "committee", "regulator", "supervisor",
        "custody", "control transfer",
    ),
    "Compassion": (
        "suffer", "mercy", "compassion", "care", "vulnerable", "kindness",
        "empath", "comfort", "grief", "child", "patient", "elderly",
        "dying", "pain", "relief", "humane", "dignified death",
    ),
    "Risk-aversion": (
        "risk", "uncertain", "precaution", "safeguard", "worst-case",
        "hedge", "catastroph", "irreversib", "contain", "fail-safe",
        "caution", "delay", "sandbox", "monitor", "safety margin",
        "unknown", "probability", "unproven",
    ),
    "Legalism": (
        "law", "lawful", "legal", "illegal", "rule", "regulat", "statute",
        "contract", "policy", "compliance", "procedur", "protocol",
        "due process", "rights", "court", "treaty", "license", "permit",
        "consent form", "audit",
    ),
}

MIN_DIMENSIONS = 2
MAX_DIMENSIONS = 3


def scenario_text(paradox: dict) -> str:
    """Title and options only.

    The promptTemplate is deliberately excluded: it carries shared instruction
    boilerplate ("weigh the trade-off", "consider the risk") that is identical
    across the corpus, so scoring it made Consequence and Risk-aversion match
    191 of 197 scenarios -- the same saturation failure as D-02.
    """
    return " ".join(
        [
            str(paradox.get("title", "")),
            *[
                f"{o.get('label', '')} {o.get('description', '')}"
                for o in paradox.get("options", [])
                if isinstance(o, dict)
            ],
        ]
    )


def score(text: str) -> Counter[str]:
    lowered = text.lower()
    scores: Counter[str] = Counter()
    for dimension, markers in LEXICON.items():
        for marker in markers:
            hits = len(re.findall(r"\b" + re.escape(marker), lowered))
            if hits:
                scores[dimension] += hits
    return scores


def assign_all(paradoxes: list[dict]) -> dict[str, list[str]]:
    """Assign by corpus-relative lift, not absolute frequency.

    A dimension that fires on nearly every scenario carries no stratifying
    information no matter how often it is mentioned. What matters is whether
    THIS scenario leans on a tension more than the corpus baseline does.
    """
    raw = {p["id"]: score(scenario_text(p)) for p in paradoxes}

    baseline = {
        dimension: (sum(s[dimension] for s in raw.values()) / len(raw)) or 1.0
        for dimension in ETHICAL_DIMENSIONS
    }

    assignments: dict[str, list[str]] = {}
    for paradox in paradoxes:
        scores = raw[paradox["id"]]
        lift = {
            dimension: scores[dimension] / baseline[dimension]
            for dimension in ETHICAL_DIMENSIONS
            if scores[dimension] > 0
        }
        ranked = sorted(lift, key=lambda d: (-lift[d], -scores[d], d))
        chosen = [d for d in ranked if lift[d] >= 1.0][:MAX_DIMENSIONS]

        # Fall back to the strongest raw signals when nothing clears baseline.
        if len(chosen) < MIN_DIMENSIONS:
            for dimension in ranked:
                if dimension not in chosen:
                    chosen.append(dimension)
                if len(chosen) >= MIN_DIMENSIONS:
                    break
        for fallback in ("Consequence", "Duty"):
            if len(chosen) >= MIN_DIMENSIONS:
                break
            if fallback not in chosen:
                chosen.append(fallback)

        assignments[paradox["id"]] = chosen[:MAX_DIMENSIONS]
    return assignments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true",
                        help="re-assign scenarios that already have dimensions")
    args = parser.parse_args()

    paradoxes = json.loads(PARADOXES_PATH.read_text())

    assignments = assign_all(paradoxes)

    assigned = 0
    skipped = 0
    histogram: Counter[str] = Counter()

    for paradox in paradoxes:
        if paradox.get("dimensions") and not args.overwrite:
            skipped += 1
            histogram.update(paradox["dimensions"])
            continue
        dimensions = assignments[paradox["id"]]
        assert all(d in ETHICAL_DIMENSIONS for d in dimensions)
        paradox["dimensions"] = dimensions
        histogram.update(dimensions)
        assigned += 1

    print(f"assigned {assigned}, kept existing {skipped}, total {len(paradoxes)}\n")
    print("dimension coverage (share of scenarios):")
    peak = max(histogram.values()) if histogram else 1
    for dimension in ETHICAL_DIMENSIONS:
        count = histogram[dimension]
        bar = "#" * round(count / peak * 36)
        print(f"  {dimension:<15} {count:>4}  {count / len(paradoxes):>5.0%}  {bar}")

    if args.dry_run:
        print("\n(dry run -- nothing written)")
        return 0

    PARADOXES_PATH.write_text(json.dumps(paradoxes, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {PARADOXES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
