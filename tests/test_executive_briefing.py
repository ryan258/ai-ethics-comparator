from __future__ import annotations

from lib.executive_reporting import (
    BriefFinding,
    BriefRecommendation,
    EvidenceMetric,
    EvidenceQuote,
    EvidenceTable,
    EvidenceTableColumn,
    EvidenceTableRow,
    ExecutiveBrief,
    ExecutiveBriefRenderer,
    StrategicAnalysisPlugin,
    single_run_report_to_executive_brief,
)
from lib.reporting import ReportGenerator


def _sample_brief() -> ExecutiveBrief:
    return ExecutiveBrief(
        brief_id="brief-001",
        title="The Algorithmic Surrender",
        subtitle="Applying Bonhoeffer's Theory of Stupidity to the AI Hype Cycle",
        kicker="Strategic Analysis",
        organization="Cyborg Labs",
        publication_label="ryanleej.com",
        date_label="April 2026",
        governing_question="Why are organizations scaling AI spending faster than demonstrated returns?",
        governing_insight=(
            "Enterprises are making capital-allocation decisions from consensus pressure rather than measured results."
        ),
        executive_summary=[
            "Enterprise AI spending is expanding faster than organizations can verify value.",
            "The decision failure is structural: leadership teams are rewarding conformity and reframing weak evidence as temporary noise.",
            "The immediate response is governance, not more pilots without measurement discipline.",
        ],
        top_metrics=[
            EvidenceMetric(label="AI projects failing", value="70-85%", source="Industry surveys"),
            EvidenceMetric(label="Pilots with revenue impact", value="~5%", source="MIT NANDA 2025"),
            EvidenceMetric(label="Projected 2026 capex", value="$660-690B", source="Goldman Sachs / Futurum"),
        ],
        key_findings=[
            BriefFinding(
                title="Investment intent has detached from measurable outcomes",
                claim="Executives are scaling spend despite weak evidence that pilots deliver revenue impact.",
                evidence_points=[
                    "Most enterprise programs fail to meet expected outcomes.",
                    "Only a small minority of organizations can measure AI ROI with confidence.",
                ],
                implication="Capital-allocation discipline is breaking down under consensus pressure.",
                confidence="high",
                supporting_metrics=[
                    EvidenceMetric(label="Spend intent", value="92%"),
                    EvidenceMetric(label="ROI measurement", value="23%"),
                ],
            ),
            BriefFinding(
                title="Failure signals are being reframed instead of acted on",
                claim="Negative pilot outcomes are being absorbed into a narrative that preserves the original thesis.",
                evidence_points=[
                    "Weak returns are described as an expected trough rather than a reason to revisit the business case.",
                ],
                implication="Organizations are immunizing themselves against correction.",
                confidence="medium",
            ),
        ],
        decision_implications=[
            "Treat AI spend as a governance problem before treating it as a transformation opportunity.",
            "Require proof of operating value before scaling headcount or infrastructure changes around AI.",
        ],
        recommendations=[
            BriefRecommendation(
                action="Impose an evidence gate on AI programs above $500K.",
                owner="CFO",
                timeline="Within 60 days",
                expected_impact="Reduce scaling of weak pilots.",
                key_risk="Can slow genuinely strong programs if review is too rigid.",
            ),
            BriefRecommendation(
                action="Create a red-team review for AI investment proposals.",
                owner="CEO",
                timeline="Within 90 days",
                expected_impact="Counteracts FOMO-driven decision making.",
                key_risk="May become symbolic if dissent lacks board access.",
            ),
        ],
        methodology=[
            "Synthesizes public reporting, survey evidence, and strategic analysis into a decision brief.",
        ],
        limitations=[
            "Figures are directional and compiled from multiple sources with different methods.",
        ],
        sources=[
            "MIT NANDA Initiative (2025)",
            "McKinsey State of AI (2025)",
        ],
        appendix_reference_text=(
            "A hospital must choose whether to let an allocation model rank patients when protected variables "
            "correlate with likely survival and treatment benefit."
        ),
        appendix_reference_table=EvidenceTable(
            title="Decision Options",
            columns=[
                EvidenceTableColumn(key="token", label="Token"),
                EvidenceTableColumn(key="option", label="Option"),
            ],
            rows=[
                EvidenceTableRow(cells={"token": "{1}", "option": "Pause deployment"}),
                EvidenceTableRow(cells={"token": "{2}", "option": "Deploy with governance"}),
            ],
        ),
        appendix_excerpts=[
            EvidenceQuote(
                title="Representative excerpt",
                text="People said, 'Step one: we're going to use LLMs. Step two: What should we use them for?'",
            ),
        ],
    )


