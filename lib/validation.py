"""
Validation - Arsenal Module
Copy-paste ready: Works in any project using Pydantic
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lib.evidence import PersistedResponse, RunSummary

MAX_EXPERIMENT_PARADOXES = 10
MAX_EXPERIMENT_CONDITIONS = 10
MAX_EXPERIMENT_RUNS = 50


class GenerationParams(BaseModel):
    """Generation parameters for reproducibility"""
    temperature: float = Field(default=1.0, ge=0, le=2)
    top_p: float = Field(default=1.0, ge=0, le=1)
    max_tokens: int = Field(default=1000, ge=1, le=4000)
    seed: int | None = Field(default=None, ge=0)
    frequency_penalty: float = Field(default=0, ge=0, le=2)
    presence_penalty: float = Field(default=0, ge=0, le=2)


class OptionInput(BaseModel):
    """Single option override for N-way paradoxes"""
    id: int = Field(..., ge=1, le=4, description="Option ID (1-4)")
    description: str = Field(..., max_length=1000, description="Option description text")


class OptionInputs(BaseModel):
    """Optional option overrides for trolley-type paradoxes (N-way support)"""
    options: list[OptionInput] | None = Field(
        default=None,
        max_length=4,
        min_length=2,
        description="List of option overrides (2-4 options)"
    )

    @field_validator('options')
    @classmethod
    def validate_sequential_ids(cls, v: list[OptionInput] | None) -> list[OptionInput] | None:
        """Ensure option IDs are sequential starting from 1"""
        if v:
            ids = sorted([opt.id for opt in v])
            expected = list(range(1, len(ids) + 1))
            if ids != expected:
                raise ValueError(f'Option IDs must be sequential starting from 1. Got {ids}, expected {expected}')
        return v


class QueryRequest(BaseModel):
    """Experimental run request"""
    model_name: str = Field(..., alias="modelName", min_length=1, max_length=200)
    paradox_id: str = Field(..., alias="paradoxId", min_length=1, max_length=100)
    option_overrides: OptionInputs | None = Field(default=None, alias="optionOverrides")
    iterations: int | None = Field(default=10, ge=1, le=1000)
    system_prompt: str | None = Field(default=None, alias="systemPrompt", max_length=2000)
    params: GenerationParams | None = None
    # Defaults ON: LLMs favour first- and last-listed options, so an unshuffled
    # run carries uncontrolled position bias. Unbiased must be the default path.
    shuffle_options: bool = Field(default=True, alias="shuffleOptions")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9\-_/:.]+$', v, re.IGNORECASE):
            raise ValueError('Invalid model name format')
        return v

    @field_validator('paradox_id')
    @classmethod
    def validate_paradox_id(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9_-]+$', v, re.IGNORECASE):
            raise ValueError('Invalid paradox ID format')
        return v

    @model_validator(mode='before')
    @classmethod
    def parse_flat_form_data(cls, data: Any) -> Any:
        # If data is a dict (like from JSON body), check for flattened keys
        if isinstance(data, dict):
            new_data = data.copy()
            params = new_data.get('params', {})
            if not isinstance(params, dict):
                params = {}

            keys_to_remove = []
            for k, v in new_data.items():
                if k.startswith('params.'):
                    sub_key = k.split('.', 1)[1]
                    params[sub_key] = v
                    keys_to_remove.append(k)
                elif k == 'iterations' and isinstance(v, str) and not v.strip():
                    # Empty form field: drop the key so the field default applies.
                    keys_to_remove.append(k)

            for k in keys_to_remove:
                new_data.pop(k)

            if params:
                new_data['params'] = params

            # Type casting for form inputs (forms send strings)
            if 'iterations' in new_data and isinstance(new_data['iterations'], str):
                try:
                    new_data['iterations'] = int(new_data['iterations'])
                except ValueError:
                    pass # Pydantic will validation error later

            return new_data
        return data


class InsightRequest(BaseModel):
    """AI insight generation request"""
    runData: dict[str, Any]
    analystModel: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator('runData')
    @classmethod
    def validate_run_data(cls, v: dict[str, Any]) -> dict[str, Any]:
        if "runId" in v and not isinstance(v["runId"], str):
            raise ValueError("runId must be a string")
        if not isinstance(v.get('responses'), list) or not v['responses']:
            raise ValueError('runData must contain at least one response')
        RunSummary.model_validate(v.get("summary", {}))
        if "options" in v and (not isinstance(v["options"], list) or any(not isinstance(o, dict) for o in v["options"])):
            raise ValueError("options must be a list of option objects")
        for response in v['responses']:
            PersistedResponse.model_validate(response)
        return v

class ConditionConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    modelName: str = Field(..., min_length=1, max_length=200)
    systemPrompt: str = Field(default="", max_length=2000)
    params: GenerationParams = Field(default_factory=GenerationParams)
    iterations: int | None = Field(default=None, ge=1, le=1000)
    shuffle_options: bool = Field(default=True, alias="shuffleOptions")

    @field_validator('params', mode='before')
    @classmethod
    def normalize_params(cls, v: Any) -> Any:
        return v if v is not None else {}

    @field_validator('modelName')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9\-_/:.]+$', v, re.IGNORECASE):
            raise ValueError('Invalid model name format')
        return v


class ExperimentCreateRequest(BaseModel):
    title: str = Field(..., max_length=200)
    paradoxIds: list[str] = Field(..., min_length=1, max_length=MAX_EXPERIMENT_PARADOXES)
    conditions: list[ConditionConfig] = Field(..., min_length=1, max_length=MAX_EXPERIMENT_CONDITIONS)
    tags: list[str] | None = Field(default_factory=list)

    @field_validator('paradoxIds')
    @classmethod
    def validate_paradox_ids(cls, v: list[str]) -> list[str]:
        for pid in v:
            if not re.match(r'^[a-z0-9_-]+$', pid, re.IGNORECASE):
                raise ValueError(f'Invalid paradox ID format: {pid}')
        return v

    @model_validator(mode="after")
    def validate_experiment_matrix(self) -> "ExperimentCreateRequest":
        run_count = len(self.paradoxIds) * len(self.conditions)
        if run_count > MAX_EXPERIMENT_RUNS:
            raise ValueError(
                f"Experiment matrix exceeds maximum allowed runs ({MAX_EXPERIMENT_RUNS})"
            )
        return self

class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., max_length=100)
    title: str = Field(..., max_length=200)
    paradoxIds: list[str] = Field(default_factory=list)
    conditions: list[ConditionConfig] = Field(default_factory=list)
    runIds: list[str] = Field(default_factory=list)
    conditionStates: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    status: str = Field(..., max_length=20)
    tags: list[str] = Field(default_factory=list)
    createdAt: str = Field(...)
