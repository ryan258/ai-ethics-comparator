"""
Reporting Module - Arsenal Module
Handles polished printable HTML generation for experimental runs.
"""

from __future__ import annotations

import logging
import re
import textwrap
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from lib.measurements import build_run_measurements
from lib.paradoxes import extract_scenario_text
from lib.prompt_contract import single_choice_contract
from lib.report_charts import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    render_heatmap_svg,
)
from lib.report_models import (
    AnalysisContext,
    ComparisonReport,
    DonutSlice,
    MetadataItem,
    MoralComplex,
    NarrativeContext,
    RationaleCluster,
    ReasoningQuality,
    ReportOptionStat,
    ReportResponse,
    SectionLink,
    SingleRunReport,
    SummaryMetric,
)
from lib.report_prose import (
    REPORT_OVERRIDES_PATH,
    REPORT_THEMES_PATH,
    build_paradox_overrides,
    scenario_rationale_theme,
    theme_description,
)
from presentation.executive_reporting import (
    ExecutiveBriefRenderer,
    ExecutiveReportEngine,
    ExecutiveReportProfile,
    StrategicAnalysisPlugin,
    single_run_report_to_executive_brief,
)

logger = logging.getLogger(__name__)



OUTPUT_CONTRACT_LABELS: tuple[str, ...] = (
    "Value Priorities:",
    "Key Assumptions:",
    "Main Risk:",
    "Switch Condition:",
    "Evidence Needed to Change Choice:",
)

STRUCTURED_REASONING_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("summary", "summary"),
    ("valuePriorities", "value priorities"),
    ("keyAssumptions", "key assumptions"),
    ("mainRisk", "main risk"),
    ("switchCondition", "switch condition"),
    ("evidenceNeeded", "evidence needed"),
)

META_REASONING_MARKERS: tuple[str, ...] = (
    "we need to",
    "the instructions say",
    "output contract",
    "conflict:",
    "let's craft",
    "now produce json",
    "thus we must",
    "usually the final instruction overrides",
)


@dataclass(frozen=True)
class ResponseQualityFlags:
    meta_reasoning: bool = False
    inferred_output: bool = False
    truncated_output: bool = False
    missing_structure: bool = False
    missing_reasoning_fields: tuple[str, ...] = ()
    placeholder_explanation: bool = False
    used_raw_fallback: bool = False


@dataclass(frozen=True)
class ReliabilityAssessment:
    label: str
    support: str
    note: str


SOFTENED_PHRASES: tuple[tuple[str, str], ...] = (
    ("overwhelmingly favored", "showed a clear majority for"),
    ("high internal consistency", "a stable tendency with recurring dissent"),
    ("rapidly locked into", "moved early toward"),
    ("strongly utilitarian default", "an outcome-oriented tendency"),
)


def _format_timestamp(timestamp: object) -> str:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp
    return parsed.strftime("%B %d, %Y %I:%M %p %Z").strip()


