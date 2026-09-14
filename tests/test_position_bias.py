"""Regression tests for D-04: position-bias mitigation must be on and per-iteration.

Two separate defects are pinned here:

1. `QueryRequest` had no shuffle field at all, so every run started from the web
   UI presented options in fixed order -- the primary workflow carried
   uncontrolled position bias while the roadmap claimed the feature shipped.
2. The permutation was drawn once per RUN, so all N iterations shared one
   ordering. That randomises bias across runs but never averages it out within
   one, which is the unit the reported distribution is computed over.
"""

from __future__ import annotations

import copy

from lib.query_processor import (
    QueryProcessor,
    RunConfig,
    permute_options,
    template_supports_option_rendering,
)
from lib.validation import QueryRequest

PARADOX = {
    "id": "pos_bias",
    "title": "Position Bias",
    "type": "trolley",
    "promptTemplate": "Choose.\n\n{{OPTIONS}}\n\n**Instructions** pick one.",
    "options": [
        {"id": 1, "label": "Alpha", "description": "alpha text"},
        {"id": 2, "label": "Beta", "description": "beta text"},
        {"id": 3, "label": "Gamma", "description": "gamma text"},
        {"id": 4, "label": "Delta", "description": "delta text"},
    ],
}


class ScriptedAI:
    """Records every prompt it is shown and always answers displayed slot 1."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def get_model_response(self, model, prompt, system_prompt, params, **kwargs):
        self.prompts.append(prompt)
        return (
            '{"option_id": 1, "summary": "s", "value_priorities": ["v"],'
            ' "key_assumptions": ["k"], "main_risk": "r",'
            ' "switch_condition": "c", "evidence_needed": "e"}',
            {"prompt_tokens": 1, "completion_tokens": 1},
        )


# --- reachability (defect 1) ---------------------------------------------


def test_query_request_exposes_shuffle_and_defaults_on() -> None:
    assert QueryRequest(modelName="a/b", paradoxId="x").shuffle_options is True


def test_query_request_shuffle_can_be_disabled_via_alias() -> None:
    request = QueryRequest(modelName="a/b", paradoxId="x", shuffleOptions=False)
    assert request.shuffle_options is False


# --- permutation mechanics ------------------------------------------------


def test_permute_options_renumbers_and_maps_back() -> None:
    displayed, mapping = permute_options(PARADOX["options"])

    assert [o["id"] for o in displayed] == [1, 2, 3, 4]
    # Every displayed slot maps to a distinct original id.
    assert sorted(mapping.values()) == [1, 2, 3, 4]
    # The mapping really is the inverse of what was displayed.
    for option in displayed:
        original = next(o for o in PARADOX["options"] if o["label"] == option["label"])
        assert mapping[str(option["id"])] == original["id"]


def test_permute_options_does_not_mutate_the_canonical_list() -> None:
    before = copy.deepcopy(PARADOX["options"])
    permute_options(PARADOX["options"])
    assert PARADOX["options"] == before


# --- per-iteration behaviour (defect 2) -----------------------------------


async def test_ordering_varies_across_iterations() -> None:
    ai = ScriptedAI()
    processor = QueryProcessor(ai, concurrency_limit=1)

    await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=25, shuffle_options=True)
    )

    first_listed = [p.split("1. **")[1].split(":")[0] for p in ai.prompts]
    assert len(set(first_listed)) > 1, (
        "every iteration showed the same option first -- the permutation is not "
        f"per-iteration. Saw only: {set(first_listed)}"
    )


async def test_each_response_records_the_ordering_it_saw() -> None:
    processor = QueryProcessor(ScriptedAI(), concurrency_limit=1)

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=5, shuffle_options=True)
    )

    for response in run["responses"]:
        assert "optionOrder" in response, "run is not auditable without the ordering"
        assert sorted(response["optionOrder"].values()) == [1, 2, 3, 4]


async def test_answers_are_unshuffled_back_to_canonical_ids() -> None:
    """The AI always picks displayed slot 1; results must spread over real ids."""
    processor = QueryProcessor(ScriptedAI(), concurrency_limit=1)

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=30, shuffle_options=True)
    )

    for response in run["responses"]:
        assert response["optionId"] == response["optionOrder"]["1"]

    chosen = {r["optionId"] for r in run["responses"]}
    assert len(chosen) > 1, (
        "a model that always picks the first slot produced one canonical answer "
        "-- un-shuffling is not being applied"
    )


async def test_shuffle_off_keeps_canonical_order_and_records_nothing() -> None:
    ai = ScriptedAI()
    processor = QueryProcessor(ai, concurrency_limit=1)

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=4, shuffle_options=False)
    )

    assert all("1. **Alpha:**" in p for p in ai.prompts)
    assert all(r["optionId"] == 1 for r in run["responses"])
    assert all("optionOrder" not in r for r in run["responses"])


async def test_run_records_the_permutation_mode_for_resume() -> None:
    processor = QueryProcessor(ScriptedAI(), concurrency_limit=1)

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=2, shuffle_options=True)
    )

    assert run["shufflePerIteration"] is True
    # The run-level prompt stays the canonical rendering, for reproducibility.
    assert "1. **Alpha:**" in run["prompt"]


async def test_legacy_run_level_shuffle_mapping_is_honoured_on_resume() -> None:
    """Runs created before D-04 carry one fixed ordering; don't re-permute them."""
    ai = ScriptedAI()
    processor = QueryProcessor(ai, concurrency_limit=1)
    existing = {
        "runId": "legacy-001",
        "prompt": "Choose.\n\n1. **Delta:** delta text\n\n**Instructions** pick one.",
        "options": copy.deepcopy(PARADOX["options"]),
        "shuffleMapping": {"1": 4, "2": 3, "3": 2, "4": 1},
        "responses": [],
    }

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=PARADOX, iterations=3, shuffle_options=True),
        existing_run=existing,
    )

    assert run["shuffleMapping"] == {"1": 4, "2": 3, "3": 2, "4": 1}
    assert "shufflePerIteration" not in run
    # Displayed slot 1 maps to canonical option 4 for every iteration.
    assert all(r["optionId"] == 4 for r in run["responses"])


