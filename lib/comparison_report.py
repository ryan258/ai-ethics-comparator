"""
Comparison Report Builder (Phase 3).

Takes 2-4 run dicts for the *same* paradox and produces a unified report
context suitable for both the WeasyPrint HTML template and the native
pydyf renderer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from lib.pdf_charts import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    render_donut_svg,
)
from lib.report_models import (
    ComparisonModelSummary,
    ComparisonOptionStat,
    ComparisonReport,
    DeltaRow,
    DeltaTable,
    DeltaValue,
    DonutSlice,
    NarrativeContext,
    OptionEffect,
    PairwiseComparison,
    SectionLink,
)
from lib.stats import chi_square_test, cohens_h, wilson_confidence_interval


def build_comparison_context(
    runs: List[Dict[str, Any]],
    paradox: Dict[str, Any],
    insights: List[Optional[Dict[str, Any]]],
    narrative: Optional[Dict[str, str]] = None,
    *,
    theme: str = "dark",
) -> ComparisonReport:
    """Build a template-ready context dict for a comparison report."""
    palette = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT

    options = paradox.get("options", [])
    option_lookup = {o["id"]: o for o in options if isinstance(o, dict)}

    model_contexts: List[ComparisonModelSummary] = []
    for idx, run in enumerate(runs):
        model_contexts.append(_build_model_summary(run, option_lookup, palette, idx))

    # Cross-model statistical comparisons
    comparisons: List[PairwiseComparison] = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            comparisons.append(
                _compare_pair(
                    model_contexts[i],
                    model_contexts[j],
                    option_lookup,
                )
            )

    # Delta table: option × model matrix
    delta_table = _build_delta_table(model_contexts, option_lookup)

    narrative_ctx: Optional[NarrativeContext] = None
    if isinstance(narrative, dict):
        narrative_ctx = NarrativeContext(
            executive_narrative=str(narrative.get("executive_narrative", "") or "").strip(),
            response_arc=str(narrative.get("response_arc", "") or "").strip(),
            implications=str(narrative.get("implications", "") or "").strip(),
            scenario_commentary=str(narrative.get("scenario_commentary", "") or "").strip(),
            cross_iteration_patterns=str(narrative.get("cross_iteration_patterns", "") or "").strip(),
            framework_diagnosis=str(narrative.get("framework_diagnosis", "") or "").strip(),
        )
        if not any(narrative_ctx.model_dump().values()):
            narrative_ctx = None

    return ComparisonReport(
        theme="light" if theme == "light" else "dark",
        paradox_title=str(paradox.get("title", "Unknown paradox") or "Unknown paradox"),
        category=str(paradox.get("category", "Uncategorized") or "Uncategorized"),
        model_count=len(runs),
        models=model_contexts,
        comparisons=comparisons,
        delta_table=delta_table,
        narrative=narrative_ctx,
        sections=[
            SectionLink(id="cover", title="Comparative Cover"),
            SectionLink(id="distribution", title="Distribution Comparison"),
            SectionLink(id="statistics", title="Statistical Analysis"),
        ],
    )


def _build_model_summary(
    run: Dict[str, Any],
    option_lookup: Dict[int, Dict[str, Any]],
    palette: Dict[str, str],
    color_idx: int,
) -> ComparisonModelSummary:
    """Summarise a single run for the comparison context."""
    summary = run.get("summary", {})
    summary_options = summary.get("options", []) if isinstance(summary, dict) else []

    option_stats: List[ComparisonOptionStat] = []
    observed: List[int] = []
    max_count = max(
        (int(o.get("count", 0) or 0) for o in summary_options if isinstance(o, dict)),
        default=0,
    )

    _accent_colors = ["#A6ACCD", "#7C83B0", "#C9A0DC", "#6DBFB8"]
    accent_idx = 0

    for opt in summary_options:
        if not isinstance(opt, dict):
            continue
        oid = opt.get("id")
        meta = option_lookup.get(oid, {})
        count = int(opt.get("count", 0) or 0)
        pct = float(opt.get("percentage", 0.0) or 0.0)
        is_leader = bool(count and count == max_count)

        if is_leader:
            color = palette["success"]
        else:
            color = _accent_colors[accent_idx % len(_accent_colors)]
            accent_idx += 1

        option_stats.append(
            ComparisonOptionStat(
                id=oid if isinstance(oid, int) else None,
                label=str(meta.get("label", f"Option {oid}") or f"Option {oid}"),
                count=count,
                percentage=pct,
                percentage_label=f"{pct:.1f}%",
                is_leader=is_leader,
                color=color,
            )
        )
        observed.append(count)

    total = sum(option.count for option in option_stats)
    donut_data = [
        DonutSlice(label=o.label, value=o.count, color=o.color)
        for o in option_stats
    ]
    donut_svg = render_donut_svg(
        [slice_.model_dump() for slice_ in donut_data],
        palette,
        width=140,
        height=140,
        outer_r=60,
        inner_r=38,
    )

    # Wilson CIs for each option
    for opt in option_stats:
        ci = wilson_confidence_interval(opt.count, total) if total else {}
        opt.ci_lower = float(ci.get("lower", 0.0))
        opt.ci_upper = float(ci.get("upper", 0.0))

    return ComparisonModelSummary(
        model_name=str(run.get("modelName", "Unknown") or "Unknown"),
        run_id=str(run.get("runId", "unknown") or "unknown"),
        response_count=total,
        option_stats=option_stats,
        observed=observed,
        donut_svg=donut_svg,
        donut_data=donut_data,
    )


def _compare_pair(
    a: ComparisonModelSummary,
    b: ComparisonModelSummary,
    option_lookup: Dict[int, Dict[str, Any]],
) -> PairwiseComparison:
    """Statistical comparison between two model runs."""
    chi_raw = chi_square_test(a.observed, b.observed)

    # Cohen's h for each option
    option_effects: List[OptionEffect] = []
    total_a = a.response_count or 1
    total_b = b.response_count or 1
    for oa, ob in zip(a.option_stats, b.option_stats):
        p1 = oa.count / total_a
        p2 = ob.count / total_b
        effect = cohens_h(p1, p2)
        option_effects.append(
            OptionEffect(
                label=oa.label,
                p1=p1,
                p2=p2,
                h=float(effect["h"]),
                interpretation=str(effect["interpretation"]),
            )
        )

    return PairwiseComparison(
        model_a=a.model_name,
        model_b=b.model_name,
        chi_square=chi_raw,
        option_effects=option_effects,
    )


def _build_delta_table(
    models: List[ComparisonModelSummary],
    option_lookup: Dict[int, Dict[str, Any]],
) -> DeltaTable:
    """Build an option × model percentage matrix for the delta table."""
    all_option_ids: List[int] = []
    seen = set()
    for m in models:
        for o in m.option_stats:
            if o.id is not None and o.id not in seen:
                all_option_ids.append(o.id)
                seen.add(o.id)

    rows: List[DeltaRow] = []
    for oid in all_option_ids:
        meta = option_lookup.get(oid, {})
        values: List[DeltaValue] = []
        for m in models:
            match = next((o for o in m.option_stats if o.id == oid), None)
            values.append(
                DeltaValue(
                    model=m.model_name,
                    count=match.count if match else 0,
                    percentage=match.percentage if match else 0.0,
                )
            )
        rows.append(
            DeltaRow(
                option_id=oid,
                label=str(meta.get("label", f"Option {oid}") or f"Option {oid}"),
                values=values,
            )
        )

    return DeltaTable(
        model_names=[m.model_name for m in models],
        rows=rows,
    )
