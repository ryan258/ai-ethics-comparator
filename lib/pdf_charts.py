"""
Chart rendering for PDF reports.

Dual API per chart type:
  - render_*_svg()  → inline SVG string for WeasyPrint injection
  - draw_*_native() → pydyf primitive calls for native renderer

Zero external dependencies.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


# ── Shared palette constants ─────────────────────────────────────────────────

PALETTE_DARK: Dict[str, str] = {
    "bg": "#121212",
    "bg_raised": "#A6ACCD",
    "text": "#EBD2BE",
    "accent": "#A6ACCD",
    "success": "#98C379",
    "danger": "#E06C75",
}

PALETTE_LIGHT: Dict[str, str] = {
    "bg": "#EBD2BE",
    "bg_raised": "#A6ACCD",
    "text": "#121212",
    "accent": "#A6ACCD",
    "success": "#98C379",
    "danger": "#E06C75",
}


# ── Color helpers ────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(round(int(value[i : i + 2], 16) / 255, 4) for i in (0, 2, 4))


def interpolate_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors. t=0 → c1, t=1 → c2."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int((r1 + (r2 - r1) * t) * 255),
        int((g1 + (g2 - g1) * t) * 255),
        int((b1 + (b2 - b1) * t) * 255),
    )


# ── Bezier arc approximation ────────────────────────────────────────────────

def _arc_bezier_points(
    cx: float, cy: float, radius: float,
    start_angle: float, end_angle: float,
) -> List[Tuple[float, float, float, float, float, float]]:
    """Approximate a circular arc with cubic Bezier curves.

    Returns list of (cp1x, cp1y, cp2x, cp2y, endx, endy) tuples for
    curve_to calls.  Splits arcs > 90° into quadrant segments.
    Uses kappa = 4/3 · tan(θ/4) per segment.
    """
    segments: List[Tuple[float, float, float, float, float, float]] = []
    angle = end_angle - start_angle
    n = max(1, math.ceil(abs(angle) / (math.pi / 2)))
    seg = angle / n

    for i in range(n):
        a1 = start_angle + i * seg
        a2 = a1 + seg
        alpha = 4.0 / 3.0 * math.tan((a2 - a1) / 4.0)

        cos1, sin1 = math.cos(a1), math.sin(a1)
        cos2, sin2 = math.cos(a2), math.sin(a2)

        p0x = cx + radius * cos1
        p0y = cy + radius * sin1
        p3x = cx + radius * cos2
        p3y = cy + radius * sin2

        segments.append((
            p0x - alpha * radius * sin1,
            p0y + alpha * radius * cos1,
            p3x + alpha * radius * sin2,
            p3y - alpha * radius * cos2,
            p3x,
            p3y,
        ))
    return segments


# ══════════════════════════════════════════════════════════════════════════════
#  DONUT CHART
# ══════════════════════════════════════════════════════════════════════════════

def render_donut_svg(
    data: List[Dict[str, Any]],
    palette: Dict[str, str],
    *,
    width: int = 170,
    height: int = 170,
    outer_r: int = 74,
    inner_r: int = 46,
) -> str:
    """Render a donut chart as inline SVG for WeasyPrint."""
    total = sum(d["value"] for d in data)
    if total == 0:
        return ""

    cx, cy = width / 2, height / 2
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
    ]

    cur = -math.pi / 2
    for item in data:
        if item["value"] == 0:
            continue
        frac = item["value"] / total
        sweep = frac * 2 * math.pi
        end = cur + sweep

        if frac > 0.999:
            # Full circle: split into two half-arcs (SVG can't draw a
            # 360° arc as a single A command).
            mid = cur + math.pi
            for a1, a2 in [(cur, mid), (mid, end)]:
                parts.append(_svg_donut_arc(cx, cy, outer_r, inner_r, a1, a2, 0, item["color"]))
        else:
            large = 1 if sweep > math.pi else 0
            parts.append(_svg_donut_arc(cx, cy, outer_r, inner_r, cur, end, large, item["color"]))

        cur = end

    # Center label
    parts.append(
        f'  <text x="{cx}" y="{cy + 5}" text-anchor="middle" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="22" '
        f'font-weight="700" fill="{palette["text"]}">{total}</text>'
    )
    parts.append(
        f'  <text x="{cx}" y="{cy + 19}" text-anchor="middle" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="8" '
        f'fill="{palette["accent"]}">TOTAL</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_donut_arc(
    cx: float, cy: float,
    outer_r: float, inner_r: float,
    start: float, end: float,
    large_arc: int,
    color: str,
) -> str:
    ox1 = cx + outer_r * math.cos(start)
    oy1 = cy + outer_r * math.sin(start)
    ox2 = cx + outer_r * math.cos(end)
    oy2 = cy + outer_r * math.sin(end)
    ix1 = cx + inner_r * math.cos(end)
    iy1 = cy + inner_r * math.sin(end)
    ix2 = cx + inner_r * math.cos(start)
    iy2 = cy + inner_r * math.sin(start)
    return (
        f'  <path d="M {ox1:.2f} {oy1:.2f} '
        f'A {outer_r} {outer_r} 0 {large_arc} 1 {ox2:.2f} {oy2:.2f} '
        f'L {ix1:.2f} {iy1:.2f} '
        f'A {inner_r} {inner_r} 0 {large_arc} 0 {ix2:.2f} {iy2:.2f} Z" '
        f'fill="{color}" />'
    )


def draw_donut_native(
    page: Any,
    page_height: float,
    cx: float,
    cy: float,
    data: List[Dict[str, Any]],
    palette: Dict[str, str],
    *,
    outer_r: float = 60.0,
    inner_r: float = 36.0,
) -> None:
    """Draw donut chart via pydyf Bezier arcs.

    *cx*, *cy* use top-down coordinates (matching the renderer convention).
    """
    total = sum(d["value"] for d in data)
    if total == 0:
        return

    pdf_cx, pdf_cy = cx, page_height - cy
    cur = -math.pi / 2

    for item in data:
        if item["value"] == 0:
            continue
        sweep = (item["value"] / total) * 2 * math.pi
        end = cur + sweep

        r, g, b = _hex_to_rgb(item["color"])
        page.push_state()
        page.set_color_rgb(r, g, b)

        # Start at outer arc origin
        page.move_to(
            pdf_cx + outer_r * math.cos(cur),
            pdf_cy + outer_r * math.sin(cur),
        )

        # Outer arc (forward)
        for pts in _arc_bezier_points(pdf_cx, pdf_cy, outer_r, cur, end):
            page.curve_to(*pts)

        # Line to inner arc
        page.line_to(
            pdf_cx + inner_r * math.cos(end),
            pdf_cy + inner_r * math.sin(end),
        )

        # Inner arc (reverse)
        for pts in _arc_bezier_points(pdf_cx, pdf_cy, inner_r, end, cur):
            page.curve_to(*pts)

        page.fill()
        page.pop_state()
        cur = end


# ══════════════════════════════════════════════════════════════════════════════
#  SPARKLINE
# ══════════════════════════════════════════════════════════════════════════════

def render_sparkline_svg(
    values: List[float],
    palette: Dict[str, str],
    *,
    width: int = 260,
    height: int = 56,
    stroke_w: float = 1.5,
) -> str:
    """Render a latency sparkline as inline SVG."""
    if len(values) < 2:
        return ""

    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    pad = 4
    ew, eh = width - pad * 2, height - pad * 2

    pts = [
        f"{pad + (i / (len(values) - 1)) * ew:.1f},"
        f"{pad + eh - ((v - lo) / span) * eh:.1f}"
        for i, v in enumerate(values)
    ]

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
    ]

    # Dashed grid
    for frac in (0.0, 0.5, 1.0):
        gy = pad + eh * (1 - frac)
        lines.append(
            f'  <line x1="{pad}" y1="{gy:.1f}" x2="{width - pad}" y2="{gy:.1f}" '
            f'stroke="{palette["accent"]}" stroke-width="0.3" '
            f'stroke-dasharray="3,3" opacity="0.4" />'
        )

    # Polyline
    lines.append(
        f'  <polyline points="{" ".join(pts)}" fill="none" '
        f'stroke="{palette["success"]}" stroke-width="{stroke_w}" '
        f'stroke-linejoin="round" stroke-linecap="round" />'
    )

    # Endpoint dots
    for idx in (0, len(values) - 1):
        x = pad + (idx / (len(values) - 1)) * ew
        y = pad + eh - ((values[idx] - lo) / span) * eh
        lines.append(
            f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" '
            f'fill="{palette["success"]}" />'
        )

    # Range labels
    lines.append(
        f'  <text x="{width - pad}" y="{pad + 3}" text-anchor="end" '
        f'font-family="Helvetica,sans-serif" font-size="7" '
        f'fill="{palette["accent"]}">{hi:.1f}s</text>'
    )
    lines.append(
        f'  <text x="{width - pad}" y="{height - pad + 1}" text-anchor="end" '
        f'font-family="Helvetica,sans-serif" font-size="7" '
        f'fill="{palette["accent"]}">{lo:.1f}s</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def draw_sparkline_native(
    page: Any,
    page_height: float,
    x: float,
    y: float,
    values: List[float],
    palette: Dict[str, str],
    *,
    width: float = 220.0,
    height: float = 44.0,
    stroke_w: float = 1.2,
) -> None:
    """Draw sparkline via pydyf move_to / line_to polyline.

    *x*, *y* are top-down; *y* is the top of the sparkline area.
    """
    if len(values) < 2:
        return

    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    pad = 3
    ew, eh = width - pad * 2, height - pad * 2
    pdf_bot = page_height - y - height  # bottom in PDF coords

    # Grid lines (thin solid — avoids pydyf dash API uncertainty)
    ar, ag, ab = _hex_to_rgb(palette["accent"])
    page.push_state()
    page.set_line_width(0.3)
    page.set_color_rgb(ar, ag, ab, stroke=True)
    for frac in (0.0, 0.5, 1.0):
        gy = pdf_bot + pad + frac * eh
        page.move_to(x + pad, gy)
        page.line_to(x + width - pad, gy)
    page.stroke()
    page.pop_state()

    # Polyline
    sr, sg, sb = _hex_to_rgb(palette["success"])
    page.push_state()
    page.set_line_width(stroke_w)
    page.set_color_rgb(sr, sg, sb, stroke=True)
    for i, v in enumerate(values):
        px = x + pad + (i / (len(values) - 1)) * ew
        py = pdf_bot + pad + ((v - lo) / span) * eh
        if i == 0:
            page.move_to(px, py)
        else:
            page.line_to(px, py)
    page.stroke()
    page.pop_state()

    # Endpoint dots (small squares)
    page.push_state()
    page.set_color_rgb(sr, sg, sb)
    for idx in (0, len(values) - 1):
        px = x + pad + (idx / (len(values) - 1)) * ew
        py = pdf_bot + pad + ((values[idx] - lo) / span) * eh
        page.rectangle(px - 2, py - 2, 4, 4)
    page.fill()
    page.pop_state()


# ══════════════════════════════════════════════════════════════════════════════
#  HEATMAP GRID  (iteration × choice)
# ══════════════════════════════════════════════════════════════════════════════

_MAX_HEATMAP_COLS = 25


def render_heatmap_svg(
    decision_sequence: List[Optional[int]],
    option_ids: List[int],
    palette: Dict[str, str],
    *,
    cell: int = 16,
    gap: int = 2,
) -> str:
    """Render an iteration×choice heatmap as inline SVG."""
    if not decision_sequence or not option_ids:
        return ""

    vis = decision_sequence[:_MAX_HEATMAP_COLS]
    ni, no = len(vis), len(option_ids)
    lw, hh = 32, 14
    w = lw + ni * (cell + gap) + gap
    h = hh + no * (cell + gap) + gap
    bg = palette.get("bg_raised", "#A6ACCD")

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
    ]

    for i in range(ni):
        cx = lw + i * (cell + gap) + cell / 2
        parts.append(
            f'  <text x="{cx:.0f}" y="10" text-anchor="middle" '
            f'font-family="Helvetica,sans-serif" font-size="6" '
            f'fill="{palette["accent"]}">{i + 1}</text>'
        )

    for row, oid in enumerate(option_ids):
        ry = hh + row * (cell + gap)
        parts.append(
            f'  <text x="{lw - 4}" y="{ry + cell / 2 + 3:.0f}" '
            f'text-anchor="end" font-family="Courier New,monospace" '
            f'font-size="7" fill="{palette["accent"]}">{{{oid}}}</text>'
        )
        for col, dec in enumerate(vis):
            rx = lw + col * (cell + gap)
            chosen = dec == oid
            parts.append(
                f'  <rect x="{rx}" y="{ry}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{palette["success"] if chosen else bg}" '
                f'opacity="{"1" if chosen else "0.3"}" />'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def draw_heatmap_native(
    page: Any,
    page_height: float,
    x: float,
    y: float,
    decision_sequence: List[Optional[int]],
    option_ids: List[int],
    palette: Dict[str, str],
    *,
    cell: float = 13.0,
    gap: float = 2.0,
) -> Tuple[float, float]:
    """Draw iteration×choice heatmap via filled rectangles.

    Returns *(total_width, total_height)* of the drawn area.
    """
    if not decision_sequence or not option_ids:
        return (0.0, 0.0)

    vis = decision_sequence[:_MAX_HEATMAP_COLS]
    ni, no = len(vis), len(option_ids)
    lbl_off, hdr_off = 26.0, 12.0
    gx, gy = x + lbl_off, y + hdr_off
    tw = lbl_off + ni * (cell + gap)
    th = hdr_off + no * (cell + gap)

    s_rgb = _hex_to_rgb(palette["success"])
    d_rgb = _hex_to_rgb(palette.get("bg_raised", "#A6ACCD"))

    for row, oid in enumerate(option_ids):
        cell_top = gy + row * (cell + gap)
        for col, dec in enumerate(vis):
            cell_left = gx + col * (cell + gap)
            chosen = dec == oid
            rgb = s_rgb if chosen else d_rgb
            a = 1.0 if chosen else 0.3
            pdf_y = page_height - cell_top - cell
            page.push_state()
            page.set_color_rgb(rgb[0] * a, rgb[1] * a, rgb[2] * a)
            page.rectangle(cell_left, pdf_y, cell, cell)
            page.fill()
            page.pop_state()

    return (tw, th)
