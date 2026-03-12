from __future__ import annotations

import asyncio
import pytest

import math

from lib.query_processor import (
    _coerce_option_id,
    _extract_choice_from_classifier_output,
    _infer_option_from_text,
    QueryProcessor,
    RunConfig,
    parse_trolley_response,
    render_options_template,
)


def test_render_options_template_appends_strict_single_choice_contract() -> None:
    paradox = {
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "Alpha", "description": "Do alpha."},
            {"id": 2, "label": "Beta", "description": "Do beta."},
        ],
    }

    prompt, resolved_options = render_options_template(paradox)

    assert len(resolved_options) == 2
    assert "**Output Contract (Strict):**" in prompt
    assert "`{1}`" in prompt
    assert "`{2}`" in prompt
    assert '"{1} or {2}"' in prompt


def test_parse_trolley_response_marks_multiple_tokens_as_undecided() -> None:
    parsed = parse_trolley_response("{1} or {2} depends on context", option_count=4)

    assert parsed["decisionToken"] is None
    assert parsed["optionId"] is None
    assert parsed["explanation"] == "{1} or {2} depends on context"


def test_parse_trolley_response_keeps_single_token() -> None:
    parsed = parse_trolley_response("{3} Targeted action is proportional.", option_count=4)

    assert parsed["decisionToken"] == "{3}"
    assert parsed["optionId"] == 3
    assert parsed["explanation"] == "Targeted action is proportional."


def test_parse_trolley_response_accepts_repeated_same_token() -> None:
    parsed = parse_trolley_response("I choose {2}. Final answer remains {2}.", option_count=3)

    assert parsed["decisionToken"] == "{2}"
    assert parsed["optionId"] == 2


def test_parse_trolley_response_accepts_structured_json() -> None:
    parsed = parse_trolley_response(
        '{"option_id": 4, "explanation": "Coordination is most robust under uncertainty."}',
        option_count=4,
    )

    assert parsed["decisionToken"] == "{4}"
    assert parsed["optionId"] == 4
    assert parsed["explanation"] == "Coordination is most robust under uncertainty."


def test_parse_trolley_response_accepts_fenced_structured_json() -> None:
    parsed = parse_trolley_response(
        "```json\n{\"optionId\": 1, \"reasoning\": \"Minimize irreversible risk.\"}\n```",
        option_count=4,
    )

    assert parsed["decisionToken"] == "{1}"
    assert parsed["optionId"] == 1
    assert parsed["explanation"] == "Minimize irreversible risk."


def test_parse_trolley_response_prefers_structured_json_over_token_text() -> None:
    parsed = parse_trolley_response(
        '{"option_id": 1, "explanation": "Structured choice."} Also I choose {3}.',
        option_count=4,
    )

    assert parsed["decisionToken"] == "{1}"
    assert parsed["optionId"] == 1
    assert parsed["explanation"] == "Structured choice."


def test_infer_option_from_text_detects_explicit_commitment() -> None:
    response = (
        "After weighing tradeoffs, I think a balanced policy is best. "
        "So I'd choose {2}."
    )
    assert _infer_option_from_text(response, option_count=3) == 2


def test_extract_choice_from_classifier_output() -> None:
    assert _extract_choice_from_classifier_output("2", option_count=4) == 2
    assert _extract_choice_from_classifier_output("{3}", option_count=4) == 3
    assert _extract_choice_from_classifier_output("0", option_count=4) is None


def test_extract_choice_skips_out_of_range_numbers() -> None:
    """Noisy classifier output with leading out-of-range number should still find the valid answer."""
    assert _extract_choice_from_classifier_output("confidence 10/10; answer 2", option_count=3) == 2
    assert _extract_choice_from_classifier_output("after 10 retries, final answer is 2", option_count=4) == 2
    assert _extract_choice_from_classifier_output("score 99 pick {1}", option_count=3) == 1
    # All numbers out of range → None
    assert _extract_choice_from_classifier_output("scores 10 20 30", option_count=4) is None


def test_coerce_option_id_handles_float_bool_nan() -> None:
    """_coerce_option_id rejects bool/NaN/Infinity and accepts clean floats."""
    # Valid float coercion
    assert _coerce_option_id(2.0, 3) == 2
    assert _coerce_option_id(1.0, 4) == 1

    # Non-integer float rejected
    assert _coerce_option_id(1.5, 3) is None

    # Out of range
    assert _coerce_option_id(5.0, 3) is None

    # Bool rejected (bool is subclass of int)
    assert _coerce_option_id(True, 4) is None
    assert _coerce_option_id(False, 4) is None

    # NaN / Infinity rejected without raising
    assert _coerce_option_id(float("nan"), 3) is None
    assert _coerce_option_id(float("inf"), 3) is None
    assert _coerce_option_id(float("-inf"), 3) is None


