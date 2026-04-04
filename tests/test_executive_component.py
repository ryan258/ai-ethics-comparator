from __future__ import annotations

from lib.executive_reporting import (
    AuditRecord,
    BriefMetadataItem,
    EvidenceMetric,
    EvidenceObservation,
    EvidencePackage,
    EvidenceQuote,
    ExecutiveBrief,
    ExecutiveBriefingComponent,
)


def _sample_evidence_package() -> EvidencePackage:
    return EvidencePackage(
        package_id="evidence-001",
        subject="Algorithmic Surrender",
        governing_question="Why are organizations scaling AI before proving value?",
        governing_insight="Leaders are treating consensus as evidence.",
        summary_metrics=[
            EvidenceMetric(label="Programs missing targets", value="70-85%", source="Industry surveys"),
            EvidenceMetric(label="Pilots with measured ROI", value="23%", source="McKinsey"),
        ],
        observations=[
            EvidenceObservation(
                title="Investment intent outpaces proof",
                summary="Organizations are increasing spend despite weak evidence of operational returns.",
                evidence_points=[
                    "Most enterprise programs do not hit expected outcomes.",
                    "Only a minority of operators report reliable ROI measurement.",
                ],
                significance="Governance discipline is lagging behind investment commitments.",
                confidence="high",
            ),
            EvidenceObservation(
                title="Failure signals are being normalized",
                summary="Weak pilot outcomes are being reframed as temporary noise instead of decision inputs.",
                evidence_points=[
                    "Negative outcomes are often described as part of a normal adoption curve.",
                ],
                significance="Leadership teams are becoming less responsive to disconfirming evidence.",
                confidence="medium",
            ),
        ],
        excerpts=[
            EvidenceQuote(
                title="Investment intent outpaces proof",
                text="We decided to use LLMs before deciding what problem they would solve.",
                attribution="Industry interview",
                significance="Shows strategy being driven by momentum rather than problem definition.",
            ),
        ],
        methodology=["Synthesis of survey evidence, public reporting, and analyst review."],
        limitations=["Underlying studies use different samples and definitions of success."],
        sources=["McKinsey State of AI", "Industry survey synthesis"],
        audit_records=[
            AuditRecord(
                title="Evidence overlap is directional",
                summary="The ROI and spend-intent figures come from separate studies.",
                severity="warning",
            )
        ],
        metadata=[
            BriefMetadataItem(label="organization", value="Cyborg Labs"),
            BriefMetadataItem(label="publication", value="ryanleej.com"),
            BriefMetadataItem(label="date", value="April 2026"),
        ],
    )


def test_component_builds_brief_from_evidence_package() -> None:
    component = ExecutiveBriefingComponent(templates_dir="templates")

    brief = component.build_brief(_sample_evidence_package())

    assert isinstance(brief, ExecutiveBrief)
    assert brief.title == "Algorithmic Surrender"
    assert brief.governing_insight == "Leaders are treating consensus as evidence."
    assert brief.key_findings
    assert brief.decision_implications


def test_component_renders_html_directly_from_evidence_package() -> None:
    component = ExecutiveBriefingComponent(templates_dir="templates")

    html = component.render_html(_sample_evidence_package())

    assert "Algorithmic Surrender" in html
    assert "Executive Summary" in html
    assert "Key Findings" in html


def test_component_accepts_prebuilt_executive_brief() -> None:
    component = ExecutiveBriefingComponent(templates_dir="templates")
    brief = component.build_brief(_sample_evidence_package())

    html = component.render_html(brief)

    assert "Algorithmic Surrender" in html
    assert "Governance discipline is lagging behind investment commitments." in html


def test_component_renders_pdf_with_fake_html_backend() -> None:
    calls: list[tuple[str, str]] = []

    class FakeHTML:
        def __init__(self, *, string: str, base_url: str) -> None:
            calls.append((string, base_url))

        def write_pdf(self) -> bytes:
            return b"%PDF-fake"

    component = ExecutiveBriefingComponent(
        templates_dir="templates",
        html_class=FakeHTML,
    )

    pdf_bytes = component.render_pdf(_sample_evidence_package())

    assert pdf_bytes == b"%PDF-fake"
    assert calls
    assert "Algorithmic Surrender" in calls[0][0]
