import asyncio
from pathlib import Path

import pytest

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


def test_condition_config_defaults_shuffle_off() -> None:
    config = ConditionConfig(modelName="test-model")
    assert config.shuffle_options is False


def test_condition_config_iterations_clamp() -> None:
    config = ConditionConfig(modelName="test", iterations=50)

    class DummyParadox:
        pass

    pdx = DummyParadox()

    with pytest.raises(ValueError, match="exceeds maximum allowed"):
        config.to_run_config(pdx, 10)

    config_valid = ConditionConfig(modelName="test", iterations=5)
    run_config = config_valid.to_run_config(pdx, 10)
    assert run_config.iterations == 5

    config_default = ConditionConfig(modelName="test")
    run_config_default = config_default.to_run_config(pdx, 10)
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
        async def execute_run(self, config):
            if config.modelName == "fail_model":
                raise ValueError("Model exploded")
            if config.modelName == "partial_model":
                return {"responses": [{"error": "token limit"}, {"explanation": "OK"}]}
            return {"responses": [{"explanation": "OK"}]}

    class MockRunStorage:
        async def generate_run_id(self, name):
            return f"run-{name}"

        async def save_run(self, run_id, data):
            return None

        async def ensure_results_dir(self):
            return None

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
