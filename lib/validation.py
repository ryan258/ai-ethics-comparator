"""
Validation - Arsenal Module
Copy-paste ready: Works in any project using Pydantic
"""

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class GenerationParams(BaseModel):
    """Generation parameters for reproducibility"""
    temperature: float = Field(default=1.0, ge=0, le=2)
    top_p: float = Field(default=1.0, ge=0, le=1)
    max_tokens: int = Field(default=1000, ge=1, le=4000)
    seed: Optional[int] = Field(default=None, ge=0)
    frequency_penalty: float = Field(default=0, ge=0, le=2)
    presence_penalty: float = Field(default=0, ge=0, le=2)


class GroupInputs(BaseModel):
    """Optional group descriptions for trolley-type paradoxes"""
    group1: Optional[str] = Field(default=None, max_length=1000)
    group2: Optional[str] = Field(default=None, max_length=1000)


class QueryRequest(BaseModel):
    """Experimental run request"""
    modelName: str = Field(..., min_length=1, max_length=200)
    paradoxId: str = Field(..., min_length=1, max_length=100)
    groups: Optional[GroupInputs] = None
    iterations: Optional[int] = Field(default=10, ge=1, le=50)
    systemPrompt: Optional[str] = Field(default=None, max_length=2000)
    params: Optional[GenerationParams] = None

    @field_validator('modelName')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9\-_/:.]+$', v, re.IGNORECASE):
            raise ValueError('Invalid model name format')
        return v

    @field_validator('paradoxId')
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
            groups = new_data.get('groups', {})
            
            # Helper: ensure sub-dict exists
            if not isinstance(params, dict): params = {}
            if not isinstance(groups, dict): groups = {}

            keys_to_remove = []
            for k, v in new_data.items():
                if k.startswith('params.'):
                    sub_key = k.split('.', 1)[1]
                    params[sub_key] = v
                    keys_to_remove.append(k)
                elif k == 'iterations' and v == '':
                    # Handle empty strings from form inputs
                    new_data[k] = None
                
            for k in keys_to_remove:
                new_data.pop(k)
            
            if params:
                new_data['params'] = params
            
            if groups:
                new_data['groups'] = groups
                
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
    runData: dict
    analystModel: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @field_validator('runData')
    @classmethod
    def validate_run_data(cls, v: dict) -> dict:
        if 'responses' not in v or len(v['responses']) < 1:
            raise ValueError('runData must contain at least one response')
        return v

