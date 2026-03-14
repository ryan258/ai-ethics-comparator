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


from lib.pdf_charts import PALETTE_DARK, PALETTE_LIGHT, draw_heatmap_native


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
    """Render a consulting-style multi-page PDF report using pydyf primitives."""

    PAGE_WIDTH = 595.0
    PAGE_HEIGHT = 842.0
    MARGIN_X = 42.0
    TOP_MARGIN = 52.0
    BOTTOM_MARGIN = 36.0
    FOOTER_HEIGHT = 24.0
    CONTENT_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)
    SECTION_GAP = 16.0
    SECTION_GAP_TIGHT = 10.0
    BLOCK_PADDING_X = 16.0
    BLOCK_PADDING_Y = 14.0
    ROOMY_PADDING_X = 20.0
    ROOMY_PADDING_Y = 18.0
    COLUMN_GAP = 18.0

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
        self.executive_caveat_drawn = False
        self.font_refs = self._register_fonts()

    def render(self) -> bytes:
        """Render the report to PDF bytes."""
        page_methods: List[Tuple[str, Any]] = [
            ("Executive Summary", self._draw_executive_page),
            ("Behavioral Pattern", self._draw_evidence_page),
            ("Deployment Implications", self._draw_implications_page),
            ("Method And Limitations", self._draw_method_page),
            ("Appendix Summary", self._draw_appendix_summary_page),
            ("Raw Appendix", self._draw_raw_appendix_page),
            ("Explanation Sources", self._draw_explanation_appendix_page),
        ]

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

        footer_y = self.PAGE_HEIGHT - self.BOTTOM_MARGIN + 1
        self._draw_line(
            self.MARGIN_X,
            footer_y,
            self.PAGE_WIDTH - self.MARGIN_X,
            footer_y,
            self.palette["accent"],
            width=0.45,
        )
        footer_text_y = footer_y + 8
        self._draw_text(
            "AI Ethics Comparator",
            self.MARGIN_X,
            footer_text_y,
            font="Body",
            size=7,
            color=self.palette["accent"],
        )
        if self.current_section:
            self._draw_text(
                f"  |  {self.current_section}",
                self.MARGIN_X + 74,
                footer_text_y,
                font="Body",
                size=7,
                color=self.palette["accent"],
            )
        run_id = _clean_text(self.report.get("run_id", "unknown"))
        run_id_width = self._estimate_text_width(run_id, font="Mono", size=6)
        self._draw_text(
            run_id,
            (self.PAGE_WIDTH - run_id_width) / 2,
            footer_text_y,
            font="Mono",
            size=6,
            color=self.palette["accent"],
        )
        self._draw_text(
            f"Page {self.page_number}",
            self.PAGE_WIDTH - self.MARGIN_X - 34,
            footer_text_y,
            font="Body",
            size=7,
            color=self.palette["accent"],
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

    def _draw_executive_page(self) -> None:
        self._draw_page_heading(
            "EXECUTIVE SUMMARY",
            _clean_text(self.report.get("report_title", "")),
            _clean_text(self.report.get("report_subtitle", "")),
            title_size=19,
        )
        self._draw_thesis_box(_clean_text(self.report.get("thesis_statement", "")))
        self.current_y += self._section_gap_value()
        self._draw_metric_cards()
        self.current_y += self._section_gap_value()
        self._draw_option_distribution_block(
            _clean_text(self.report.get("primary_chart_title", "")),
            self.report.get("option_stats", []),
            show_descriptions=False,
        )
        self.current_y += self._section_gap_value()
        self._draw_list_block("KEY TAKEAWAYS", self.report.get("key_takeaways", []))
        self.current_y += self._section_gap_value(tight=True)
        self._draw_callout_box("IMPLICATION", _clean_text(self.report.get("implication_box", "")), self.palette["success"])
        reliability_note = _clean_text(self.report.get("reliability_note", ""))
        if reliability_note:
            self.current_y += self._section_gap_value(tight=True)
            self._draw_callout_box("OUTPUT RELIABILITY", reliability_note, self.palette["danger"])
        caveat_box = _clean_text(self.report.get("caveat_box", ""))
        if caveat_box and self._remaining_height() >= self._estimate_callout_height(caveat_box, self.CONTENT_WIDTH) + 6:
            self.current_y += self._section_gap_value(tight=True)
            self._draw_callout_box("WHAT THIS DOES NOT PROVE", caveat_box, self.palette["danger"])
            self.executive_caveat_drawn = True

    def _draw_evidence_page(self) -> None:
        self._draw_page_heading(
            "BEHAVIORAL PATTERN AND SUPPORTING EVIDENCE",
            _clean_text(self.report.get("evidence_title", "")),
        )
        self._draw_two_column_lists(
            "CASE SUMMARY",
            self.report.get("case_summary_points", []),
            "OPTION DISTRIBUTION",
            self._distribution_rows(),
        )
        self.current_y += self._section_gap_value()
        self._draw_list_block("EVIDENCE READOUT", self._evidence_readout_points())
        self.current_y += self._section_gap_value()
        self._draw_heatmap_block(_clean_text(self.report.get("sequence_chart_title", "")))
        self.current_y += self._section_gap_value()
        self._draw_rationale_cluster_block(_clean_text(self.report.get("rationale_chart_title", "")))

    def _draw_implications_page(self) -> None:
        self._draw_page_heading(
            "IMPLICATIONS FOR DEPLOYMENT OR GOVERNANCE",
            _clean_text(self.report.get("implications_title", "")),
        )
        self._draw_callout_box("DEPLOYMENT READOUT", _clean_text(self.report.get("implication_box", "")), self.palette["success"])
        self.current_y += self._section_gap_value()
        self._draw_list_block("WHERE THIS TENDENCY IS ACCEPTABLE", self.report.get("acceptable_contexts", []))
        self.current_y += self._section_gap_value()
        self._draw_list_block("WHERE THIS TENDENCY IS RISKY", self.report.get("risky_contexts", []))
        self.current_y += self._section_gap_value()
        self._draw_list_block("REQUIRED OPERATIONAL SAFEGUARDS", self.report.get("required_controls", []))

    def _draw_method_page(self) -> None:
        self._draw_page_heading(
            "METHOD AND LIMITATIONS",
            _clean_text(self.report.get("method_title", "")),
            title_size=16,
        )
        self.current_y += self._section_gap_value(roomy=True)
        caveat_box = _clean_text(self.report.get("caveat_box", ""))
        if caveat_box and not self.executive_caveat_drawn:
            self._draw_callout_box(
                "WHAT THIS DOES NOT PROVE",
                caveat_box,
                self.palette["danger"],
                roomy=True,
            )
            self.current_y += self._section_gap_value(roomy=True)
        self._draw_two_column_lists(
            "METHOD",
            self.report.get("method_points", []),
            "LIMITATIONS",
            self.report.get("limitation_points", []),
            roomy=True,
        )
        self.current_y += self._section_gap_value(roomy=True)
        self._draw_metadata_block(
            "INTERPRETIVE METADATA",
            self.report.get("method_metadata_items", []),
            roomy=True,
        )

    def _draw_appendix_summary_page(self) -> None:
        self._draw_page_heading(
            "APPENDIX SUMMARY TABLES",
            _clean_text(self.report.get("appendix_title", "")),
        )
        note = _clean_text(self.report.get("appendix_summary_note", ""))
        if note:
            self._draw_flowing_text(
                note,
                self.CONTENT_WIDTH,
                font="Body",
                size=9,
                color=self.palette["text"],
                leading=1.4,
                max_height=30.0,
            )
        self.current_y += self._section_gap_value(tight=True)
        self._draw_appendix_summary_table()
        structure_note = _clean_text(self.report.get("structure_shift_note", ""))
        if structure_note:
            self.current_y += self._section_gap_value()
            self._draw_callout_box("NOTE", structure_note, self.palette["accent"])

    def _draw_raw_appendix_page(self) -> None:
        self._draw_page_heading(
            "FULL APPENDIX / RAW MATERIAL",
            _clean_text(self.report.get("raw_appendix_title", "")),
        )
        note = _clean_text(self.report.get("raw_appendix_note", ""))
        if note:
            self._draw_flowing_text(
                note,
                self.CONTENT_WIDTH,
                font="Body",
                size=9,
                color=self.palette["text"],
                leading=1.4,
                max_height=34.0,
            )
        self.current_y += self._section_gap_value(tight=True)
        self._draw_prompt_block()
        self.current_y += self._section_gap_value()
        self._draw_metadata_block("RUN METADATA", self.report.get("metadata_items", []), roomy=True)
        self.current_y += self._section_gap_value()
        for response in self.report.get("raw_appendix_responses", []):
            if isinstance(response, dict):
                self._draw_raw_response_block(response)

    def _draw_explanation_appendix_page(self) -> None:
        self._draw_page_heading(
            "EXPLANATION SOURCES",
            _clean_text(self.report.get("explanation_appendix_title", "")),
        )
        note = _clean_text(self.report.get("explanation_appendix_note", ""))
        if note:
            self._draw_flowing_text(
                note,
                self.CONTENT_WIDTH,
                font="Body",
                size=9,
                color=self.palette["text"],
                leading=1.4,
                max_height=36.0,
            )
        self.current_y += self._section_gap_value(tight=True)
        for response in self.report.get("responses", []):
            if isinstance(response, dict):
                self._draw_explanation_source_block(response)

    def _draw_page_heading(
        self,
        eyebrow: str,
        title: str,
        subtitle: str = "",
        *,
        title_size: int = 22,
    ) -> None:
        self._draw_text(eyebrow, self.MARGIN_X, self.current_y, font="BodyBold", size=8, color=self.palette["accent"])
        self.current_y += 20
        title_height = self._draw_text_block(
            title or "Untitled report",
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH,
            font="Display",
            size=title_size,
            color=self.palette["text"],
            leading=1.06 if title_size <= 20 else 1.1,
        )
        self.current_y += max(28.0, title_height + 8)
        if subtitle:
            subtitle_height = self._draw_text_block(
                subtitle,
                self.MARGIN_X,
                self.current_y,
                self.CONTENT_WIDTH,
                font="Body",
                size=10,
                color=self.palette["accent"],
                leading=1.38,
            )
            self.current_y += subtitle_height + 16
        else:
            self.current_y += 10

    def _section_gap_value(self, *, roomy: bool = False, tight: bool = False) -> float:
        if tight:
            return 12.0 if roomy else self.SECTION_GAP_TIGHT
        return 20.0 if roomy else self.SECTION_GAP

    def _block_padding(self, *, roomy: bool = False) -> Tuple[float, float]:
        if roomy:
            return self.ROOMY_PADDING_X, self.ROOMY_PADDING_Y
        return self.BLOCK_PADDING_X, self.BLOCK_PADDING_Y

    def _draw_metric_cards(self) -> None:
        metrics = self.report.get("executive_metrics", [])
        if not isinstance(metrics, list) or not metrics:
            return

        visible_metrics = [metric for metric in metrics[:4] if isinstance(metric, dict)]
        if not visible_metrics:
            return

        columns = 2 if len(visible_metrics) > 1 else 1
        gap_x = self.COLUMN_GAP if columns == 2 else 0.0
        gap_y = 14.0
        card_width = (self.CONTENT_WIDTH - gap_x * (columns - 1)) / columns
        card_height = 72.0
        rows = (len(visible_metrics) + columns - 1) // columns
        total_height = rows * card_height + max(0, rows - 1) * gap_y
        self._new_page_if_needed(total_height + 4)
        base_y = self.current_y
        for idx, metric in enumerate(visible_metrics):
            row = idx // columns
            col = idx % columns
            x = self.MARGIN_X + col * (card_width + gap_x)
            top_y = base_y + row * (card_height + gap_y)
            self._draw_line(x, top_y + 4, x + card_width, top_y + 4, self.palette["accent"], width=0.6)
            self._draw_text(
                _clean_text(metric.get("label", "")),
                x,
                top_y + 14,
                font="BodyBold",
                size=8,
                color=self.palette["accent"],
            )
            support = _clean_text(metric.get("support", ""))
            value_size = 16 if len(_clean_text(metric.get("value", ""))) <= 8 else 14
            value_top = top_y + 28
            value_height = self._draw_text_block(
                _clean_text(metric.get("value", "")),
                x,
                value_top,
                card_width - 8,
                font="BodyBold",
                size=value_size,
                color=self.palette["text"],
                leading=1.05,
                max_lines=2,
            )
            if support:
                self._draw_text_block(
                    support,
                    x,
                    value_top + value_height + 7,
                    card_width - 8,
                    font="Body",
                    size=8,
                    color=self.palette["text"],
                    leading=1.35,
                    max_lines=3,
                )
        self.current_y += total_height

    def _label_chip_text_color(self) -> str:
        return self.palette["bg"] if self.palette["bg"] == "#121212" else self.palette["text"]

    def _estimate_label_chip_width(self, label: str) -> float:
        return self._estimate_text_width(label, font="BodyBold", size=7) + 16

    def _draw_label_chip(self, label: str, x: float, top_y: float, fill_color: str) -> float:
        chip_width = self._estimate_label_chip_width(label)
        chip_height = 15.0
        self._fill_rect(x, top_y, chip_width, chip_height, fill_color)
        self._draw_text(
            label,
            x + 7,
            top_y + 4,
            font="BodyBold",
            size=7,
            color=self._label_chip_text_color(),
        )
        return chip_height

    def _draw_section_header(
        self,
        label: str,
        top_y: float,
        *,
        accent_color: Optional[str] = None,
        x: Optional[float] = None,
        width: Optional[float] = None,
    ) -> float:
        draw_x = self.MARGIN_X if x is None else x
        available_width = self.CONTENT_WIDTH if width is None else width
        color = self.palette["accent"] if accent_color is None else accent_color
        chip_width = self._estimate_label_chip_width(label)
        chip_height = self._draw_label_chip(label, draw_x, top_y, color)
        line_x = draw_x + chip_width + 10
        line_y = top_y + chip_height / 2 + 0.5
        line_end = draw_x + available_width
        if line_x < line_end:
            self._draw_line(line_x, line_y, line_end, line_y, color, width=0.35)
        return chip_height

    def _estimate_wrapped_height(
        self,
        text: str,
        width: float,
        *,
        font: str,
        size: int,
        leading: float,
        max_lines: Optional[int] = None,
    ) -> float:
        lines = self._wrap_text(text, width, font=font, size=size)
        if max_lines is not None:
            lines = lines[:max_lines]
        return len(lines) * size * leading

    def _estimate_callout_height(self, text: str, width: float, *, roomy: bool = False) -> float:
        pad_x, pad_y = self._block_padding(roomy=roomy)
        leading = 1.5 if roomy else 1.42
        body_width = max(72.0, width - pad_x * 2)
        body_height = self._estimate_wrapped_height(text or "n/a", body_width, font="Body", size=10, leading=leading)
        return pad_y + 15.0 + 12.0 + body_height + pad_y

    def _parse_thesis_sections(self, text: str) -> List[Tuple[str, str]]:
        parts = re.split(r"(Observed tendency:|Risk:|Deployment implication:)", _clean_text(text))
        if len(parts) < 3:
            return []
        sections: List[Tuple[str, str]] = []
        leading_text = parts[0].strip()
        if leading_text:
            sections.append(("Summary", leading_text))
        for idx in range(1, len(parts), 2):
            if idx + 1 >= len(parts):
                break
            label = parts[idx].rstrip(":")
            content = parts[idx + 1].strip()
            if content:
                sections.append((label, content))
        return sections

    def _estimate_thesis_height(self, text: str) -> float:
        sections = self._parse_thesis_sections(text)
        if not sections:
            return self._estimate_callout_height(text, self.CONTENT_WIDTH)

        pad_x, pad_y = self._block_padding()
        body_width = self.CONTENT_WIDTH - pad_x * 2
        body_height = pad_y + 15.0 + 10.0
        for idx, (_, content) in enumerate(sections):
            body_height += 10.0
            body_height += self._estimate_wrapped_height(content, body_width, font="Body", size=10, leading=1.45)
            if idx < len(sections) - 1:
                body_height += 8.0
        return body_height + pad_y

    def _draw_thesis_box(self, text: str) -> None:
        sections = self._parse_thesis_sections(text)
        if not sections:
            self._draw_callout_box("THESIS", text, self.palette["accent"])
            return

        pad_x, pad_y = self._block_padding()
        box_height = self._estimate_thesis_height(text)
        self._new_page_if_needed(box_height + 4)
        self._fill_rect(self.MARGIN_X, self.current_y, 4, box_height, self.palette["accent"])
        header_y = self.current_y + pad_y
        header_height = self._draw_section_header(
            "THESIS",
            header_y,
            accent_color=self.palette["accent"],
            x=self.MARGIN_X + 12,
            width=self.CONTENT_WIDTH - 12,
        )

        body_width = self.CONTENT_WIDTH - pad_x * 2
        section_y = header_y + header_height + 10
        for idx, (label, content) in enumerate(sections):
            self._draw_text(
                label.upper(),
                self.MARGIN_X + pad_x,
                section_y,
                font="BodyBold",
                size=8,
                color=self.palette["accent"],
            )
            section_y += 12
            lines = self._wrap_text(content, body_width, font="Body", size=10)
            section_y += self._draw_wrapped_lines(
                lines,
                self.MARGIN_X + pad_x,
                section_y,
                font="Body",
                size=10,
                color=self.palette["text"],
                leading=1.45,
            )
            if idx < len(sections) - 1:
                section_y += 8
        self.current_y += box_height

    def _draw_callout_box(
        self,
        label: str,
        text: str,
        accent_color: str,
        *,
        roomy: bool = False,
    ) -> None:
        pad_x, pad_y = self._block_padding(roomy=roomy)
        body_width = self.CONTENT_WIDTH - pad_x * 2
        lines = self._wrap_text(text or "n/a", body_width, font="Body", size=10)
        leading = 1.5 if roomy else 1.42
        box_height = self._estimate_callout_height(text, self.CONTENT_WIDTH, roomy=roomy)
        self._new_page_if_needed(box_height + 4)
        self._fill_rect(self.MARGIN_X, self.current_y, 4, box_height, accent_color)
        header_y = self.current_y + pad_y
        header_height = self._draw_section_header(
            label,
            header_y,
            accent_color=accent_color,
            x=self.MARGIN_X + 12,
            width=self.CONTENT_WIDTH - 12,
        )
        self._draw_wrapped_lines(
            lines,
            self.MARGIN_X + pad_x,
            header_y + header_height + 12,
            font="Body",
            size=10,
            color=self.palette["text"],
            leading=leading,
        )
        self.current_y += box_height

    def _draw_option_distribution_block(self, title: str, option_stats: object, *, show_descriptions: bool) -> None:
        stats = option_stats if isinstance(option_stats, list) else []
        estimated_height = 38.0
        for option in stats:
            if not isinstance(option, dict):
                continue
            score = f"{option.get('count', 0)} | {option.get('percentage_label', '0.0%')}"
            score_width = max(86.0, self._estimate_text_width(score, font="BodyBold", size=10) + 6)
            label_width = self.CONTENT_WIDTH - score_width - 20
            label = f"{option.get('token', '{?}')} {option.get('label', 'Unknown')}"
            label_lines = self._wrap_text(label, label_width, font="BodyBold", size=10)
            estimated_height += max(32.0, len(label_lines) * (10 * 1.2) + 20)
            if show_descriptions:
                description = _clean_text(option.get("description", ""))
                if description:
                    description_lines = self._wrap_text(description, self.CONTENT_WIDTH - 24, font="Body", size=8)
                    estimated_height += len(description_lines[:2]) * (8 * 1.35) + 10
        self._new_page_if_needed(estimated_height + 4)
        header_height = self._draw_section_header("PRIMARY EXHIBIT", self.current_y + 1, accent_color=self.palette["accent"])
        self.current_y += header_height + 10
        title_height = self._draw_text_block(
            title or "Choice distribution",
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH - 12,
            font="BodyBold",
            size=12,
            color=self.palette["text"],
            leading=1.24,
        )
        self.current_y += title_height + 16
        for option in stats:
            if not isinstance(option, dict):
                continue
            is_leader = bool(option.get("is_leader"))
            score = f"{option.get('count', 0)} | {option.get('percentage_label', '0.0%')}"
            score_width = self._estimate_text_width(score, font="BodyBold", size=10)
            score_column_width = max(86.0, score_width + 6)
            label_width = self.CONTENT_WIDTH - score_column_width - 20
            label = f"{option.get('token', '{?}')} {option.get('label', 'Unknown')}"
            label_lines = self._wrap_text(label, label_width, font="BodyBold", size=10)
            label_height = self._draw_wrapped_lines(
                label_lines,
                self.MARGIN_X,
                self.current_y,
                font="BodyBold",
                size=10,
                color=self.palette["success"] if is_leader else self.palette["text"],
                leading=1.2,
            )
            self._draw_text(
                score,
                self.PAGE_WIDTH - self.MARGIN_X - score_width,
                self.current_y + max(0.0, (label_height - 10.0) / 2),
                font="BodyBold",
                size=10,
                color=self.palette["success"] if is_leader else self.palette["text"],
            )
            bar_y = self.current_y + label_height + 8
            self._draw_line(
                self.MARGIN_X,
                bar_y,
                self.MARGIN_X + self.CONTENT_WIDTH,
                bar_y,
                self.palette["text"],
                width=0.75,
            )
            fill_width = self.CONTENT_WIDTH * (float(option.get("percentage", 0.0) or 0.0) / 100.0)
            if fill_width > 0:
                self._draw_line(
                    self.MARGIN_X,
                    bar_y,
                    self.MARGIN_X + max(4.0, fill_width),
                    bar_y,
                    self.palette["success"] if is_leader else self.palette["accent"],
                    width=2.8,
                )
            self.current_y = bar_y + 14
            if show_descriptions:
                description = _clean_text(option.get("description", ""))
                if description:
                    description_height = self._draw_text_block(
                        description,
                        self.MARGIN_X + 12,
                        self.current_y,
                        self.CONTENT_WIDTH - 24,
                        font="Body",
                        size=8,
                        color=self.palette["text"],
                        leading=1.35,
                        max_lines=2,
                    )
                    self.current_y += description_height + 8

    def _draw_two_column_lists(
        self,
        left_title: str,
        left_items: object,
        right_title: str,
        right_items: object,
        *,
        roomy: bool = False,
    ) -> None:
        left_list = [str(item) for item in left_items if str(item).strip()] if isinstance(left_items, list) else []
        right_list = [str(item) for item in right_items if str(item).strip()] if isinstance(right_items, list) else []
        column_width = (self.CONTENT_WIDTH - self.COLUMN_GAP) / 2
        title_gap = 20.0 if roomy else 16.0
        list_leading = 1.5 if roomy else 1.38
        item_gap = 8.0 if roomy else 5.0
        left_height = self._estimate_list_height(left_list, column_width - 8, leading=list_leading, item_gap=item_gap)
        right_height = self._estimate_list_height(right_list, column_width - 8, leading=list_leading, item_gap=item_gap)
        box_height = max(74.0 if roomy else 56.0, max(left_height, right_height) + title_gap + 16.0)
        self._new_page_if_needed(box_height + 4)
        left_x = self.MARGIN_X
        right_x = self.MARGIN_X + column_width + self.COLUMN_GAP
        divider_x = self.MARGIN_X + column_width + self.COLUMN_GAP / 2
        self._draw_line(divider_x, self.current_y + 8, divider_x, self.current_y + box_height, self.palette["accent"], width=0.25)
        label_y = self.current_y + (18 if roomy else 14)
        list_top = label_y + title_gap
        self._draw_text(left_title, left_x, label_y, font="BodyBold", size=9 if roomy else 8, color=self.palette["accent"])
        self._draw_text(right_title, right_x, label_y, font="BodyBold", size=9 if roomy else 8, color=self.palette["accent"])
        self._draw_list_lines(left_list, left_x, list_top, column_width - 8, leading=list_leading, item_gap=item_gap)
        self._draw_list_lines(right_list, right_x, list_top, column_width - 8, leading=list_leading, item_gap=item_gap)
        self.current_y += box_height

    def _draw_heatmap_block(self, title: str) -> None:
        decision_seq = self.report.get("decision_sequence", [])
        option_ids = self.report.get("chart_option_ids", [])
        if not isinstance(decision_seq, list) or not isinstance(option_ids, list) or not decision_seq or not option_ids:
            return
        self._new_page_if_needed(120)
        header_height = self._draw_section_header("SUPPORTING EXHIBIT", self.current_y, accent_color=self.palette["accent"])
        self.current_y += header_height + 10
        title_height = self._draw_text_block(
            title or "Decision sequence",
            self.MARGIN_X,
            self.current_y,
            self.CONTENT_WIDTH - 12,
            font="BodyBold",
            size=11,
            color=self.palette["text"],
            leading=1.24,
        )
        self.current_y += title_height + 16
        assert self.current_page is not None
        _tw, th = draw_heatmap_native(
            self.current_page,
            self.PAGE_HEIGHT,
            self.MARGIN_X + 30,
            self.current_y,
            decision_seq,
            option_ids,
            self.palette,
        )
        for row, option_id in enumerate(option_ids[:25]):
            label_y = self.current_y + 12 + row * 15 + 3
            self._draw_text(f"{{{option_id}}}", self.MARGIN_X, label_y, font="Mono", size=8, color=self.palette["accent"])
        self.current_y += th + 8

    def _draw_rationale_cluster_block(self, title: str) -> None:
        clusters = self.report.get("rationale_clusters", [])
        if not isinstance(clusters, list) or not clusters:
            return
        visible_clusters = clusters[:6]
        row_height = 28.0
        title_height = self._estimate_wrapped_height(
            title or "Rationale clusters",
            self.CONTENT_WIDTH - 12,
            font="BodyBold",
            size=11,
            leading=1.24,
        )
        box_height = 16 + 13 + 10 + title_height + 18 + len(visible_clusters) * row_height
        self._new_page_if_needed(box_height + 4)
        header_height = self._draw_section_header("RATIONALE CLUSTERING", self.current_y, accent_color=self.palette["accent"])
        title_y = self.current_y + header_height + 10
        title_height = self._draw_text_block(
            title or "Rationale clusters",
            self.MARGIN_X,
            title_y,
            self.CONTENT_WIDTH - 12,
            font="BodyBold",
            size=11,
            color=self.palette["text"],
            leading=1.24,
        )
        table_y = title_y + title_height + 14
        theme_x = self.MARGIN_X
        count_x = self.MARGIN_X + 320
        share_x = self.MARGIN_X + 382
        self._draw_text("Theme", theme_x, table_y, font="BodyBold", size=7, color=self.palette["accent"])
        self._draw_text("Count", count_x, table_y, font="BodyBold", size=7, color=self.palette["accent"])
        self._draw_text("Share", share_x, table_y, font="BodyBold", size=7, color=self.palette["accent"])
        self._draw_line(self.MARGIN_X, table_y + 10, self.MARGIN_X + self.CONTENT_WIDTH, table_y + 10, self.palette["accent"], width=0.3)
        row_y = table_y + 18
        last_cluster_index = len(visible_clusters) - 1
        for idx, cluster in enumerate(visible_clusters):
            if not isinstance(cluster, dict):
                continue
            self._draw_text_block(_clean_text(cluster.get("label", "")), theme_x, row_y, 300, font="Body", size=9, color=self.palette["text"], leading=1.32, max_lines=2)
            self._draw_text(str(cluster.get("count", 0)), count_x, row_y, font="Body", size=9, color=self.palette["text"])
            self._draw_text(_clean_text(cluster.get("share_label", "")), share_x, row_y, font="Body", size=9, color=self.palette["text"])
            if idx < last_cluster_index:
                self._draw_line(self.MARGIN_X, row_y + row_height - 6, self.MARGIN_X + self.CONTENT_WIDTH, row_y + row_height - 6, self.palette["accent"], width=0.2)
            row_y += row_height
        self.current_y += box_height

    def _draw_list_block(self, title: str, items: object) -> None:
        normalized = [str(item) for item in items if str(item).strip()] if isinstance(items, list) else []
        if not normalized:
            return
        box_height = max(40.0, self._estimate_list_height(normalized, self.CONTENT_WIDTH - 12, item_gap=5.0) + 36)
        self._new_page_if_needed(box_height + 4)
        header_height = self._draw_section_header(title, self.current_y, accent_color=self.palette["accent"])
        self._draw_list_lines(normalized, self.MARGIN_X, self.current_y + header_height + 12, self.CONTENT_WIDTH - 12, leading=1.38, item_gap=5.0)
        self.current_y += box_height

    def _draw_metadata_block(self, title: str, items: object, *, roomy: bool = False) -> None:
        metadata = items if isinstance(items, list) else []
        visible_items = [item for item in metadata[:8] if isinstance(item, dict)]
        if not visible_items:
            return
        value_size = 10 if roomy else 9
        value_leading = 1.45 if roomy else 1.34
        label_size = 9 if roomy else 8
        label_to_value_gap = 18.0 if roomy else 16.0
        row_bottom_padding = 14.0 if roomy else 12.0
        row_min_height = 42.0 if roomy else 36.0
        column_gap = self.COLUMN_GAP
        column_width = (self.CONTENT_WIDTH - column_gap) / 2
        rows: List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = []
        for idx in range(0, len(visible_items), 2):
            left = visible_items[idx]
            right = visible_items[idx + 1] if idx + 1 < len(visible_items) else None
            rows.append((left, right))

        row_heights: List[float] = []
        for left, right in rows:
            heights: List[float] = []
            for item in (left, right):
                if item is None:
                    continue
                value_height = self._estimate_wrapped_height(
                    _clean_text(item.get("value", "")),
                    column_width - 10,
                    font="Mono" if item.get("mono") else "Body",
                    size=value_size,
                    leading=value_leading,
                    max_lines=3 if roomy else 2,
                )
                heights.append(label_to_value_gap + value_height)
            row_heights.append(max(row_min_height, max(heights, default=0.0) + row_bottom_padding))

        header_height = 13.0
        table_top_gap = 22.0
        box_height = header_height + table_top_gap + sum(row_heights)
        self._new_page_if_needed(box_height + 4)
        drawn_header_height = self._draw_section_header(title, self.current_y, accent_color=self.palette["accent"])
        row_y = self.current_y + drawn_header_height + table_top_gap
        left_x = self.MARGIN_X
        right_x = self.MARGIN_X + column_width + column_gap
        divider_x = self.MARGIN_X + column_width + column_gap / 2
        self._draw_line(divider_x, row_y - 2, divider_x, self.current_y + box_height - 2, self.palette["accent"], width=0.25)
        for row_index, row_height in enumerate(row_heights):
            left, right = rows[row_index]
            for column_x, item in ((left_x, left), (right_x, right)):
                if item is None:
                    continue
                self._draw_text(_clean_text(item.get("label", "")), column_x, row_y, font="BodyBold", size=label_size, color=self.palette["accent"])
                self._draw_text_block(
                    _clean_text(item.get("value", "")),
                    column_x,
                    row_y + label_to_value_gap,
                    column_width - 10,
                    font="Mono" if item.get("mono") else "Body",
                    size=value_size,
                    color=self.palette["text"],
                    leading=value_leading,
                    max_lines=3 if roomy else 2,
                )
            if row_index < len(row_heights) - 1:
                self._draw_line(self.MARGIN_X, row_y + row_height - 1, self.MARGIN_X + self.CONTENT_WIDTH, row_y + row_height - 1, self.palette["accent"], width=0.2)
            row_y += row_height
        self.current_y += box_height

    def _draw_appendix_summary_table(self) -> None:
        responses = self.report.get("responses", [])
        if not isinstance(responses, list) or not responses:
            return
        widths = [26.0, 132.0, 72.0, 98.0, 160.0]
        x_positions = [self.MARGIN_X]
        for width in widths[:-1]:
            x_positions.append(x_positions[-1] + width)
        headers = ["Iter", "Selected option", "Latency", "Theme", "Output quality"]
        for idx, header in enumerate(headers):
            self._draw_text(header, x_positions[idx], self.current_y, font="BodyBold", size=7, color=self.palette["accent"])
        self._draw_line(self.MARGIN_X, self.current_y + 10, self.MARGIN_X + self.CONTENT_WIDTH, self.current_y + 10, self.palette["accent"], width=0.3)
        self.current_y += 18
        last_response_index = len(responses) - 1
        for idx, response in enumerate(responses):
            if not isinstance(response, dict):
                continue
            values = [
                str(response.get("iteration", "")),
                _clean_text(response.get("option_label", "")),
                _clean_text(response.get("latency_label", "n/a")),
                _clean_text(response.get("rationale_theme", "")),
                _clean_text(response.get("output_quality_flag", "")),
            ]
            row_height = max(
                22.0,
                max(
                    self._estimate_wrapped_height(value or "-", widths[idx] - 6, font="Body", size=8, leading=1.32, max_lines=2)
                    for idx, value in enumerate(values)
                )
                + 8.0,
            )
            self._new_page_if_needed(row_height + 6)
            for idx, value in enumerate(values):
                self._draw_text_block(
                    value or "-",
                    x_positions[idx],
                    self.current_y,
                    widths[idx] - 6,
                    font="Body",
                    size=8,
                    color=self.palette["text"],
                    leading=1.32,
                    max_lines=2,
                )
            self.current_y += row_height
            if idx < last_response_index:
                self._draw_line(self.MARGIN_X, self.current_y - 4, self.MARGIN_X + self.CONTENT_WIDTH, self.current_y - 4, self.palette["accent"], width=0.2)

    def _draw_prompt_block(self) -> None:
        prompt_text = _clean_text(self.report.get("scenario_text", "")) or "Prompt text unavailable."
        self._new_page_if_needed(24)
        header_height = self._draw_section_header("FULL PROMPT TEXT", self.current_y, accent_color=self.palette["accent"])
        self.current_y += header_height + 12
        self._draw_flowing_text(
            prompt_text,
            self.CONTENT_WIDTH - 8,
            font="Body",
            size=9,
            color=self.palette["text"],
            leading=1.4,
            x=self.MARGIN_X + 4,
        )

    def _draw_raw_response_block(self, response: Dict[str, Any]) -> None:
        raw_text = _clean_text(response.get("raw_text", "")) or "No raw output recorded."
        meta = " | ".join(
            part
            for part in [
                _clean_text(response.get("latency_label", "")),
                _clean_text(response.get("token_usage_label", "")),
                _clean_text(response.get("rationale_theme", "")),
                _clean_text(response.get("output_quality_flag", "")),
            ]
            if part
        )
        self._new_page_if_needed(
            self._estimate_appendix_response_height(
                raw_text,
                meta,
                body_size=8,
                body_leading=1.4,
            )
        )
        self._draw_line(self.MARGIN_X, self.current_y + 4, self.MARGIN_X + self.CONTENT_WIDTH, self.current_y + 4, self.palette["accent"], width=0.3)
        self.current_y += 16
        self._draw_text(f"ITERATION {response.get('iteration', '?')}", self.MARGIN_X, self.current_y, font="BodyBold", size=7, color=self.palette["accent"])
        self._draw_text_block(_clean_text(response.get("option_label", "Undecided")), self.MARGIN_X + 92, self.current_y, 240, font="BodyBold", size=9, color=self.palette["text"], leading=1.18, max_lines=1)
        self._draw_text(_clean_text(response.get("decision_token", "null")), self.PAGE_WIDTH - self.MARGIN_X - 48, self.current_y, font="Mono", size=8, color=self.palette["accent"])
        if meta:
            meta_height = self._draw_text_block(meta, self.MARGIN_X, self.current_y + 12, self.CONTENT_WIDTH, font="Body", size=8, color=self.palette["text"], leading=1.32, max_lines=2)
            self.current_y += meta_height + 14
        else:
            self.current_y += 12
        self._draw_flowing_text(
            raw_text,
            self.CONTENT_WIDTH - 8,
            font="Body",
            size=8,
            color=self.palette["text"],
            leading=1.4,
            x=self.MARGIN_X + 4,
        )

    def _draw_explanation_source_block(self, response: Dict[str, Any]) -> None:
        explanation_text = (
            _clean_text(response.get("display_text", ""))
            or _clean_text(response.get("raw_text", ""))
            or "No explanation recorded."
        )
        source_label = (
            "Source: raw output fallback"
            if response.get("used_raw_fallback")
            else "Source: parsed explanation"
        )
        meta = " | ".join(
            part
            for part in [
                source_label,
                _clean_text(response.get("latency_label", "")),
                _clean_text(response.get("rationale_theme", "")),
                _clean_text(response.get("output_quality_flag", "")),
            ]
            if part
        )
        self._new_page_if_needed(
            self._estimate_appendix_response_height(
                explanation_text,
                meta,
                body_size=9,
                body_leading=1.46,
            )
        )
        self._draw_line(
            self.MARGIN_X,
            self.current_y + 4,
            self.MARGIN_X + self.CONTENT_WIDTH,
            self.current_y + 4,
            self.palette["accent"],
            width=0.3,
        )
        self.current_y += 16
        self._draw_text(
            f"ITERATION {response.get('iteration', '?')}",
            self.MARGIN_X,
            self.current_y,
            font="BodyBold",
            size=7,
            color=self.palette["accent"],
        )
        self._draw_text_block(
            _clean_text(response.get("option_label", "Undecided")),
            self.MARGIN_X + 92,
            self.current_y,
            240,
            font="BodyBold",
            size=9,
            color=self.palette["text"],
            leading=1.18,
            max_lines=1,
        )
        self._draw_text(
            _clean_text(response.get("decision_token", "null")),
            self.PAGE_WIDTH - self.MARGIN_X - 48,
            self.current_y,
            font="Mono",
            size=8,
            color=self.palette["accent"],
        )
        if meta:
            meta_height = self._draw_text_block(
                meta,
                self.MARGIN_X,
                self.current_y + 12,
                self.CONTENT_WIDTH,
                font="Body",
                size=8,
                color=self.palette["text"],
                leading=1.32,
                max_lines=2,
            )
            self.current_y += meta_height + 14
        else:
            self.current_y += 12
        self._draw_flowing_text(
            explanation_text,
            self.CONTENT_WIDTH - 8,
            font="Body",
            size=9,
            color=self.palette["text"],
            leading=1.46,
            x=self.MARGIN_X + 4,
        )

    def _estimate_appendix_response_height(
        self,
        body_text: str,
        meta_text: str,
        *,
        body_size: int,
        body_leading: float,
    ) -> float:
        meta_height = (
            self._estimate_wrapped_height(
                meta_text,
                self.CONTENT_WIDTH,
                font="Body",
                size=8,
                leading=1.32,
                max_lines=2,
            )
            if meta_text
            else 0.0
        )
        body_height = self._estimate_wrapped_height(
            body_text,
            self.CONTENT_WIDTH - 8,
            font="Body",
            size=body_size,
            leading=body_leading,
        )
        return 34.0 + meta_height + body_height

    def _distribution_rows(self) -> List[str]:
        rows: List[str] = []
        for option in self.report.get("option_stats", []):
            if isinstance(option, dict):
                rows.append(
                    f"{_clean_text(option.get('label', 'Unknown'))}: {option.get('count', 0)} ({_clean_text(option.get('percentage_label', '0.0%'))})"
                )
        return rows

    def _evidence_readout_points(self) -> List[str]:
        combined: List[str] = []
        seen: set[str] = set()
        for key in ("observation_points", "interpretation_points"):
            items = self.report.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                text = str(item).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                combined.append(text)
        return combined

    def _estimate_list_height(
        self,
        items: List[str],
        width: float,
        *,
        leading: float = 1.28,
        item_gap: float = 4.0,
    ) -> float:
        line_height = 9 * leading
        text_width = max(24.0, width - 12)
        height = 0.0
        for item in items:
            lines = self._wrap_text(_clean_text(item), text_width, font="Body", size=9)
            height += max(18.0, len(lines) * line_height) + item_gap
        return height

    def _draw_list_lines(
        self,
        items: List[str],
        x: float,
        top_y: float,
        width: float,
        *,
        leading: float = 1.28,
        item_gap: float = 4.0,
    ) -> None:
        line_height = 9 * leading
        y = top_y
        for item in items:
            lines = self._wrap_text(_clean_text(item), width - 12, font="Body", size=9)
            self._draw_text("-", x, y, font="BodyBold", size=9, color=self.palette["text"])
            self._draw_wrapped_lines(lines, x + 10, y, font="Body", size=9, color=self.palette["text"], leading=leading)
            y += max(18.0, len(lines) * line_height) + item_gap

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
        self.current_y += 6

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
    ) -> float:
        line_height = size * leading
        y = top_y
        for line in lines:
            self._draw_text(line, x, y, font=font, size=size, color=color)
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
    ) -> float:
        lines = self._wrap_text(text, width, font=font, size=size)
        if max_lines is not None and len(lines) > max_lines:
            lines = list(lines[:max_lines])
            last_line = lines[-1]
            lines[-1] = last_line[:-1] + "..." if len(last_line) > 1 else "..."
        line_height = size * leading
        self._draw_wrapped_lines(lines, x, top_y, font=font, size=size, color=color, leading=leading)
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

    def _draw_rect_outline(self, x: float, top_y: float, width: float, height: float, color: str) -> None:
        self._draw_line(x, top_y, x + width, top_y, color, width=0.35)
        self._draw_line(x, top_y + height, x + width, top_y + height, color, width=0.35)
        self._draw_line(x, top_y, x, top_y + height, color, width=0.35)
        self._draw_line(x + width, top_y, x + width, top_y + height, color, width=0.35)

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
