"""
Query Processor - Arsenal Module
Executes experimental runs with paradox-aware response parsing
Nearly copy-paste ready: Depends on ai_service patterns
"""

import asyncio
import json
import math
import re
import hashlib
import time
import random
import copy
from typing import Awaitable, Callable, Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import logging
from lib.ai_service import AIService, StructuredOutputSchema
from lib.query_errors import (
    InvalidChoiceError,
    MissingExplanationError,
    ParseAmbiguityError,
    QueryExecutionError,
    RetryableQueryError,
)

logger = logging.getLogger(__name__)

REASONING_TEXT_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("summary", ("Summary",)),
    ("valuePriorities", ("Value Priorities",)),
    ("keyAssumptions", ("Key Assumptions",)),
    ("mainRisk", ("Main Risk",)),
    ("switchCondition", ("Switch Condition",)),
    ("evidenceNeeded", ("Evidence Needed to Change Choice", "Evidence Needed")),
)


def _decision_tokens(option_count: int) -> List[str]:
    """Return canonical decision tokens for the current option count."""
    return [f"{{{i}}}" for i in range(1, option_count + 1)]


def _strict_single_choice_contract(option_count: int) -> str:
    """Build a strict output contract to enforce one decision token."""
    tokens = _decision_tokens(option_count)
    token_list = ", ".join(f"`{token}`" for token in tokens)
    return (
        "\n\n**Output Contract (Strict):**\n\n"
        "- Return only a JSON object (no markdown, no code fences).\n"
        f"- The JSON must contain `option_id` as an integer in range 1..{option_count}.\n"
        "- The parser also accepts `optionId`, but prefer `option_id`.\n"
        "- The JSON must contain `summary` as a short string.\n"
        "- The JSON must contain `value_priorities` as an array of short strings.\n"
        "- The JSON must contain `key_assumptions` as an array of short strings.\n"
        "- The JSON must contain `main_risk`, `switch_condition`, and `evidence_needed` as strings.\n"
        f"- Allowed option tokens for reference: {token_list}.\n"
        "- Do not write token alternatives such as \"{1} or {2}\"."
    )


def _choice_response_schema(option_count: int) -> StructuredOutputSchema:
    """Structured-output schema for primary forced-choice model calls."""
    return StructuredOutputSchema(
        name=f"forced_choice_response_{option_count}",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "option_id": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": option_count,
                },
                "summary": {
                    "type": "string",
                    "minLength": 1,
                },
                "value_priorities": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
                "key_assumptions": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                },
                "main_risk": {
                    "type": "string",
                    "minLength": 1,
                },
                "switch_condition": {
                    "type": "string",
                    "minLength": 1,
                },
                "evidence_needed": {
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": [
                "option_id",
                "summary",
                "value_priorities",
                "key_assumptions",
                "main_risk",
                "switch_condition",
                "evidence_needed",
            ],
        },
    )