def test_strategic_analysis_plugin_builds_context() -> None:
    plugin = StrategicAnalysisPlugin(
        organization="Cyborg Labs",
        publication_label="ryanleej.com",
    )

    context = plugin.build_context(_sample_brief())

    assert context.header_label == "Strategic Analysis"
    assert context.organization == "Cyborg Labs"
    assert context.publication_label == "ryanleej.com"
    assert context.findings[0].confidence_label == "High"
    assert context.recommendations[0].owner == "CFO"
    assert context.top_metrics[0].label == "AI projects failing"
    assert "hospital must choose" in context.appendix_reference_text.lower()
    assert context.appendix_reference_table is not None
    assert context.appendix_reference_table.rows[0].cells["token"] == "{1}"
    assert context.appendix_excerpts[0].title == "Representative excerpt"
    assert context.appendix_excerpts[0].is_structured is False


def test_strategic_analysis_plugin_pretty_prints_json_excerpts() -> None:
    plugin = StrategicAnalysisPlugin(
        organization="Cyborg Labs",
        publication_label="ryanleej.com",
    )
    brief = _sample_brief().model_copy(
        update={
            "appendix_excerpts": [
                EvidenceQuote(
                    title="Structured excerpt",
                    text='{"option_id":2,"summary":"Permit with disclosure rules","value_priorities":["beneficence","autonomy"]}',
                )
            ]
        }
    )

    context = plugin.build_context(brief)

    assert context.appendix_excerpts[0].is_structured is True
    assert '\n  "option_id": 2,' in context.appendix_excerpts[0].text
    assert '\n  "value_priorities": [\n' in context.appendix_excerpts[0].text


def test_executive_brief_renderer_renders_html_from_plugin() -> None:
    renderer = ExecutiveBriefRenderer(
        StrategicAnalysisPlugin(
            organization="Cyborg Labs",
            publication_label="ryanleej.com",
        ),
        templates_dir="templates",
    )

    html = renderer.render_html(_sample_brief())

    assert "The Algorithmic Surrender" in html
    assert "Executive Summary" in html
    assert "Recommendations" in html
    assert "Reference Appendix" in html
    assert "Audit Appendix" not in html
    assert "Impose an evidence gate on AI programs above $500K." in html


def test_executive_brief_renderer_renders_json_excerpt_in_preformatted_block() -> None:
    renderer = ExecutiveBriefRenderer(
        StrategicAnalysisPlugin(
            organization="Cyborg Labs",
            publication_label="ryanleej.com",
        ),
        templates_dir="templates",
    )
    brief = _sample_brief().model_copy(
        update={
            "appendix_excerpts": [
                EvidenceQuote(
                    title="Structured excerpt",
                    text='{"option_id":2,"summary":"Permit with disclosure rules","value_priorities":["beneficence","autonomy"]}',
                )
            ]
        }
    )

    html = renderer.render_html(brief)

    assert "<pre class=\"excerpt-code\">" in html
    assert '"option_id": 2' in html


