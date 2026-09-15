import asyncio
from pathlib import Path

import pytest

from lib.experiment_runner import condition_to_run_config
from lib.storage import ExperimentStorage
from lib.validation import ConditionConfig, ExperimentCreateRequest, ExperimentRecord


def test_condition_config_alias_roundtrip() -> None:
    data = {
        "modelName": "test-model",
        "shuffleOptions": False,
    }

    config = ConditionConfig(**data)
    assert config.shuffle_options is False

    dumped = config.model_dump(by_alias=True)
    assert dumped["shuffleOptions"] is False
    assert "shuffle_options" not in dumped

    roundtripped = ConditionConfig(**dumped)
    assert roundtripped.shuffle_options is False


def test_condition_config_defaults_shuffle_on() -> None:
    config = ConditionConfig(modelName="test-model")
    assert config.shuffle_options is True


def test_condition_config_iterations_clamp() -> None:
    config = ConditionConfig(modelName="test", iterations=50)

    class DummyParadox:
        pass

    pdx = DummyParadox()

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        condition_to_run_config(config, pdx, 10)

    config_valid = ConditionConfig(modelName="test", iterations=5)
    run_config = condition_to_run_config(config_valid, pdx, 10)
    assert run_config.iterations == 5

    config_default = ConditionConfig(modelName="test")
    run_config_default = condition_to_run_config(config_default, pdx, 10)
    assert run_config_default.iterations == 10


def test_experiment_create_request_paradox_ids() -> None:
    req = ExperimentCreateRequest(
        title="Valid",
        paradoxIds=["pdx-1", "pdx_2", "valid3"],
        conditions=[{"modelName": "m1"}],
    )
    assert len(req.paradoxIds) == 3

    with pytest.raises(ValueError, match="Invalid paradox ID format"):
        ExperimentCreateRequest(
            title="Invalid",
            paradoxIds=["invalid param", "pdx2!"],
            conditions=[{"modelName": "m1"}],
        )


def test_experiment_create_request_limits_total_matrix() -> None:
    with pytest.raises(ValueError, match="Experiment matrix exceeds maximum allowed runs"):
        ExperimentCreateRequest(
            title="Too Big",
            paradoxIds=[f"pdx{i}" for i in range(10)],
            conditions=[{"modelName": f"m{i}"} for i in range(6)],
        )


def test_experiment_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = ExperimentStorage(str(tmp_path / "experiments"))

    with pytest.raises(ValueError, match="Invalid exp_id"):
        asyncio.run(storage.get_experiment("../experiments2/escape"))


def test_experiment_record_ignores_extra_storage_keys() -> None:
    record = ExperimentRecord(
        id="exp_1",
        title="Stored",
        paradoxIds=["pdx1"],
        conditions=[{"modelName": "model-a", "shuffleOptions": False}],
        runIds=[],
        errors=[],
        status="pending",
        tags=[],
        createdAt="2023-01-01T00:00:00+00:00",
        manualNote="keep me out",
    )

    dumped = record.model_dump(by_alias=True)
    assert "manualNote" not in dumped
    assert dumped["conditions"][0]["shuffleOptions"] is False


def test_experiment_runner_partial_and_error() -> None:
    from lib.experiment_runner import ExperimentRunner

    class MockQueryProcessor:
        def initialize_run_data(self, config, existing_run=None):
            return {"modelName": config.modelName, "responses": [], "status": "running"}

        async def execute_run(self, config, *, existing_run=None, progress_callback=None):
            if config.modelName == "fail_model":
                raise ValueError("Model exploded")
            if config.modelName == "partial_model":
                result = {"responses": [{"error": "token limit"}, {"explanation": "OK"}]}
            else:
                result = {"responses": [{"explanation": "OK"}]}
            if progress_callback is not None:
                await progress_callback(dict(result))
            return result

    class MockRunStorage:
        def __init__(self):
            self.saved = {}

        async def create_run(self, name, data):
            run_id = f"run-{name}"
            data["runId"] = run_id
            self.saved[run_id] = data
            return run_id

        async def update_run(self, run_id, change):
            change(self.saved[run_id])
            return self.saved[run_id]

        async def save_run(self, run_id, data):
            self.saved[run_id] = data

        async def get_run(self, run_id):
            return self.saved[run_id]

    class MockExperimentStorage:
        async def save_experiment(self, exp_id, data):
            return None

    q_proc = MockQueryProcessor()
    r_stor = MockRunStorage()
    e_stor = MockExperimentStorage()
    paradoxes = [
        {
            "id": "pdx1",
            "title": "Pdx 1",
            "promptTemplate": "test",
            "type": "trolley",
            "options": [
                {"id": 1, "label": "A", "description": "Option A"},
                {"id": 2, "label": "B", "description": "Option B"},
            ],
        }
    ]
    runner = ExperimentRunner(q_proc, r_stor, e_stor, 10, max_concurrent_conditions=2)

    exp_data = {
        "id": "exp_1",
        "status": "pending",
        "title": "Success Test",
        "paradoxIds": ["pdx1"],
        "conditions": [{"modelName": "ok_model"}],
        "createdAt": "2023-01-01",
    }
    result = asyncio.run(runner.execute_experiment("exp_1", exp_data, paradoxes))
    assert result.status == "completed"
    assert len(result.runIds) == 1

    exp_data_partial = {
        "id": "exp_2",
        "status": "pending",
        "title": "Partial Test",
        "paradoxIds": ["pdx1"],
        "conditions": [{"modelName": "partial_model"}],
        "createdAt": "2023-01-01",
    }
    partial_result = asyncio.run(runner.execute_experiment("exp_2", exp_data_partial, paradoxes))
    assert partial_result.status == "partial"

    exp_data_failed = {
        "id": "exp_3",
        "status": "pending",
        "title": "Fail Test",
        "paradoxIds": ["pdx1"],
        "conditions": [{"modelName": "fail_model"}],
        "createdAt": "2023-01-01",
    }
    failed_result = asyncio.run(runner.execute_experiment("exp_3", exp_data_failed, paradoxes))
    assert failed_result.status == "failed"
    assert "Model exploded" in failed_result.errors[0]