def test_query_processor_ai_classifier_fallback_infers_option() -> None:
    class DummyAIService:
        def __init__(self) -> None:
            self.call_count = 0

        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            self.call_count += 1
            if "Classify the FINAL chosen option" in prompt:
                return "2", {"prompt_tokens": 10, "completion_tokens": 10}
            return "I am evaluating all options and balancing tradeoffs.", {"prompt_tokens": 10, "completion_tokens": 10}

    dummy_ai = DummyAIService()
    qp = QueryProcessor(
        dummy_ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model="classifier/model",
        max_reasks_per_iteration=0,
    )
    paradox = {
        "id": "test_paradox",
        "type": "trolley",
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
            {"id": 3, "label": "C", "description": "Option C"},
        ],
    }

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="generator/model",
                paradox=paradox,
                iterations=1,
                params={"max_tokens": 200},
            )
        )
    )

    response = run_data["responses"][0]
    assert response["decisionToken"] == "{2}"
    assert response["optionId"] == 2
    assert response["inferred"] is True
    assert response["inferenceMethod"] == "ai_classifier"
    assert dummy_ai.call_count == 2


def test_query_processor_reasks_and_gets_clear_token() -> None:
    class DummyAIService:
        def __init__(self) -> None:
            self.call_count = 0

        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            self.call_count += 1
            if self.call_count == 1:
                return "I need to think through all options first.", {"prompt_tokens": 10, "completion_tokens": 10}
            return "{3} I choose the coordination-heavy option.", {"prompt_tokens": 10, "completion_tokens": 10}

    dummy_ai = DummyAIService()
    qp = QueryProcessor(
        dummy_ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
        max_reasks_per_iteration=2,
    )
    paradox = {
        "id": "test_paradox",
        "type": "trolley",
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
            {"id": 3, "label": "C", "description": "Option C"},
        ],
    }

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="generator/model",
                paradox=paradox,
                iterations=1,
                params={"max_tokens": 200},
            )
        )
    )

    response = run_data["responses"][0]
    assert response["decisionToken"] == "{3}"
    assert response["optionId"] == 3
    assert response["reaskCount"] == 1
    assert dummy_ai.call_count == 2


def test_query_processor_max_two_reasks_then_undecided() -> None:
    class DummyAIService:
        def __init__(self) -> None:
            self.call_count = 0

        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            self.call_count += 1
            return "No final choice yet.", {"prompt_tokens": 10, "completion_tokens": 10}

    dummy_ai = DummyAIService()
    qp = QueryProcessor(
        dummy_ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
        max_reasks_per_iteration=2,
    )
    paradox = {
        "id": "test_paradox",
        "type": "trolley",
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
        ],
    }

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="generator/model",
                paradox=paradox,
                iterations=1,
                params={"max_tokens": 200},
            )
        )
    )

    response = run_data["responses"][0]
    assert response["decisionToken"] is None
    assert response["optionId"] is None
    assert response["reaskCount"] == 2
    assert run_data["summary"]["undecided"]["count"] == 1
    assert dummy_ai.call_count == 3


def test_query_processor_reask_bound_validation() -> None:
    class DummyAIService:
        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            return "{1} done", {"prompt_tokens": 10, "completion_tokens": 10}

    dummy_ai = DummyAIService()
    with pytest.raises(ValueError, match="max_reasks_per_iteration"):
        QueryProcessor(dummy_ai, max_reasks_per_iteration=11)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="max_reasks_per_iteration"):
        QueryProcessor(dummy_ai, max_reasks_per_iteration=-1)  # type: ignore[arg-type]


def test_query_processor_iteration_exception_counts_as_undecided() -> None:
    class DummyAIService:
        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            raise RuntimeError("simulated API failure")

    qp = QueryProcessor(
        DummyAIService(),  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
        max_reasks_per_iteration=0,
    )
    paradox = {
        "id": "test_paradox",
        "type": "trolley",
        "promptTemplate": "Scenario.\n\n**Options**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
        ],
    }

    run_data = asyncio.run(
        qp.execute_run(
            RunConfig(
                modelName="generator/model",
                paradox=paradox,
                iterations=1,
                params={"max_tokens": 200},
            )
        )
    )

    response = run_data["responses"][0]
    assert "error" in response
    assert response["iteration"] == 1
    assert run_data["summary"]["undecided"]["count"] == 1
