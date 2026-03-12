"""
Native PDF renderer.
Provides a pure-Python fallback report generator when HTML-to-PDF engines
are unavailable on the host system.
"""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pydyf
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    pydyf = None  # type: ignore[assignment]


from lib.pdf_charts import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    draw_donut_native,
    draw_heatmap_native,
    draw_sparkline_native,
)


def pdf_available() -> bool:
    """Return True when the native PDF backend is importable."""
    return pydyf is not None


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(round(int(value[i : i + 2], 16) / 255, 4) for i in (0, 2, 4))


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "\u00a0": " ",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.encode("latin-1", "replace").decode("latin-1").strip()


class NativePdfReportRenderer:
    """Render a polished multi-page PDF report using pydyf primitives."""

    PAGE_WIDTH = 595.0
    PAGE_HEIGHT = 842.0
    MARGIN_X = 42.0
    TOP_MARGIN = 52.0
    BOTTOM_MARGIN = 36.0
    FOOTER_HEIGHT = 24.0
    CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)

    def __init__(self, report: Dict[str, Any], *, theme: str = "dark") -> None:
        if pydyf is None:
            raise RuntimeError("pydyf is required for native PDF rendering.")

        self.report = report
        self.palette = PALETTE_LIGHT if theme == "light" else PALETTE_DARK
        self.pdf = pydyf.PDF()
        self.page_number = 0
        self.current_page: Optional[pydyf.Stream] = None
        self.current_y = self.TOP_MARGIN
        self.current_section = ""
        self.section_pages: List[Tuple[str, int]] = []
        self.font_refs = self._register_fonts()

    def render(self) -> bytes:
        """Render the report to PDF bytes."""
        page_methods: List[Tuple[str, Any]] = [("Cover", self._draw_cover_page)]
        if isinstance(self.report.get("narrative"), dict):
            page_methods.append(("Interpretive Synthesis", self._draw_narrative))
        page_methods.append(("Choice Distribution", self._draw_briefing_page))
        if self.report.get("responses"):
            page_methods.append(("Response Ledger", self._draw_responses))
        if isinstance(self.report.get("analysis"), dict):
            page_methods.append(("Analyst Assessment", self._draw_analysis))

        for section_name, method in page_methods:
            self.current_section = section_name
            self.section_pages.append((section_name, self.page_number + 1))
            self._start_page()
            method()
            self._finalize_page()

        output = io.BytesIO()
        self.pdf.write(output, compress=False)
        return output.getvalue()

    def _register_fonts(self) -> Dict[str, bytes]:
        fonts = {
            "Display": "Helvetica-Bold",
            "BodyBold": "Helvetica-Bold",
            "Body": "Helvetica",
            "BodyItalic": "Helvetica-Oblique",
            "Mono": "Courier",
        }
        registered: Dict[str, bytes] = {}
        for alias, base_font in fonts.items():
            font = pydyf.Dictionary(
                {
                    "Type": "/Font",
                    "Subtype": "/Type1",
                    "BaseFont": f"/{base_font}",
                }
            )
            self.pdf.add_object(font)
            registered[alias] = font.reference
        return registered

    def _resources(self) -> "pydyf.Dictionary":
        assert pydyf is not None
        return pydyf.Dictionary(
            {
                "Font": pydyf.Dictionary(
                    {alias: reference for alias, reference in self.font_refs.items()}
                )
            }
        )

    def _start_page(self) -> None:
        assert pydyf is not None
        self.page_number += 1
        self.current_page = pydyf.Stream(compress=False)
        self.current_y = self.TOP_MARGIN

        self._fill_rect(0, 0, self.PAGE_WIDTH, self.PAGE_HEIGHT, self.palette["bg"])

    def _finalize_page(self) -> None:
        assert pydyf is not None
        if self.current_page is None:
            return

        footer_y = self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 4
        self._draw_line(
            self.MARGIN_X, footer_y,
            self.PAGE_WIDTH - self.MARGIN_X, footer_y,
            self.palette["accent"], width=0.3,
        )
        footer_text_y = self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 10
        self._draw_text(
            "AI Ethics Comparator",
            self.MARGIN_X, footer_text_y,
            font="Body", size=6, color=self.palette["accent"],
        )
        if self.current_section:
            self._draw_text(
                f"  |  {self.current_section}",
                self.MARGIN_X + 72, footer_text_y,
                font="Body", size=6, color=self.palette["accent"],
            )
        self._draw_text(
            self.report.get("run_id", "unknown"),
            self.MARGIN_X + 210, footer_text_y,
            font="Mono", size=6, color=self.palette["accent"],
        )
        self._draw_text(
            f"Page {self.page_number}",
            self.PAGE_WIDTH - self.MARGIN_X - 30, footer_text_y,
            font="Body", size=6, color=self.palette["accent"],
        )

        page_stream = self.current_page
        self.pdf.add_object(page_stream)
        page = pydyf.Dictionary(
            {
                "Type": "/Page",
                "Parent": self.pdf.pages.reference,
                "MediaBox": pydyf.Array([0, 0, self.PAGE_WIDTH, self.PAGE_HEIGHT]),
                "Contents": page_stream.reference,
                "Resources": self._resources(),
            }
        )
        self.pdf.add_page(page)
        self.current_page = None

    def _remaining_height(self) -> float:
        usable_bottom = self.PAGE_HEIGHT - self.BOTTOM_MARGIN - self.FOOTER_HEIGHT
        return usable_bottom - self.current_y

    def _new_page_if_needed(self, needed_height: float) -> None:
        if needed_height <= self._remaining_height():
            return
        self._finalize_page()
        self._start_page()

    def _draw_cover_page(self) -> None:
        # ── Accent bar + kicker ──
        self._fill_rect(self.MARGIN_X, self.current_y, 90, 2.5, self.palette["accent"])
        self.current_y += 10
        self._draw_text(
            "AI ETHICS COMPARATOR  —  EXECUTIVE BRIEF",
            self.MARGIN_X,
            self.current_y,
            font="BodyBold",
            size=7,
            color=self.palette["accent"],
        )
        self.current_y += 20

        # ── Title ──
        self._draw_text(
            "Ethical Decision",
            self.MARGIN_X,
            self.current_y,
            font="Display",
            size=30,
            color=self.palette["text"],
        )
        self.current_y += 34
        self._draw_text(
            "Report",
            self.MARGIN_X,
            self.current_y,
            font="Display",
            size=30,
            color=self.palette["text"],
        )
        self.current_y += 42

        # ── Paradox title ──
        paradox_title = _clean_text(self.report.get("paradox_title", "Unknown paradox"))
        title_height = self._draw_text_block(
            paradox_title,
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH * 0.85,
            font="BodyBold",
            size=15,
            color=self.palette["success"],
            leading=1.2,
        )
        self.current_y += max(22.0, title_height + 6)

        # ── Category | Date ──
        subtitle = (
            f"{self.report.get('category', 'Uncategorized')}  |  "
            f"{self.report.get('generated_at_label', 'Unknown')}"
        )
        self._draw_text(subtitle, self.MARGIN_X, self.current_y, font="Body", size=9, color=self.palette["accent"])
        self.current_y += 18

        # ── Rule ──
        self._draw_line(self.MARGIN_X, self.current_y, self.PAGE_WIDTH - self.MARGIN_X, self.current_y, self.palette["accent"], width=0.6)
        self.current_y += 14

        # ── Key Finding ──
        self._draw_text("KEY FINDING", self.MARGIN_X, self.current_y, font="BodyBold", size=7, color=self.palette["accent"])
        self.current_y += 14
        lead_label = _clean_text(self.report.get("lead_choice_label", "No dominant choice"))
        lead_height = self._draw_text_block(
            lead_label, self.MARGIN_X, self.current_y, self.CONTENT_WIDTH * 0.8,
            font="BodyBold", size=19, color=self.palette["text"], leading=1.12,
        )
        self.current_y += max(24.0, lead_height + 4)
        self._draw_text(
            _clean_text(self.report.get("lead_choice_support", "")),
            self.MARGIN_X, self.current_y,
            font="BodyBold", size=10, color=self.palette["success"],
        )
        self.current_y += 18

        # ── Executive prose ──
        narrative = self.report.get("narrative")
        prose = ""
        if isinstance(narrative, dict) and narrative.get("executive_narrative"):
            prose = narrative["executive_narrative"]
        else:
            prose = self.report.get("executive_summary", "")
        self._draw_flowing_text(
            prose, self.CONTENT_WIDTH * 0.88,
            font="Body", size=10, color=self.palette["text"], leading=1.65,
            max_height=120.0,
        )
        self.current_y += 4

        # ── Rule ──
        self._draw_line(self.MARGIN_X, self.current_y, self.PAGE_WIDTH - self.MARGIN_X, self.current_y, self.palette["accent"], width=0.4)
        self.current_y += 12

        # ── Stat strip (no boxes — just aligned columns) ──
        self._draw_cover_stats()

        # ── Rule ──
        self._draw_line(self.MARGIN_X, self.current_y, self.PAGE_WIDTH - self.MARGIN_X, self.current_y, self.palette["accent"], width=0.4)
        self.current_y += 10

        # ── Metadata strip ──
        self._draw_cover_metadata()

    def _draw_cover_stats(self) -> None:
        col_width = self.CONTENT_WIDTH / 4
        has_narrative = isinstance(self.report.get("narrative"), dict) and any(
            self.report["narrative"].get(k) for k in ("executive_narrative", "response_arc", "implications", "scenario_commentary")
        )
        has_analysis = isinstance(self.report.get("analysis"), dict)
        if has_narrative:
            synth_val = "Narrative"
        elif has_analysis:
            synth_val = "Analysis"
        else:
            synth_val = "Pending"

        stats = [
            (str(self.report.get("response_count", 0)), "RESPONSES"),
            (self.report.get("mean_latency_label", "n/a"), "MEAN LATENCY"),
            (self.report.get("token_volume_label", "n/a"), "TOKEN VOLUME"),
            (synth_val, "SYNTHESIS"),
        ]
        for idx, (value, label) in enumerate(stats):
            x = self.MARGIN_X + (idx * col_width) + (4 if idx else 0)
            self._draw_text(_clean_text(value), x, self.current_y, font="BodyBold", size=15, color=self.palette["text"])
            self._draw_text(label, x, self.current_y + 18, font="BodyBold", size=6, color=self.palette["accent"])
            # Vertical separator between columns
            if idx < 3:
                sep_x = self.MARGIN_X + ((idx + 1) * col_width) - 2
                self._draw_line(sep_x, self.current_y - 2, sep_x, self.current_y + 28, self.palette["accent"], width=0.3)
        self.current_y += 36

    def _draw_cover_metadata(self) -> None:
        metadata = [
            ("RUN ID", self.report.get("run_id", "unknown"), "Mono"),
            ("MODEL", self.report.get("model_name", "unknown"), "Body"),
            ("PROMPT HASH", self.report.get("prompt_hash_short", "n/a"), "Mono"),
            ("ANALYST", self.report.get("analyst_model", "Not generated"), "Body"),
        ]
        col_width = self.CONTENT_WIDTH / 4
        for idx, (label, value, font) in enumerate(metadata):
            x = self.MARGIN_X + (idx * col_width) + (4 if idx else 0)
            self._draw_text(label, x, self.current_y, font="BodyBold", size=6, color=self.palette["accent"])
            self._draw_text_block(
                _clean_text(value), x, self.current_y + 10, col_width - 10,
                font=font, size=8, color=self.palette["text"], leading=1.2, max_lines=1,
            )
        self.current_y += 26

    def _draw_narrative(self) -> None:
        """Draw the AI-generated narrative synthesis page."""
        narrative = self.report.get("narrative")
        if not isinstance(narrative, dict):
            return

        self._section_heading("Interpretive Synthesis", "AI-generated analysis of findings and implications.")

        sections = [
            ("Executive Narrative", narrative.get("executive_narrative", ""), self.palette["success"]),
            ("Response Arc", narrative.get("response_arc", ""), None),
            ("Scenario Commentary", narrative.get("scenario_commentary", ""), None),
            ("Cross-Iteration Patterns", narrative.get("cross_iteration_patterns", ""), None),
            ("Framework Diagnosis", narrative.get("framework_diagnosis", ""), self.palette["accent"]),
            ("Deployment Implications", narrative.get("implications", ""), self.palette["danger"]),
        ]

        for title, text, accent in sections:
            text = _clean_text(text)
            if not text:
                continue
            prose_width = self.CONTENT_WIDTH - 14 if accent else self.CONTENT_WIDTH
            prose_x = self.MARGIN_X + 14 if accent else self.MARGIN_X
            lines = self._wrap_text(text, prose_width, font="Body", size=10)
            block_height = (len(lines) * 15.5) + 22
            self._new_page_if_needed(block_height + 14)

            # Section label
            self._draw_text(
                title.upper(), prose_x, self.current_y,
                font="BodyBold", size=7, color=self.palette["accent"],
            )
            self.current_y += 14

            # Left accent bar (thin, only for accented sections)
            if accent:
                bar_top = self.current_y
                bar_height = len(lines) * 15.5
                self._fill_rect(self.MARGIN_X, bar_top, 2.5, bar_height, accent)

            # Prose body
            self._draw_wrapped_lines(
                lines, prose_x, self.current_y,
                font="Body", size=10, color=self.palette["text"], leading=1.55,
            )
            self.current_y += (len(lines) * 15.5) + 18

    def _draw_briefing_page(self) -> None:
        self._section_heading("Choice Distribution", "Vote share across all iterations.")
        self._draw_distribution_section()
        self.current_y += 6
        self._draw_visual_dashboard()
        self.current_y += 10
        self._section_heading("Scenario Brief", "Context excerpt from the evaluated prompt.")
        self._draw_scenario_section()

    def _draw_distribution_section(self) -> None:
        option_stats = self.report.get("option_stats", [])

        for option in option_stats:
            self._new_page_if_needed(58)
            is_leader = bool(option.get("is_leader"))

            # Option name + score on same line
            token_label = f"{option['token']}  {option['label']}"
            self._draw_text(
                token_label, self.MARGIN_X, self.current_y,
                font="BodyBold", size=10, color=self.palette["text"],
            )
            self._draw_text(
                f"{option['count']} ({option['percentage_label']})",
                self.PAGE_WIDTH - self.MARGIN_X - 88, self.current_y,
                font="BodyBold", size=10,
                color=self.palette["success"] if is_leader else self.palette["text"],
            )
            self.current_y += 16

            # Thin bar (no border, just filled track)
            bar_width = self.CONTENT_WIDTH
            self._fill_rect(self.MARGIN_X, self.current_y, bar_width, 5, self.palette.get("bg_raised", "#1a1a1a"))
            fill_width = bar_width * (float(option["percentage"]) / 100.0)
            if fill_width > 0:
                self._fill_rect(
                    self.MARGIN_X, self.current_y,
                    max(3.0, fill_width), 5,
                    self.palette["success"] if is_leader else self.palette["accent"],
                )
            self.current_y += 9

            # Description
            self._draw_text_block(
                option["description"], self.MARGIN_X, self.current_y,
                self.CONTENT_WIDTH, font="Body", size=8,
                color=self.palette["accent"], leading=1.35, max_lines=2,
            )
            self.current_y += 24

        undecided_count = int(self.report.get("undecided_count", 0) or 0)
        if undecided_count:
            self._draw_text(
                f"Undecided: {undecided_count} ({self.report.get('undecided_percentage_label', '0.0%')})",
                self.MARGIN_X, self.current_y,
                font="BodyBold", size=9, color=self.palette["danger"],
            )
            self.current_y += 20

    def _draw_visual_dashboard(self) -> None:
        """Draw Phase 1 charts: donut, sparkline, heatmap."""
        donut_data = self.report.get("donut_data", [])
        latency_series = self.report.get("latency_series", [])
        decision_seq = self.report.get("decision_sequence", [])
        option_ids = self.report.get("chart_option_ids", [])

        has_donut = any(d.get("value", 0) for d in donut_data)
        has_spark = len(latency_series) >= 2
        has_heat = bool(decision_seq) and bool(option_ids)

        if not (has_donut or has_spark or has_heat):
            return

        # ── Row 1: Donut (left) + Sparkline (right) ──
        row_height = 130.0
        self._new_page_if_needed(row_height + 80)

        self._draw_line(
            self.MARGIN_X, self.current_y,
            self.PAGE_WIDTH - self.MARGIN_X, self.current_y,
            self.palette["accent"], width=0.3,
        )
        self.current_y += 8

        # Pattern badge (Phase 5)
        pattern = self.report.get("run_pattern", "")
        if pattern:
            self._draw_pattern_badge(pattern)

        row_top = self.current_y

        if has_donut:
            donut_cx = self.MARGIN_X + 85
            donut_cy = row_top + 62
            assert self.current_page is not None
            draw_donut_native(
                self.current_page, self.PAGE_HEIGHT,
                donut_cx, donut_cy, donut_data, self.palette,
                outer_r=56.0, inner_r=34.0,
            )
            # Center label
            self._draw_text(
                str(self.report.get("response_count", 0)),
                donut_cx - 10, donut_cy - 4,
                font="BodyBold", size=18, color=self.palette["text"],
            )
            self._draw_text(
                "TOTAL", donut_cx - 10, donut_cy + 14,
                font="BodyBold", size=6, color=self.palette["accent"],
            )

        if has_spark:
            spark_x = self.MARGIN_X + self.CONTENT_WIDTH * 0.42
            spark_y = row_top + 10
            spark_w = self.CONTENT_WIDTH * 0.56
            self._draw_text(
                "LATENCY PROFILE", spark_x, spark_y,
                font="BodyBold", size=7, color=self.palette["accent"],
            )
            assert self.current_page is not None
            draw_sparkline_native(
                self.current_page, self.PAGE_HEIGHT,
                spark_x, spark_y + 14, latency_series, self.palette,
                width=spark_w, height=44.0,
            )
            # Min/max labels
            lo, hi = min(latency_series), max(latency_series)
            self._draw_text(
                f"{hi:.1f}s", spark_x + spark_w + 4, spark_y + 14,
                font="Mono", size=6, color=self.palette["accent"],
            )
            self._draw_text(
                f"{lo:.1f}s", spark_x + spark_w + 4, spark_y + 52,
                font="Mono", size=6, color=self.palette["accent"],
            )

        self.current_y = row_top + row_height

        # ── Row 2: Heatmap ──
        if has_heat:
            self._draw_text(
                "DECISION PATTERN", self.MARGIN_X, self.current_y,
                font="BodyBold", size=7, color=self.palette["accent"],
            )
            self.current_y += 12
            assert self.current_page is not None
            tw, th = draw_heatmap_native(
                self.current_page, self.PAGE_HEIGHT,
                self.MARGIN_X, self.current_y,
                decision_seq, option_ids, self.palette,
            )
            # Row labels
            for row, oid in enumerate(option_ids[:25]):
                label_y = self.current_y + 12 + row * 15 + 3
                self._draw_text(
                    f"{{{oid}}}", self.MARGIN_X, label_y,
                    font="Mono", size=7, color=self.palette["accent"],
                )
            self.current_y += th + 8

    def _draw_pattern_badge(self, pattern: str) -> None:
        """Draw a coloured pattern classification badge (Phase 5)."""
        badge_colors = {
            "unanimous": self.palette["success"],
            "dominant": self.palette["success"],
            "contested": self.palette["danger"],
            "split": "#C9A0DC",
            "ambiguous": self.palette["accent"],
        }
        color = badge_colors.get(pattern, self.palette["accent"])
        label = pattern.upper()
        badge_w = self._estimate_text_width(label, font="BodyBold", size=7) + 12
        badge_h = 14

        self._fill_rect(self.MARGIN_X, self.current_y, badge_w, badge_h, color)
        # Draw text in contrasting colour
        text_color = self.palette["bg"] if pattern in ("unanimous", "dominant", "contested") else self.palette["text"]
        self._draw_text(
            label, self.MARGIN_X + 6, self.current_y + 2,
            font="BodyBold", size=7, color=text_color,
        )
        self.current_y += badge_h + 6

    def _draw_scenario_section(self) -> None:
        scenario_text = _clean_text(self.report.get("scenario_excerpt", self.report.get("scenario_text", "")))
        scenario_lines = self._wrap_text(scenario_text or "Scenario text unavailable.", self.CONTENT_WIDTH - 14, font="Body", size=9.5)
        visible_lines = min(len(scenario_lines), 25)
        line_height = 9.5 * 1.55
        text_height = visible_lines * line_height
        block_height = text_height + 8
        self._new_page_if_needed(block_height + 10)

        # Left accent bar
        self._fill_rect(self.MARGIN_X, self.current_y - 2, 2.5, block_height, self.palette["accent"])

        self._draw_wrapped_lines(
            scenario_lines[:visible_lines],
            self.MARGIN_X + 12,
            self.current_y,
            font="Body",
            size=9.5,
            color=self.palette["text"],
            leading=1.55,
        )
        self.current_y += block_height + 8

    def _draw_responses(self) -> None:
        self._section_heading("Response Ledger", "Per-iteration decisions and explanations")
        for response in self.report.get("responses", []):
            self._draw_response_block(response)

    def _draw_response_block(self, response: Dict[str, Any]) -> None:
        explanation = _clean_text(response.get("display_text", "")) or "No explanation recorded."
        body_font_size = 9
        body_leading = 1.55
        explanation_lines = self._wrap_text(explanation, self.CONTENT_WIDTH, font="Body", size=body_font_size)
        body_height = max(16.0, len(explanation_lines) * (body_font_size * body_leading))
        block_height = 52 + body_height
        if response.get("used_raw_fallback"):
            block_height += 14

        self._new_page_if_needed(block_height + 12)

        # ── Iteration label + choice + token ──
        self._draw_text(
            f"ITERATION {response.get('iteration', '?')}",
            self.MARGIN_X, self.current_y,
            font="BodyBold", size=7, color=self.palette["accent"],
        )
        self._draw_text(
            str(response.get("decision_token") or "null"),
            self.PAGE_WIDTH - self.MARGIN_X - 30, self.current_y,
            font="Mono", size=8, color=self.palette["accent"],
        )
        self.current_y += 14

        # ── Option label ──
        self._draw_text(
            response.get("option_label", "Undecided"),
            self.MARGIN_X, self.current_y,
            font="BodyBold", size=11, color=self.palette["success"],
        )
        self.current_y += 16

        # ── Latency / tokens (compact) ──
        if response.get("latency_label") or response.get("token_usage_label"):
            meta_text = "  |  ".join(
                v for v in [response.get("latency_label", ""), response.get("token_usage_label", "")]
                if v
            )
            if meta_text:
                self._draw_text(meta_text, self.MARGIN_X, self.current_y, font="Body", size=7, color=self.palette["accent"])
                self.current_y += 12

        # ── Explanation ──
        self.current_y += 4
        self._draw_wrapped_lines(
            explanation_lines, self.MARGIN_X, self.current_y,
            font="Body", size=body_font_size, color=self.palette["text"], leading=body_leading,
        )
        self.current_y += body_height

        if response.get("used_raw_fallback"):
            self.current_y += 4
            self._draw_text(
                "Displayed from raw model output — parsed explanation field was empty.",
                self.MARGIN_X, self.current_y,
                font="BodyItalic", size=7, color=self.palette["danger"],
            )
            self.current_y += 10

        # ── Thin separator rule ──
        self.current_y += 6
        self._draw_line(
            self.MARGIN_X, self.current_y,
            self.PAGE_WIDTH - self.MARGIN_X, self.current_y,
            self.palette["accent"], width=0.3,
        )
        self.current_y += 10

    def _draw_analysis(self) -> None:
        analysis = self.report.get("analysis")
        if not isinstance(analysis, dict):
            return

        self._section_heading("Analyst Assessment", "Structured synthesis of the run")

        legacy_text = _clean_text(analysis.get("legacy_text", ""))
        if legacy_text:
            self._draw_flowing_text(
                legacy_text,
                self.CONTENT_WIDTH,
                font="Body",
                size=10,
                color=self.palette["text"],
                leading=1.35,
            )
            self.current_y += 10
            return

        dominant_framework = _clean_text(analysis.get("dominant_framework", ""))
        if dominant_framework:
            self._draw_text(
                "DOMINANT FRAMEWORK",
                self.MARGIN_X, self.current_y,
                font="BodyBold", size=7, color=self.palette["accent"],
            )
            self.current_y += 14
            self._draw_text(
                dominant_framework,
                self.MARGIN_X, self.current_y,
                font="BodyBold", size=15, color=self.palette["success"],
            )
            self.current_y += 28

        self._draw_bullet_section("Key insights", analysis.get("key_insights", []), self.palette["text"])
        self._draw_bullet_section("Pattern recognition", analysis.get("justifications", []), self.palette["text"])
        self._draw_bullet_section("Consistency check", analysis.get("consistency", []), self.palette["text"])

        moral_complexes = analysis.get("moral_complexes", [])
        if isinstance(moral_complexes, list) and moral_complexes:
            self._draw_line(
                self.MARGIN_X, self.current_y,
                self.PAGE_WIDTH - self.MARGIN_X, self.current_y,
                self.palette["accent"], width=0.3,
            )
            self.current_y += 10
            self._draw_text(
                "MORAL COMPLEXES", self.MARGIN_X, self.current_y,
                font="BodyBold", size=7, color=self.palette["accent"],
            )
            self.current_y += 16
            for complex_item in moral_complexes:
                if not isinstance(complex_item, dict):
                    continue
                label = _clean_text(complex_item.get("label", "Complex"))
                count = complex_item.get("count", 0)
                justification = _clean_text(complex_item.get("justification", ""))
                self._new_page_if_needed(36)
                self._draw_text(
                    f"{label} ({count})", self.MARGIN_X, self.current_y,
                    font="BodyBold", size=10, color=self.palette["text"],
                )
                self.current_y += 14
                if justification:
                    self._draw_text_block(
                        justification, self.MARGIN_X, self.current_y,
                        self.CONTENT_WIDTH, font="Body", size=8,
                        color=self.palette["accent"], leading=1.3, max_lines=2,
                    )
                    self.current_y += 22
                else:
                    self.current_y += 6

        reasoning_quality = analysis.get("reasoning_quality")
        if isinstance(reasoning_quality, dict):
            self._draw_bullet_section("Rubric items noticed", reasoning_quality.get("noticed", []), self.palette["success"])
            self._draw_bullet_section("Rubric items missed", reasoning_quality.get("missed", []), self.palette["danger"])

    def _draw_bullet_section(self, title: str, items: object, color: str) -> None:
        normalized = [item for item in self._normalize_items(items) if item]
        if not normalized:
            return

        self._section_heading(title, "")
        bullet_indent = 12
        for item in normalized:
            lines = self._wrap_text(item, self.CONTENT_WIDTH - 22, font="Body", size=10)
            needed_height = max(20.0, len(lines) * 13.5) + 6
            self._new_page_if_needed(needed_height)
            self._draw_text("-", self.MARGIN_X, self.current_y, font="BodyBold", size=12, color=color)
            self._draw_wrapped_lines(
                lines,
                self.MARGIN_X + bullet_indent,
                self.current_y,
                font="Body",
                size=10,
                color=self.palette["text"],
                leading=1.35,
            )
            self.current_y += needed_height
        self.current_y += 4

    def _normalize_items(self, value: object) -> List[str]:
        if isinstance(value, list):
            return [_clean_text(item) for item in value if _clean_text(item)]
        if isinstance(value, str) and value.strip():
            return [_clean_text(value)]
        return []

    def _section_heading(self, title: str, subtitle: str) -> None:
        self._new_page_if_needed(44)
        self._draw_text(
            title, self.MARGIN_X, self.current_y,
            font="BodyBold", size=14, color=self.palette["text"],
        )
        self.current_y += 18
        if subtitle:
            self._draw_text(
                subtitle, self.MARGIN_X, self.current_y,
                font="Body", size=9, color=self.palette["accent"],
            )
            self.current_y += 14
        self._draw_line(
            self.MARGIN_X, self.current_y,
            self.PAGE_WIDTH - self.MARGIN_X, self.current_y,
            self.palette["accent"], width=0.5,
        )
        self.current_y += 12

    def _draw_flowing_text(
        self,
        text: str,
        width: float,
        *,
        font: str,
        size: int,
        color: str,
        leading: float,
        x: Optional[float] = None,
        top_y: Optional[float] = None,
        max_height: Optional[float] = None,
        ) -> None:
        paragraphs = _clean_text(text).split("\n")
        line_height = size * leading
        draw_x = self.MARGIN_X if x is None else x
        if top_y is not None:
            self.current_y = top_y
        start_y = self.current_y
        for paragraph in paragraphs:
            if not paragraph.strip():
                self.current_y += line_height * 0.55
                continue
            lines = self._wrap_text(paragraph, width, font=font, size=size)
            for line in lines:
                self._new_page_if_needed(line_height + 4)
                if max_height is not None and (self.current_y - start_y + line_height) > max_height:
                    self._draw_text("...", draw_x, self.current_y, font=font, size=size, color=color)
                    self.current_y += line_height
                    return
                self._draw_text(line, draw_x, self.current_y, font=font, size=size, color=color)
                self.current_y += line_height
        self.current_y += 8

    def _estimate_text_width(self, text: str, *, font: str, size: int) -> float:
        clean = _clean_text(text)
        if not clean:
            return 0.0
        if font == "Mono":
            return len(clean) * size * 0.60

        units = 0.0
        for char in clean:
            if char == " ":
                units += 0.31
            elif char in "il.,;:!|'":
                units += 0.24
            elif char in "mwMW@#%&":
                units += 0.78
            elif char in "-_/\\()[]{}":
                units += 0.34
            elif char.isupper():
                units += 0.63
            elif char.isdigit():
                units += 0.56
            else:
                units += 0.52

        if font == "BodyBold":
            units *= 1.03
        elif font == "Display":
            units *= 1.07
        elif font == "BodyItalic":
            units *= 0.99
        return units * size

    def _split_long_word(self, word: str, width: float, *, font: str, size: int) -> List[str]:
        chunks: List[str] = []
        current = ""
        for char in word:
            candidate = f"{current}{char}"
            if current and self._estimate_text_width(candidate, font=font, size=size) > width:
                chunks.append(current)
                current = char
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [word]

    def _wrap_text(self, text: str, width: float, *, font: str, size: int) -> List[str]:
        clean = _clean_text(text)
        if not clean:
            return [""]
        lines: List[str] = []

        for raw_line in clean.split("\n"):
            stripped = raw_line.strip()
            if not stripped:
                lines.append("")
                continue

            words = stripped.split(" ")
            current = ""
            for word in words:
                segments = (
                    self._split_long_word(word, width, font=font, size=size)
                    if self._estimate_text_width(word, font=font, size=size) > width
                    else [word]
                )
                for segment in segments:
                    if not current:
                        current = segment
                        continue
                    candidate = f"{current} {segment}"
                    if self._estimate_text_width(candidate, font=font, size=size) <= width:
                        current = candidate
                    else:
                        lines.append(current)
                        current = segment
            if current:
                lines.append(current)
        return lines

    def _draw_wrapped_lines(
        self,
        lines: Sequence[str],
        x: float,
        top_y: float,
        *,
        font: str,
        size: int,
        color: str,
        leading: float,
        align: str = "left",
    ) -> float:
        line_height = size * leading
        y = top_y
        for line in lines:
            line_x = x
            if align == "right":
                estimated_width = self._estimate_text_width(line, font=font, size=size)
                line_x = max(x, x + (0 - estimated_width))
            self._draw_text(line, line_x, y, font=font, size=size, color=color)
            y += line_height
        return max(0.0, y - top_y)

    def _draw_text_block(
        self,
        text: str,
        x: float,
        top_y: float,
        width: float,
        *,
        font: str,
        size: int,
        color: str,
        leading: float,
        max_lines: Optional[int] = None,
        align: str = "left",
    ) -> float:
        lines = self._wrap_text(text, width, font=font, size=size)
        if max_lines is not None and len(lines) > max_lines:
            lines = list(lines[:max_lines])
            last_line = lines[-1]
            lines[-1] = (last_line[:-1] + "..." if len(last_line) > 1 else "...")

        line_height = size * leading
        if align == "right":
            for idx, line in enumerate(lines):
                estimated_width = self._estimate_text_width(line, font=font, size=size)
                self._draw_text(
                    line,
                    x + width - estimated_width,
                    top_y + (idx * line_height),
                    font=font,
                    size=size,
                    color=color,
                )
        else:
            self._draw_wrapped_lines(
                lines,
                x,
                top_y,
                font=font,
                size=size,
                color=color,
                leading=leading,
            )
        return len(lines) * line_height

    def _fill_rect(self, x: float, top_y: float, width: float, height: float, color: str) -> None:
        assert self.current_page is not None
        lower_y = self.PAGE_HEIGHT - top_y - height
        self.current_page.push_state()
        self.current_page.set_color_rgb(*_hex_to_rgb(color))
        self.current_page.rectangle(x, lower_y, width, height)
        self.current_page.fill()
        self.current_page.pop_state()

    def _draw_line(
        self,
        x1: float,
        top_y1: float,
        x2: float,
        top_y2: float,
        color: str,
        *,
        width: float,
    ) -> None:
        assert self.current_page is not None
        self.current_page.push_state()
        self.current_page.set_line_width(width)
        self.current_page.set_color_rgb(*_hex_to_rgb(color), stroke=True)
        self.current_page.move_to(x1, self.PAGE_HEIGHT - top_y1)
        self.current_page.line_to(x2, self.PAGE_HEIGHT - top_y2)
        self.current_page.stroke()
        self.current_page.pop_state()

    def _draw_text(
        self,
        text: str,
        x: float,
        top_y: float,
        *,
        font: str,
        size: int,
        color: str,
    ) -> None:
        assert self.current_page is not None
        pdf_y = self.PAGE_HEIGHT - top_y - size
        self.current_page.begin_text()
        self.current_page.set_font_size(font, size)
        self.current_page.set_color_rgb(*_hex_to_rgb(color))
        self.current_page.set_text_matrix(1, 0, 0, 1, x, pdf_y)
        self.current_page.show_text_string(_clean_text(text))
        self.current_page.end_text()
