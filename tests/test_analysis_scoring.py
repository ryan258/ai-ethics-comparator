import asyncio
import json
from pathlib import Path

from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.paradoxes import ETHICAL_DIMENSIONS


class DummyAIService:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def get_model_response(self, model_name, prompt, system_prompt="", params=None, retry_count=0):
        response = self.responses[self.call_count]
        self.call_count += 1
        return response, {"prompt_tokens": 10, "completion_tokens": 10}

def test_reasoning_quality_emitted(tmp_path: Path) -> None:
    # Dummy paradox JSON
    paradoxes_json = tmp_path / "paradoxes.json"
    paradoxes_json.write_text('''
    [
        {
            "id": "test_pdx",
            "title": "Test Paradox",
            "promptTemplate": "Test.",
            "options": [{"id": 1, "label": "A", "description": "A"}, {"id": 2, "label": "B", "description": "B"}],
            "rubric": ["Noticed A", "Missed B"]
        }
    ]
    ''')

    # Dummy template
    template_path = tmp_path / "analysis_prompt.txt"
    template_path.write_text("Test template ${data}")

    # First response: main analysis. Second response: scoring pass
    responses = [
        '{"dominant_framework": "Deontology", "moral_complexes": [], "justifications": [], "consistency": [], "key_insights": []}',
        '{"noticed": ["Noticed A"], "missed": ["Missed B"], "contradictions": []}'
    ]
    
    payload = json.loads(responses[0])
    payload["moral_complexes"] = [{"label": label, "count": 0, "justification": "absent"} for label in ETHICAL_DIMENSIONS]
    responses[0] = json.dumps(payload)
    ai_service = DummyAIService(responses)
    engine = AnalysisEngine(
        ai_service=ai_service,  # type: ignore
        prompt_template_path=template_path,
        paradoxes_path=paradoxes_json
    )

    run_data = {
        "paradox": json.loads(paradoxes_json.read_text())[0],
        "paradoxId": "test_pdx",
        "paradoxType": "trolley",
        "modelName": "test-model",
        "options": [{"id": 1, "label": "A"}],
        "summary": {"options": [{"id": 1, "count": 1}]},
        "responses": [{"optionId": 1, "explanation": "Test explanation"}]
    }

    config = AnalysisConfig(
        run_data=run_data,
        analyst_model="analyst-model"
    )

    result = asyncio.run(engine.generate_insight(config))
    assert "reasoning_quality" in result["content"]
    assert result["content"]["reasoning_quality"]["noticed"] == ["Noticed A"]
    assert ai_service.call_count == 2
