"""Regression tests for run-execution bounds, persistence, and failure surfacing.

Each test here covers a path that previously had no coverage, which is why the
suite stayed green while the behaviour was broken.
"""

from __future__ import annotations

import asyncio

import pytest

from lib.query_errors import AuthenticationError, InvalidModelOutputError
from lib.query_processor import QueryProcessor, RunConfig

GOOD_RESPONSE = (
    '{"option_id": 1, "summary": "s", "value_priorities": ["v"], '
    '"key_assumptions": ["k"], "main_risk": "r", "switch_condition": "c", '
    '"evidence_needed": "e"}'
)

PARADOX = {
    "id": "p",
    "type": "trolley",
    "promptTemplate": "Scenario.\n\n{{OPTIONS}}",
    "options": [
        {"id": 1, "label": "A", "description": "a"},
        {"id": 2, "label": "B", "description": "b"},
    ],
}


class _CountingAI:
    """Minimal AIService stand-in that records how many calls it received."""

    def __init__(self, responder) -> None:
        self.calls = 0
        self._responder = responder

    async def get_model_response(
        self,
        model_name,
        prompt,
        system_prompt="",
        params=None,
        retry_count=0,
        *,
        response_schema=None,
    ):
        self.calls += 1
        await asyncio.sleep(0)  # yield so a runaway loop cannot starve the loop
        return self._responder(self.calls), {"prompt_tokens": 1, "completion_tokens": 1}


def test_reask_budget_is_enforced_and_records_undecided() -> None:
    """A model that never emits a valid choice must not re-ask forever."""
    ai = _CountingAI(lambda _n: "I cannot decide between these options.")
    processor = QueryProcessor(
        ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
        max_reasks_per_iteration=2,
    )

    run_data = asyncio.run(
        processor.execute_run(RunConfig(modelName="m", paradox=PARADOX, iterations=1))
    )

    # 1 initial attempt + exactly max_reasks_per_iteration re-asks.
    assert ai.calls == 3

    response = run_data["responses"][0]
    assert response["optionId"] is None
    assert response["error"]
    assert response["reaskCount"] == 2
    # An exhausted iteration counts as undecided, not as a silent drop.
    assert run_data["summary"]["undecided"]["count"] == 1
    assert run_data["summary"]["total"] == 1


def test_unusable_output_spends_the_reask_budget_not_the_provider_budget() -> None:
    """An empty provider response must degrade to undecided, not abort the run.

    InvalidModelOutputError derives from RetryableQueryError, so it used to land
    in the provider-retry branch: same prompt re-sent, then a raise that failed
    the whole run. It is a parsing concern and belongs on the re-ask budget.
    """

    def responder(call: int) -> str:
        if call <= 2:
            raise InvalidModelOutputError("Model returned an empty response")
        return GOOD_RESPONSE

    ai = _CountingAI(responder)
    processor = QueryProcessor(
        ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model="classifier",
        max_reasks_per_iteration=2,
        max_provider_retries_per_iteration=3,
    )

    run_data = asyncio.run(
        processor.execute_run(RunConfig(modelName="m", paradox=PARADOX, iterations=1))
    )

    # 2 unusable attempts (re-asked with a corrected prompt) then a good one.
    # The classifier is never consulted about empty text, so no extra calls.
    assert ai.calls == 3
    assert run_data["responses"][0]["optionId"] == 1
    assert run_data["status"] == "completed"


def test_unusable_output_exhausting_the_reask_budget_records_undecided() -> None:
    def responder(_call: int) -> str:
        raise InvalidModelOutputError("Model returned an empty response")

    ai = _CountingAI(responder)
    processor = QueryProcessor(
        ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model="classifier",
        max_reasks_per_iteration=2,
    )

    run_data = asyncio.run(
        processor.execute_run(RunConfig(modelName="m", paradox=PARADOX, iterations=2))
    )

    assert run_data["status"] == "completed"
    assert run_data["summary"]["undecided"]["count"] == 2
    for response in run_data["responses"]:
        assert response["optionId"] is None
        assert "empty response" in response["error"]


def test_reask_budget_of_zero_does_not_retry() -> None:
    ai = _CountingAI(lambda _n: "no choice here")
    processor = QueryProcessor(
        ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
        max_reasks_per_iteration=0,
    )

    asyncio.run(processor.execute_run(RunConfig(modelName="m", paradox=PARADOX, iterations=1)))

    assert ai.calls == 1


def test_progress_is_persisted_after_each_iteration() -> None:
    """Persistence must happen as iterations land, not once the batch finishes."""
    ai = _CountingAI(lambda _n: GOOD_RESPONSE)
    processor = QueryProcessor(
        ai,  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
    )

    snapshots: list[int] = []

    async def progress(snapshot):
        snapshots.append(snapshot["completedIterations"])

    asyncio.run(
        processor.execute_run(
            RunConfig(modelName="m", paradox=PARADOX, iterations=4),
            progress_callback=progress,
        )
    )

    # One persist per iteration, each carrying strictly more completed work.
    assert snapshots == [1, 2, 3, 4]


def test_terminal_provider_failure_propagates_without_orphaning_siblings() -> None:
    """gather must wait for every iteration, then surface the failure."""
    started = 0
    finished = 0

    class _AI:
        async def get_model_response(self, *args, **kwargs):
            nonlocal started, finished
            started += 1
            mine = started
            await asyncio.sleep(0.01)
            if mine == 1:
                raise AuthenticationError("bad key")
            finished += 1
            return GOOD_RESPONSE, {"prompt_tokens": 1, "completion_tokens": 1}

    processor = QueryProcessor(
        _AI(),  # type: ignore[arg-type]
        concurrency_limit=4,
        choice_inference_model=None,
    )

    with pytest.raises(AuthenticationError):
        asyncio.run(
            processor.execute_run(RunConfig(modelName="m", paradox=PARADOX, iterations=4))
        )

    # Every sibling ran to completion rather than being left orphaned.
    assert started == 4
    assert finished == 3


def test_successful_iterations_persist_before_a_terminal_failure() -> None:
    """Partial work survives so the run can be resumed."""

    class _AI:
        def __init__(self) -> None:
            self.calls = 0

        async def get_model_response(self, *args, **kwargs):
            self.calls += 1
            await asyncio.sleep(0)
            if self.calls == 2:
                raise AuthenticationError("bad key")
            return GOOD_RESPONSE, {"prompt_tokens": 1, "completion_tokens": 1}

    processor = QueryProcessor(
        _AI(),  # type: ignore[arg-type]
        concurrency_limit=1,
        choice_inference_model=None,
    )

    persisted: list[dict] = []

    async def progress(snapshot):
        persisted.append(snapshot)

    with pytest.raises(AuthenticationError):
        asyncio.run(
            processor.execute_run(
                RunConfig(modelName="m", paradox=PARADOX, iterations=3),
                progress_callback=progress,
            )
        )

    assert persisted, "completed iterations must reach storage before the failure"
    assert persisted[-1]["completedIterations"] >= 1
