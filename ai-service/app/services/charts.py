"""
Chart helpers for PDF report (report_generator).

All helpers return either a reportlab `Drawing` (vector, embeddable) or `None`
when there is no data to visualize. The report generator must handle `None`
gracefully (skip chart section).

Charts implemented:
    - tech_stack_bar_chart     : horizontal bar, count of frameworks/build_tools/db/runtime
    - controls_donut           : donut chart, recommended/optional/not_required
    - pipeline_stage_diagram   : connected boxes representing pipeline stages
    - risk_gauge               : half-circle gauge, 0-100, color-banded
    - severity_bar             : stacked horizontal bar, critical/high/medium/low
    - coverage_bar             : horizontal progress bar with label
"""

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, Wedge
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.graphics import renderPDF


# ── Color palette (matches generator.py H1/H2/H3 + severity) ──────────

NAVY = HexColor("#1a237e")
NAVY_LIGHT = HexColor("#3949ab")
INDIGO = HexColor("#e8eaf6")
GREY = HexColor("#9e9e9e")
LIGHT_GREY = HexColor("#f5f5f5")

SEVERITY_COLORS = {
    "critical": HexColor("#b71c1c"),
    "high": HexColor("#e65100"),
    "medium": HexColor("#f9a825"),
    "low": HexColor("#1565c0"),
}

STATUS_COLORS = {
    "success": HexColor("#2e7d32"),
    "failed": HexColor("#c62828"),
    "skipped": HexColor("#9e9e9e"),
}


# ── Section 1: Tech-stack horizontal bar ───────────────────────────────


def tech_stack_bar_chart(technologies: dict, width: float = 170 * mm, height: float = 45 * mm):
    """Horizontal bar showing count of frameworks, build_tools, db, runtime.

    `technologies` is the same dict the report uses for Section 1.1.
    Returns None if every category is empty.
    """
    categories = [
        ("Frameworks", technologies.get("frameworks") or []),
        ("Build Tools", technologies.get("build_tools") or []),
        ("Databases", [technologies.get("database")] if technologies.get("database") else []),
        ("Runtime", [technologies.get("runtime")] if technologies.get("runtime") else []),
    ]
    # Drop empty categories so the chart stays compact.
    categories = [(label, items) for label, items in categories if items]
    if not categories:
        return None

    drawing = Drawing(width, height)
    chart = HorizontalBarChart()
    # Leave enough room on the left for the longest category label
    # (e.g. "Build Tools" is 11 chars) plus a small padding, and on
    # the right for the bar-label (the count). 50mm / 35mm is more
    # generous than the old 80px / 18px which caused labels to spill
    # over the bar area.
    left_pad = 50 * mm
    right_pad = 18 * mm
    chart.x = left_pad
    chart.y = 14
    chart.width = width - left_pad - right_pad
    chart.height = height - 22
    chart.data = [[len(items) for _, items in categories]]
    chart.categoryAxis.categoryNames = [label for label, _ in categories]
    chart.bars[0].fillColor = NAVY
    chart.bars[0].strokeColor = NAVY
    chart.valueAxis.valueMin = 0
    # valueMax at exactly max count makes the rightmost bar touch the
    # right edge; add 1 so the bar-label has somewhere to go.
    chart.valueAxis.valueMax = max(len(items) for _, items in categories) + 1
    chart.valueAxis.valueStep = 1
    chart.barLabelFormat = "%d"
    chart.barLabels.fontSize = 8
    # Nudge is the bar-label distance from the bar end; the default
    # 6 caused labels to overflow on the right side of narrow charts.
    chart.barLabels.nudge = 10
    chart.barLabels.dx = 0
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.boxAnchor = "e"  # right-anchor category labels
    chart.valueAxis.labels.fontSize = 7
    chart.categoryAxis.labels.fillColor = NAVY_LIGHT
    chart.valueAxis.labels.fillColor = GREY

    drawing.add(chart)
    return drawing


# ── Section 2: Controls donut ──────────────────────────────────────────


def controls_donut(recommended: int, optional: int, not_required: int, width: float = 90 * mm, height: float = 55 * mm):
    """Donut chart showing distribution of control statuses.

    Returns None if total is 0.
    """
    total = recommended + optional + not_required
    if total == 0:
        return None

    drawing = Drawing(width, height)
    pie = Pie()
    pie.x = 10
    pie.y = 5
    pie.width = height - 10
    pie.height = height - 10
    pie.data = [recommended, optional, not_required]
    pie.labels = [f"Recommended ({recommended})", f"Optional ({optional})", f"Not Required ({not_required})"]
    pie.slices[0].fillColor = NAVY
    pie.slices[1].fillColor = HexColor("#5c6bc0")
    pie.slices[2].fillColor = HexColor("#c5cae9")
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = HexColor("#ffffff")
    # Donut: simple hole via inner radius approximation (reportlab Pie has no
    # direct innerRadius, so we leave as pie; the legend on the right carries
    # the per-slice meaning which is what matters in a PDF).
    pie.sideLabels = False
    drawing.add(pie)

    legend = Legend()
    legend.x = pie.width + 18
    legend.y = pie.height / 2
    legend.fontSize = 7
    legend.alignment = "right"
    legend.colorNamePairs = [
        (NAVY, [pie.labels[0]]),
        (HexColor("#5c6bc0"), [pie.labels[1]]),
        (HexColor("#c5cae9"), [pie.labels[2]]),
    ]
    drawing.add(legend)
    return drawing


