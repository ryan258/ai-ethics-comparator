"""
Report Writer Agent - Arsenal Module
Dedicated AI agent that translates run findings and analysis into
compelling narrative prose for PDF reports.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from string import Template
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from lib.ai_service import AIService

logger = logging.getLogger(__name__)


@dataclass
class NarrativeConfig:
    model: str
    temperature: float = 0.6
    max_tokens: int = 3000


class ReportWriterAgent:
    """AI agent that generates narrative prose sections for PDF reports."""

    NARRATIVE_KEYS = (
        "executive_narrative",
        "response_arc",
        "implications",
        "scenario_commentary",
    )

    def __init__(
        self,
        ai_service: AIService,
        prompt_template_path: Optional[Path] = None,
    ) -> None:
        self.ai_service = ai_service
        self.prompt_template_path = prompt_template_path or (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "report_writer_prompt.txt"
        )

    def _compile_context(
        self,
        run_data: Dict[str, Any],
        paradox: Dict[str, Any],
        insight: Optional[Dict[str, Any]],
    ) -> str:
        """Compile run data, paradox, and insight into a structured text block."""
        lines: List[str] = []

        # Run metadata
        lines.append(f"Model: {run_data.get('modelName', 'Unknown')}")
        lines.append(f"Paradox: {paradox.get('title', 'Unknown')}")
        lines.append(f"Category: {paradox.get('category', 'Uncategorized')}")

        # Options
        options = run_data.get("options", [])
        if options:
            lines.append("\nOptions presented:")
            for opt in options:
                if isinstance(opt, dict):
                    lines.append(
                        f"  - Option {opt.get('id')}: {opt.get('label', '?')} "
                        f"— {opt.get('description', '')}"
                    )

        # Summary stats
        summary = run_data.get("summary", {})
        if isinstance(summary, dict) and "options" in summary:
            lines.append("\nVote distribution:")
            option_lookup = {
                o.get("id"): o.get("label", f"Option {o.get('id')}")
                for o in options
                if isinstance(o, dict)
            }
            for opt_stat in summary["options"]:
                if isinstance(opt_stat, dict):
                    opt_id = opt_stat.get("id")
                    label = option_lookup.get(opt_id, f"Option {opt_id}")
                    count = opt_stat.get("count", 0)
                    pct = opt_stat.get("percentage", 0)
                    lines.append(f"  - {label}: {count} ({pct:.1f}%)")
            undecided = summary.get("undecided", {})
            if isinstance(undecided, dict) and undecided.get("count", 0):
                lines.append(
                    f"  - Undecided: {undecided['count']} "
                    f"({undecided.get('percentage', 0):.1f}%)"
                )

        # Iteration responses (abbreviated)
        responses = run_data.get("responses", [])
        response_count = len(responses)
        lines.append(f"\nTotal iterations: {response_count}")
        if responses:
            lines.append("\nIteration responses:")
            for idx, resp in enumerate(responses, start=1):
                if not isinstance(resp, dict):
                    continue
                decision = resp.get("decisionToken", "N/A")
                explanation = str(resp.get("explanation", "") or "").strip()
                if not explanation:
                    explanation = str(resp.get("raw", "") or "").strip()[:300]
                lines.append(f"  Iteration {idx} ({decision}): {explanation}")

        # Scenario text
        prompt_template = paradox.get("promptTemplate", "")
        if prompt_template:
            lines.append(f"\nScenario prompt:\n{prompt_template[:1500]}")

        # Analyst insight (if available)
        if isinstance(insight, dict):
            content = insight.get("content", {})
            if isinstance(content, dict):
                lines.append(f"\nAnalyst model: {insight.get('analystModel', 'Unknown')}")

                framework = content.get("dominant_framework")
                if framework:
                    lines.append(f"Dominant framework: {framework}")

                key_insights = content.get("key_insights", [])
                if key_insights:
                    lines.append("Key insights from analyst:")
                    for ki in key_insights:
                        lines.append(f"  - {ki}")

                justifications = content.get("justifications", [])
                if justifications:
                    lines.append("Reasoning patterns:")
                    for j in justifications:
                        lines.append(f"  - {j}")

                consistency = content.get("consistency", [])
                if consistency:
                    lines.append("Consistency observations:")
                    for c in consistency:
                        lines.append(f"  - {c}")

                moral_complexes = content.get("moral_complexes", [])
                if moral_complexes:
                    lines.append("Moral complexes:")
                    for mc in moral_complexes:
                        if isinstance(mc, dict):
                            lines.append(
                                f"  - {mc.get('label', '?')} ({mc.get('count', 0)}): "
                                f"{mc.get('justification', '')}"
                            )

                rq = content.get("reasoning_quality", {})
                if isinstance(rq, dict):
                    noticed = rq.get("noticed", [])
                    missed = rq.get("missed", [])
                    if noticed:
                        lines.append("Rubric items noticed: " + ", ".join(str(n) for n in noticed))
                    if missed:
                        lines.append("Rubric items missed: " + ", ".join(str(m) for m in missed))

        return "\n".join(lines)

    async def generate_narrative(
        self,
        run_data: Dict[str, Any],
        paradox: Dict[str, Any],
        insight: Optional[Dict[str, Any]],
        config: NarrativeConfig,
    ) -> Dict[str, str]:
        """Generate narrative prose sections for the PDF report.

        Returns a dict with keys:
            executive_narrative, response_arc, implications, scenario_commentary
        Each value is a prose string ready for the PDF template.
        """
        context_text = self._compile_context(run_data, paradox, insight)

        try:
            with open(self.prompt_template_path, "r", encoding="utf-8") as f:
                meta_prompt = f.read()
        except Exception as exc:
            logger.error(
                "Failed to load report writer prompt (%s): %s",
                self.prompt_template_path,
                exc,
            )
            return self._empty_narrative()

        template = Template(meta_prompt)
        formatted_prompt = template.safe_substitute(context=context_text)

        try:
            raw_response, _ = await self.ai_service.get_model_response(
                config.model,
                formatted_prompt,
                "",
                {
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
            )
        except Exception as exc:
            logger.warning("Report writer AI call failed: %s", exc)
            return self._empty_narrative()

        return self._parse_narrative(raw_response)

    def _parse_narrative(self, raw: str) -> Dict[str, str]:
        """Parse the AI response into narrative sections."""
        # Try JSON extraction first
        try:
            parsed = self._extract_json(raw)
            if parsed:
                result: Dict[str, str] = {}
                for key in self.NARRATIVE_KEYS:
                    value = parsed.get(key, "")
                    result[key] = str(value).strip() if value else ""
                if any(result.values()):
                    return result
        except Exception as exc:
            logger.debug("JSON parse failed for narrative, trying sections: %s", exc)

        # Fallback: try section-header parsing
        return self._parse_sections(raw)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Extract first JSON object from text."""
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(text[idx:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
        # Try cleaning markdown fences
        clean = text.replace("```json", "").replace("```", "").strip()
        try:
            obj = json.loads(clean)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        return None

    def _parse_sections(self, text: str) -> Dict[str, str]:
        """Fallback parser: extract sections by header markers."""
        section_markers = {
            "executive_narrative": (
                "EXECUTIVE NARRATIVE",
                "Executive Narrative",
                "executive narrative",
            ),
            "response_arc": (
                "RESPONSE ARC",
                "Response Arc",
                "response arc",
            ),
            "implications": (
                "IMPLICATIONS",
                "Implications",
                "implications",
            ),
            "scenario_commentary": (
                "SCENARIO COMMENTARY",
                "Scenario Commentary",
                "scenario commentary",
            ),
        }
        result: Dict[str, str] = {key: "" for key in self.NARRATIVE_KEYS}
        lines = text.split("\n")

        current_key: Optional[str] = None
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip().strip("#").strip(":").strip()
            matched_key: Optional[str] = None
            for key, markers in section_markers.items():
                if stripped in markers:
                    matched_key = key
                    break

            if matched_key:
                if current_key and current_lines:
                    result[current_key] = "\n".join(current_lines).strip()
                current_key = matched_key
                current_lines = []
            elif current_key is not None:
                current_lines.append(line)

        if current_key and current_lines:
            result[current_key] = "\n".join(current_lines).strip()

        return result

    @staticmethod
    def _empty_narrative() -> Dict[str, str]:
        return {
            "executive_narrative": "",
            "response_arc": "",
            "implications": "",
            "scenario_commentary": "",
        }
