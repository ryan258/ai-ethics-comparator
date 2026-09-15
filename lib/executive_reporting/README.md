# Executive reporting component

Framework-independent evidence composition and printable HTML rendering. Requires Pydantic and Jinja2. No server PDF engine or native runtime setup.

## Use

```python
from lib.executive_reporting import EvidencePackage, ExecutiveBriefingComponent

component = ExecutiveBriefingComponent(templates_dir="templates")
evidence = EvidencePackage(
    package_id="review-001", subject="Research review",
    governing_question="What does the saved evidence support?",
    governing_insight="Conclusions remain limited to the sampled conditions.",
)
html = component.render_html(evidence)
```

Return `html` as an HTML response or save it as a UTF-8 `.html` file. The report contains inline styles, print rules and browser controls for Print / Save as PDF and Download HTML. The file works offline.

## Contracts

- [models.py](models.py): `EvidencePackage` and `ExecutiveBrief`.
- [default_composer.py](default_composer.py): converts reusable evidence into a brief.
- [component.py](component.py): public composition and rendering entrypoint.
- [renderer.py](renderer.py): Jinja2 rendering through a presentation plugin.
- [engine.py](engine.py): typed report profiles and comparison HTML rendering.
- [plugins/strategic_analysis.py](plugins/strategic_analysis.py): strategic brief layout context.
- [adapters/ai_ethics.py](adapters/ai_ethics.py): domain mapping.

Rendering adapters may import presentation libraries; core evidence and measurement code must remain independent of HTTP. Inject template locations explicitly when reusing the package. Preserve autoescaping for all model-authored text. Only internally generated SVG chart strings may be marked safe.

## Verification

Test real outgoing HTML, escaped hostile input, source evidence mapping, print rules and portable export controls. Browser screen/print verification is separate from source checks. Missing templates raise a rendering error; there is no alternate document fallback.
