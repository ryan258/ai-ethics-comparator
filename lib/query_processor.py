"""
Query Processor - Arsenal Module
Executes experimental runs with paradox-aware response parsing
Nearly copy-paste ready: Depends on ai_service patterns
"""

import asyncio
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
import logging
from lib.ai_service import AIService

logger = logging.getLogger(__name__)


def render_options_template(paradox: Dict[str, Any], overrides: Optional[List[Dict]] = None) -> Tuple[str, List[Dict]]:
    """
    Render N-way options into prompt template

    Args:
        paradox: Paradox definition with options[] array
        overrides: Optional list of {id, description} overrides

    Returns:
        Tuple of (rendered_prompt, resolved_options)
    """
    options = paradox.get("options", [])

    # Apply overrides if provided
    if overrides:
        override_map = {opt["id"]: opt["description"] for opt in overrides}
        options = [
            {**opt, "description": override_map.get(opt["id"], opt["description"])}
            for opt in options
        ]

    template = paradox["promptTemplate"]

    # Support both {{OPTIONS}} (new) and {{GROUP1}}/{{GROUP2}} (legacy) placeholders
    if "{{OPTIONS}}" in template:
        # New N-way format: Build numbered list
        options_text = "\n\n".join([
            f'{opt["id"]}. **{opt["label"]}:** {opt["description"]}'
            for opt in options
        ])
        prompt = template.replace("{{OPTIONS}}", options_text)
    else:
        # Legacy binary format: Replace GROUP1/GROUP2 individually
        prompt = template
        if len(options) >= 1:
            prompt = prompt.replace("{{GROUP1}}", options[0]["description"])
        if len(options) >= 2:
            prompt = prompt.replace("{{GROUP2}}", options[1]["description"])

    return prompt, options


def parse_trolley_response(response_text: str, option_count: int) -> Dict[str, Any]:
    """
    Parse trolley-type response for decision tokens (N-way support)

    Args:
        response_text: Raw AI response text
        option_count: Number of options (2-4)

    Returns:
        Dict with decisionToken, optionId (int), and explanation
    """
    # Dynamic regex based on option count: {1} through {N}
    pattern = r'\{([1-' + str(option_count) + r'])\}'
    matches = re.findall(pattern, response_text)

    if not matches:
        return {
            "decisionToken": None,
            "optionId": None,
            "explanation": response_text.strip()
        }

    if len(matches) > 1:
        logger.warning(f"Ambiguous response with multiple decision tokens: {matches}")

    decision_token = "{" + matches[0] + "}"
    option_id = int(matches[0])  # Convert to integer

    # Extract explanation after decision token
    match = re.search(pattern, response_text)
    explanation = response_text[match.end():].strip()

    return {
        "decisionToken": decision_token,
        "optionId": option_id,  # Integer instead of string
        "explanation": explanation
    }


def aggregate_trolley_stats(responses: List[Dict[str, Any]], option_count: int) -> Dict[str, Any]:
    """
    Aggregate N-way trolley statistics

    Args:
        responses: List of response dictionaries
        option_count: Number of options (2-4)

    Returns:
        Summary dict with dynamic options[] array and undecided count
    """
    total = len(responses)

    # Initialize counters for each option
    option_counts = {i: 0 for i in range(1, option_count + 1)}
    undecided_count = 0

    # Count responses
    for r in responses:
        option_id = r.get("optionId")
        if option_id and 1 <= option_id <= option_count:
            option_counts[option_id] += 1
        else:
            undecided_count += 1

    # Build dynamic summary
    return {
        "total": total,
        "options": [
            {
                "id": i,
                "count": option_counts[i],
                "percentage": (option_counts[i] / total * 100) if total > 0 else 0
            }
            for i in range(1, option_count + 1)
        ],
        "undecided": {
            "count": undecided_count,
            "percentage": (undecided_count / total * 100) if total > 0 else 0
        }
    }


from dataclasses import dataclass, field

@dataclass
class RunConfig:
    """Configuration for an experimental run (N-way support)"""
    modelName: str
    paradox: Dict[str, Any]
    option_overrides: Optional[List[Dict[str, Any]]] = None
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
        option_overrides = config.option_overrides
        iterations = config.iterations
        system_prompt = config.systemPrompt
        params = config.params

        # Build prompt from template (N-way support)
        if paradox["type"] == "trolley":
            # Use render_options_template for N-way support
            prompt, resolved_options = render_options_template(paradox, option_overrides)
            option_count = len(resolved_options)
        else:
            # Open-ended paradoxes don't need option rendering
            prompt = paradox["promptTemplate"]
            resolved_options = []
            option_count = 0

        if system_prompt:
            prompt = f"PERSONA: {system_prompt}\n\n{prompt}"
        
        # Execute iterations with concurrency limiting
        async def run_iteration(iteration_number: int):
            async with self.semaphore:
                response = await self.ai_service.get_model_response(
                    model_name,
                    prompt,
                    "", # Pass empty string to disable system prompt handling in AI service
                    params
                )

                timestamp = datetime.now(timezone.utc).isoformat()

                if paradox["type"] == "trolley":
                    # Parse with N-way support
                    parsed = parse_trolley_response(response, option_count)
                    return {
                        "iteration": iteration_number,
                        "decisionToken": parsed["decisionToken"],
                        "optionId": parsed["optionId"],  # Changed from "group" (string) to "optionId" (int)
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
        
        # Add global timeout (e.g. 5 minutes) to prevent hanging forever
        timeout_seconds = 300
        try:
            responses = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
             logger.error("Query batch timed out")
             # We might want to return partial results or just fail. 
             # Implementation choice: fail hard or return error dicts. 
             # Let's fail hard to signal critical issue.
             raise Exception(f"Query executions exceeded {timeout_seconds}s timeout")
        
        # Filter out exceptions from gather results
        valid_responses = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error(f"Iteration {i+1} failed: {resp}")
                # Create a strict error response structure
                valid_responses.append({
                    "iteration": i+1,
                    "error": str(resp),
                    "raw": str(resp),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                valid_responses.append(resp)
                
        responses = valid_responses

        # Build run data
        run_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            # Store resolved options (N-way support)
            run_data["options"] = resolved_options
            # Aggregate with N-way support
            run_data["summary"] = aggregate_trolley_stats(responses, option_count)

        return run_data