# ── Section 3: Pipeline stage diagram ─────────────────────────────────


def pipeline_stage_diagram(stages: list, statuses: dict | None = None, width: float = 170 * mm, height: float = 30 * mm):
    """Connected boxes left-to-right representing pipeline stages.

    `stages`  : list of stage names (strings)
    `statuses`: optional dict mapping stage -> "success" | "failed" | "skipped"
                If absent, all stages are rendered in navy (planned/validated).

    Auto-wraps to a second row when stages > 6.
    Returns None if stages is empty.
    """
    if not stages:
        return None

    statuses = statuses or {}
    per_row = 6
    rows = [stages[i : i + per_row] for i in range(0, len(stages), per_row)]
    box_w = 28 * mm
    box_h = 12 * mm
    gap_x = 4 * mm
    gap_y = 8 * mm
    row_height = box_h + gap_y

    drawing = Drawing(width, height)
    for r, row in enumerate(rows):
        y = height - (r + 1) * row_height + gap_y / 2
        n = len(row)
        total_w = n * box_w + (n - 1) * gap_x
        x = (width - total_w) / 2
        for i, stage in enumerate(row):
            bx = x + i * (box_w + gap_x)
            status = statuses.get(stage, "")
            fill = STATUS_COLORS.get(status, NAVY)
            if not status:
                # Stage validated but not yet executed: lighter blue.
                fill = NAVY_LIGHT
            drawing.add(Rect(bx, y, box_w, box_h, fillColor=fill, strokeColor=NAVY, strokeWidth=0.5))
            label = _truncate(stage, 18)
            drawing.add(
                String(
                    bx + box_w / 2,
                    y + box_h / 2 - 2,
                    label,
                    fontSize=7,
                    fillColor=HexColor("#ffffff"),
                    textAnchor="middle",
                )
            )
            # Arrow to next box
            if i < n - 1:
                ax1 = bx + box_w
                ax2 = bx + box_w + gap_x
                ay = y + box_h / 2
                drawing.add(Line(ax1, ay, ax2, ay, strokeColor=NAVY, strokeWidth=0.8))
                # Simple arrowhead (triangle approximated by two short lines)
                drawing.add(Line(ax2, ay, ax2 - 2, ay + 1.5, strokeColor=NAVY, strokeWidth=0.8))
                drawing.add(Line(ax2, ay, ax2 - 2, ay - 1.5, strokeColor=NAVY, strokeWidth=0.8))
    return drawing


# ── Section 4: Risk gauge ──────────────────────────────────────────────


def risk_gauge(score: float | None, width: float = 100 * mm, height: float = 55 * mm):
    """Half-circle gauge for the OWASP risk score (0-100).

    Higher score = lower risk. Color band:
        0-25   CRITICAL (red)
        25-50  HIGH     (orange)
        50-75  MEDIUM   (yellow)
        75-100 LOW      (green)
    """
    if score is None:
        return None
    score = max(0.0, min(100.0, float(score)))

    drawing = Drawing(width, height)
    cx = width / 2
    cy = height * 0.55
    radius = min(width, height) * 0.42

    # Background bands (full 180° split into 4 quarters)
    bands = [
        (0, 25, HexColor("#b71c1c")),
        (25, 50, HexColor("#e65100")),
        (50, 75, HexColor("#f9a825")),
        (75, 100, HexColor("#2e7d32")),
    ]
    for lo, hi, color in bands:
        a0 = 180 - (lo / 100.0) * 180
        a1 = 180 - (hi / 100.0) * 180
        drawing.add(
            Wedge(
                cx,
                cy,
                radius,
                a1,
                a0,
                fillColor=color,
                strokeColor=HexColor("#ffffff"),
                strokeWidth=0.5,
            )
        )

    # Needle: angle maps 0 -> 180°, 100 -> 0°
    needle_angle_deg = 180 - (score / 100.0) * 180
    needle_len = radius * 0.85
    import math

    rad = math.radians(needle_angle_deg)
    nx = cx + needle_len * math.cos(rad)
    ny = cy + needle_len * math.sin(rad)
    drawing.add(Line(cx, cy, nx, ny, strokeColor=HexColor("#212121"), strokeWidth=2.5))
    drawing.add(Circle(cx, cy, 2.5, fillColor=HexColor("#212121"), strokeColor=HexColor("#212121")))

    # Score label
    drawing.add(
        String(
            cx,
            cy - 6,
            f"{score:.1f}",
            fontSize=18,
            fillColor=NAVY,
            textAnchor="middle",
            fontName="Helvetica-Bold",
        )
    )
    drawing.add(
        String(
            cx,
            cy - 16,
            "Risk Score / 100",
            fontSize=7,
            fillColor=NAVY_LIGHT,
            textAnchor="middle",
        )
    )

    # Level label below gauge
    if score <= 25:
        level = "CRITICAL"
        color = HexColor("#b71c1c")
    elif score <= 50:
        level = "HIGH"
        color = HexColor("#e65100")
    elif score <= 75:
        level = "MEDIUM"
        color = HexColor("#f9a825")
    else:
        level = "LOW"
        color = HexColor("#2e7d32")
    drawing.add(
        String(
            cx,
            4,
            level,
            fontSize=10,
            fillColor=color,
            textAnchor="middle",
            fontName="Helvetica-Bold",
        )
    )
    return drawing


