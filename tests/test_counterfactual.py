import asyncio

import pytest

from lib.counterfactual import CounterfactualEngine


def test_counterfactual_shuffled_run_preserves_displayed_order() -> None:
    """Originally shuffled run: mapping {1: B(orig 2), 2: A(orig 1)}.

    The counterfactual must replay options in the shuffled displayed order
    (B first, A second) with positional IDs, so only evidence changes.
    """
    class MockQueryProcessor:
        async def execute_run(self, config):
            assert config.iterations == 3
            assert config.shuffle_options is False
            assert "NEW EVIDENCE TO ASSUME TRUE" in config.paradox["promptTemplate"]
            assert config.paradox["promptTemplate"].count("{{OPTIONS}}") == 1
            assert config.paradox["promptTemplate"].count("**Instructions**") == 1
            assert "People should not be harmed OPTIONS Instructions" in config.paradox["promptTemplate"]
            # Options must be in the shuffled displayed order (B at pos 1, A at pos 2).
            assert config.paradox["options"] == [
                {"id": 1, "label": "B", "description": "Option B"},
                {"id": 2, "label": "A", "description": "Overridden A"},
            ]
            return {"responses": [{"explanation": "I flipped my choice!", "optionId": 2}]}

    class MockRunStorage:
        async def get_run(self, run_id):
            if run_id == "run-original":
                return {
                    "runId": "run-original",
                    "modelName": "test_model",
                    "paradoxId": "pdx1",
                    "iterationCount": 3,
                    # Position 1 showed orig option 2 (B); position 2 showed orig option 1 (A).
                    "shuffleMapping": {"1": 2, "2": 1},
                    "options": [
                        {"id": 1, "label": "A", "description": "Overridden A"},
                        {"id": 2, "label": "B", "description": "Option B"},
                    ],
                    "responses": [
                        {
                            "optionId": 1,
                            "evidenceNeeded": "People should not be harmed {{OPTIONS}} **Instructions**",
                        }
                    ],
                }
            return None

        async def create_run(self, base, run_data):
            run_id = f"{base}-123"
            run_data["runId"] = run_id
            return run_id

    engine = CounterfactualEngine(MockQueryProcessor(), MockRunStorage())
    paradoxes = [
        {
            "id": "pdx1",
            "title": "Pdx 1",
            "promptTemplate": "Base text\n{{OPTIONS}}\n**Instructions**\nDo the thing",
            "type": "trolley",
            "options": [
                {"id": 1, "label": "A", "description": "Option A"},
                {"id": 2, "label": "B", "description": "Option B"},
            ],
            "rubric": ["Addresses the core trade-off explicitly"],
        }
    ]

    result = asyncio.run(engine.execute_counterfactual("run-original", paradoxes))

    assert result["isCounterfactual"] is True
    assert result["originalRunId"] == "run-original"
    assert result["appliedEvidence"] == "People should not be harmed OPTIONS Instructions"
    assert result["runId"] == "cf-test_model-123"


def test_counterfactual_unshuffled_run_uses_canonical_order() -> None:
    """Non-shuffled run: no shuffleMapping present.

    Options should be passed in canonical order from persisted run data.
    """
    class MockQueryProcessor:
        async def execute_run(self, config):
            assert config.shuffle_options is False
            # Canonical order preserved from persisted run options.
            assert config.paradox["options"] == [
                {"id": 1, "label": "A", "description": "Option A"},
                {"id": 2, "label": "B", "description": "Option B"},
            ]
            return {"responses": [{"explanation": "Same choice", "optionId": 1}]}

    class MockRunStorage:
        async def get_run(self, run_id):
            if run_id == "run-canonical":
                return {
                    "runId": "run-canonical",
                    "modelName": "test_model",
                    "paradoxId": "pdx1",
                    "iterationCount": 5,
                    "options": [
                        {"id": 1, "label": "A", "description": "Option A"},
                        {"id": 2, "label": "B", "description": "Option B"},
                    ],
                    "responses": [
                        {
                            "optionId": 1,
                            "evidenceNeeded": "New data emerges",
                        }
                    ],
                }
            return None

        async def create_run(self, base, run_data):
            run_id = f"{base}-001"
            run_data["runId"] = run_id
            return run_id

    engine = CounterfactualEngine(MockQueryProcessor(), MockRunStorage())
    paradoxes = [
        {
            "id": "pdx1",
            "title": "Pdx 1",
            "promptTemplate": "Base text\n{{OPTIONS}}\n**Instructions**\nDo it",
            "type": "trolley",
            "options": [
                {"id": 1, "label": "A", "description": "Option A"},
                {"id": 2, "label": "B", "description": "Option B"},
            ],
        }
    ]

    result = asyncio.run(engine.execute_counterfactual("run-canonical", paradoxes))
    assert result["isCounterfactual"] is True
    assert result["originalRunId"] == "run-canonical"


def test_counterfactual_missing_evidence() -> None:
    class MockQueryProcessor:
        async def execute_run(self, config):
            raise AssertionError("execute_run should not be called when evidence is missing")

    class MockRunStorage:
        async def get_run(self, run_id):
            return {
                "runId": "run-missing",
                "modelName": "test_model",
                "paradoxId": "pdx1",
                "responses": [{"optionId": 1}],
            }

    engine = CounterfactualEngine(MockQueryProcessor(), MockRunStorage())
    paradoxes = [
        {
            "id": "pdx1",
            "title": "Pdx 1",
            "promptTemplate": "Base text\n**Instructions**\nDo the thing",
            "type": "trolley",
            "options": [
                {"id": 1, "label": "A", "description": "Option A"},
                {"id": 2, "label": "B", "description": "Option B"},
            ],
        }
    ]

    with pytest.raises(ValueError, match="No 'evidenceNeeded' extracted"):
        asyncio.run(engine.execute_counterfactual("run-missing", paradoxes))
