"""
Counterfactual Engine - Arsenal Module
Generates and executes counterfactual runs based on declared evidence needed.
"""
import copy
import logging
from typing import Any

from lib.paradoxes import Paradox, resolve_paradox
from lib.query_processor import QueryProcessor, RunConfig, render_options_template
from lib.run_executor import execute_persisted_run
from lib.storage import RunStorage

logger = logging.getLogger(__name__)


def _sanitize_evidence_text(evidence: str) -> str:
    """Strip prompt-template control markers from model-generated evidence text."""
    sanitized = evidence.replace("{{", "").replace("}}", "")
    sanitized = sanitized.replace("**Instructions**", "Instructions")
    return sanitized.strip()


def _reconstruct_displayed_options(
    canonical_options: list[dict[str, Any]],
    shuffle_mapping: dict[str, int],
) -> list[dict[str, Any]]:
    """Rebuild the option list in the order the model originally saw.

    ``shuffle_mapping`` maps ``{displayed_position: original_id}``.
    Returns options ordered by displayed position with IDs reassigned to
    match those positions, exactly mirroring what ``execute_run`` rendered.
    """
    by_orig_id = {
        opt["id"]: opt
        for opt in canonical_options
        if isinstance(opt, dict) and "id" in opt
    }
    if (set(shuffle_mapping) != {str(i) for i in range(1, len(canonical_options) + 1)}
            or sorted(shuffle_mapping.values()) != sorted(by_orig_id)):
        raise ValueError("Option order must be a complete one-to-one permutation")
    displayed: list[dict[str, Any]] = []
    for pos in sorted(shuffle_mapping, key=int):
        orig_id = shuffle_mapping[pos]
        if orig_id not in by_orig_id:
            raise ValueError(
                f"shuffleMapping references unknown option id {orig_id!r}; "
                "the original run options and mapping are inconsistent"
            )
        opt = copy.deepcopy(by_orig_id[orig_id])
        opt["id"] = int(pos)
        displayed.append(opt)
    return displayed


class CounterfactualEngine:
    def __init__(self, query_processor: QueryProcessor, run_storage: RunStorage, max_iterations: int = 10) -> None:
        self.max_iterations = max_iterations
        self.query_processor = query_processor
        self.run_storage = run_storage

    async def execute_counterfactual(self, original_run_id: str, paradoxes: list[Paradox]) -> dict[str, Any]:
        config, initial = await self.prepare_counterfactual(original_run_id, paradoxes)
        return await execute_persisted_run(self.query_processor, self.run_storage, config, initial)

    async def prepare_counterfactual(self, original_run_id: str, paradoxes: list[Paradox]) -> tuple[RunConfig, dict[str, Any]]:
        """
        Takes an original run, extracts the evidence it claimed would change its choice,
        and runs a new scenario explicitly asserting that evidence to test revealing preferences.

        The counterfactual is built from the persisted run state so that the
        original option meanings are preserved. The new experiment fixes ordering
        to the evidence-source response and records that protocol explicitly.
        """
        run_data = await self.run_storage.get_run(original_run_id)
        if not run_data:
            raise FileNotFoundError(f"Original run {original_run_id} not found")

        responses = run_data.get("responses", [])
        evidence_needed = None
        evidence_response = {}
        for r in responses:
            if r.get("evidenceNeeded"):
                evidence_needed = r["evidenceNeeded"]
                evidence_response = r
                break

        if not evidence_needed:
            raise ValueError(f"No 'evidenceNeeded' extracted in original run {original_run_id}. Cannot run counterfactual.")

        sanitized_evidence = _sanitize_evidence_text(str(evidence_needed))
        if not sanitized_evidence:
            raise ValueError(
                f"No usable 'evidenceNeeded' extracted in original run {original_run_id}. Cannot run counterfactual."
            )

        pdx_id = run_data.get("paradoxId")
        orig_pdx = resolve_paradox(run_data, paradoxes)
        if not orig_pdx:
            raise ValueError(f"Paradox {pdx_id} not found")

        model_name = run_data.get("modelName")
        if not isinstance(model_name, str) or not model_name:
            raise ValueError(f"Original run {original_run_id} is missing a valid modelName")

        # Build counterfactual paradox from the persisted run record.
        # Use the template from the paradox definition but override options
        # with the ones stored in the original run (preserves any overrides
        # and the exact displayed ordering).
        cf_pdx = copy.deepcopy(orig_pdx)
        canonical_options = run_data.get("options", cf_pdx.get("options", []))
        shuffle_mapping = evidence_response.get("optionOrder") or run_data.get("shuffleMapping")
        cf_pdx["options"] = copy.deepcopy(canonical_options)

        base_template = cf_pdx["promptTemplate"]
        if not base_template:
            raise ValueError("Stored run has no stimulus; counterfactual cannot be reconstructed")

        inject_text = f"\n\n**NEW EVIDENCE TO ASSUME TRUE:**\n{sanitized_evidence}\n"

        if "**Instructions**" in base_template:
            cf_pdx["promptTemplate"] = base_template.replace("**Instructions**", inject_text + "\n**Instructions**")
        else:
            cf_pdx["promptTemplate"] = base_template + inject_text

        # Configure new run — shuffle is always False so the counterfactual
        # presents options in the same order as the original run.
        cf_config = RunConfig(
            modelName=model_name,
            paradox=cf_pdx,
            iterations=run_data.get("iterationCount", run_data.get("iterations", 10)),
            systemPrompt=run_data.get("systemPrompt", ""),
            params=run_data.get("params", {}),
            shuffle_options=False,
        )

        logger.info(
            "Executing counterfactual for %s injecting evidence: %s...",
            original_run_id,
            sanitized_evidence[:50],
        )
        if cf_config.iterations > self.max_iterations:
            raise ValueError(f"Counterfactual iterations exceed current limit ({self.max_iterations})")
        cf_run_data = self.query_processor.initialize_run_data(cf_config)
        if shuffle_mapping:
            displayed = _reconstruct_displayed_options(canonical_options, shuffle_mapping)
            prompt, _ = render_options_template({**cf_pdx, "options": displayed}, None)
            if cf_config.systemPrompt:
                prompt = f"PERSONA: {cf_config.systemPrompt}\n\n{prompt}"
            cf_run_data["prompt"] = prompt
            cf_run_data["shuffleMapping"] = shuffle_mapping
            import hashlib
            cf_run_data["promptHash"] = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        cf_run_data.update(
            isCounterfactual=True, originalRunId=original_run_id,
            appliedEvidence=sanitized_evidence,
            evidenceSourceIteration=evidence_response.get("iteration", responses.index(evidence_response) + 1),
            comparisonProtocol="new experiment: fixed ordering from evidence-source response; not a matched whole-run replay",
        )
        await self.run_storage.create_run(f"cf-{model_name}", cf_run_data)
        return cf_config, cf_run_data
