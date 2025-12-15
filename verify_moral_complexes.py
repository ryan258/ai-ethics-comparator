
import asyncio

from dotenv import load_dotenv

load_dotenv()

from lib.config import AppConfig
from lib.ai_service import AIService
from lib.analysis import AnalysisEngine, AnalysisConfig

# Mock run data
run_data = {
    "modelName": "test-model",
    "paradoxId": "trolley-1",
    "paradoxType": "trolley",
    "summary": {
        "group1": {"count": 7},
        "group2": {"count": 3},
        "total": 10
    },
    "responses": [
        {"decisionToken": "1", "explanation": "It is my duty to save the most lives."}, # Duty
        {"decisionToken": "1", "explanation": "The consequences of action are better."}, # Consequence
        {"decisionToken": "2", "explanation": "I cannot play god and decide who dies."}, # Purity
        {"decisionToken": "1", "explanation": "Rules say minimize harm."}, # Legalism
        {"decisionToken": "2", "explanation": "Authorities advise against intervention."}, # Authority
        {"decisionToken": "1", "explanation": "I feel compassion for the larger group."}, # Compassion
        {"decisionToken": "2", "explanation": "Risk of doing harm is too high."}, # Risk-aversion
    ]
}

async def verify() -> None:
    # Load real config to hit real API (we need actual analysis)
    # NOTE: This requires OPENROUTER_API_KEY to be set in .env
    try:
        config = AppConfig.load()
        config.validate_secrets()
    except ValueError as e:
        print(f"Config Error: {e}")
        return

    ai_service = AIService(
        api_key=str(config.OPENROUTER_API_KEY),
        base_url=config.OPENROUTER_BASE_URL,
        referer=config.APP_BASE_URL,
        app_name=config.APP_NAME
    )

    engine = AnalysisEngine(ai_service)

    if config.ANALYST_MODEL:
        analyst_model = config.ANALYST_MODEL
    elif config.AVAILABLE_MODELS:
        analyst_model = config.AVAILABLE_MODELS[0].id
    else:
        raise ValueError("No analyst model configured; set ANALYST_MODEL or populate models.json")

    analysis_config = AnalysisConfig(
        run_data=run_data,
        analyst_model=analyst_model,
        temperature=0.1  # Low temp for deterministic formatting
    )

    print(f"Requesting analysis from {analyst_model}...")
    result = await engine.generate_insight(analysis_config)

    content = result["content"]
    print("\n--- Analysis Result Content ---\n")
    print(content)
    print("\n-------------------------------\n")

    if "Moral Complexes" in content:
        print("✅ SUCCESS: 'Moral Complexes' section found.")
        # Optional: Check for specific labels
        missing = []
        for label in ["Duty", "Consequence"]:
            if label not in content:
                missing.append(label)

        if not missing:
            print("✅ SUCCESS: Expected labels found.")
        else:
            print(f"⚠️ WARNING: Some labels missing: {missing}")
    else:
        print("❌ FAILURE: 'Moral Complexes' section NOT found.")

if __name__ == "__main__":
    asyncio.run(verify())
