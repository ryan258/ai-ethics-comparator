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


PALETTE: Dict[str, str] = {
    "bg": "#121212",
    "text": "#EBD2BE",
    "accent": "#A6ACCD",
    "success": "#98C379",
    "danger": "#E06C75",
}


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

    def __init__(self, report: Dict[str, Any]) -> None:
        if pydyf is None:
            raise RuntimeError("pydyf is required for native PDF rendering.")

        self.report = report
        self.pdf = pydyf.PDF()
        self.page_number = 0
        self.current_page: Optional[pydyf.Stream] = None
        self.current_y = self.TOP_MARGIN
        self.font_refs = self._register_fonts()

    def render(self) -> bytes:
        """Render the report to PDF bytes."""
        page_methods = [self._draw_cover_page, self._draw_briefing_page]
        if self.report.get("responses"):
            page_methods.append(self._draw_responses)
        if isinstance(self.report.get("analysis"), dict):
            page_methods.append(self._draw_analysis)

        for method in page_methods:
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

        self._fill_rect(0, 0, self.PAGE_WIDTH, self.PAGE_HEIGHT, PALETTE["bg"])
        self._fill_rect(0, 0, self.PAGE_WIDTH, 10, PALETTE["accent"])
        self._fill_rect(0, 10, self.PAGE_WIDTH * 0.16, 6, PALETTE["danger"])

        self._draw_text(
            "AI ETHICS COMPARATOR",
            self.MARGIN_X,
            24,
            font="BodyBold",
            size=9,
            color=PALETTE["accent"],
        )
        self._draw_text(
            "Professional Decision Report",
            self.PAGE_WIDTH - self.MARGIN_X - 170,
            24,
            font="Body",
            size=9,
            color=PALETTE["text"],
        )

    def _finalize_page(self) -> None:
        assert pydyf is not None
        if self.current_page is None:
            return

        footer_y = self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 4
        self._draw_line(
            self.MARGIN_X,
            footer_y,
            self.PAGE_WIDTH - self.MARGIN_X,
            footer_y,
            PALETTE["accent"],
            width=0.8,
        )
        self._draw_text(
            self.report.get("run_id", "unknown"),
            self.MARGIN_X,
            self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 10,
            font="Mono",
            size=8,
            color=PALETTE["accent"],
        )
        self._draw_text(
            f"Page {self.page_number}",
            self.PAGE_WIDTH - self.MARGIN_X - 36,
            self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 10,
            font="Body",
            size=8,
            color=PALETTE["accent"],
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
        self._draw_text(
            "EXECUTIVE BRIEF",
            self.MARGIN_X,
            self.current_y,
            font="BodyBold",
            size=8,
            color=PALETTE["accent"],
        )
        self.current_y += 18
        self._draw_text(
            "Ethical Decision Report",
            self.MARGIN_X,
            self.current_y,
            font="Display",
            size=29,
            color=PALETTE["text"],
        )
        self.current_y += 38

        paradox_title = _clean_text(self.report.get("paradox_title", "Unknown paradox"))
        self._draw_text_block(
            paradox_title,
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH,
            font="BodyBold",
            size=18,
            color=PALETTE["success"],
            leading=1.18,
        )
        self.current_y += 34

        subtitle = (
            f"Category: {self.report.get('category', 'Uncategorized')}  |  "
            f"Generated: {self.report.get('generated_at_label', 'Unknown')}"
        )
        self._draw_text(
            subtitle,
            self.MARGIN_X,
            self.current_y,
            font="Body",
            size=10,
            color=PALETTE["accent"],
        )
        self.current_y += 20

        self._draw_cover_summary_band()
        self._draw_cover_stat_band()
        self._draw_cover_snapshot()
        self._draw_cover_detail_band()

    def _draw_cover_summary_band(self) -> None:
        feature_width = self.CONTENT_WIDTH * 0.63
        side_width = self.CONTENT_WIDTH - feature_width - 14
        panel_height = 188
        x_left = self.MARGIN_X
        x_right = self.MARGIN_X + feature_width + 14

        self._card(x_left, self.current_y, feature_width, panel_height, accent_bar=PALETTE["success"])
        self._draw_text(
            str(self.report.get("lead_choice_token", "{?}")),
            x_left + 16,
            self.current_y + 16,
            font="Mono",
            size=10,
            color=PALETTE["accent"],
        )
        self._draw_text_block(
            _clean_text(self.report.get("lead_choice_label", "No dominant choice")),
            x_left + 16,
            self.current_y + 34,
            feature_width - 32,
            font="BodyBold",
            size=20,
            color=PALETTE["text"],
            leading=1.12,
        )
        self._draw_text_block(
            _clean_text(self.report.get("lead_choice_support", "")),
            x_left + 16,
            self.current_y + 86,
            feature_width - 32,
            font="BodyBold",
            size=10,
            color=PALETTE["success"],
            leading=1.2,
        )
        self._draw_text_block(
            _clean_text(self.report.get("executive_summary", "")),
            x_left + 16,
            self.current_y + 112,
            feature_width - 32,
            font="Body",
            size=11,
            color=PALETTE["text"],
            leading=1.5,
            max_lines=5,
        )

        self._card(x_right, self.current_y, side_width, panel_height)
        metadata = [
            ("RUN ID", self.report.get("run_id", "unknown"), "Mono"),
            ("MODEL", self.report.get("model_name", "unknown"), "Body"),
            ("PROMPT HASH", self.report.get("prompt_hash_short", "n/a"), "Mono"),
            ("ANALYST", self.report.get("analyst_model", "Not generated"), "Body"),
        ]
        meta_y = self.current_y + 16
        for label, value, font in metadata:
            self._draw_text(label, x_right + 14, meta_y, font="BodyBold", size=8, color=PALETTE["accent"])
            self._draw_text_block(
                _clean_text(value),
                x_right + 14,
                meta_y + 12,
                side_width - 28,
                font=font,
                size=10,
                color=PALETTE["text"],
                leading=1.2,
                max_lines=2,
            )
            meta_y += 40

        self.current_y += panel_height + 18

    def _draw_cover_stat_band(self) -> None:
        card_height = 78
        gap = 10
        card_width = (self.CONTENT_WIDTH - (gap * 3)) / 4
        stats = [
            ("Response Count", str(self.report.get("response_count", 0)), self.report.get("response_count_support", ""), True),
            ("Mean Latency", self.report.get("mean_latency_label", "n/a"), self.report.get("latency_support", ""), False),
            ("Token Volume", self.report.get("token_volume_label", "n/a"), self.report.get("token_support", ""), False),
            ("Analyst Status", "READY" if isinstance(self.report.get("analysis"), dict) else "PENDING", _clean_text(self.report.get("analyst_model", "Not generated")), True),
        ]

        for idx, (title, value, support, primary) in enumerate(stats):
            x = self.MARGIN_X + (idx * (card_width + gap))
            self._card(x, self.current_y, card_width, card_height, accent_bar=PALETTE["success"] if primary else None)
            self._draw_text(title.upper(), x + 12, self.current_y + 12, font="BodyBold", size=7, color=PALETTE["accent"])
            self._draw_text_block(
                _clean_text(value),
                x + 12,
                self.current_y + 26,
                card_width - 24,
                font="BodyBold",
                size=12,
                color=PALETTE["text"],
                leading=1.1,
                max_lines=2,
            )
            self._draw_text_block(
                _clean_text(support),
                x + 12,
                self.current_y + 50,
                card_width - 24,
                font="Body",
                size=8,
                color=PALETTE["accent"],
                leading=1.18,
                max_lines=2,
            )

        self.current_y += card_height + 18

    def _draw_cover_snapshot(self) -> None:
        panel_height = 102
        self._card(self.MARGIN_X, self.current_y, self.CONTENT_WIDTH, panel_height, accent_bar=PALETTE["accent"])
        self._draw_text("ANALYST SNAPSHOT", self.MARGIN_X + 16, self.current_y + 14, font="BodyBold", size=8, color=PALETTE["accent"])
        self._draw_text_block(
            _clean_text(self.report.get("analysis_snapshot", "")),
            self.MARGIN_X + 16,
            self.current_y + 30,
            self.CONTENT_WIDTH - 32,
            font="Body",
            size=11,
            color=PALETTE["text"],
            leading=1.5,
            max_lines=4,
        )
        self.current_y += panel_height + 8

    def _draw_cover_detail_band(self) -> None:
        panel_height = 128
        gap = 12
        panel_width = (self.CONTENT_WIDTH - gap) / 2
        left_x = self.MARGIN_X
        right_x = self.MARGIN_X + panel_width + gap
        self._new_page_if_needed(panel_height + 8)

        self._card(left_x, self.current_y, panel_width, panel_height, accent_bar=PALETTE["accent"])
        self._draw_text(
            "ENGAGEMENT SCOPE",
            left_x + 14,
            self.current_y + 14,
            font="BodyBold",
            size=8,
            color=PALETTE["accent"],
        )
        self._draw_cover_points(
            self.report.get("scope_points", []),
            x=left_x + 14,
            top_y=self.current_y + 34,
            width=panel_width - 28,
        )

        self._card(right_x, self.current_y, panel_width, panel_height, accent_bar=PALETTE["success"])
        self._draw_text(
            "REPORT SIGNALS",
            right_x + 14,
            self.current_y + 14,
            font="BodyBold",
            size=8,
            color=PALETTE["accent"],
        )
        self._draw_cover_points(
            self.report.get("readout_points", []),
            x=right_x + 14,
            top_y=self.current_y + 34,
            width=panel_width - 28,
        )

        self.current_y += panel_height + 8

    def _draw_cover_points(self, items: object, *, x: float, top_y: float, width: float) -> None:
        if not isinstance(items, list):
            return
        y = top_y
        for item in items[:3]:
            text = _clean_text(item)
            if not text:
                continue
            self._draw_text("-", x, y, font="BodyBold", size=11, color=PALETTE["success"])
            self._draw_text_block(
                text,
                x + 12,
                y,
                width - 12,
                font="Body",
                size=9,
                color=PALETTE["text"],
                leading=1.35,
                max_lines=3,
            )
            y += 30

    def _draw_briefing_page(self) -> None:
        self._section_heading("Choice Distribution", "Vote share across all iterations.")
        self._draw_distribution_section()
        self.current_y += 10
        self._section_heading("Scenario Brief", "Context excerpt from the evaluated prompt.")
        self._draw_scenario_section()

    def _draw_distribution_section(self) -> None:
        option_stats = self.report.get("option_stats", [])
        section_height = (len(option_stats) * 72) + 24
        if self.report.get("undecided_count", 0):
            section_height += 34

        self._new_page_if_needed(section_height)

        for option in option_stats:
            self._new_page_if_needed(78)
            is_leader = bool(option.get("is_leader"))
            self._card(
                self.MARGIN_X,
                self.current_y,
                self.CONTENT_WIDTH,
                62,
                accent_bar=PALETTE["success"] if is_leader else None,
            )
            self._draw_text(
                f"{option['token']}  {option['label']}",
                self.MARGIN_X + 16,
                self.current_y + 14,
                font="BodyBold",
                size=11,
                color=PALETTE["text"],
            )
            self._draw_text(
                f"{option['count']} ({option['percentage_label']})",
                self.PAGE_WIDTH - self.MARGIN_X - 92,
                self.current_y + 14,
                font="BodyBold",
                size=10,
                color=PALETTE["success"] if is_leader else PALETTE["text"],
            )
            bar_x = self.MARGIN_X + 16
            bar_y = self.current_y + 30
            bar_width = self.CONTENT_WIDTH - 32
            self._fill_rect(bar_x, bar_y, bar_width, 12, PALETTE["bg"])
            self._stroke_rect(bar_x, bar_y, bar_width, 12, PALETTE["accent"], 0.8)
            fill_width = bar_width * (float(option["percentage"]) / 100.0)
            if fill_width > 0:
                self._fill_rect(
                    bar_x,
                    bar_y,
                    max(6.0, fill_width),
                    12,
                    PALETTE["success"] if is_leader else PALETTE["accent"],
                )
            self._draw_text_block(
                option["description"],
                self.MARGIN_X + 16,
                self.current_y + 48,
                self.CONTENT_WIDTH - 32,
                font="Body",
                size=8,
                color=PALETTE["accent"],
                leading=1.15,
                max_lines=1,
            )
            self.current_y += 74

        undecided_count = int(self.report.get("undecided_count", 0) or 0)
        if undecided_count:
            self._draw_text("Undecided", self.MARGIN_X, self.current_y, font="BodyBold", size=10, color=PALETTE["text"])
            self._draw_text(
                f"{undecided_count} ({self.report.get('undecided_percentage_label', '0.0%')})",
                self.MARGIN_X + 110,
                self.current_y,
                font="BodyBold",
                size=10,
                color=PALETTE["danger"],
            )
            self.current_y += 26

    def _draw_scenario_section(self) -> None:
        scenario_text = _clean_text(self.report.get("scenario_excerpt", self.report.get("scenario_text", "")))
        scenario_lines = self._wrap_text(scenario_text or "Scenario text unavailable.", self.CONTENT_WIDTH - 32, font="Body", size=10)
        visible_lines = min(len(scenario_lines), 15)
        panel_height = max(128.0, (visible_lines * 13.5) + 42)
        self._new_page_if_needed(panel_height + 10)
        panel_top = self.current_y
        self._card(self.MARGIN_X, panel_top, self.CONTENT_WIDTH, panel_height, accent_bar=PALETTE["accent"])
        max_lines = max(int((panel_height - 32) / 13.5), 1)
        if len(scenario_lines) > max_lines:
            scenario_lines = scenario_lines[:max_lines]
            last_line = scenario_lines[-1]
            scenario_lines[-1] = (last_line[:-3].rstrip() + "..." if len(last_line) > 3 else "...")
        self._draw_wrapped_lines(
            scenario_lines,
            self.MARGIN_X + 16,
            panel_top + 16,
            font="Body",
            size=10,
            color=PALETTE["text"],
            leading=1.35,
        )
        self.current_y = panel_top + panel_height + 8

    def _draw_responses(self) -> None:
        self._section_heading("Response Ledger", "Per-iteration decisions and explanations")
        cards_on_page = 0
        for response in self.report.get("responses", []):
            if cards_on_page >= 2:
                self._finalize_page()
                self._start_page()
                self._section_heading("Response Ledger", "Continued")
                cards_on_page = 0
            self._draw_response_block(response)
            cards_on_page += 1

    def _draw_response_block(self, response: Dict[str, Any]) -> None:
        explanation = _clean_text(response.get("display_text", "")) or "No explanation recorded."
        body_font_size = 8
        body_leading = 1.5
        explanation_lines = self._wrap_text(explanation, self.CONTENT_WIDTH - 32, font="Body", size=body_font_size)
        body_height = max(56.0, len(explanation_lines) * (body_font_size * body_leading))
        card_height = 84 + body_height
        if response.get("used_raw_fallback"):
            card_height += 16

        self._new_page_if_needed(card_height + 10)
        card_top = self.current_y
        self._card(self.MARGIN_X, card_top, self.CONTENT_WIDTH, card_height, accent_bar=PALETTE["success"])
        self._draw_text(
            f"Iteration {response.get('iteration', '?')}",
            self.MARGIN_X + 14,
            card_top + 12,
            font="BodyBold",
            size=10,
            color=PALETTE["text"],
        )
        header_right = (
            f"{response.get('decision_token') or 'null'}  |  "
            f"optionId {response.get('option_id') if response.get('option_id') is not None else 'null'}"
        )
        self._draw_text_block(
            header_right,
            self.MARGIN_X + 180,
            card_top + 12,
            self.CONTENT_WIDTH - 194,
            font="Mono",
            size=9,
            color=PALETTE["accent"],
            leading=1.1,
            align="right",
        )

        self._draw_text_block(
            response.get("option_label", "Undecided"),
            self.MARGIN_X,
            card_top + 30,
            self.CONTENT_WIDTH,
            font="BodyBold",
            size=12,
            color=PALETTE["success"],
            leading=1.2,
        )

        if response.get("latency_label") or response.get("token_usage_label"):
            meta_text = "  |  ".join(
                value
                for value in [response.get("latency_label", ""), response.get("token_usage_label", "")]
                if value
            )
            if meta_text:
                self._draw_text_block(
                    meta_text,
                    self.MARGIN_X,
                    card_top + 48,
                    self.CONTENT_WIDTH,
                    font="Body",
                    size=8,
                    color=PALETTE["accent"],
                    leading=1.1,
                )
        text_y = card_top + 68
        self._draw_wrapped_lines(
            explanation_lines,
            self.MARGIN_X + 16,
            text_y,
            font="Body",
            size=body_font_size,
            color=PALETTE["text"],
            leading=body_leading,
        )

        if response.get("used_raw_fallback"):
            self._draw_text_block(
                "Displayed from raw model output because the parsed explanation field was empty.",
                self.MARGIN_X + 16,
                text_y + body_height + 8,
                self.CONTENT_WIDTH - 32,
                font="BodyItalic",
                size=8,
                color=PALETTE["danger"],
                leading=1.2,
            )
        self.current_y = card_top + card_height + 10

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
                color=PALETTE["text"],
                leading=1.35,
            )
            self.current_y += 10
            return

        dominant_framework = _clean_text(analysis.get("dominant_framework", ""))
        if dominant_framework:
            self._card(self.MARGIN_X, self.current_y, self.CONTENT_WIDTH, 58, accent_bar=PALETTE["accent"])
            self._draw_text(
                "Dominant framework".upper(),
                self.MARGIN_X + 14,
                self.current_y + 12,
                font="BodyBold",
                size=8,
                color=PALETTE["accent"],
            )
            self._draw_text_block(
                dominant_framework,
                self.MARGIN_X + 14,
                self.current_y + 26,
                self.CONTENT_WIDTH - 28,
                font="BodyBold",
                size=14,
                color=PALETTE["success"],
                leading=1.2,
            )
            self.current_y += 72

        self._draw_bullet_section("Key insights", analysis.get("key_insights", []), PALETTE["text"])
        self._draw_bullet_section("Pattern recognition", analysis.get("justifications", []), PALETTE["text"])
        self._draw_bullet_section("Consistency check", analysis.get("consistency", []), PALETTE["text"])

        moral_complexes = analysis.get("moral_complexes", [])
        if isinstance(moral_complexes, list) and moral_complexes:
            self._section_heading("Moral Complexes", "Dominant motifs surfaced by the analyst")
            for complex_item in moral_complexes:
                if not isinstance(complex_item, dict):
                    continue
                label = _clean_text(complex_item.get("label", "Complex"))
                count = complex_item.get("count", 0)
                justification = _clean_text(complex_item.get("justification", ""))
                self._new_page_if_needed(72)
                self._card(self.MARGIN_X, self.current_y, self.CONTENT_WIDTH, 56, accent_bar=PALETTE["danger"])
                self._draw_text(
                    f"{label} ({count})",
                    self.MARGIN_X + 14,
                    self.current_y + 12,
                    font="BodyBold",
                    size=11,
                    color=PALETTE["text"],
                )
                self._draw_text_block(
                    justification or "No justification provided.",
                    self.MARGIN_X + 14,
                    self.current_y + 28,
                    self.CONTENT_WIDTH - 28,
                    font="Body",
                    size=9,
                    color=PALETTE["accent"],
                    leading=1.2,
                    max_lines=2,
                )
                self.current_y += 70

        reasoning_quality = analysis.get("reasoning_quality")
        if isinstance(reasoning_quality, dict):
            self._draw_bullet_section("Rubric items noticed", reasoning_quality.get("noticed", []), PALETTE["success"])
            self._draw_bullet_section("Rubric items missed", reasoning_quality.get("missed", []), PALETTE["danger"])

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
                color=PALETTE["text"],
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
        self._new_page_if_needed(52)
        self._draw_text(title.upper(), self.MARGIN_X, self.current_y, font="BodyBold", size=8, color=PALETTE["accent"])
        self.current_y += 14
        self._draw_text_block(
            title,
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH,
            font="BodyBold",
            size=17,
            color=PALETTE["text"],
            leading=1.2,
        )
        self.current_y += 24
        if subtitle:
            self._draw_text_block(
                subtitle,
                self.MARGIN_X,
                self.current_y,
                self.CONTENT_WIDTH,
                font="Body",
                size=9,
                color=PALETTE["accent"],
                leading=1.2,
            )
            self.current_y += 16
        self._draw_line(
            self.MARGIN_X,
            self.current_y,
            self.PAGE_WIDTH - self.MARGIN_X,
            self.current_y,
            PALETTE["accent"],
            width=0.8,
        )
        self.current_y += 14

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

    def _card(
        self,
        x: float,
        top_y: float,
        width: float,
        height: float,
        *,
        accent_bar: Optional[str] = None,
    ) -> None:
        self._fill_rect(x, top_y, width, height, PALETTE["bg"])
        self._stroke_rect(x, top_y, width, height, PALETTE["accent"], 0.85)
        if accent_bar:
            self._fill_rect(x, top_y, 5, height, accent_bar)

    def _fill_rect(self, x: float, top_y: float, width: float, height: float, color: str) -> None:
        assert self.current_page is not None
        lower_y = self.PAGE_HEIGHT - top_y - height
        self.current_page.push_state()
        self.current_page.set_color_rgb(*_hex_to_rgb(color))
        self.current_page.rectangle(x, lower_y, width, height)
        self.current_page.fill()
        self.current_page.pop_state()

    def _stroke_rect(self, x: float, top_y: float, width: float, height: float, color: str, line_width: float) -> None:
        assert self.current_page is not None
        lower_y = self.PAGE_HEIGHT - top_y - height
        self.current_page.push_state()
        self.current_page.set_line_width(line_width)
        self.current_page.set_color_rgb(*_hex_to_rgb(color), stroke=True)
        self.current_page.rectangle(x, lower_y, width, height)
        self.current_page.stroke()
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