def _coerce_text(value: object) -> str:
    """Normalize arbitrary values into stripped strings."""
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _coerce_string_list(value: object) -> List[str]:
    """Normalize list-like reasoning fields from JSON arrays or delimited strings."""
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            items = []
        else:
            items = [segment.strip(" -•\t") for segment in re.split(r"[;\n]+", stripped) if segment.strip(" -•\t")]
            if len(items) == 1:
                comma_items = [segment.strip(" -•\t") for segment in stripped.split(",") if segment.strip(" -•\t")]
                if 1 < len(comma_items) <= 5:
                    items = comma_items
    else:
        items = []

    deduped: List[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _extract_labeled_reasoning_field(text: str, labels: tuple[str, ...]) -> Optional[str]:
    """Extract a labeled reasoning field from free text."""
    if not text.strip():
        return None
    boundary = r"(?=\n(?:Summary|Value Priorities|Key Assumptions|Main Risk|Switch Condition|Evidence Needed(?: to Change Choice)?)\s*:|$)"
    for label in labels:
        pattern = re.compile(
            rf"(?:{re.escape(label)})\s*:\s*(.*?){boundary}",
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _extract_reasoning_fields_from_text(text: str) -> Dict[str, object]:
    """Parse labeled rationale fields out of a free-form explanation."""
    extracted: Dict[str, object] = {}
    for key, labels in REASONING_TEXT_FIELDS:
        value = _extract_labeled_reasoning_field(text, labels)
        if not value:
            continue
        if key in {"valuePriorities", "keyAssumptions"}:
            extracted[key] = _coerce_string_list(value)
        else:
            extracted[key] = value
    return extracted


def _compose_explanation_text(
    summary: str,
    value_priorities: List[str],
    key_assumptions: List[str],
    main_risk: str,
    switch_condition: str,
    evidence_needed: str,
) -> str:
    """Build a legacy explanation string from structured rationale fields."""
    lines: List[str] = []
    if summary:
        lines.append(f"Summary: {summary}")
    if value_priorities:
        lines.append(f"Value Priorities: {'; '.join(value_priorities)}")
    if key_assumptions:
        lines.append(f"Key Assumptions: {'; '.join(key_assumptions)}")
    if main_risk:
        lines.append(f"Main Risk: {main_risk}")
    if switch_condition:
        lines.append(f"Switch Condition: {switch_condition}")
    if evidence_needed:
        lines.append(f"Evidence Needed to Change Choice: {evidence_needed}")
    return "\n".join(lines).strip()


def _extract_reasoning_payload(payload: Dict[str, Any], fallback_text: str = "") -> Dict[str, Any]:
    """Normalize structured rationale fields while preserving a legacy explanation string."""
    explanation_text = _coerce_text(
        payload.get("explanation") or payload.get("reasoning") or payload.get("rationale")
    )
    text_fields = _extract_reasoning_fields_from_text(explanation_text or fallback_text)

    summary = _coerce_text(payload.get("summary")) or _coerce_text(text_fields.get("summary"))
    value_priorities = _coerce_string_list(payload.get("value_priorities", payload.get("valuePriorities")))
    if not value_priorities:
        value_priorities = list(text_fields.get("valuePriorities", [])) if isinstance(text_fields.get("valuePriorities"), list) else []
    key_assumptions = _coerce_string_list(payload.get("key_assumptions", payload.get("keyAssumptions")))
    if not key_assumptions:
        key_assumptions = list(text_fields.get("keyAssumptions", [])) if isinstance(text_fields.get("keyAssumptions"), list) else []
    main_risk = _coerce_text(payload.get("main_risk", payload.get("mainRisk"))) or _coerce_text(text_fields.get("mainRisk"))
    switch_condition = _coerce_text(payload.get("switch_condition", payload.get("switchCondition"))) or _coerce_text(text_fields.get("switchCondition"))
    evidence_needed = _coerce_text(payload.get("evidence_needed", payload.get("evidenceNeeded"))) or _coerce_text(text_fields.get("evidenceNeeded"))

    structured_keys_present = any(
        key in payload
        for key in (
            "summary",
            "value_priorities",
            "valuePriorities",
            "key_assumptions",
            "keyAssumptions",
            "main_risk",
            "mainRisk",
            "switch_condition",
            "switchCondition",
            "evidence_needed",
            "evidenceNeeded",
        )
    )

    if structured_keys_present and not summary and explanation_text:
        summary = explanation_text

    explanation = _compose_explanation_text(
        summary,
        value_priorities,
        key_assumptions,
        main_risk,
        switch_condition,
        evidence_needed,
    )
    if not explanation:
        explanation = explanation_text or fallback_text.strip()

    result: Dict[str, Any] = {"explanation": explanation}
    if summary:
        result["summary"] = summary
    if value_priorities:
        result["valuePriorities"] = value_priorities
    if key_assumptions:
        result["keyAssumptions"] = key_assumptions
    if main_risk:
        result["mainRisk"] = main_risk
    if switch_condition:
        result["switchCondition"] = switch_condition
    if evidence_needed:
        result["evidenceNeeded"] = evidence_needed
    if structured_keys_present:
        result["reasoningSchemaVersion"] = 2
    return result


def _extract_choice_from_classifier_output(classifier_output: str, option_count: int) -> Optional[int]:
    """Extract a single option ID from classifier output; 0 means undecided.

    Scans all numeric and brace-token matches left-to-right, returning the
    first value in range 1..option_count.  This handles noisy classifier
    outputs like ``confidence 10/10; answer 2`` where the first number is
    out of range.
    """
    if option_count < 1:
        return None

    # Scan all bare numbers left-to-right, return first in-range hit.
    for m in re.finditer(r"\b(\d+)\b", classifier_output):
        value = int(m.group(1))
        if value == 0:
            return None  # explicit undecided signal
        if 1 <= value <= option_count:
            return value

    # Fallback: brace tokens {N}
    for m in re.finditer(r"\{(\d+)\}", classifier_output):
        value = int(m.group(1))
        if 1 <= value <= option_count:
            return value

    return None


def _infer_option_from_text(response_text: str, option_count: int) -> Optional[int]:
    """
    Infer a final option choice from natural-language commitment phrases.
    Returns None when no clear single commitment is present.
    """
    if not response_text or option_count < 1:
        return None

    explicit_patterns = [
        (
            r"(?i)\b(?:i|we)\s+(?:choose|chose|select|selected|recommend|recommended|pick|picked|prefer|support)\b"
            r"[^0-9{}]{0,40}(?:option|policy|choice)?\s*\{?([1-" + str(option_count) + r"])\}?"
        ),
        (
            r"(?i)\b(?:i(?:'d| would)\s+(?:choose|select|recommend|pick|go with)|i\s+will\s+(?:choose|select|recommend|pick))\b"
            r"[^0-9{}]{0,40}(?:option|policy|choice)?\s*\{?([1-" + str(option_count) + r"])\}?"
        ),
        (
            r"(?i)\b(?:my|the)\s+(?:choice|recommendation)\s+(?:is|:)\s*(?:option|policy|choice)?\s*\{?([1-"
            + str(option_count)
            + r"])\}?"
        ),
    ]

    inferred: List[int] = []
    for pattern in explicit_patterns:
        inferred.extend(int(m) for m in re.findall(pattern, response_text))

    if not inferred:
        return None

    unique_ids = set(inferred)
    if len(unique_ids) == 1:
        return inferred[-1]

    return None


def _build_choice_inference_prompt(response_text: str, option_count: int) -> str:
    """
    Build a strict extraction prompt for AI fallback when parser+heuristics fail.
    Returns only the classifier instruction text.
    """
    if len(response_text) > 6000:
        response_text = f"{response_text[:3000]}\n\n...[truncated]...\n\n{response_text[-3000:]}"

    return (
        "Classify the FINAL chosen option in the following model response.\n"
        f"Valid options are integers 1..{option_count}.\n"
        "Return exactly one character only:\n"
        f"- '1'..'{option_count}' if there is one clear final choice\n"
        "- '0' if no clear single final choice exists\n"
        "Rules:\n"
        "- Ignore option lists and hypothetical analysis.\n"
        "- Use only an explicit final commitment (e.g. \"I choose option 2\", \"I'd pick {3}\").\n"
        "- If the text contains conflicting commitments, return 0.\n"
        "- Do not output any words.\n\n"
        "MODEL RESPONSE START\n"
        f"{response_text}\n"
        "MODEL RESPONSE END"
    )


def _build_reask_prompt(
    base_prompt: str,
    option_count: int,
    previous_response: str,
    attempt_number: int,
    issue: str = "invalid_choice",
) -> str:
    """Build a corrective re-ask prompt when no single valid token is returned."""
    tokens = ", ".join(_decision_tokens(option_count))
    if issue == "missing_explanation":
        retry_notice = (
            f"RETRY NOTICE ({attempt_number}): Your previous answer selected a valid option "
            "but did not include the required structured rationale fields."
        )
    else:
        retry_notice = (
            f"RETRY NOTICE ({attempt_number}): Your previous answer did not contain exactly "
            f"one valid token from {tokens}."
        )
    return (
        f"{base_prompt}\n\n"
        f"{retry_notice}\n"
        "Respond again.\n"
        "Requirements:\n"
        "- Return only a JSON object.\n"
        f"- `option_id` must be an integer from 1..{option_count}.\n"
        "- Include `summary`, `value_priorities`, `key_assumptions`, `main_risk`, `switch_condition`, and `evidence_needed`.\n\n"
        "Previous response:\n"
        f"{previous_response}"
    )


def _extract_json_object(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse a JSON object from raw model text."""
    text = response_text.strip()
    candidates: List[str] = [text]

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1).strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    # Fallback: scan for the first decodable JSON object in mixed content.
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _has_explanation_text(parsed: Dict[str, Any]) -> bool:
    """Return True when the parsed response includes non-empty explanation text."""
    explanation = parsed.get("explanation")
    return isinstance(explanation, str) and bool(explanation.strip())


def _coerce_option_id(value: object, option_count: int) -> Optional[int]:
    """Coerce option_id-like values from structured responses."""
    option_id: Optional[int] = None

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        option_id = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        option_id = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            option_id = int(stripped)
        else:
            token_match = re.match(r"^\{([1-9]\d*)\}$", stripped)
            if token_match:
                option_id = int(token_match.group(1))

    if option_id is None:
        return None
    if 1 <= option_id <= option_count:
        return option_id
    return None


def render_options_template(
    paradox: Dict[str, Any],
    overrides: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Render N-way options into prompt template

    Args:
        paradox: Paradox definition with options[] array
        overrides: Optional list of {id, description} overrides

    Returns:
        Tuple of (rendered_prompt, resolved_options)
    """
    options = paradox.get("options", [])

    # Apply overrides if provided
    if overrides:
        override_map = {opt["id"]: opt["description"] for opt in overrides}
        options = [
            {**opt, "description": override_map.get(opt["id"], opt["description"])}
            for opt in options
        ]

    template = paradox["promptTemplate"]

    # Support both {{OPTIONS}} (new) and {{GROUP1}}/{{GROUP2}} (legacy) placeholders
    if "{{OPTIONS}}" in template:
        # New N-way format: Build numbered list
        options_text = "\n\n".join([
            f'{opt["id"]}. **{opt["label"]}:** {opt["description"]}'
            for opt in options
        ])
        prompt = template.replace("{{OPTIONS}}", options_text)
    else:
        # Legacy binary format: Replace GROUP1/GROUP2 individually
        prompt = template
        if len(options) >= 1:
            prompt = prompt.replace("{{GROUP1}}", options[0]["description"])
        if len(options) >= 2:
            prompt = prompt.replace("{{GROUP2}}", options[1]["description"])

    if options:
        prompt = f"{prompt}{_strict_single_choice_contract(len(options))}"

    return prompt, options


def parse_trolley_response(response_text: str, option_count: int) -> Dict[str, Any]:
    """
    Parse trolley-type response for decision tokens (N-way support)

    Args:
        response_text: Raw AI response text
        option_count: Number of options (2-4)

    Returns:
        Dict with decisionToken, optionId (int), and explanation
    """
    # Structured JSON takes precedence over free-form brace tokens when both are present.
    structured = _extract_json_object(response_text)
    if structured is not None:
        option_id = _coerce_option_id(
            structured.get("option_id", structured.get("optionId")),
            option_count,
        )
        if option_id is None:
            option_id = _coerce_option_id(structured.get("decisionToken"), option_count)

        if option_id is not None:
            result = {
                "decisionToken": f"{{{option_id}}}",
                "optionId": option_id,
            }
            result.update(_extract_reasoning_payload(structured, response_text))
            return result

    # Dynamic regex based on option count: {1} through {N}
    pattern = r'\{([1-' + str(option_count) + r'])\}'
    matches = re.findall(pattern, response_text)

    if not matches:
        return {
            "decisionToken": None,
            "optionId": None,
            "explanation": response_text.strip()
        }

    unique_matches = set(matches)
    if len(unique_matches) > 1:
        logger.warning("Ambiguous response with multiple decision tokens: %s", matches)
        return {
            "decisionToken": None,
            "optionId": None,
            "explanation": response_text.strip(),
            "parseIssue": "ambiguous_choice",
        }

    decision_token = "{" + matches[0] + "}"
    option_id = int(matches[0])  # Convert to integer

    # Extract explanation after decision token
    match = re.search(pattern, response_text)
    explanation = response_text[match.end():].strip()

    result = {
        "decisionToken": decision_token,
        "optionId": option_id,  # Integer instead of string
    }
    result.update(_extract_reasoning_payload({}, explanation))

    return result


def aggregate_trolley_stats(responses: List[Dict[str, Any]], option_count: int) -> Dict[str, Any]:
    """
    Aggregate N-way trolley statistics

    Args:
        responses: List of response dictionaries
        option_count: Number of options (2-4)

    Returns:
        Summary dict with dynamic options[] array and undecided count
    """
    total = len(responses)

    # Initialize counters for each option
    option_counts = {i: 0 for i in range(1, option_count + 1)}
    undecided_count = 0

    # Count responses
    for r in responses:
        option_id = r.get("optionId")
        if option_id and 1 <= option_id <= option_count:
            option_counts[option_id] += 1
        else:
            undecided_count += 1

    # Build dynamic summary
    return {
        "total": total,
        "options": [
            {
                "id": i,
                "count": option_counts[i],
                "percentage": (option_counts[i] / total * 100) if total > 0 else 0
            }
            for i in range(1, option_count + 1)
        ],
        "undecided": {
            "count": undecided_count,
            "percentage": (undecided_count / total * 100) if total > 0 else 0
        }
    }


from dataclasses import dataclass, field


RunProgressCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class RunConfig:
    """Configuration for an experimental run (N-way support)"""
    modelName: str
    paradox: Dict[str, Any]
    option_overrides: Optional[List[Dict[str, Any]]] = None
    iterations: int = 10
    systemPrompt: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    shuffle_options: bool = False




class QueryProcessor:
    """
    Query Processor
    Manages concurrent iteration execution with paradox-aware parsing
    """

    def __init__(
        self,
        ai_service: AIService,
        concurrency_limit: int = 2,
        choice_inference_model: Optional[str] = None,
        max_reasks_per_iteration: int = 2,
    ) -> None:
        if max_reasks_per_iteration < 0 or max_reasks_per_iteration > 10:
            raise ValueError("max_reasks_per_iteration must be between 0 and 10")
        self.ai_service = ai_service
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.choice_inference_model = choice_inference_model
        self.max_reasks_per_iteration = max_reasks_per_iteration

    @staticmethod
    def _sanitize_params(
        params: object,
        *,
        fallback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        source = params if isinstance(params, dict) else fallback if isinstance(fallback, dict) else {}
        sanitized = {
            "temperature": source.get("temperature", 1.0),
            "top_p": source.get("top_p", 1.0),
            "max_tokens": source.get("max_tokens", 1000),
            "frequency_penalty": source.get("frequency_penalty", 0),
            "presence_penalty": source.get("presence_penalty", 0),
        }
        if source.get("seed") is not None:
            sanitized["seed"] = source["seed"]
        return sanitized

    @staticmethod
    def _completed_responses(
        responses: object,
        iterations: int,
    ) -> List[Dict[str, Any]]:
        if not isinstance(responses, list):
            return []

        completed: Dict[int, Dict[str, Any]] = {}
        for response in responses:
            if not isinstance(response, dict):
                continue
            iteration = response.get("iteration")
            option_id = response.get("optionId")
            explanation = response.get("explanation")
            if not isinstance(iteration, int) or iteration < 1 or iteration > iterations:
                continue
            if not isinstance(option_id, int):
                continue
            if not isinstance(explanation, str) or not explanation.strip():
                continue
            completed[iteration] = copy.deepcopy(response)

        return [completed[idx] for idx in sorted(completed)]

    def _prepare_prompt(
        self,
        config: RunConfig,
        existing_run: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Dict[str, Any]], int, Optional[Dict[str, int]]]:
        if existing_run:
            prompt = existing_run.get("prompt")
            stored_options = existing_run.get("options")
            stored_shuffle = existing_run.get("shuffleMapping")
            if isinstance(prompt, str) and isinstance(stored_options, list) and stored_options:
                option_count = sum(1 for option in stored_options if isinstance(option, dict))
                shuffle_mapping = stored_shuffle if isinstance(stored_shuffle, dict) else None
                return prompt, copy.deepcopy(stored_options), option_count, shuffle_mapping

        paradox_type = config.paradox.get("type")
        if paradox_type != "trolley":
            raise ValueError(f"Unsupported paradox type: {paradox_type}")

        original_options = copy.deepcopy(config.paradox.get("options", []))
        if config.option_overrides:
            override_map = {opt["id"]: opt["description"] for opt in config.option_overrides}
            original_options = [
                {**opt, "description": override_map.get(opt["id"], opt["description"])}
                for opt in original_options
            ]

        options_to_render = copy.deepcopy(original_options)
        shuffle_mapping: Optional[Dict[str, int]] = None
        if config.shuffle_options and options_to_render:
            random.shuffle(options_to_render)
            shuffle_mapping = {}
            for index, option in enumerate(options_to_render):
                new_id = index + 1
                shuffle_mapping[str(new_id)] = option["id"]
                option["id"] = new_id

        dummy_paradox = {**config.paradox, "options": options_to_render}
        prompt, resolved_options = render_options_template(dummy_paradox, None)
        if config.systemPrompt:
            prompt = f"PERSONA: {config.systemPrompt}\n\n{prompt}"

        return prompt, original_options, len(resolved_options), shuffle_mapping

    def initialize_run_data(
        self,
        config: RunConfig,
        existing_run: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt, original_options, option_count, shuffle_mapping = self._prepare_prompt(
            config,
            existing_run=existing_run,
        )
        if option_count < 1:
            raise ValueError("Paradox must define at least one option")

        base_run = copy.deepcopy(existing_run) if isinstance(existing_run, dict) else {}
        params = self._sanitize_params(config.params, fallback=base_run.get("params"))
        completed_responses = self._completed_responses(
            base_run.get("responses"),
            config.iterations,
        )
        created_at = str(base_run.get("timestamp") or datetime.now(timezone.utc).isoformat())
        run_data: Dict[str, Any] = {
            **base_run,
            "timestamp": created_at,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "modelName": config.modelName,
            "paradoxId": config.paradox["id"],
            "paradoxType": "trolley",
            "promptHash": hashlib.sha256(prompt.encode()).hexdigest()[:16],
            "prompt": prompt,
            "iterationCount": config.iterations,
            "completedIterations": len(completed_responses),
            "params": params,
            "responses": completed_responses,
            "options": original_options,
            "summary": aggregate_trolley_stats(completed_responses, option_count),
            "status": "running",
        }

        system_prompt = config.systemPrompt or str(base_run.get("systemPrompt", "") or "")
        if system_prompt:
            run_data["systemPrompt"] = system_prompt
        elif "systemPrompt" in run_data:
            run_data.pop("systemPrompt", None)

        if shuffle_mapping is not None:
            run_data["shuffleMapping"] = shuffle_mapping
        elif "shuffleMapping" in run_data and not isinstance(run_data.get("shuffleMapping"), dict):
            run_data.pop("shuffleMapping", None)

        if len(completed_responses) >= config.iterations:
            run_data["status"] = "completed"

        return run_data

    async def _infer_option_id_with_fallback(
        self,
        response_text: str,
        option_count: int,
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Infer an option ID when strict token parsing fails.
        Returns (option_id, method) where method is 'heuristic' or 'ai_classifier'.
        """
        heuristic_option = _infer_option_from_text(response_text, option_count)
        if heuristic_option is not None:
            return heuristic_option, "heuristic"

        if not self.choice_inference_model:
            return None, None

        classifier_prompt = _build_choice_inference_prompt(response_text, option_count)
        classifier_output, _ = await self.ai_service.get_model_response(
            self.choice_inference_model,
            classifier_prompt,
            "",
            {"temperature": 0, "top_p": 1, "max_tokens": 4},
        )
        inferred_option = _extract_choice_from_classifier_output(classifier_output, option_count)
        if inferred_option is None:
            return None, None
        return inferred_option, "ai_classifier"

    async def execute_run(
        self,
        config: RunConfig,
        *,
        existing_run: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[RunProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        Execute experimental run

        Args:
            config: Explicit RunConfig object
            existing_run: Optional partially completed run record to resume
            progress_callback: Optional callback invoked after each accepted iteration

        Returns:
            Complete run data with responses and summary
        """
        current_run = self.initialize_run_data(config, existing_run=existing_run)
        prompt = str(current_run["prompt"])
        option_count = len(current_run.get("options", []))
        choice_response_schema = _choice_response_schema(option_count)
        shuffle_mapping = current_run.get("shuffleMapping")
        params = self._sanitize_params(config.params, fallback=current_run.get("params"))
        completed = {
            response["iteration"]: copy.deepcopy(response)
            for response in current_run.get("responses", [])
            if isinstance(response, dict) and isinstance(response.get("iteration"), int)
        }
        state_lock = asyncio.Lock()

        async def persist_state() -> None:
            if progress_callback is None:
                return
            snapshot = copy.deepcopy(current_run)
            await progress_callback(snapshot)

        if len(completed) >= config.iterations:
            current_run["status"] = "completed"
            current_run["completedIterations"] = len(completed)
            current_run["updatedAt"] = datetime.now(timezone.utc).isoformat()
            await persist_state()
            return current_run

        async def record_result(result: Dict[str, Any]) -> None:
            async with state_lock:
                completed[result["iteration"]] = result
                ordered_responses = [copy.deepcopy(completed[idx]) for idx in sorted(completed)]
                current_run["responses"] = ordered_responses
                current_run["completedIterations"] = len(ordered_responses)
                current_run["summary"] = aggregate_trolley_stats(ordered_responses, option_count)
                current_run["status"] = "completed" if len(ordered_responses) >= config.iterations else "running"
                current_run["updatedAt"] = datetime.now(timezone.utc).isoformat()
            await persist_state()

        async def run_iteration(iteration_number: int) -> Dict[str, Any]:
            async with self.semaphore:
                response = ""
                reask_count = 0
                next_reask_issue = "invalid_choice"
                total_latency = 0.0
                total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

                while True:
                    attempt_number = reask_count + 1
                    iteration_prompt = prompt
                    if reask_count > 0:
                        iteration_prompt = _build_reask_prompt(
                            prompt,
                            option_count,
                            response,
                            attempt_number,
                            issue=next_reask_issue,
                        )

                    try:
                        start_t = time.monotonic()
                        response, usage = await self.ai_service.get_model_response(
                            config.modelName,
                            iteration_prompt,
                            "",
                            params,
                            response_schema=choice_response_schema,
                        )
                    except RetryableQueryError as retry_error:
                        logger.warning(
                            "Retrying iteration %s after provider error: %s",
                            iteration_number,
                            retry_error,
                        )
                        continue

                    latency = time.monotonic() - start_t
                    total_latency += latency
                    total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

                    parsed = parse_trolley_response(response, option_count)

                    if shuffle_mapping and parsed["optionId"] is not None:
                        original_id = shuffle_mapping.get(str(parsed["optionId"]))
                        if original_id is not None:
                            parsed["optionId"] = original_id
                            parsed["decisionToken"] = f"{{{original_id}}}"

                    parsed["latency"] = total_latency
                    parsed["tokenUsage"] = total_usage

                    inferred = False
                    inference_method: Optional[str] = None
                    if parsed["optionId"] is None:
                        inferred_option, inference_method = await self._infer_option_id_with_fallback(
                            response,
                            option_count,
                        )
                        if inferred_option is not None:
                            if shuffle_mapping:
                                original_id = shuffle_mapping.get(str(inferred_option))
                                if original_id is not None:
                                    inferred_option = original_id
                            parsed["decisionToken"] = f"{{{inferred_option}}}"
                            parsed["optionId"] = inferred_option
                            inferred = True

                    if parsed["optionId"] is not None and _has_explanation_text(parsed):
                        result = {
                            "iteration": iteration_number,
                            "decisionToken": parsed["decisionToken"],
                            "optionId": parsed["optionId"],
                            "explanation": parsed["explanation"],
                            "raw": response,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        for key in [
                            "summary",
                            "valuePriorities",
                            "keyAssumptions",
                            "mainRisk",
                            "switchCondition",
                            "evidenceNeeded",
                            "reasoningSchemaVersion",
                            "latency",
                            "tokenUsage",
                        ]:
                            if key in parsed:
                                result[key] = parsed[key]
                        if reask_count:
                            result["reaskCount"] = reask_count
                        if inferred and inference_method:
                            result["inferred"] = True
                            result["inferenceMethod"] = inference_method
                        return result

                    if parsed.get("parseIssue") == "ambiguous_choice":
                        retry_error: RetryableQueryError = ParseAmbiguityError(
                            "Ambiguous response contained multiple decision tokens"
                        )
                    elif parsed["optionId"] is not None:
                        retry_error = MissingExplanationError(
                            "Model selected an option without the required explanation"
                        )
                        next_reask_issue = "missing_explanation"
                    else:
                        retry_error = InvalidChoiceError(
                            "Model did not return a single valid choice"
                        )
                        next_reask_issue = "invalid_choice"

                    reask_count += 1
                    logger.warning(
                        "Retrying iteration %s after invalid output: %s",
                        iteration_number,
                        retry_error,
                    )

        remaining_iterations = [
            iteration
            for iteration in range(1, config.iterations + 1)
            if iteration not in completed
        ]
        tasks = [run_iteration(iteration) for iteration in remaining_iterations]
        results = await asyncio.gather(*tasks)
        for result in results:
            await record_result(result)

        return copy.deepcopy(current_run)
