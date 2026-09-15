"""Behavioral reproductions for the September evidence/lifecycle audit."""
import asyncio
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.evidence import ANALYSIS_VERSION, evidence_hash, validate_comparison
from lib.experiment_runner import ExperimentRunner
from lib.paradoxes import (
    ETHICAL_DIMENSIONS,
    _normalize_paradox,
    load_paradoxes,
)
from lib.query_processor import aggregate_trolley_stats
from lib.reporting import ReportGenerator
from lib.stats import chi_square_test, wilson_confidence_interval
from lib.storage import ExperimentStorage, RunStorage
from lib.validation import InsightRequest

ROOT = Path(__file__).resolve().parents[1]
PDX = {"id": "p", "title": "OLD", "type": "trolley", "promptTemplate": "OLD stimulus\n{{OPTIONS}}", "options": [
    {"id": 1, "label": "A", "description": "meaning A"}, {"id": 2, "label": "B", "description": "meaning B"}]}


def analyst_payload():
    return {"dominant_framework": "Duty", "moral_complexes": [
        {"label": label, "count": 0, "justification": "absent"} for label in ETHICAL_DIMENSIONS],
        "justifications": [], "consistency": [], "key_insights": []}


@pytest.mark.parametrize("fallback", [False, True])
async def test_real_outgoing_analysis_contains_evidence_and_stimulus(tmp_path, fallback):
    class AI:
        async def get_model_response(self, model, prompt, *args):
            assert "UNIQUE-EVIDENCE" in prompt
            assert "OLD stimulus" in prompt and "meaning B" in prompt
            assert "temperature" in prompt and "persona-marker" in prompt
            assert "{data}" not in prompt
            return json.dumps(analyst_payload()), {}
    engine = AnalysisEngine(AI(), prompt_template_path=tmp_path/'missing' if fallback else ROOT/'templates/analysis_prompt.txt')
    run = {"paradox": PDX, "paradoxId": "p", "options": PDX["options"], "params": {"temperature": 0.4},
           "systemPrompt": "persona-marker", "responses": [{"explanation": "UNIQUE-EVIDENCE"}]}
    result = await engine.generate_insight(AnalysisConfig(run, "analyst"))
    assert result["analysisVersion"] == ANALYSIS_VERSION
    assert result["evidenceHash"] == evidence_hash(run)
    assert result["content"]["moral_complexes"][0]["count"] == 0


@pytest.mark.parametrize("data", [{"responses": None}, {"responses": [None]}, {"responses": [{"explanation": []}]}, {"responses": [{"optionId": "1"}]}])
def test_malformed_nested_run_input_is_validation_error(data):
    with pytest.raises(ValidationError):
        InsightRequest(runData=data)


