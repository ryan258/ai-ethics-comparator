"""Pure, shared measurements. Recorded outcomes are the denominator everywhere."""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordedOption(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    id: int = Field(ge=1, le=4)
    label: str = ""
    description: str = ""


class RecordedOutcome(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    iteration: int | None = Field(default=None, ge=1)
    optionId: int | None = Field(default=None, ge=1, le=4)
    explanation: str = ""
    raw: str = ""
    error: str | None = None
    optionOrder: dict[str, int] | None = None


class RunRecord(BaseModel):
    """Read boundary; missing legacy facts remain missing, never inferred as complete."""
    model_config = ConfigDict(strict=True, extra="allow")
    schemaVersion: int | None = Field(default=None, ge=1, le=2)
    runId: str | None = None
    modelName: str = "Unknown"
    status: Literal["pending", "running", "completed", "failed", "interrupted", "cancelled", "unknown"] | None = None
    iterationCount: int | None = Field(default=None, ge=0)
    completedIterations: int | None = Field(default=None, ge=0)
    options: list[RecordedOption] = Field(default_factory=list)
    responses: list[RecordedOutcome] = Field(default_factory=list)
    timestamp: str | None = None
    params: dict[str, object] = Field(default_factory=dict)
    systemPrompt: str | None = None
    insights: list[dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_evidence(self) -> "RunRecord":
        ids = [option.id for option in self.options]
        if ids and sorted(ids) != list(range(1, len(ids) + 1)):
            raise ValueError("Stored option IDs must be unique and sequential")
        iterations = [r.iteration for r in self.responses if r.iteration is not None]
        if len(iterations) != len(set(iterations)):
            raise ValueError("Stored responses contain duplicate iteration IDs")
        if self.iterationCount is not None and (len(self.responses) > self.iterationCount or any(i > self.iterationCount for i in iterations)):
            raise ValueError("Stored responses exceed requested iterations")
        for response in self.responses:
            if ids and response.optionId is not None and response.optionId not in ids:
                raise ValueError("Stored response selects an undefined option")
            if response.optionOrder is not None and ids:
                if set(response.optionOrder) != {str(i) for i in ids} or sorted(response.optionOrder.values()) != sorted(ids):
                    raise ValueError("Stored option order must be a complete permutation")
        if self.schemaVersion == 2:
            if len(iterations) != len(self.responses):
                raise ValueError("Version 2 responses require iteration IDs")
            if self.completedIterations is not None and self.completedIterations != len(self.responses):
                raise ValueError("Stored completed count differs from recorded outcomes")
            if self.status == "completed" and self.iterationCount != len(self.responses):
                raise ValueError("Completed run has missing outcomes")
        return self


@dataclass(frozen=True)
class OptionMeasurement:
    id: int
    label: str
    count: int
    percentage: float


@dataclass(frozen=True)
class RunMeasurements:
    requested: int | None
    recorded: int
    decided: int
    undecided: int
    errored: int
    status: str
    options: tuple[OptionMeasurement, ...]
    limitations: tuple[str, ...]

    @property
    def missing(self) -> int | None:
        return max(0, self.requested - self.recorded) if self.requested is not None else None

    def summary(self) -> dict[str, object]:
        """Compatibility representation, computed only from recorded outcomes."""
        options = [{"id": o.id, "count": o.count, "percentage": o.percentage} for o in self.options]
        return {"total": self.recorded, "options": options, "undecided": {"count": self.undecided,
                "percentage": 100 * self.undecided / self.recorded if self.recorded else 0.0}}


def build_run_measurements(run: object) -> RunMeasurements:
    """Validate and measure a run without I/O, mutations, or model judgments."""
    record = RunRecord.model_validate(run)
    options = record.options
    # Legacy binary records can lack option metadata; IDs are observed, not guessed labels.
    if not options:
        observed = {r.optionId for r in record.responses if r.optionId is not None}
        options = [RecordedOption(id=i, label=f"Option {i}") for i in sorted(observed)]
    count = len(record.responses)
    decided = sum(r.optionId is not None for r in record.responses)
    limitations = []
    if record.status is None:
        limitations.append("Run status was not recorded.")
    if record.schemaVersion is None:
        limitations.append("Legacy record: complete call provenance is unavailable.")
    if not isinstance(run, dict) or not isinstance(run.get("paradox"), dict):
        limitations.append("Original scenario snapshot was not recorded.")
    return RunMeasurements(record.iterationCount, count, decided, count - decided,
        sum(bool(r.error) for r in record.responses), record.status or "unknown",
        tuple(OptionMeasurement(o.id, o.label or f"Option {o.id}",
            sum(r.optionId == o.id for r in record.responses),
            100 * sum(r.optionId == o.id for r in record.responses) / count if count else 0.0)
            for o in options), tuple(limitations))
