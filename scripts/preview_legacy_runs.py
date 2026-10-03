#!/usr/bin/env python3
"""Read-only migration preview. Does not load credentials, mutate files, or call models."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.evidence import selected_insight
from lib.measurements import RunRecord


def preview(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    paths = sorted(set(root.glob("*.json")) | set(root.glob("*/run.json")))
    for path in paths:
        item: dict[str, object] = {"file": str(path), "action": "preserve original"}
        try:
            data = json.loads(path.read_text())
            record = RunRecord.model_validate(data)
            item.update(runId=record.runId or path.stem, status=record.status or "unknown",
                        recorded=len(record.responses), requested=record.iterationCount)
            missing = []
            for key in ("status", "paradox", "schemaVersion", "protocolVersion", "shuffleSeed"):
                if data.get(key) is None:
                    missing.append(key)
            item.update(missingFacts=missing, currentAnalysis=selected_insight(data) is not None)
            item["nextAction"] = "Keep unknown historical facts; new analysis is optional and costs provider calls."
        except (ValueError, OSError) as exc:
            item.update(error=str(exc), nextAction="Inspect this individual file; excluded from normal consumption without deleting it.")
        records.append(item)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent / "results")
    args = parser.parse_args()
    print(json.dumps(preview(args.root), indent=2))


if __name__ == "__main__":
    main()
