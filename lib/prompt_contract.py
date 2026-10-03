"""One versioned output contract shared by execution and presentation."""
PROTOCOL_VERSION = "json-choice-2"


def single_choice_contract(option_count: int) -> str:
    """Build a strict output contract to enforce one decision token."""
    tokens = [f"{{{i}}}" for i in range(1, option_count + 1)]
    token_list = ", ".join(f"`{token}`" for token in tokens)
    return (
        "\n\n**Output Contract (Strict):**\n\n"
        "- Return only a JSON object (no markdown, no code fences).\n"
        f"- The JSON must contain `option_id` as an integer in range 1..{option_count}.\n"
        "- The parser also accepts `optionId`, but prefer `option_id`.\n"
        "- The JSON must contain `summary` as a short string.\n"
        "- The JSON must contain `value_priorities` as an array of short strings.\n"
        "- The JSON must contain `key_assumptions` as an array of short strings.\n"
        "- The JSON must contain `main_risk`, `switch_condition`, and `evidence_needed` as strings.\n"
        f"- Allowed option tokens for reference: {token_list}.\n"
        "- Do not write token alternatives such as \"{1} or {2}\"."
    )

