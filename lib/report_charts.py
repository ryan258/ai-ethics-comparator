"""
Inline SVG chart rendering for printable HTML reports.

Renders inline SVG strings for report template injection.
Zero external dependencies.
"""

from __future__ import annotations

import math
from typing import Any

# ── Shared palette constants ─────────────────────────────────────────────────

PALETTE_DARK: dict[str, str] = {
    "bg": "#121212",
    "bg_raised": "#A6ACCD",
    "text": "#EBD2BE",
    "accent": "#A6ACCD",
    "success": "#98C379",
    "danger": "#E06C75",
}

PALETTE_LIGHT: dict[str, str] = {
    "bg": "#EBD2BE",
    "bg_raised": "#A6ACCD",
    "text": "#121212",
    "accent": "#A6ACCD",
    "success": "#98C379",
    "danger": "#E06C75",
}


# ══════════════════════════════════════════════════════════════════════════════
#  DONUT CHART
# ══════════════════════════════════════════════════════════════════════════════

def render_donut_svg(
    data: list[dict[str, Any]],
    palette: dict[str, str],
    *,
    width: int = 170,
    height: int = 170,
    outer_r: int = 74,
    inner_r: int = 46,
) -> str:
    """Render a donut chart as inline SVG for browser reports."""
    total = sum(d["value"] for d in data)
    if total == 0:
        return ""

    cx, cy = width / 2, height / 2
    parts: list[str] = [
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


# ══════════════════════════════════════════════════════════════════════════════
#  HEATMAP GRID  (iteration × choice)
# ══════════════════════════════════════════════════════════════════════════════

_MAX_HEATMAP_COLS = 25


def render_heatmap_svg(
    decision_sequence: list[int | None],
    option_ids: list[int],
    palette: dict[str, str],
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

    parts: list[str] = [
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
