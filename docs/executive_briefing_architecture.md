# Executive Briefing Architecture

## Intent

This package reframes reporting around a brief-first pipeline:

1. `EvidencePackage`
2. `ExecutiveBriefComposer`
3. `ExecutiveBrief`
4. `ExecutiveBriefPlugin`
5. `ExecutiveBriefRenderer`

The goal is to separate:

- domain evidence and synthesis
- decision-ready narrative structure
- presentation style

That separation makes the system reusable without collapsing it into a generic "PDF export" utility.

## Core Contracts

### `EvidencePackage`

Normalized evidence for a project or analysis run.

Use it to hold:

- summary metrics
- observations
- evidence tables
- excerpts
- methodology notes
- limitations
- sources
- audit records

### `ExecutiveBriefComposer`

Domain-specific logic that converts evidence into a decision-ready brief.

This is where a project decides:

- what the headline is
- which findings matter
- how confidence should be expressed
- what recommendations follow

### `ExecutiveBrief`

Presentation-neutral decision document.

It holds:

- title and subtitle
- governing question and governing insight
- executive summary paragraphs
- top metrics
- key findings
- decision implications
- recommendations
- method, limitations, and sources
- audit appendix material

### `ExecutiveBriefPlugin`

Presentation plugin that turns an `ExecutiveBrief` into a template context.

This is the reusable style layer for other projects.

It should define:

- `plugin_id`
- `display_name`
- `template_name`
- `build_context(brief)`

### `ExecutiveBriefRenderer`

Renderer that applies a plugin to a brief and emits HTML or PDF.

The renderer owns:

- Jinja template loading
- context rendering
- optional WeasyPrint PDF generation

## Strategic Analysis Plugin

`StrategicAnalysisPlugin` is the first reusable presentation plugin.

It encodes the answer-first consulting format:

- sparse cover page
- executive summary with governing insight
- key findings section
- recommendation table
- method, limitations, and sources
- audit appendix

Use it when the target deliverable is a strategic memo or executive briefing rather than a raw technical report.

## Drop-In Component

The package now exposes a single public entrypoint for other projects:

1. hand it an `EvidencePackage`
2. let the default `EvidencePackageComposer` build an `ExecutiveBrief`
3. render through a presentation plugin such as `StrategicAnalysisPlugin`

That means other repos do not need `SingleRunReport`, `ReportGenerator`, or any of the AI-ethics-specific reporting code in this project.

## Current Migration Strategy

The existing AI ethics PDF system remains in place.

The new package is intentionally parallel to the current routes so we can migrate in stages:

1. build reusable brief contracts
2. prove the style plugin
3. add domain adapters from current report contexts into `ExecutiveBrief`
4. switch current report routes to render through the new brief-first path

## How Another Project Would Use It

1. Normalize project outputs into an `EvidencePackage`.
2. Instantiate `ExecutiveBriefingComponent`.
3. Render HTML or PDF directly from the evidence package.
4. Optionally swap in a custom composer or plugin when a project needs domain-specific synthesis or presentation.

## Example

```python
from lib.executive_reporting import EvidencePackage, ExecutiveBriefingComponent

evidence = EvidencePackage(
    package_id="brief-001",
    subject="Algorithmic Surrender",
    governing_question="Why are teams scaling AI spend faster than measured returns?",
    governing_insight="Decision-makers are rewarding momentum before evidence.",
)

component = ExecutiveBriefingComponent(templates_dir="templates")

brief = component.build_brief(evidence)
html = component.render_html(evidence)
pdf_bytes = component.render_pdf(evidence)
```

For richer domains, replace the default composer:

```python
from lib.executive_reporting import ExecutiveBriefingComponent

component = ExecutiveBriefingComponent(
    composer=MyDomainComposer(),
    templates_dir="templates",
)
```

## Boundary Rules

- composers own judgment and domain logic
- plugins own style and document shape
- renderers own output mechanics
- evidence packages should not contain presentation copy
- raw logs belong in the audit appendix, not the executive brief body
