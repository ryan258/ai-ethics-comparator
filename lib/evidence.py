"""Stable evidence identities and analysis measurement contracts."""
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lib.paradoxes import ETHICAL_DIMENSIONS, resolve_paradox

ANALYSIS_VERSION = 2


class PersistedResponse(BaseModel):
    """Validate consumed response fields; retain provider extensions separately."""
    model_config = ConfigDict(strict=True, extra="allow")
    iteration: int | None = Field(default=None, ge=1)
    optionId: int | None = Field(default=None, ge=1, le=4)
    explanation: str = ""
    raw: str = ""
    decisionToken: str | None = None
    evidenceNeeded: str | None = None
    optionOrder: dict[str, int] | None = None


class SummaryCount(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    count: int = Field(default=0, ge=0)
    percentage: float = Field(default=0, ge=0, le=100)
    id: int | None = Field(default=None, ge=1, le=4)


class RunSummary(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    options: list[SummaryCount] = Field(default_factory=list)
    group1: SummaryCount = Field(default_factory=SummaryCount)
    group2: SummaryCount = Field(default_factory=SummaryCount)
    undecided: SummaryCount = Field(default_factory=SummaryCount)


class ReasoningQuality(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    noticed: list[str]
    missed: list[str]


class MoralComplex(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    label: str
    count: int = Field(ge=0)
    justification: str

    @field_validator("label")
    @classmethod
    def known_label(cls, value: str) -> str:
        if value not in ETHICAL_DIMENSIONS:
            raise ValueError("Unknown moral complex")
        return value


class AnalystOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    dominant_framework: str
    moral_complexes: list[MoralComplex]
    justifications: list[str]
    consistency: list[str]
    key_insights: list[str]


def evidence_hash(run: dict[str, Any]) -> str:
    """Exclude derived artifacts and mutable status timestamps from identity."""
    fields = ("paradoxId", "paradox", "prompt", "options", "params", "systemPrompt",
              "modelName", "responses", "iterationCount", "shuffleMapping", "shufflePerIteration")
    data = {key: run.get(key) for key in fields}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def valid_insight(run: dict[str, Any], insight: dict[str, Any]) -> bool:
    return (insight.get("analysisVersion") == ANALYSIS_VERSION
            and insight.get("evidenceHash") == evidence_hash(run)
            and isinstance(insight.get("content"), dict)
            and "legacy_text" not in insight["content"])


def selected_insight(run: dict[str, Any]) -> dict[str, Any] | None:
    insights = run.get("insights", [])
    if not isinstance(insights, list):
        return None
    return next((i for i in reversed(insights) if isinstance(i, dict) and valid_insight(run, i)), None)


def validate_comparison(runs: list[dict[str, Any]]) -> None:
    """Require identical stored scenario and canonical option meanings."""
    ids = [r.get("runId") for r in runs]
    if len(runs) < 2 or len(ids) != len(set(ids)):
        raise ValueError("Comparison requires distinct runs")
    identities = []
    for run in runs:
        pdx = resolve_paradox(run, [])
        if not pdx["promptTemplate"].strip():
            raise ValueError("Comparison requires stored stimulus evidence")
        identity = {"id": pdx["id"], "stimulus": pdx["promptTemplate"],
                    "options": run.get("options", pdx["options"])}
        identities.append(json.dumps(identity, sort_keys=True))
    if len(set(identities)) != 1:
        raise ValueError("Runs must have the same stored scenario revision and option meanings")
