# Executive Reporting

`lib/executive_reporting` is a reusable executive-briefing package.

It is designed for projects that have evidence, findings, excerpts, and metrics, but do not want to hand-write a polished decision memo every time. The package takes normalized evidence, composes an executive brief, and renders that brief through a presentation plugin.

The current default output is a consulting-style strategic brief.

## What You Get

- A typed evidence contract: `EvidencePackage`
- A presentation-neutral brief model: `ExecutiveBrief`
- A default composer for generic evidence: `EvidencePackageComposer`
- A one-object drop-in entrypoint: `ExecutiveBriefingComponent`
- A reusable presentation plugin: `StrategicAnalysisPlugin`
- HTML rendering via Jinja2
- PDF rendering via WeasyPrint when available

This package is meant to be reused without inheriting the AI-ethics-specific reporting system in the rest of this repo.

## The Core Flow

The package works in four layers:

1. `EvidencePackage`
2. `ExecutiveBriefComposer`
3. `ExecutiveBrief`
4. `ExecutiveBriefPlugin` + `ExecutiveBriefRenderer`

The shortest path is:

```python
from lib.executive_reporting import EvidencePackage, ExecutiveBriefingComponent

evidence = EvidencePackage(
    package_id="brief-001",
    subject="Algorithmic Surrender",
    governing_question="Why are organizations scaling AI before proving value?",
    governing_insight="Leadership is treating consensus as evidence.",
)

component = ExecutiveBriefingComponent(templates_dir="templates")

brief = component.build_brief(evidence)
html = component.render_html(evidence)
pdf_bytes = component.render_pdf(evidence)
```

If you already have a composed `ExecutiveBrief`, you can pass that directly:

```python
html = component.render_html(brief)
pdf_bytes = component.render_pdf(brief)
```

## Files To Copy Into A New Project

At minimum, copy:

- [__init__.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/__init__.py)
- [models.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/models.py)
- [composer.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/composer.py)
- [default_composer.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/default_composer.py)
- [component.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/component.py)
- [renderer.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/renderer.py)
- [weasyprint_runtime.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/weasyprint_runtime.py)
- [plugins/base.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/plugins/base.py)
- [plugins/strategic_analysis.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/plugins/strategic_analysis.py)
- [strategic_analysis_brief.html](/Users/ryanjohnson/Projects/ai-ethics-comparator/templates/reports/strategic_analysis_brief.html)

Optional:

- [adapters/](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/adapters) if you want to adapt an existing domain-specific report model into `ExecutiveBrief`
- [engine.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/engine.py) if you want the older profile-driven report engine that this repo still uses in parallel
- [examples/mckinsey_style_brief_blueprint.html](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/examples/mckinsey_style_brief_blueprint.html) if you want a commented example template that shows how to structure an answer-first consulting brief

## Python Dependencies

The reusable package relies on:

- `pydantic`
- `jinja2`
- `weasyprint` for PDF output

If you only need `render_html`, you do not need WeasyPrint at runtime.

This repo currently uses `uv`, so in a new project the cleanest path is to add those dependencies to `pyproject.toml` and keep the environment under `uv sync`.

## Template Requirements

The default plugin expects:

- a Jinja2 templates root
- the strategic template at `templates/reports/strategic_analysis_brief.html`

If you keep the same path layout, this works:

```python
component = ExecutiveBriefingComponent(templates_dir="templates")
```

If you move the template, either:

- point `templates_dir` at the new root, or
- create your own plugin with a different `template_name`

## Template Blueprint

If you want to build your own consulting-style template, start from:

- [mckinsey_style_brief_blueprint.html](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/examples/mckinsey_style_brief_blueprint.html)

That file is intentionally commented section by section. It shows:

- how to structure the cover
- how to make the executive summary answer-first
- how to lay out findings as claim / evidence / implication
- how to keep recommendations action-oriented
- how to treat the appendix as factual reference material

The blueprint assumes the same `report` context shape used by `StrategicAnalysisPlugin`. The easiest path for a new project is:

1. copy the blueprint into your own `templates/reports/` directory
2. rename it for your project
3. keep the same context field names at first
4. once it renders correctly, decide whether you need a custom plugin context

If you want to start from the existing live implementation instead of the commented blueprint, copy:

- [strategic_analysis_brief.html](/Users/ryanjohnson/Projects/ai-ethics-comparator/templates/reports/strategic_analysis_brief.html)

## Data Contract

### `EvidencePackage`

This is the input contract for new projects.

Important fields:

