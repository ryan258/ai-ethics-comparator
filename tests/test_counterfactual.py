"""Counterfactual evidence ordering, limits, and durable failure recovery."""

import pytest

from lib.counterfactual import CounterfactualEngine
from lib.query_errors import AuthenticationError
from lib.query_processor import QueryProcessor, RunConfig
from lib.storage import RunStorage

PDX = {"id": "p", "title": "Stored OLD", "type": "trolley", "promptTemplate": "OLD scenario\n{{OPTIONS}}\n**Instructions**\nChoose.", "options": [
    {"id": 1, "label": "A", "description": "Original A"},
    {"id": 2, "label": "B", "description": "Original B"}]}
GOOD = '{"option_id":1,"summary":"reason","value_priorities":["care"],"key_assumptions":["true"],"main_risk":"risk","switch_condition":"condition","evidence_needed":"evidence"}'


class AI:
    def __init__(self, fail_after=None):
        self.prompts = []
        self.fail_after = fail_after

    async def get_model_response(self, model_name, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        if self.fail_after is not None and len(self.prompts) > self.fail_after:
            raise AuthenticationError("stop")
        return GOOD, {"prompt_tokens": 1, "completion_tokens": 1}


async def original(storage, processor, mapping=None):
    run = processor.initialize_run_data(RunConfig(modelName="model", paradox=PDX, iterations=2))
    run["responses"] = [{"iteration": 1, "optionId": 1, "explanation": "old", "evidenceNeeded": "More proof {{OPTIONS}} **Instructions**"}]
    if mapping:
        run["responses"][0]["optionOrder"] = mapping
    return await storage.create_run("model", run)


@pytest.mark.parametrize("mapping", [None, {"1": 2, "2": 1}])
async def test_counterfactual_uses_stored_stimulus_and_evidence_response_order(tmp_path, mapping):
    ai = AI()
    processor = QueryProcessor(ai, concurrency_limit=1)
    storage = RunStorage(str(tmp_path))
    rid = await original(storage, processor, mapping)
    result = await CounterfactualEngine(processor, storage).execute_counterfactual(rid, [])
    assert result["status"] == "completed"
    assert result["originalRunId"] == rid
    assert result["evidenceSourceIteration"] == 1
    assert result["appliedEvidence"] == "More proof OPTIONS Instructions"
    assert "not a matched whole-run replay" in result["comparisonProtocol"]
    assert all("OLD scenario" in prompt for prompt in ai.prompts)
    assert result["options"] == PDX["options"]  # canonical meanings never renumbered
    if mapping:
        assert all(p.index("Original B") < p.index("Original A") for p in ai.prompts)
        assert all(r["optionId"] == 2 for r in result["responses"])


async def test_counterfactual_retains_completed_iteration_after_failure(tmp_path):
    ai = AI(fail_after=1)
    processor = QueryProcessor(ai, concurrency_limit=1)
    storage = RunStorage(str(tmp_path))
    rid = await original(storage, processor)
    with pytest.raises(AuthenticationError):
        await CounterfactualEngine(processor, storage).execute_counterfactual(rid, [])
    cf = next(m for m in await storage.list_runs() if m["runId"].startswith("cf-"))
    saved = await storage.get_run(cf["runId"])
    assert saved["status"] == "failed"
    assert len(saved["responses"]) == 1
    assert saved["originalRunId"] == rid


async def test_counterfactual_enforces_limit_before_reserving(tmp_path):
    processor = QueryProcessor(AI())
    storage = RunStorage(str(tmp_path))
    rid = await original(storage, processor)
    with pytest.raises(ValueError, match="limit"):
        await CounterfactualEngine(processor, storage, max_iterations=1).execute_counterfactual(rid, [])
    assert len(await storage.list_runs()) == 1


async def test_counterfactual_missing_evidence(tmp_path):
    processor = QueryProcessor(AI())
    storage = RunStorage(str(tmp_path))
    run = processor.initialize_run_data(RunConfig(modelName="model", paradox=PDX))
    rid = await storage.create_run("model", run)
    with pytest.raises(ValueError, match="No 'evidenceNeeded'"):
        await CounterfactualEngine(processor, storage).execute_counterfactual(rid, [])