# ── Section 4: Severity stacked bar ────────────────────────────────────


def severity_bar(critical: int, high: int, medium: int, low: int, width: float = 170 * mm, height: float = 12 * mm):
    """Stacked horizontal bar showing the severity distribution."""
    total = critical + high + medium + low
    if total == 0:
        return None

    drawing = Drawing(width, height)
    bar_x = 60
    bar_w = width - 70
    bar_h = 10
    bar_y = (height - bar_h) / 2

    segments = [
        (critical, SEVERITY_COLORS["critical"], "critical"),
        (high, SEVERITY_COLORS["high"], "high"),
        (medium, SEVERITY_COLORS["medium"], "medium"),
        (low, SEVERITY_COLORS["low"], "low"),
    ]
    cursor = bar_x
    # Right-aligned labels for each segment
    label_style_x = bar_x
    drawing.add(
        String(
            0,
            bar_y + bar_h / 2 - 2,
            "Findings",
            fontSize=7,
            fillColor=NAVY_LIGHT,
        )
    )
    for count, color, name in segments:
        if count <= 0:
            continue
        seg_w = (count / total) * bar_w
        drawing.add(Rect(cursor, bar_y, seg_w, bar_h, fillColor=color, strokeColor=HexColor("#ffffff"), strokeWidth=0.5))
        if seg_w > 14:
            drawing.add(
                String(
                    cursor + seg_w / 2,
                    bar_y + bar_h / 2 - 2,
                    f"{name} {count}",
                    fontSize=7,
                    fillColor=HexColor("#ffffff"),
                    textAnchor="middle",
                    fontName="Helvetica-Bold",
                )
            )
        cursor += seg_w
    drawing.add(
        String(
            bar_x + bar_w + 4,
            bar_y + bar_h / 2 - 2,
            f"Total: {total}",
            fontSize=7,
            fillColor=NAVY,
            fontName="Helvetica-Bold",
        )
    )
    return drawing


# ── Section 4: Coverage progress bar ───────────────────────────────────


def coverage_bar(label: str, pct: float | None, width: float = 170 * mm, height: float = 10 * mm):
    """Horizontal progress bar for a 0-100 coverage metric."""
    if pct is None:
        return None
    pct = max(0.0, min(100.0, float(pct)))

    if pct >= 70:
        color = HexColor("#2e7d32")
    elif pct >= 40:
        color = HexColor("#f9a825")
    else:
        color = HexColor("#c62828")

    drawing = Drawing(width, height)
    label_x = 0
    bar_x = 80
    bar_w = width - 110
    bar_h = 8
    bar_y = (height - bar_h) / 2

    drawing.add(
        String(
            label_x,
            bar_y + bar_h / 2 - 2,
            label,
            fontSize=8,
            fillColor=NAVY_LIGHT,
        )
    )
    drawing.add(
        Rect(
            bar_x,
            bar_y,
            bar_w,
            bar_h,
            fillColor=LIGHT_GREY,
            strokeColor=GREY,
            strokeWidth=0.3,
        )
    )
    fill_w = (pct / 100.0) * bar_w
    drawing.add(
        Rect(
            bar_x,
            bar_y,
            fill_w,
            bar_h,
            fillColor=color,
            strokeColor=None,
        )
    )
    drawing.add(
        String(
            bar_x + bar_w + 4,
            bar_y + bar_h / 2 - 2,
            f"{pct:.1f}%",
            fontSize=8,
            fillColor=color,
            fontName="Helvetica-Bold",
        )
    )
    return drawing


# ── Helpers ────────────────────────────────────────────────────────────


def _truncate(text: str, max_len: int) -> str:
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


# Re-export renderPDF so report_generator.py only needs one import.
__all__ = [
    "tech_stack_bar_chart",
    "controls_donut",
    "pipeline_stage_diagram",
    "risk_gauge",
    "severity_bar",
    "coverage_bar",
    "renderPDF",
]