- `subject`: document title / report topic
- `governing_question`: the core question the brief answers
- `governing_insight`: the top-line conclusion
- `summary_metrics`: headline metrics for the cover/summary section
- `observations`: structured findings with evidence and significance
- `evidence_tables`: optional tabular evidence
- `excerpts`: quotes or raw-output excerpts
- `methodology`, `limitations`, `sources`: back-matter inputs
- `metadata`: optional labels like `organization`, `publication`, `date`, `headline`, `subtitle`

Example:

```python
from lib.executive_reporting import (
    BriefMetadataItem,
    EvidenceMetric,
    EvidenceObservation,
    EvidencePackage,
    EvidenceQuote,
)

evidence = EvidencePackage(
    package_id="brief-001",
    subject="Algorithmic Surrender",
    governing_question="Why is AI investment outpacing measured returns?",
    governing_insight="Decision-makers are rewarding momentum before evidence.",
    summary_metrics=[
        EvidenceMetric(label="Programs missing targets", value="70-85%", source="Industry surveys"),
        EvidenceMetric(label="Pilots with measured ROI", value="23%", source="McKinsey"),
    ],
    observations=[
        EvidenceObservation(
            title="Investment intent outpaces proof",
            summary="Organizations are increasing spend despite weak evidence of operational returns.",
            evidence_points=[
                "Most enterprise programs miss expected outcomes.",
                "Only a minority of operators report reliable ROI measurement.",
            ],
            significance="Governance discipline is lagging behind investment commitments.",
            confidence="high",
        ),
    ],
    excerpts=[
        EvidenceQuote(
            title="Representative quote",
            text="We decided to use LLMs before deciding what problem they would solve.",
        ),
    ],
    methodology=["Synthesis of survey evidence, public reporting, and analyst review."],
    limitations=["Underlying studies use different samples and success definitions."],
    sources=["McKinsey State of AI", "Industry survey synthesis"],
    metadata=[
        BriefMetadataItem(label="organization", value="Cyborg Labs"),
        BriefMetadataItem(label="publication", value="ryanleej.com"),
        BriefMetadataItem(label="date", value="April 2026"),
    ],
)
```

## Default Behavior

`EvidencePackageComposer` is the default generic composer.

It does the following:

- uses `subject` as the title
- uses `governing_insight` as the default headline
- builds up to three summary paragraphs
- promotes top metrics into the brief
- turns observations into key findings
- falls back to evidence tables if observations are sparse
- derives decision implications from observation and excerpt significance

This is good enough for many projects, but it is intentionally generic.

If your project has domain-specific reasoning, use a custom composer.

## Drop-In Integration Checklist

If you are moving this into a new repo, do this in order:

1. Copy the package files listed above.
2. Copy the strategic template.
3. Add `pydantic`, `jinja2`, and optionally `weasyprint` to `pyproject.toml`.
4. Normalize your project outputs into `EvidencePackage`.
5. Instantiate `ExecutiveBriefingComponent`.
6. Call `render_html()` first.
7. Only after HTML looks right, enable `render_pdf()`.

That sequence keeps the integration surface small and avoids debugging PDF/runtime issues before your content mapping is correct.

## Rendering HTML

HTML is the easiest way to validate a new integration.

```python
component = ExecutiveBriefingComponent(templates_dir="templates")
html = component.render_html(evidence)
```

Use this when:

- you want to preview the layout
- you are building a web view
- you do not want to install WeasyPrint yet

## Rendering PDF

PDF output uses WeasyPrint through [renderer.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/renderer.py).

```python
pdf_bytes = component.render_pdf(evidence)
```

If WeasyPrint is not available, `render_pdf()` raises.

The package includes [weasyprint_runtime.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/weasyprint_runtime.py), which helps macOS find Homebrew-installed native libraries.

### macOS Notes

If PDF rendering fails on macOS, install the native libs first:

```sh
brew install cairo pango gdk-pixbuf libffi
```

On Apple Silicon, this environment variable is the important one:

```sh
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}
```

If you only care about HTML output, skip all of this.

## Customizing The Composer

If your project already has strong domain logic, replace the default composer.

Your custom class should subclass `ExecutiveBriefComposer` and return an `ExecutiveBrief`.

```python
from lib.executive_reporting import ExecutiveBriefComposer, ExecutiveBriefingComponent, ExecutiveBrief


class IncidentReviewComposer(ExecutiveBriefComposer):
    def compose(self, evidence) -> ExecutiveBrief:
        return ExecutiveBrief(
            title=evidence.subject,
            governing_insight="The system failed because detection thresholds lagged attack velocity.",
            executive_summary=[
                "The incident response system detected the attack too late.",
                "The root cause was monitoring design, not analyst execution.",
            ],
        )


component = ExecutiveBriefingComponent(
    composer=IncidentReviewComposer(),
    templates_dir="templates",
)
```

Use a custom composer when:

- your brief has non-generic recommendation logic
- your findings need domain-specific prioritization
- your confidence language is not generic `high/medium/low/directional`
- your appendix should carry project-specific reference material

## Customizing The Presentation Plugin

The strategic brief is only one presentation layer.

If another project wants:

- a board memo
- an internal risk review
- a policy appendix
- a branded client deliverable

create a new plugin instead of overloading the current template.

The plugin contract lives in [plugins/base.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/plugins/base.py).

You provide:

- `plugin_id`
- `display_name`
- `template_name`
- `build_context(brief)`

Then wire it in:

```python
component = ExecutiveBriefingComponent(
    composer=MyComposer(),
    plugin=MyPlugin(),
    templates_dir="templates",
)
```

## Appendix Strategy

The package supports two different appendix ideas:

- generic evidence excerpts through `EvidencePackage.excerpts`
- richer reference material through `ExecutiveBrief.appendix_reference_text` and `appendix_reference_table`

The strategic brief currently renders:

- `Scenario`
- `Decision Options`
- `Raw Responses`

If your project needs a different appendix structure, change the plugin and template, not the base evidence contract.

## Structured Raw Excerpts

The strategic plugin detects JSON-looking raw excerpts and pretty-prints them for readability.

That means you can store verbatim raw model output in `EvidenceQuote.text`, and the template will render:

- JSON as formatted code blocks
- everything else as normal prose

The underlying stored evidence is not modified.

## Testing A New Integration

The safest way to integrate this into a new repo is to add three tests immediately:

1. `EvidencePackage -> ExecutiveBrief`
2. `render_html()` from a sample package
3. `render_pdf()` with a fake HTML backend

This repo already follows that pattern in:

- [test_executive_component.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/tests/test_executive_component.py)
- [test_executive_briefing.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/tests/test_executive_briefing.py)

For PDF tests, inject a fake `html_class` so the test does not require native WeasyPrint:

```python
class FakeHTML:
    def __init__(self, *, string: str, base_url: str) -> None:
        self.string = string
        self.base_url = base_url

    def write_pdf(self) -> bytes:
        return b"%PDF-fake"


component = ExecutiveBriefingComponent(
    templates_dir="templates",
    html_class=FakeHTML,
)
```

## What Is Not Part Of The Drop-In Surface

These are project-specific and should not be copied unless you need them:

- the AI-ethics adapter in [adapters/ai_ethics.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/executive_reporting/adapters/ai_ethics.py)
- the legacy report engine in [lib/reporting.py](/Users/ryanjohnson/Projects/ai-ethics-comparator/lib/reporting.py)
- the old profile-based `ExecutiveReportEngine` unless you are intentionally using that older route

For a clean integration, start from:

- `EvidencePackage`
- `ExecutiveBriefingComponent`
- `StrategicAnalysisPlugin`

## Recommended Copy Strategy

If you are vendoring this into a new repo rather than packaging it formally, copy the package in this order:

1. `models.py`
2. `composer.py`
3. `default_composer.py`
4. `plugins/base.py`
5. `plugins/strategic_analysis.py`
6. `renderer.py`
7. `weasyprint_runtime.py`
8. `component.py`
9. the template file
10. `__init__.py`

That keeps import dependencies straightforward.

## Common Failure Modes

### `render_html()` fails with template not found

Cause:

- wrong `templates_dir`
- template file not copied
- custom plugin points at the wrong `template_name`

Fix:

- confirm `templates/reports/strategic_analysis_brief.html` exists
- pass the correct `templates_dir`

### `render_pdf()` fails on macOS

Cause:

- WeasyPrint native dependencies missing
- shell cannot find Homebrew libraries

Fix:

- install `cairo`, `pango`, `gdk-pixbuf`, `libffi`
- set `DYLD_FALLBACK_LIBRARY_PATH`

### Output feels generic

Cause:

- using `EvidencePackageComposer` for a domain that needs strong editorial judgment

Fix:

- write a custom composer

### Appendix is wrong for the project

Cause:

- relying on the default strategic plugin for a project with different reference needs

Fix:

- write a custom plugin and template

## Design Rules

When extending this package, keep these boundaries intact:

- evidence models should stay presentation-neutral
- composers should own judgment
- plugins should own appearance and appendix shape
- renderers should own Jinja2/WeasyPrint mechanics
- raw evidence should stay verbatim; formatting belongs in the plugin/template layer

## Current Status In This Repo

In this repo, the package is now genuinely reusable, but the app still also contains legacy reporting code in parallel. The AI-ethics-specific adapter exists as a bridge from the old `SingleRunReport` model into the new executive-brief layer.

For a new project, you do not need that bridge unless you already have an intermediate report model of your own.