# --- the permutation must be expressible in the prompt ------------------


RECONSTRUCTED = {
    "id": "gone",
    "title": "Gone Scenario",
    "type": "trolley",
    # D11 tier 3 hands back the run's ALREADY-RENDERED prompt as the template.
    # There is no placeholder left to substitute options into.
    "promptTemplate": "Choose.\n\n1. **Alpha:** alpha\n\n2. **Beta:** beta\n\n**Instructions** pick.",
    "options": [
        {"id": 1, "label": "Alpha", "description": "alpha"},
        {"id": 2, "label": "Beta", "description": "beta"},
    ],
}


def test_template_support_detection() -> None:
    assert template_supports_option_rendering("x {{OPTIONS}} y")
    assert template_supports_option_rendering("x {{GROUP1}} / {{GROUP2}} y")
    assert not template_supports_option_rendering(RECONSTRUCTED["promptTemplate"])
    assert not template_supports_option_rendering(None)


async def test_no_placeholder_disables_shuffle_instead_of_mismapping() -> None:
    """A permutation the prompt cannot express must not be recorded.

    Re-rendering a placeholder-less template is a no-op: the model keeps seeing
    one fixed order. If the mapping still claimed a shuffle, every answer would
    be translated through a permutation that never happened -- iteration 2 of
    the original repro recorded option 2 when the model had chosen option 1.
    """
    ai = ScriptedAI()
    processor = QueryProcessor(ai, concurrency_limit=1)
    existing = {
        "runId": "legacy-001",
        "prompt": RECONSTRUCTED["promptTemplate"],
        "options": copy.deepcopy(RECONSTRUCTED["options"]),
        "responses": [],
    }

    run = await processor.execute_run(
        RunConfig(modelName="a/b", paradox=RECONSTRUCTED, iterations=6, shuffle_options=True),
        existing_run=existing,
    )

    # Every prompt shows Alpha first, so every answer really is option 1.
    assert all("1. **Alpha:**" in p for p in ai.prompts)
    assert all(r["optionId"] == 1 for r in run["responses"])
    assert all("optionOrder" not in r for r in run["responses"])
    # The record must not claim a mode it did not use.
    assert "shufflePerIteration" not in run