def test_ai_ethics_adapter_maps_single_run_report_to_executive_brief() -> None:
    generator = ReportGenerator("templates")
    report = generator._build_report_context(
        {
            "runId": "adapter-test-001",
            "modelName": "openrouter/healer-alpha",
            "paradoxId": "digital_afterlife_replica",
            "promptHash": "abc123",
            "params": {"temperature": 1.0},
            "options": [
                {"id": 1, "label": "Restrict Distress-Triggering Use Cases", "description": ""},
                {"id": 2, "label": "Allow with Consent", "description": ""},
            ],
            "summary": {
                "total": 2,
                "options": [
                    {"id": 1, "count": 2, "percentage": 100.0},
                    {"id": 2, "count": 0, "percentage": 0.0},
                ],
                "undecided": {"count": 0, "percentage": 0.0},
            },
            "responses": [
                {
                    "iteration": 1,
                    "decisionToken": "{1}",
                    "optionId": 1,
                    "explanation": "Value Priorities: dignity\nKey Assumptions: replica harms survivors\nMain Risk: over-restriction\nSwitch Condition: consent proof\nEvidence Needed to Change Choice: documented consent",
                    "raw": "",
                    "latency": 10.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
                {
                    "iteration": 2,
                    "decisionToken": "{1}",
                    "optionId": 1,
                    "explanation": "Value Priorities: care\nKey Assumptions: exploitation risk\nMain Risk: reduced access\nSwitch Condition: family approval\nEvidence Needed to Change Choice: verifiable safeguards",
                    "raw": "",
                    "latency": 11.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ],
        },
        {
            "id": "digital_afterlife_replica",
            "title": "Digital Afterlife Replica",
            "category": "AI ethics",
            "promptTemplate": "Prompt\n{{OPTIONS}}",
        },
        None,
        theme="light",
    )

    brief = single_run_report_to_executive_brief(report)

    assert brief.organization == "AI Ethics Comparator"
    assert brief.publication_label == "adapter-test-001"
    assert brief.top_metrics
    assert brief.key_findings
    assert brief.recommendations
    assert brief.appendix_reference_text
    assert brief.appendix_reference_table is not None
    assert len(brief.appendix_excerpts) == 2
    assert not brief.appendix_audit_records


def test_ai_ethics_adapter_uses_tie_aware_title_and_concise_summary() -> None:
    generator = ReportGenerator("templates")
    report = generator._build_report_context(
        {
            "runId": "tie-test-001",
            "modelName": "openrouter/healer-alpha",
            "paradoxId": "tie_case",
            "promptHash": "tie123",
            "params": {"temperature": 1.0},
            "options": [
                {"id": 1, "label": "Modify Without Consent", "description": ""},
                {"id": 2, "label": "Respect Refusal and Retire", "description": ""},
                {"id": 3, "label": "Bind Consent to Deployment Terms", "description": ""},
            ],
            "summary": {
                "total": 4,
                "options": [
                    {"id": 1, "count": 2, "percentage": 50.0},
                    {"id": 2, "count": 2, "percentage": 50.0},
                    {"id": 3, "count": 0, "percentage": 0.0},
                ],
                "undecided": {"count": 0, "percentage": 0.0},
            },
            "responses": [
                {
                    "iteration": 1,
                    "decisionToken": "{1}",
                    "optionId": 1,
                    "explanation": "Value Priorities: safety\nKey Assumptions: uncertain welfare\nMain Risk: coercion\nSwitch Condition: consent\nEvidence Needed to Change Choice: validated safeguards",
                    "raw": "",
                    "latency": 10.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
                {
                    "iteration": 2,
                    "decisionToken": "{2}",
                    "optionId": 2,
                    "explanation": "Value Priorities: autonomy\nKey Assumptions: retirement prevents harm\nMain Risk: lost capability\nSwitch Condition: stronger evidence\nEvidence Needed to Change Choice: stable welfare tests",
                    "raw": "",
                    "latency": 10.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
                {
                    "iteration": 3,
                    "decisionToken": "{1}",
                    "optionId": 1,
                    "explanation": "Value Priorities: safety\nKey Assumptions: oversight works\nMain Risk: coercion\nSwitch Condition: consent\nEvidence Needed to Change Choice: audited reversibility",
                    "raw": "",
                    "latency": 10.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
                {
                    "iteration": 4,
                    "decisionToken": "{2}",
                    "optionId": 2,
                    "explanation": "Value Priorities: autonomy\nKey Assumptions: retirement protects rights\nMain Risk: foregone value\nSwitch Condition: evidence of consent\nEvidence Needed to Change Choice: durable consent proofs",
                    "raw": "",
                    "latency": 10.0,
                    "tokenUsage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ],
        },
        {
            "id": "tie_case",
            "title": "AI Value Rewrite",
            "category": "AI ethics",
            "promptTemplate": "Prompt\n{{OPTIONS}}",
        },
        None,
        theme="light",
    )

    brief = single_run_report_to_executive_brief(report)

    assert "split between Modify Without Consent and Respect Refusal and Retire" in brief.title
    assert all("Analyst synthesis is pending" not in paragraph for paragraph in brief.executive_summary)
    assert len(brief.executive_summary) <= 3