def test_duplicate_scenario_and_option_ids_rejected(tmp_path):
    pdx = copy.deepcopy(PDX)
    pdx["options"][1]["id"] = 1
    assert _normalize_paradox(pdx) is None
    path = tmp_path/'paradoxes.json'
    path.write_text(json.dumps([PDX, PDX]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_paradoxes(path)


def test_jointly_empty_category_cannot_change_significance():
    assert chi_square_test([18, 10], [10, 18]) == chi_square_test([18, 10, 0], [10, 18, 0])
    assert chi_square_test([1, 0], [2, 0]) is None
    with pytest.raises(ValueError):
        chi_square_test([1], [1, 2])
    with pytest.raises(ValueError):
        chi_square_test([-1, 2], [1, 2])
    ci = wilson_confidence_interval(50, 100)
    assert abs(ci["marginOfError"] - (ci["upper"] - ci["lower"])/2) < 0.0001


async def test_run_1000_is_readable_and_next_allocation_advances(tmp_path):
    storage = RunStorage(str(tmp_path))
    await storage.save_run("model-999", {"runId": "model-999"})
    rid = await storage.create_run("model", {"responses": []})
    assert rid == "model-1000"
    assert (await storage.get_run(rid))["runId"] == rid
    assert await storage.create_run("model", {}) == "model-1001"
    assert await storage.migrate_legacy_run_ids() == {}


async def test_concurrent_derived_updates_survive_stale_progress(tmp_path):
    storage = RunStorage(str(tmp_path))
    initial = {"responses": [], "insights": [], "status": "running"}
    rid = await storage.create_run("model", initial)
    await asyncio.gather(*[
        storage.update_run(rid, lambda run, n=n: run.setdefault("insights", []).append({"id": n}))
        for n in range(8)])
    await storage.update_run(rid, lambda run: run.update(narrative={"text": "new"}))
    await storage.save_run(rid, {**initial, "responses": [{"iteration": 1}]})
    final = await storage.get_run(rid)
    assert len(final["insights"]) == 8 and final["narrative"] == {"text": "new"}
    assert len(final["responses"]) == 1


def test_comparisons_reject_duplicates_revision_and_meaning_drift():
    one = {"runId": "m-001", "paradox": PDX, "options": PDX["options"]}
    two = copy.deepcopy(one); two["runId"] = "m-002"
    validate_comparison([one, two])
    with pytest.raises(ValueError, match="distinct"):
        validate_comparison([one, one])
    two["paradox"]["promptTemplate"] = "NEW"
    with pytest.raises(ValueError, match="revision"):
        validate_comparison([one, two])
    two = copy.deepcopy(one); two["runId"] = "m-002"; two["options"][0]["description"] = "different"
    with pytest.raises(ValueError, match="meanings"):
        validate_comparison([one, two])


@pytest.mark.parametrize("scenario", ["king_pet_sematary", "borges_pierre_menard"])
@pytest.mark.parametrize("choices", [[1]*4, [2]*4, [3]*4, [4]*4, [1,2,3,4], [None]*4])
def test_shipped_overrides_cannot_override_measured_outcomes(scenario, choices):
    pdx = next(p for p in load_paradoxes(ROOT/'paradoxes.json') if p['id'] == scenario)
    responses = [{"iteration": i, "optionId": c, "explanation": "care", "raw": "care"} for i,c in enumerate(choices, 1)]
    run = {"runId": "m-001", "modelName": "model", "paradoxId": scenario, "paradoxType": "trolley", "responses": responses,
           "options": pdx['options'], "summary": aggregate_trolley_stats(responses, 4)}
    gen = ReportGenerator(templates_dir=str(ROOT/'templates'))
    report = gen._build_report_context(run, pdx, None)
    if choices[0] is None:
        assert "No directional result" in report.thesis_statement
    elif len(set(choices)) == 1:
        label = pdx['options'][choices[0]-1]['label']
        assert label in report.report_title
        assert "4 of 4" in report.executive_summary
    else:
        assert "split" in report.report_title.lower()


async def test_experiment_reservation_survives_cancellation(tmp_path):
    entered = asyncio.Event()
    class Processor:
        def initialize_run_data(self, config):
            return {"modelName": config.modelName, "responses": [], "status": "running"}
        async def execute_run(self, config, existing_run=None, progress_callback=None):
            entered.set()
            await asyncio.Event().wait()
    runs = RunStorage(str(tmp_path/'runs')); experiments = ExperimentStorage(str(tmp_path/'experiments'))
    exp = {"id": "exp_1", "title": "x", "status": "pending", "createdAt": "today", "paradoxIds": ["p"], "conditions": [{"modelName": "m", "iterations": 1}]}
    await experiments.save_experiment("exp_1", exp)
    claim_results = await asyncio.gather(experiments.claim_experiment("exp_1"), experiments.claim_experiment("exp_1"), return_exceptions=True)
    assert sum(isinstance(r, ValueError) for r in claim_results) == 1
    exp = next(r for r in claim_results if isinstance(r, dict))
    runner = ExperimentRunner(Processor(), runs, experiments)
    task = asyncio.create_task(runner.execute_experiment("exp_1", exp, [PDX]))
    await entered.wait()
    manifest = await experiments.get_experiment("exp_1")
    assert len(manifest["runIds"]) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    saved = await runs.get_run(manifest["runIds"][0])
    assert saved["status"] == "interrupted"
    manifest = await experiments.get_experiment("exp_1")
    assert manifest["conditionStates"][saved["runId"]] == "interrupted"


async def test_shuffled_resume_uses_saved_stimulus_after_live_edit():
    from lib.query_processor import QueryProcessor, RunConfig
    class AI:
        async def get_model_response(self, model, prompt, *args, **kwargs):
            assert 'OLD stimulus' in prompt and 'NEW stimulus' not in prompt
            return ('{"option_id":1,"summary":"s","value_priorities":["v"],"key_assumptions":["k"],"main_risk":"r","switch_condition":"c","evidence_needed":"e"}', {})
    processor = QueryProcessor(AI(), concurrency_limit=1)
    original = RunConfig(modelName='model', paradox=PDX, iterations=1, shuffle_options=True)
    saved = processor.initialize_run_data(original)
    changed = {**PDX, 'title':'NEW', 'promptTemplate':'NEW stimulus\n{{OPTIONS}}'}
    result = await processor.execute_run(RunConfig(modelName='model', paradox=changed, iterations=1, shuffle_options=True), existing_run=saved)
    assert result['paradox']['title'] == 'OLD'
    assert result['paradoxTitle'] == 'OLD'
    assert result['responses'][0]['optionOrder']
