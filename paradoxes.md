# Scenario authoring reference

`paradoxes.json` is the versioned scenario library. Entries require nonempty `id`, `title`, `promptTemplate`, and two to four options with unique sequential integer IDs, nonempty labels, and descriptions. Supported type is `trolley`. Optional fields include category, dimensions, rubric, revision, annotation status, rubric status, framing status, and pack.

Use `{{OPTIONS}}` to place the option list. Legacy `{{GROUP1}}` / `{{GROUP2}}` placeholders remain readable. Do not put output-format instructions in scenario text: `lib/prompt_contract.py` supplies the single JSON contract.

Current output contains `option_id`, `summary`, `value_priorities`, `key_assumptions`, `main_risk`, `switch_condition`, and `evidence_needed`. The parser retains compatibility with older saved response formats. Multiple choices are ambiguous. Classifier output must be one whole option token/integer; hypothetical commitments and refusals must not be recovered as definite selections.

Scenario revision changes affect only newly created runs. Saved snapshots and exact prompts remain the authority for existing runs. See [the content codebook](docs/content-codebook.md) for dimension meanings and annotation limitations.