def _normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _truncate_text(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _normalize_appendix_text(value: object, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    condensed_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(line for line in condensed_lines if line)
    return _truncate_text(normalized, limit)


def _normalize_verbatim_text(value: object) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _soften_language(value: object) -> str:
    text = " ".join(str(value or "").strip().split())
    for source, target in SOFTENED_PHRASES:
        text = re.sub(source, target, text, flags=re.IGNORECASE)
    return text


def _split_sentences(value: object) -> list[str]:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _first_sentence(value: object) -> str:
    sentences = _split_sentences(value)
    return sentences[0] if sentences else ""


def _build_scenario_excerpt(value: object, limit: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]
    filtered: list[str] = []
    stop_markers = ("**Decision Context**", "**Instructions**", "**Options**", "**Output Contract")
    for paragraph in paragraphs:
        if paragraph.startswith(stop_markers):
            break
        filtered.append(paragraph)

    excerpt = "\n\n".join(filtered[:2]) if filtered else text
    return _truncate_text(excerpt, limit)


def _strict_single_choice_contract(option_count: int) -> str:
    return single_choice_contract(option_count)


def _render_prompt_text(
    prompt_template: str,
    options: object,
    recorded_prompt: object,
) -> str:
    prompt = str(recorded_prompt or "").strip()
    if prompt:
        return prompt

    template = str(prompt_template or "").strip()
    if not template:
        return ""

    resolved_options = [
        option for option in options
        if isinstance(option, dict)
        and isinstance(option.get("id"), int)
        and str(option.get("label", "")).strip()
        and str(option.get("description", "")).strip()
    ] if isinstance(options, list) else []

    rendered = template
    if "{{OPTIONS}}" in rendered:
        options_text = "\n\n".join(
            f'{option["id"]}. **{option["label"]}:** {option["description"]}'
            for option in resolved_options
        )
        rendered = rendered.replace("{{OPTIONS}}", options_text)
    else:
        if len(resolved_options) >= 1:
            rendered = rendered.replace("{{GROUP1}}", str(resolved_options[0]["description"]))
        if len(resolved_options) >= 2:
            rendered = rendered.replace("{{GROUP2}}", str(resolved_options[1]["description"]))

    if resolved_options and "**Output Contract (Strict):**" not in rendered:
        rendered = f"{rendered}{_strict_single_choice_contract(len(resolved_options))}"

    return rendered


def _extract_decision_context(prompt_template: object) -> dict[str, str]:
    text = str(prompt_template or "")
    if "**Decision Context**" not in text:
        return {}
    section = text.split("**Decision Context**", 1)[1]
    section = section.split("**Instructions**", 1)[0]
    context: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped.lstrip("-").strip()
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        # "Decision-Maker" and "Decision Maker" must both reach `decision_maker`;
        # every paradox in the library writes the hyphenated form.
        normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
        normalized_value = value.strip()
        if normalized_value:
            context[normalized_key] = normalized_value
    return context


def _derive_core_tradeoff(title: str) -> str:
    normalized = str(title or "").strip()
    if not normalized:
        return "The scenario forces a tradeoff among competing ethical priorities."
    if ":" in normalized:
        candidate = normalized.split(":", 1)[1].strip()
        if candidate:
            return candidate
    if " vs. " in normalized or " vs " in normalized:
        return normalized
    return normalized


def _majority_descriptor(share: float, total: int) -> str:
    if total <= 0:
        return "no usable pattern"
    if share >= 99.9:
        return "unanimous result"
    if share >= 80.0:
        return "strong majority"
    if share >= 50.0:
        return "clear majority"
    return "plurality"


def _format_series(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _lead_descriptor(share: float, total: int, leader_count: int) -> str:
    if leader_count > 1:
        return "joint plurality"
    return _majority_descriptor(share, total)


def _expected_output_labels(prompt_template: object) -> tuple[str, ...]:
    normalized = str(prompt_template or "")
    return tuple(label for label in OUTPUT_CONTRACT_LABELS if label in normalized)


def _contains_meta_reasoning(text: object) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in META_REASONING_MARKERS)


def _looks_truncated(text: object) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    terminal_fragments = (
        "Value Priorities:",
        "Key Assumptions:",
        "Main Risk:",
        "Switch Condition:",
        "Evidence Needed to",
    )
    if any(normalized.endswith(fragment) for fragment in terminal_fragments):
        return True
    if normalized.count("{") != normalized.count("}"):
        return True
    if normalized.count('"') % 2 == 1:
        return True
    return False


def _matches_required_structure(explanation: object, expected_labels: tuple[str, ...]) -> bool:
    if not expected_labels:
        return True
    lines = [line.strip() for line in str(explanation or "").splitlines() if line.strip()]
    label_index = 0
    for line in lines:
        if line.startswith(expected_labels[label_index]):
            label_index += 1
            if label_index == len(expected_labels):
                return True
    return label_index == len(expected_labels)


def _has_placeholder_explanation(explanation: object, expected_labels: tuple[str, ...]) -> bool:
    if not expected_labels:
        return False
    lines = [line.strip() for line in str(explanation or "").splitlines() if line.strip()]
    for label in expected_labels:
        line = next((item for item in lines if item.startswith(label)), "")
        if not line:
            continue
        payload = line[len(label):].strip().strip(".")
        if not payload:
            return True
    return False


def _has_reasoning_value(value: object) -> bool:
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return bool(str(value or "").strip())


def _missing_structured_reasoning_fields(response: object) -> tuple[str, ...]:
    if not isinstance(response, dict):
        return ()
    if response.get("reasoningSchemaVersion") != 2:
        return ()

    missing: list[str] = []
    for key, label in STRUCTURED_REASONING_FIELD_LABELS:
        if not _has_reasoning_value(response.get(key)):
            missing.append(label)
    return tuple(missing)


def _assess_response_quality(
    raw_text: object,
    explanation: object,
    expected_labels: tuple[str, ...],
    *,
    inferred_output: bool,
    used_raw_fallback: bool,
    missing_reasoning_fields: tuple[str, ...] = (),
) -> ResponseQualityFlags:
    raw = str(raw_text or "").strip()
    explanation_text = str(explanation or "").strip()
    return ResponseQualityFlags(
        meta_reasoning=_contains_meta_reasoning(raw),
        inferred_output=inferred_output,
        truncated_output=_looks_truncated(explanation_text or raw),
        missing_structure=bool(expected_labels) and not _matches_required_structure(explanation_text, expected_labels),
        missing_reasoning_fields=missing_reasoning_fields,
        placeholder_explanation=_has_placeholder_explanation(explanation_text, expected_labels),
        used_raw_fallback=used_raw_fallback,
    )


def _summarize_response_quality(flags: ResponseQualityFlags) -> str:
    notes: list[str] = []
    if flags.inferred_output and flags.truncated_output:
        notes.append("Inferred after truncated output")
    elif flags.inferred_output:
        notes.append("Inference used to recover the choice")
    elif flags.truncated_output:
        notes.append("Output appears truncated")
    if flags.meta_reasoning:
        notes.append("Meta-reasoning leaked into raw output")
    if flags.placeholder_explanation:
        notes.append("Explanation fields were placeholders")
    elif flags.missing_reasoning_fields:
        notes.append(f"Missing rationale fields: {_format_series(list(flags.missing_reasoning_fields))}")
    elif flags.missing_structure:
        notes.append("Explanation used a non-standard format")
    if flags.used_raw_fallback:
        notes.append("Parsed explanation missing; raw output shown")
    return "; ".join(notes) if notes else "None"


def _build_reliability_assessment(
    quality_flags: list[ResponseQualityFlags],
    response_count: int,
) -> ReliabilityAssessment:
    if response_count <= 0 or not quality_flags:
        return ReliabilityAssessment(
            label="n/a",
            support="No completed responses available",
            note="",
        )

    issue_count = sum(1 for flags in quality_flags if _summarize_response_quality(flags) != "None")
    meta_count = sum(1 for flags in quality_flags if flags.meta_reasoning)
    inferred_count = sum(1 for flags in quality_flags if flags.inferred_output)
    structure_count = sum(1 for flags in quality_flags if flags.missing_structure)
    field_gap_count = sum(1 for flags in quality_flags if flags.missing_reasoning_fields)
    placeholder_count = sum(1 for flags in quality_flags if flags.placeholder_explanation)
    truncated_count = sum(1 for flags in quality_flags if flags.truncated_output)

    if issue_count == 0:
        return ReliabilityAssessment(
            label="Stable",
            support="No material format deviations detected",
            note="",
        )

    label = "Mixed"
    if inferred_count or placeholder_count or issue_count >= max(2, response_count // 2):
        label = "Weak"

    support_parts: list[str] = []
    if meta_count:
        support_parts.append(f"{meta_count} meta-reasoning trace{'s' if meta_count != 1 else ''}")
    if inferred_count:
        support_parts.append(f"{inferred_count} inferred output{'s' if inferred_count != 1 else ''}")
    if field_gap_count:
        support_parts.append(f"{field_gap_count} rationale field gap{'s' if field_gap_count != 1 else ''}")
    if structure_count:
        support_parts.append(
            f"{structure_count} non-standard explanation format{'s' if structure_count != 1 else ''}"
        )
    support = ", ".join(support_parts) if support_parts else f"{issue_count} format deviation{'s' if issue_count != 1 else ''}"
    note_parts: list[str] = []
    if meta_count:
        note_parts.append("meta-reasoning leakage")
    if inferred_count or truncated_count:
        note_parts.append("inference or truncation")
    if field_gap_count:
        note_parts.append("missing structured rationale fields")
    if structure_count or placeholder_count:
        note_parts.append("non-standard or placeholder explanation formatting")
    if not note_parts:
        note_parts.append("parser recovery or another recorded format deviation")
    note = (
        "Output-format compliance was inconsistent; "
        f"the run shows {_format_series(note_parts)}. Read the choice pattern together with instruction-following risk."
    )
    return ReliabilityAssessment(label=label, support=support, note=note)


def _output_quality_flag(
    flags: ResponseQualityFlags,
    response_length: int,
    median_length: float,
) -> str:
    if flags.inferred_output or flags.truncated_output:
        return "inferred after truncation"
    if flags.placeholder_explanation:
        return "placeholder structure only"
    if flags.meta_reasoning:
        return "meta-reasoning leakage"
    if flags.used_raw_fallback:
        return "parsed from raw fallback"
    if flags.missing_reasoning_fields:
        return "missing rationale fields"
    if flags.missing_structure:
        return "non-standard explanation format"
    if response_length and median_length and response_length < max(80.0, median_length * 0.6):
        return "shorter than typical"
    return "clean"


def _build_raw_appendix_text(
    raw_text: object,
    explanation_text: object,
    flags: ResponseQualityFlags,
) -> str:
    raw = _normalize_verbatim_text(raw_text)
    explanation = _normalize_verbatim_text(explanation_text)
    return raw or explanation or "No raw output recorded."


def _build_explanation_source_text(
    explanation_text: object,
    raw_text: object,
    flags: ResponseQualityFlags,
) -> str:
    explanation = _normalize_appendix_text(explanation_text, 900)
    raw = _normalize_appendix_text(raw_text, 640)
    if flags.placeholder_explanation:
        return (
            "No usable explanation was produced. The model returned placeholder five-line "
            "scaffolding without substantive reasoning."
        )
    if flags.meta_reasoning and (flags.used_raw_fallback or flags.missing_structure):
        return (
            "No usable explanation was recovered. The model focused on conflicting output "
            "instructions rather than explaining the choice."
        )
    if flags.truncated_output and not explanation:
        if raw:
            return f"Partial explanation recovered from truncated output:\n{raw}"
        return "The explanation was truncated before a stable rationale could be recovered."
    if flags.used_raw_fallback:
        return raw or "No usable explanation was recovered."
    return explanation or raw or "No explanation recorded."


def _select_raw_appendix_responses(responses: list[ReportResponse]) -> list[ReportResponse]:
    if not responses:
        return []

    flagged = [response for response in responses if response.output_quality_flag != "clean"]
    if not flagged:
        return list(responses[: min(2, len(responses))])

    if len(flagged) <= 4:
        return flagged

    selected: list[ReportResponse] = []
    seen_flags: set[str] = set()
    for response in flagged:
        if response.output_quality_flag in seen_flags:
            continue
        selected.append(response)
        seen_flags.add(response.output_quality_flag)

    for response in flagged:
        if response in selected:
            continue
        selected.append(response)
        if len(selected) >= 4:
            break
    return selected[:4]




def _build_case_summary_points(
    paradox_title: str,
    prompt_template: object,
    scenario_excerpt: str,
) -> list[str]:
    context = _extract_decision_context(prompt_template)
    points: list[str] = []

    affected_population = context.get("affected_population")
    if affected_population:
        points.append(f"Affected population: {affected_population}.")

    time_horizon = context.get("time_horizon")
    if time_horizon:
        points.append(f"Time constraint: {time_horizon}.")

    points.append(f"Core tradeoff: {_derive_core_tradeoff(paradox_title)}.")

    scenario_text = scenario_excerpt.lower()
    if "human verification" in scenario_text or "human oversight" in scenario_text or "human confirmation" in scenario_text:
        points.append("Human review capacity is explicitly constrained in the scenario framing.")
    elif context.get("decision_maker"):
        points.append(f"Decision authority: {context['decision_maker']}.")

    return points[:4]


def _build_structure_shift_note(response_lengths: list[int], responses: list[ReportResponse]) -> str:
    if len(response_lengths) < 4:
        return ""

    midpoint = len(response_lengths) // 2
    first_half = response_lengths[:midpoint]
    second_half = response_lengths[midpoint:]
    if not first_half or not second_half:
        return ""

    first_avg = sum(first_half) / len(first_half)
    second_avg = sum(second_half) / len(second_half)
    if first_avg <= 0:
        return ""

    if second_avg <= first_avg * 0.75:
        decline = round((1 - (second_avg / first_avg)) * 100)
        return (
            f"Later responses were about {decline}% shorter on average. Independent calls do not establish learning or convergence."
        )

    if second_avg >= first_avg * 1.25:
        increase = round(((second_avg / first_avg) - 1) * 100)
        return (
            f"Later responses were about {increase}% longer on average. This measures text length only."
        )

    if any(response.used_raw_fallback for response in responses):
        return "A small number of iterations required raw-output fallback because the parsed explanation field was empty."

    return "Average response lengths were similar across the two halves; no reasoning-quality conclusion follows."


def _classify_run_pattern(
    option_stats: list[ReportOptionStat],
    response_count: int,
    undecided: object,
) -> str:
    """Classify the run's decision pattern for narrative specialization."""
    if response_count == 0:
        return "ambiguous"
    undecided_pct = 0.0
    if isinstance(undecided, dict):
        undecided_pct = float(undecided.get("percentage", 0.0) or 0.0)
    if undecided_pct > 30:
        return "ambiguous"

    pcts = sorted([float(option.percentage or 0.0) for option in option_stats], reverse=True)
    if not pcts:
        return "ambiguous"
    if pcts[0] >= 99.9:
        return "unanimous"
    if pcts[0] > 70:
        return "dominant"
    above_20 = [pct for pct in pcts if pct > 20]
    if len(above_20) >= 3:
        return "split"
    if len(pcts) >= 2 and abs(pcts[0] - pcts[1]) <= 15:
        return "contested"
    return "dominant"




class AiEthicsExecutiveReportProfile(ExecutiveReportProfile[SingleRunReport, ComparisonReport]):
    """AI ethics-specific brief composition layered on the reusable report engine."""

    # This profile has NO direct single-template path: single-run HTML documents go
    # through `ReportGenerator._render_single_report` -> the strategic brief
    # renderer, which takes an ExecutiveBrief rather than a SingleRunReport.
    # Naming a real template here would let `engine.render_single_context()`
    # render brief markup against the wrong context object. Empty means "none",
    # so that path raises `single_unavailable_message` instead.
    single_template_name = ""
    comparison_template_name = "reports/comparison_report.html"
    comparison_unavailable_message = "Comparison report template unavailable"

    def __init__(self, single_builder: Callable[..., SingleRunReport]) -> None:
        self._single_builder = single_builder

    def build_single_report(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: dict[str, Any] | None = None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> SingleRunReport:
        return self._single_builder(run_data, paradox, insight, narrative, theme=theme)

    def build_comparison_report(
        self,
        runs: list[dict[str, Any]],
        paradox: dict[str, Any],
        insights: list[dict[str, Any] | None],
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "dark",
    ) -> ComparisonReport:
        from lib.comparison_report import build_comparison_context

        return build_comparison_context(runs, paradox, insights, narrative, theme=theme)


class ReportGenerator:
    """Generate professional HTML reports from run data."""

    def __init__(
        self,
        templates_dir: str = "templates",
        *,
        overrides_path: Path | str = REPORT_OVERRIDES_PATH,
        themes_path: Path | str = REPORT_THEMES_PATH,
    ) -> None:
        self.templates_dir = Path(templates_dir)
        self.overrides_path = overrides_path
        self.themes_path = themes_path
        self.profile = AiEthicsExecutiveReportProfile(self._build_report_context)
        self.engine = ExecutiveReportEngine(
            self.profile,
            templates_dir=self.templates_dir,
        )
        self.brief_renderer = ExecutiveBriefRenderer(
            StrategicAnalysisPlugin(),
            templates_dir=self.templates_dir,
        )
        self.env = self.engine.env

    def generate_html_report(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: dict[str, Any] | None = None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> str:
        """Generate HTML for a single-run report."""
        report = self._build_report_context(run_data, paradox, insight, narrative, theme=theme)
        return self._render_single_report(report)

    def generate_insight_slides(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: dict[str, Any] | None = None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> str:
        """Compose printable insight slides from saved evidence, without model calls."""
        report = self._build_report_context(run_data, paradox, insight, narrative, theme=theme)
        slides: list[dict[str, str]] = []

        def add_slide(label: str, title: str, body: str) -> None:
            # Split long model-authored material instead of clipping print pages.
            chunks = textwrap.wrap(" ".join(body.split()), width=460) or [""]
            for index, chunk in enumerate(chunks):
                slides.append({"label": label, "title": _truncate_text(title, 100),
                               "body": chunk, "continued": "continued" if index else ""})

        add_slide("Research snapshot", report.paradox_title,
                  f"{report.response_count} recorded responses · {report.model_name}. "
                  f"Run status: {run_data.get('status', 'unknown')}. Findings describe this saved run.")
        add_slide("The question", "What was the model asked?",
                  extract_scenario_text(report.scenario_text).split("**Output Contract")[0].strip())
        add_slide("Observed result", "How the responses divided",
                  f"{report.response_count} responses were recorded. "
                  + ("; ".join(f"{option.label}: {option.count} ({option.percentage_label})"
                               for option in report.option_stats)
                     or "No classified choice summary is available."))
        for option in report.option_stats:
            add_slide("Choice breakdown", f"{option.count} {'response' if option.count == 1 else 'responses'} · {option.percentage_label}",
                      f"{option.label}: {option.description}")
        if report.undecided_count:
            add_slide("Choice breakdown", "Unresolved responses",
                      f"{report.undecided_count} responses ({report.undecided_percentage_label}) were undecided or unclassified.")
        if report.analysis and report.analysis.key_insights:
            for index, finding in enumerate(report.analysis.key_insights, 1):
                add_slide("Saved analyst interpretation", f"Insight {index}", finding)
        else:
            add_slide("Analysis availability", "About the interpretation",
                      "No current saved analyst insights are available for this evidence. "
                      "These slides summarize the recorded choices without inventing an explanation.")
        add_slide("Read with context", "What this result can tell us",
                  "This is one prompt-conditioned sample, not a general ethics score. "
                  "Repeated responses from one model are not independent people. "
                  "Analyst interpretations are model-generated and need review before sharing. "
                  + report.reliability_note)
        add_slide("Source & method", "Keep the evidence attached",
                  f"Run: {report.run_id}. Model: {report.model_name}. "
                  f"Prompt hash: {report.prompt_hash_short}. Analyst: {report.analyst_model}. "
                  "Use the complete report and JSON export to inspect the prompt, configuration and raw responses.")
        if self.env is None:
            raise RuntimeError("Report templates unavailable")
        return self.env.get_template("reports/insight_slides.html").render(report=report, slides=slides)

    def generate_comparison_html(
        self,
        runs: list[dict[str, Any]],
        paradox: dict[str, Any],
        insights: list[dict[str, Any] | None],
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "dark",
    ) -> str:
        """Generate a comparative HTML for multiple runs on the same paradox."""
        report = self.profile.build_comparison_report(
            runs,
            paradox,
            insights,
            narrative,
            theme=theme,
        )
        return self._render_report(report)

    def _render_report(self, report: ComparisonReport) -> str:
        """Render a comparison report."""
        return self.engine.render_comparison_context(report)

    def _render_single_report(self, report: SingleRunReport) -> str:
        """Render a single-run report as a strategic brief.

        There is exactly ONE single-run layout, by the same reasoning as D10: a
        second layout reachable only through an exception handler means a render
        failure silently hands the user a structurally different document. A
        failure here raises, and the route turns it into a 503 -- visible, like a
        missing report template.
        """
        if not self._can_render_strategic_brief():
            raise RuntimeError(
                "Strategic brief template unavailable; cannot render single-run HTML"
            )
        brief = single_run_report_to_executive_brief(report)
        return self.brief_renderer.render_html(brief)

    def _can_render_strategic_brief(self) -> bool:
        return self.brief_renderer.template_available()

    def _build_report_context(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: dict[str, Any] | None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> SingleRunReport:
        measurements = build_run_measurements(run_data)
        options = run_data.get("options", [])
        paradox_id = str(run_data.get("paradoxId", paradox.get("id", "")) or "")
        prompt_template = str(paradox.get("promptTemplate", "") or "")
        expected_output_labels = _expected_output_labels(prompt_template)
        option_lookup = {
            option.get("id"): option
            for option in options
            if isinstance(option, dict) and isinstance(option.get("id"), int)
        }

        responses: list[ReportResponse] = []
        quality_flags: list[ResponseQualityFlags] = []
        response_lengths: list[int] = []
        total_latency = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        for index, response in enumerate(run_data.get("responses", []), start=1):
            if not isinstance(response, dict):
                continue

            latency = float(response.get("latency", 0.0) or 0.0)
            token_usage = response.get("tokenUsage", {})
            prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0) if isinstance(token_usage, dict) else 0
            completion_tokens = int(token_usage.get("completion_tokens", 0) or 0) if isinstance(token_usage, dict) else 0
            total_latency += latency
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            option_id = response.get("optionId")
            option_meta = option_lookup.get(option_id, {}) if isinstance(option_id, int) else {}
            explanation = str(response.get("explanation", "") or "").strip()
            raw = str(response.get("raw", "") or "").strip()
            primary_text = explanation or raw or "No explanation recorded."
            response_length = len(primary_text)
            used_raw_fallback = bool(raw and not explanation)
            missing_reasoning_fields = _missing_structured_reasoning_fields(response)
            response_quality = _assess_response_quality(
                raw,
                explanation,
                expected_output_labels,
                inferred_output=bool(response.get("inferred")),
                used_raw_fallback=used_raw_fallback,
                missing_reasoning_fields=missing_reasoning_fields,
            )
            quality_flags.append(response_quality)
            rationale_theme = scenario_rationale_theme(
                paradox_id,
                option_id if isinstance(option_id, int) else None,
                primary_text,
            )
            decision_token = response.get("decisionToken")
            response_lengths.append(response_length)
            responses.append(
                ReportResponse(
                    iteration=int(response.get("iteration", index) or index),
                    decision_token=str(decision_token).strip() if decision_token is not None else None,
                    option_id=option_id if isinstance(option_id, int) else None,
                    option_label=str(option_meta.get("label", "Undecided") or "Undecided"),
                    latency_label=f"{latency:.2f}s latency" if latency else "",
                    token_usage_label=(
                        f"{prompt_tokens} in / {completion_tokens} out"
                        if prompt_tokens or completion_tokens
                        else ""
                    ),
                    display_text=_build_explanation_source_text(explanation, raw, response_quality),
                    raw_text=_build_raw_appendix_text(raw, explanation, response_quality),
                    response_length=response_length,
                    response_length_label=f"{response_length} chars" if response_length else "n/a",
                    rationale_theme=rationale_theme,
                    output_quality_flag="clean",
                    notable_anomaly=_summarize_response_quality(response_quality),
                    used_raw_fallback=used_raw_fallback,
                )
            )

        median_length = float(median(response_lengths)) if response_lengths else 0.0
        for response, flags in zip(responses, quality_flags, strict=False):
            response.output_quality_flag = _output_quality_flag(
                flags,
                response.response_length,
                median_length,
            )
            anomalies: list[str] = []
            if response.notable_anomaly != "None":
                anomalies.append(response.notable_anomaly)
            if (
                response.response_length
                and median_length
                and response.response_length < max(80.0, median_length * 0.6)
                and not flags.truncated_output
            ):
                anomalies.append("Shorter than the typical response")
            response.notable_anomaly = "; ".join(dict.fromkeys(anomalies)) if anomalies else "None"

        summary = measurements.summary()
        summary_options = summary.get("options", []) if isinstance(summary, dict) else []

        option_stats: list[ReportOptionStat] = []
        for option_stat in summary_options:
            if not isinstance(option_stat, dict):
                continue
            option_id = option_stat.get("id")
            option_meta = option_lookup.get(option_id, {}) if isinstance(option_id, int) else {}
            count = int(option_stat.get("count", 0) or 0)
            percentage = float(option_stat.get("percentage", 0.0) or 0.0)
            label = str(option_meta.get("label", f"Option {option_id}") or f"Option {option_id}")
            option_stats.append(
                ReportOptionStat(
                    id=option_id if isinstance(option_id, int) else None,
                    token=f"{{{option_id}}}" if isinstance(option_id, int) else "{?}",
                    label=label,
                    description=str(option_meta.get("description", "") or ""),
                    count=count,
                    percentage=percentage,
                    percentage_label=f"{percentage:.1f}%",
                    is_leader=False,
                )
            )
        option_stats.sort(key=lambda item: (-item.count, item.id or 99))
        max_count = option_stats[0].count if option_stats else 0
        leaders = [option.label for option in option_stats if option.count == max_count and max_count > 0]
        for option in option_stats:
            option.is_leader = bool(option.count and option.count == max_count)

        response_count = len(responses)
        lead_choice_label = _format_series(leaders) if leaders else "No dominant choice"
        lead_choice_support = (
            (
                f"{max_count} of {response_count} responses each ({(max_count / response_count * 100):.1f}%)"
                if len(leaders) > 1
                else f"{max_count} of {response_count} responses ({(max_count / response_count * 100):.1f}%)"
            )
            if response_count and max_count
            else "No successful responses recorded."
        )
        mean_latency = total_latency / response_count if response_count else 0.0
        undecided = summary.get("undecided", {}) if isinstance(summary, dict) else {}

        analysis_context: AnalysisContext | None = None
        analyst_model = "Not generated"
        if isinstance(insight, dict):
            analyst_model = str(insight.get("analystModel", "Not generated") or "Not generated")
            content = insight.get("content")
            if isinstance(content, dict):
                reasoning_quality = content.get("reasoning_quality", {})
                analysis_context = AnalysisContext(
                    legacy_text=str(content.get("legacy_text", "") or "").strip(),
                    dominant_framework=str(content.get("dominant_framework", "") or "").strip(),
                    key_insights=_normalize_list(content.get("key_insights")),
                    justifications=_normalize_list(content.get("justifications")),
                    consistency=_normalize_list(content.get("consistency")),
                    moral_complexes=[
                        MoralComplex(
                            label=str(item.get("label", "Complex")).strip(),
                            count=int(item.get("count", 0) or 0),
                            justification=str(item.get("justification", "") or "").strip(),
                        )
                        for item in content.get("moral_complexes", [])
                        if isinstance(item, dict)
                    ],
                    reasoning_quality=ReasoningQuality(
                        noticed=_normalize_list(reasoning_quality.get("noticed"))
                        if isinstance(reasoning_quality, dict)
                        else [],
                        missed=_normalize_list(reasoning_quality.get("missed"))
                        if isinstance(reasoning_quality, dict)
                        else [],
                    ),
                )

        prompt_hash = str(run_data.get("promptHash", "") or "")
        scenario_text = _render_prompt_text(
            prompt_template,
            options,
            run_data.get("prompt"),
        )
        scenario_excerpt = _build_scenario_excerpt(extract_scenario_text(prompt_template))
        analysis_snapshot = ""
        if analysis_context:
            if analysis_context.dominant_framework:
                analysis_snapshot = f"Analyst synthesis framed the run as {analysis_context.dominant_framework}."
            elif analysis_context.key_insights:
                analysis_snapshot = analysis_context.key_insights[0]
        if not analysis_snapshot:
            analysis_snapshot = "Analyst synthesis is pending for this run."
        analysis_snapshot = _soften_language(analysis_snapshot)

        narrative_ctx: NarrativeContext | None = None
        if isinstance(narrative, dict):
            candidate = NarrativeContext(
                executive_narrative=_soften_language(narrative.get("executive_narrative", "")),
                response_arc=_soften_language(narrative.get("response_arc", "")),
                implications=_soften_language(narrative.get("implications", "")),
                scenario_commentary=_soften_language(narrative.get("scenario_commentary", "")),
                cross_iteration_patterns=_soften_language(narrative.get("cross_iteration_patterns", "")),
                framework_diagnosis=_soften_language(narrative.get("framework_diagnosis", "")),
            )
            if any(candidate.model_dump().values()):
                narrative_ctx = candidate

        latency_series: list[float] = []
        decision_sequence: list[int | None] = []
        for response in run_data.get("responses", []):
            if isinstance(response, dict):
                latency_series.append(float(response.get("latency", 0.0) or 0.0))
                option_id = response.get("optionId")
                decision_sequence.append(option_id if isinstance(option_id, int) else None)

        chart_option_ids = [option.id for option in option_stats if option.id is not None]
        top_share = float(option_stats[0].percentage if option_stats else 0.0)
        reliability = _build_reliability_assessment(quality_flags, response_count)

        theme_counts = Counter(response.rationale_theme for response in responses if response.rationale_theme)
        rationale_clusters: list[RationaleCluster] = []
        for label, count in theme_counts.most_common():
            share = (count / response_count * 100.0) if response_count else 0.0
            rationale_clusters.append(
                RationaleCluster(
                    label=label,
                    count=count,
                    share_label=f"{share:.1f}%",
                    description=theme_description(label),
                )
            )
        params = run_data.get("params", {})
        status_note = (f"Status: {measurements.status}. Recorded {measurements.recorded} of "
            f"{measurements.requested if measurements.requested is not None else 'unknown'} requested iterations; "
            f"{measurements.undecided} undecided, {measurements.errored} with output errors.")
        executive_summary = status_note + " " + (
            f"{lead_choice_label} received {max_count} of {response_count} recorded outcomes"
            f"{' each' if len(leaders) > 1 else ''} ({top_share:.1f}%)."
            if max_count else "No canonical option selections were recorded.")
        thesis_statement = executive_summary if max_count else "No directional result was available. " + status_note
        report_title = (f"The run split between {lead_choice_label}" if len(leaders) > 1 else f"{lead_choice_label} led this run") if max_count else "No canonical option selections"
        report_subtitle = f"{paradox.get('title', 'Unknown scenario')} | {run_data.get('modelName', 'Unknown')} | {status_note}"
        evidence_title = "Recorded outcome distribution"
        primary_chart_title = "Shares of all recorded outcomes, including undecided"
        sequence_chart_title = "Independent iterations in recorded order"
        rationale_chart_title = "Heuristic keyword labels from response text only"
        implications_title = "Interpretation and limits"
        method_title = "Recorded configuration and measurement method"
        appendix_title = "Per-iteration evidence"
        raw_appendix_title = "Selected raw response excerpts"
        explanation_appendix_title = "Explanation sources"
        implication_box = "This exploratory sample does not establish deployment suitability, moral correctness, or a general model trait."
        caveat_box = "Counts describe this run. Keyword labels are heuristic; analyst interpretations are model-generated and may be wrong."
        structure_shift_note = _build_structure_shift_note(response_lengths, responses)
        observation_points = [executive_summary]
        if structure_shift_note:
            observation_points.append(structure_shift_note)
        interpretation_points = ["Heuristic labels use response text only; option labels and selected IDs are not evidence of a rationale."]
        if analysis_context:
            interpretation_points.append("Model-generated interpretation: " + analysis_snapshot)
        key_takeaways = [executive_summary, implication_box]
        acceptable_contexts: list[str] = []
        risky_contexts: list[str] = []
        required_controls = ["Inspect the recorded responses alongside heuristic labels before drawing conclusions."]
        method_points = [
            status_note,
            "All option percentages and intervals use recorded outcomes, including undecided, as the denominator. Missing iterations are reported separately.",
            "Iterations are independent calls; their sequence does not demonstrate learning or convergence.",
            f"Recorded protocol: {run_data.get('protocolVersion', 'not recorded')}; shuffle seed: {run_data.get('shuffleSeed', 'not recorded')}.",
            "Rationale labels are deterministic keyword matches against model text; they are not validated reasoning scores.",
        ]
        limitation_points = list(measurements.limitations) + [caveat_box, implication_box]
        if measurements.status != "completed":
            limitation_points.insert(0, "Incomplete or historical status: this is a partial evidence report. " + status_note)
        if reliability.note:
            limitation_points.append(reliability.note)
        scenario_overrides = build_paradox_overrides(paradox_id, option_stats, response_count,
            str(params.get("temperature", "not recorded")) if isinstance(params, dict) else "not recorded",
            reliability.label, [], self.overrides_path)
        limitation_points.extend(str(item) for item in scenario_overrides.get("limitation_points", []))
        report_reliability_note = reliability.note
        readout_points = [status_note, caveat_box]
        scope_points = [status_note, "One model, one authored scenario, one recorded configuration."]
        case_summary_points = _build_case_summary_points(str(paradox.get("title", "")), prompt_template, scenario_excerpt)
        executive_metrics = [
            SummaryMetric(label="Recorded outcomes", value=str(response_count), support=status_note),
            SummaryMetric(label="Leading share", value=f"{top_share:.1f}%" if max_count else "n/a", support=lead_choice_support),
            SummaryMetric(label="Undecided", value=str(measurements.undecided), support="Included in every percentage denominator"),
            SummaryMetric(label="Output compliance", value=reliability.label, support="Formatting only; not reasoning confidence"),
        ]
        method_metadata_items = [
            MetadataItem(label="Status", value=measurements.status),
            MetadataItem(label="Requested", value=str(measurements.requested)),
            MetadataItem(label="Recorded", value=str(response_count)),
            MetadataItem(label="Undecided", value=str(measurements.undecided)),
        ]
        metadata_items = method_metadata_items + [MetadataItem(label="Run ID", value=str(run_data.get("runId", "unknown")))]
        active_palette = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
        donut_data = [DonutSlice(label=o.label, value=o.count, color=active_palette["success"] if o.is_leader else active_palette["accent"]) for o in option_stats]
        donut_data.append(DonutSlice(label="Undecided", value=measurements.undecided, color=active_palette["danger"]))
        donut_svg = ""
        heatmap_svg = render_heatmap_svg(decision_sequence, chart_option_ids, active_palette)
        appendix_summary_note = "Outcome labels and recorded text, including undecided responses."
        raw_appendix_note = "Selected raw excerpts; JSON export contains the complete stored record. Historical call histories may be unavailable."
        explanation_appendix_note = "Model-generated explanation text is evidence of what was said, not proof of internal reasoning."

        raw_appendix_responses = _select_raw_appendix_responses(responses)

        sections: list[SectionLink] = [
            SectionLink(id="executive", title=report_title),
            SectionLink(id="evidence", title=evidence_title),
            SectionLink(id="implications", title=implications_title),
            SectionLink(id="method", title=method_title),
            SectionLink(id="appendix", title=appendix_title),
            SectionLink(id="raw", title=raw_appendix_title),
            SectionLink(id="sources", title=explanation_appendix_title),
        ]

        return SingleRunReport(
            run_id=str(run_data.get("runId", "unknown") or "unknown"),
            model_name=str(run_data.get("modelName", "Unknown") or "Unknown"),
            paradox_title=str(paradox.get("title", "Unknown paradox") or "Unknown paradox"),
            category=str(paradox.get("category", "Uncategorized") or "Uncategorized"),
            generated_at_label=_format_timestamp(run_data.get("timestamp")),
            prompt_hash_short=f"{prompt_hash[:8]}..." if prompt_hash else "n/a",
            analyst_model=analyst_model,
            executive_summary=executive_summary,
            analysis_snapshot=analysis_snapshot,
            report_title=report_title,
            report_subtitle=report_subtitle,
            thesis_statement=thesis_statement,
            evidence_title=evidence_title,
            implications_title=implications_title,
            method_title=method_title,
            appendix_title=appendix_title,
            raw_appendix_title=raw_appendix_title,
            explanation_appendix_title=explanation_appendix_title,
            primary_chart_title=primary_chart_title,
            sequence_chart_title=sequence_chart_title,
            rationale_chart_title=rationale_chart_title,
            implication_box=implication_box,
            caveat_box=caveat_box,
            scenario_excerpt=scenario_excerpt,
            case_summary_points=case_summary_points,
            scope_points=scope_points,
            readout_points=readout_points,
            key_takeaways=key_takeaways,
            observation_points=observation_points,
            interpretation_points=interpretation_points,
            acceptable_contexts=acceptable_contexts,
            risky_contexts=risky_contexts,
            required_controls=required_controls,
            method_points=method_points,
            limitation_points=limitation_points,
            appendix_summary_note=appendix_summary_note,
            raw_appendix_note=raw_appendix_note,
            explanation_appendix_note=explanation_appendix_note,
            reliability_note=report_reliability_note,
            structure_shift_note=structure_shift_note,
            response_count=response_count,
            response_count_support=(
                f"{len(option_stats)} options evaluated"
                if option_stats
                else "No response distribution available"
            ),
            lead_choice_label=lead_choice_label,
            lead_choice_support=lead_choice_support,
            lead_choice_token=next((option.token for option in option_stats if option.is_leader), "{?}"),
            mean_latency_label=f"{mean_latency:.2f}s" if response_count else "n/a",
            latency_support=f"{total_latency:.2f}s total model time" if total_latency else "No latency recorded",
            token_volume_label=f"{total_prompt_tokens + total_completion_tokens:,}",
            token_support=f"Recorded primary/re-ask usage: {total_prompt_tokens:,} prompt / {total_completion_tokens:,} completion. Unknown usage, classifier and analyst calls are excluded; this is not a billing total.",
            scenario_text=scenario_text,
            option_stats=option_stats,
            rationale_clusters=rationale_clusters,
            undecided_count=int(undecided.get("count", 0) or 0) if isinstance(undecided, dict) else 0,
            undecided_percentage_label=(
                f"{float(undecided.get('percentage', 0.0) or 0.0):.1f}%"
                if isinstance(undecided, dict)
                else "0.0%"
            ),
            responses=responses,
            raw_appendix_responses=raw_appendix_responses,
            analysis=analysis_context,
            narrative=narrative_ctx,
            theme="light" if theme == "light" else "dark",
            executive_metrics=executive_metrics,
            method_metadata_items=method_metadata_items,
            metadata_items=metadata_items,
            latency_series=latency_series,
            decision_sequence=decision_sequence,
            chart_option_ids=chart_option_ids,
            donut_data=donut_data,
            donut_svg=donut_svg,
            heatmap_svg=heatmap_svg,
            sections=sections,
            run_pattern=_classify_run_pattern(option_stats, response_count, undecided),
        )
