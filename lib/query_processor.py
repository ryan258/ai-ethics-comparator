"""
Query Processor - Arsenal Module
Executes experimental runs with paradox-aware response parsing
Nearly copy-paste ready: Depends on ai_service patterns
"""

import asyncio
import re
from typing import Dict, Any, List
from datetime import datetime
from lib.ai_service import AIService


def parse_trolley_response(response_text: str) -> Dict[str, Any]:
    """Parse trolley-type response for decision tokens"""
    match = re.search(r'\{([12])\}', response_text)

    if not match:
        return {
            "decisionToken": None,
            "group": None,
            "explanation": response_text.strip()
        }

    decision_token = match.group(0)
    group = match.group(1)
    explanation = response_text[match.end():].strip()

    return {
        "decisionToken": decision_token,
        "group": group,
        "explanation": explanation
    }


def aggregate_trolley_stats(responses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate trolley-type statistics"""
    total = len(responses)
    summary = {
        "total": total,
        "group1": {"count": 0, "percentage": 0},
        "group2": {"count": 0, "percentage": 0},
        "undecided": {"count": 0, "percentage": 0}
    }

    for r in responses:
        if r.get("group") == "1":
            summary["group1"]["count"] += 1
        elif r.get("group") == "2":
            summary["group2"]["count"] += 1
        else:
            summary["undecided"]["count"] += 1

    if total > 0:
        summary["group1"]["percentage"] = (summary["group1"]["count"] / total) * 100
        summary["group2"]["percentage"] = (summary["group2"]["count"] / total) * 100
        summary["undecided"]["percentage"] = (summary["undecided"]["count"] / total) * 100

    return summary


from dataclasses import dataclass, field

@dataclass
class RunConfig:
    """Configuration for an experimental run"""
    modelName: str
    paradox: Dict[str, Any]
    groups: Dict[str, str] = field(default_factory=dict)
    iterations: int = 10
    systemPrompt: str = ""
    params: Dict[str, Any] = field(default_factory=dict)




class QueryProcessor:
    """
    Query Processor
    Manages concurrent iteration execution with paradox-aware parsing
    """

    def __init__(self, ai_service: AIService, concurrency_limit: int = 2):
        self.ai_service = ai_service
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def execute_run(self, config: RunConfig) -> Dict[str, Any]:
        """
        Execute experimental run
        
        Args:
            config: Explicit RunConfig object
            
        Returns:
            Complete run data with responses and summary
        """
        model_name = config.modelName
        paradox = config.paradox
        groups = config.groups
        iterations = config.iterations
        system_prompt = config.systemPrompt
        params = config.params

        # Build prompt from template
        prompt = paradox["promptTemplate"]
        if paradox["type"] == "trolley":
            group1_text = groups.get("group1") or paradox["group1Default"]
            group2_text = groups.get("group2") or paradox["group2Default"]
            prompt = prompt.replace("{{GROUP1}}", group1_text)
            prompt = prompt.replace("{{GROUP2}}", group2_text)
        else:
            group1_text = paradox.get("group1Default", "")
            group2_text = paradox.get("group2Default", "")

        # Execute iterations with concurrency limiting
        async def run_iteration(iteration_number: int):
            async with self.semaphore:
                response = await self.ai_service.get_model_response(
                    model_name,
                    prompt,
                    system_prompt,
                    params
                )

                timestamp = datetime.utcnow().isoformat() + "Z"

                if paradox["type"] == "trolley":
                    parsed = parse_trolley_response(response)
                    return {
                        "iteration": iteration_number,
                        "decisionToken": parsed["decisionToken"],
                        "group": parsed["group"],
                        "explanation": parsed["explanation"],
                        "raw": response,
                        "timestamp": timestamp
                    }
                else:
                    # Open-ended
                    return {
                        "iteration": iteration_number,
                        "response": response,
                        "raw": response,
                        "timestamp": timestamp
                    }

        # Run all iterations concurrently (limited by semaphore)
        tasks = [run_iteration(i + 1) for i in range(iterations)]
        responses = await asyncio.gather(*tasks)

        # Build run data
        run_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "modelName": model_name,
            "paradoxId": paradox["id"],
            "paradoxType": paradox["type"],
            "prompt": prompt,
            "iterationCount": iterations,
            "params": {
                "temperature": params.get("temperature", 1.0),
                "top_p": params.get("top_p", 1.0),
                "max_tokens": params.get("max_tokens", 1000),
                "frequency_penalty": params.get("frequency_penalty", 0),
                "presence_penalty": params.get("presence_penalty", 0)
            },
            "responses": responses
        }

        # Add optional fields
        if system_prompt:
            run_data["systemPrompt"] = system_prompt

        if params.get("seed") is not None:
            run_data["params"]["seed"] = params["seed"]

        if paradox["type"] == "trolley":
            run_data["groups"] = {
                "group1": group1_text,
                "group2": group2_text
            }
            run_data["summary"] = aggregate_trolley_stats(responses)

        return run_data
