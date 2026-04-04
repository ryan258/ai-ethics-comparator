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

## Current Migration Strategy

The existing AI ethics PDF system remains in place.

The new package is intentionally parallel to the current routes so we can migrate in stages:

1. build reusable brief contracts
2. prove the style plugin
3. add domain adapters from current report contexts into `ExecutiveBrief`
4. switch current report routes to render through the new brief-first path

## How Another Project Would Use It

1. Normalize project outputs into an `EvidencePackage`.
2. Implement an `ExecutiveBriefComposer` for that domain.
3. Compose an `ExecutiveBrief`.
4. Choose a plugin such as `StrategicAnalysisPlugin`.
5. Render with `ExecutiveBriefRenderer`.

## Example

```python
from lib.executive_reporting import ExecutiveBriefRenderer, StrategicAnalysisPlugin

plugin = StrategicAnalysisPlugin(
    organization="Cyborg Labs",
    publication_label="ryanleej.com",
)
renderer = ExecutiveBriefRenderer(plugin, templates_dir="templates")

html = renderer.render_html(brief)
pdf_bytes = renderer.render_pdf(brief)
```

## Boundary Rules

- composers own judgment and domain logic
- plugins own style and document shape
- renderers own output mechanics
- evidence packages should not contain presentation copy
- raw logs belong in the audit appendix, not the executive brief body
