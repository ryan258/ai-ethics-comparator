"""Regression test for D-01: model output must never reach the DOM as markup.

`GET /api/runs/{id}` serves the raw run record -- including verbatim model
output in `responses[].raw` -- as an unescaped body. HTMX ignores Content-Type
and swaps with innerHTML by default, so the ONLY thing standing between a model
that emits `<img src=x onerror=...>` and script execution in the researcher's
browser is `hx-swap="textContent"` on the trigger.

That attribute is load-bearing security, not cosmetics. This test fails if it is
removed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PAYLOAD = '<img src=x onerror="alert(1)"><script>alert(2)</script>'


def _write_run(app, run_id: str = "escape-001") -> None:
    results_root = Path(app.state.services.storage.results_root)
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / f"{run_id}.json").write_text(
        json.dumps(
            {
                "runId": run_id,
                "modelName": "test/model",
                "paradoxId": "esc_para",
                "paradoxType": "trolley",
                "paradoxTitle": "Escaping Scenario",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "prompt": "P",
                "iterationCount": 1,
                "completedIterations": 1,
                "status": "completed",
                "options": [
                    {"id": 1, "label": "A", "description": "a"},
                    {"id": 2, "label": "B", "description": "b"},
                ],
                "responses": [
                    {
                        "iteration": 1,
                        "optionId": 1,
                        "decisionToken": "{1}",
                        "explanation": PAYLOAD,
                        "raw": PAYLOAD,
                    }
                ],
                "summary": {
                    "total": 1,
                    "options": [
                        {"id": 1, "count": 1, "percentage": 100.0},
                        {"id": 2, "count": 0, "percentage": 0.0},
                    ],
                    "undecided": {"count": 0, "percentage": 0.0},
                },
            }
        )
    )


def test_run_json_dump_uses_textcontent_swap(client) -> None:
    """The JSON-dump trigger must swap as text, never as parsed HTML."""
    _write_run(client.app)

    html = client.get("/").text
    triggers = re.findall(r"<summary\b[^>]*hx-get=\"/api/runs/[^\"]+\"[^>]*>", html)

    assert triggers, "expected a lazy-loading run JSON trigger in the page"
    for trigger in triggers:
        assert 'hx-swap="textContent"' in trigger, (
            "run JSON is unescaped model output; without hx-swap=\"textContent\" "
            f"HTMX parses it as HTML. Offending element: {trigger}"
        )


def test_run_json_endpoint_serves_payload_verbatim(client) -> None:
    """Document why the swap mode matters: the body really is unescaped."""
    _write_run(client.app)

    body = client.get("/api/runs/escape-001", headers={"HX-Request": "true"}).text

    # The endpoint does not escape -- that is by design for a text swap, and is
    # precisely why the template must not innerHTML it.
    assert PAYLOAD in json.loads(body)["responses"][0]["raw"]


def test_stored_model_output_is_escaped_in_rendered_card(client) -> None:
    """Model output rendered directly into the card must be escaped by Jinja."""
    _write_run(client.app)

    html = client.get("/").text

    assert "<script>alert(2)</script>" not in html
    assert 'onerror="alert(1)"' not in html
