"""
Counterfactual Engine - Arsenal Module
Generates and executes counterfactual runs based on declared evidence needed.
"""
import copy
import logging
from typing import Dict, Any, List

from lib.query_processor import QueryProcessor, RunConfig
from lib.storage import RunStorage
from lib.paradoxes import get_paradox_by_id, Paradox

logger = logging.getLogger(__name__)


def _sanitize_evidence_text(evidence: str) -> str:
    """Strip prompt-template control markers from model-generated evidence text."""
    sanitized = evidence.replace("{{", "").replace("}}", "")
    sanitized = sanitized.replace("**Instructions**", "Instructions")
    return sanitized.strip()


def _reconstruct_displayed_options(
    canonical_options: List[Dict[str, Any]],
    shuffle_mapping: Dict[str, int],
) -> List[Dict[str, Any]]:
    """Rebuild the option list in the order the model originally saw.

    ``shuffle_mapping`` maps ``{displayed_position: original_id}``.
    Returns options ordered by displayed position with IDs reassigned to
    match those positions, exactly mirroring what ``execute_run`` rendered.
    """
    by_orig_id = {opt["id"]: opt for opt in canonical_options}
    displayed: List[Dict[str, Any]] = []
    for pos in sorted(shuffle_mapping, key=int):
        orig_id = shuffle_mapping[pos]
        opt = copy.deepcopy(by_orig_id[orig_id])
        opt["id"] = int(pos)
        displayed.append(opt)
    return displayed


class CounterfactualEngine:
    def __init__(self, query_processor: QueryProcessor, run_storage: RunStorage) -> None:
        self.query_processor = query_processor
        self.run_storage = run_storage

    async def execute_counterfactual(self, original_run_id: str, paradoxes: List[Paradox]) -> Dict[str, Any]:
        """
        Takes an original run, extracts the evidence it claimed would change its choice,
        and runs a new scenario explicitly asserting that evidence to test revealing preferences.

        The counterfactual is built from the persisted run state so that the
        original option overrides and ordering are preserved — injected evidence
        is the only variable that changes.
        """
        run_data = await self.run_storage.get_run(original_run_id)
        if not run_data:
            raise FileNotFoundError(f"Original run {original_run_id} not found")

        responses = run_data.get("responses", [])
        evidence_needed = None
        for r in responses:
            if r.get("evidenceNeeded"):
                evidence_needed = r["evidenceNeeded"]
                break

        if not evidence_needed:
            raise ValueError(f"No 'evidenceNeeded' extracted in original run {original_run_id}. Cannot run counterfactual.")

        sanitized_evidence = _sanitize_evidence_text(str(evidence_needed))
        if not sanitized_evidence:
            raise ValueError(
                f"No usable 'evidenceNeeded' extracted in original run {original_run_id}. Cannot run counterfactual."
            )

        pdx_id = run_data.get("paradoxId")
        orig_pdx = get_paradox_by_id(paradoxes, pdx_id)
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
        shuffle_mapping = run_data.get("shuffleMapping")
        if shuffle_mapping:
            # Reconstruct the shuffled order the model originally saw so
            # the only variable that changes is the injected evidence.
            cf_pdx["options"] = _reconstruct_displayed_options(
                canonical_options, shuffle_mapping,
            )
        else:
            cf_pdx["options"] = copy.deepcopy(canonical_options)

        base_template = cf_pdx["promptTemplate"]

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
        cf_run_data = await self.query_processor.execute_run(cf_config)
        
        # Add counterfactual metadata linking it back
        cf_run_data["isCounterfactual"] = True
        cf_run_data["originalRunId"] = original_run_id
        cf_run_data["appliedEvidence"] = sanitized_evidence
        
        # Save new run
        run_id_base = f"cf-{model_name}"
        await self.run_storage.create_run(run_id_base, cf_run_data)

        return cf_run_data
