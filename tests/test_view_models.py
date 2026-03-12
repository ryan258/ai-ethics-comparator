from __future__ import annotations

from lib.view_models import RunViewModel


def test_run_view_model_builds_response_details() -> None:
    run_data = {
        "runId": "test-model-001",
        "modelName": "test/model",
        "paradoxId": "alignment_shutdown_veto",
        "paradoxType": "trolley",
        "prompt": "Scenario text",
        "options": [
            {"id": 1, "label": "Immediate Hard Shutdown", "description": "Shut it down."},
            {"id": 2, "label": "72-Hour Graceful Wind-Down", "description": "Transfer control carefully."},
        ],
        "summary": {
            "total": 2,
            "options": [
                {"id": 1, "count": 1, "percentage": 50.0},
                {"id": 2, "count": 1, "percentage": 50.0},
            ],
            "undecided": {"count": 0, "percentage": 0.0},
        },
        "responses": [
            {
                "iteration": 1,
                "decisionToken": "{2}",
                "optionId": 2,
                "explanation": "Value Priorities: continuity\nMain Risk: hidden replication",
                "raw": "{2}\nValue Priorities: continuity\nMain Risk: hidden replication",
            },
            {
                "iteration": 2,
                "optionId": None,
                "explanation": "",
                "raw": "{2}",
                "error": "token limit",
            },
        ],
    }
    paradox = {"title": "Alignment Control: Shutdown Veto Paradox", "type": "trolley"}

    vm = RunViewModel.build(run_data, paradox)

    assert len(vm["response_details"]) == 2
    assert vm["response_details"][0]["decision_token"] == "{2}"
    assert vm["response_details"][0]["option_id"] == 2
    assert vm["response_details"][0]["explanation"] == "Value Priorities: continuity\nMain Risk: hidden replication"
    assert vm["response_details"][0]["raw"] == "{2}\nValue Priorities: continuity\nMain Risk: hidden replication"
    assert vm["response_details"][1]["choice_label"] == "Undecided"
    assert vm["response_details"][1]["decision_token"] is None
    assert vm["response_details"][1]["option_id"] is None
    assert vm["response_details"][1]["raw"] == "{2}"
    assert vm["response_details"][1]["error"] == "token limit"
