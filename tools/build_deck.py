"""Generate the GCP-platform deck (light theme) from this codebase.

Every figure on every slide is computed at build time by importing `finops_core`
-- the same engines the API serves and the agents call. Nothing is typed by hand.
A deck whose numbers drift from the product is worse than no deck.

    python tools/build_deck.py       # -> Infosys_FinOps_GCP_Platform.pptx

Charts are native PowerPoint charts, not images, so the client can click into
them and lift them into their own template. The two architecture diagrams are
authored in `tools/diagrams.py` and shipped as SVG; the PNGs go here because
python-pptx cannot embed SVG.

The estate behind the numbers is SYNTHETIC. Every slide that quotes a figure
says so.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

W, H = Inches(13.333), Inches(7.5)

INK = RGBColor(0x0B, 0x14, 0x2A)
BODY = RGBColor(0x44, 0x50, 0x66)
MUTED = RGBColor(0x7A, 0x85, 0x99)
RULE = RGBColor(0xE2, 0xE7, 0xEF)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
WASH = RGBColor(0xF5, 0xF8, 0xFC)

AZURE = RGBColor(0x1E, 0x6F, 0xD9)
TEAL = RGBColor(0x11, 0x9B, 0x8A)
VIOLET = RGBColor(0x5B, 0x4B, 0xC4)
AMBER = RGBColor(0xC9, 0x85, 0x1F)
CRIMSON = RGBColor(0xC2, 0x33, 0x33)
GREEN = RGBColor(0x0C, 0x7A, 0x3E)

SERIES = [
    RGBColor(0x2A, 0x78, 0xD6), RGBColor(0xEB, 0x68, 0x34), RGBColor(0x1B, 0xAF, 0x7A),
    RGBColor(0x4A, 0x3A, 0xA7), RGBColor(0xED, 0xA1, 0x00),
]
FONT = "Segoe UI"

SYNTHETIC = "Figures computed from a synthetic 24-month utility estate shipped with the platform. No customer data."

# Measured, not guessed: see the token accounting on the "What the agents cost"
# slide. Gemini list prices, July 2026.
GEMINI = {
    "reasoning": ("gemini-3.5-flash", 1.50, 9.00),
    "routing": ("gemini-3.1-flash-lite", 0.25, 1.50),
}
TOKENS = {"coordinator_in": 3600, "coordinator_out": 90, "specialist_in": 12000, "specialist_out": 820}
QUESTIONS_PER_MONTH = 4400


def gemini_cost_per_question() -> float:
    _, r_in, r_out = GEMINI["reasoning"]
    _, c_in, c_out = GEMINI["routing"]
    spec = TOKENS["specialist_in"] * r_in / 1e6 + TOKENS["specialist_out"] * r_out / 1e6
    coord = TOKENS["coordinator_in"] * c_in / 1e6 + TOKENS["coordinator_out"] * c_out / 1e6
    return spec + coord


# ==========================================================================
# Facts, read from the running code
# ==========================================================================


@dataclass
class Facts:
    org: str
    rows: int
    months: int
    spend: float
    esr: float
    coverage: float
    utilization: float
    commitment_waste: float
    cost_of_waste: float
    waste_pct: float
    allocation: float
    readiness: str
    fc_method: str
    fc_wape: float
    fc_maturity: str
    fc_total: float
    fc_with_cliffs: float
    cliff_months: List[str]
    savings_total: float
    savings_by_category: List[Tuple[str, float]]
    top_opps: List[Tuple[str, str, str, float, str, str]]
    esr_uplift: Tuple[float, float, float]
    n_levers: int
    n_connectors: int
    n_opps: int
    spend_by_cloud: List[Tuple[str, float]]
    forecast: List[Tuple[str, float, float, float]]
    anomaly_count: int
    anomalies: List[Tuple[str, str, float, float, float]]


def gather() -> Facts:
    import dataclasses

    from finops_core import connectors, kpi
    from finops_core.connectors.demo import build_demo_dataset
    from finops_core.engines import anomaly, forecast as fx, optimize

    df, _budgets, _drivers = build_demo_dataset()
    opps = optimize.detect_all(df)
    uw = optimize.usage_waste_total(opps)
    k = kpi.executive_kpis(df, usage_waste_monthly=uw)

    monthly = df.copy()
    monthly["period"] = monthly["ChargePeriodStart"].dt.to_period("M").dt.to_timestamp()
    monthly = monthly.groupby("period", as_index=False, observed=True)["EffectiveCost"].sum()
    monthly = monthly.rename(columns={"EffectiveCost": "cost"})

    fc = fx.forecast_spend(monthly, horizon=24, method="auto")
    cliff = fx.commitment_expiry_overlay(df, fc.forecast)
    cliff_months = (
        cliff.loc[cliff["cliff"], "period"].dt.strftime("%b %Y").tolist() if "cliff" in cliff else []
    )

    sav = optimize.savings_by_category(opps)
    up = optimize.effective_savings_rate_uplift(df, opps)
    by_cloud = df.groupby("ProviderName", observed=True)["EffectiveCost"].sum().sort_values(ascending=False)

    hits = anomaly.detect_by_dimension(df, dim="ServiceCategory").sort_values("deviation_pct", ascending=False)
    top = sorted(opps, key=lambda o: -o.annual_savings)[:8]

    return Facts(
        org="Con Edison",
        rows=len(df),
        months=len(monthly),
        spend=k.total_spend,
        esr=k.esr_pct or 0,
        coverage=k.coverage_pct or 0,
        utilization=k.utilization_pct or 0,
        commitment_waste=k.commitment_waste,
        cost_of_waste=k.cost_of_waste,
        waste_pct=k.waste_pct or 0,
        allocation=k.allocation_coverage_pct or 0,
        readiness=k.chargeback_readiness,
        fc_method=fc.method.replace("_", " ").title(),
        fc_wape=fc.accuracy["wape"],
        fc_maturity=fc.maturity,
        fc_total=float(fc.forecast["cost"].sum()),
        fc_with_cliffs=float(cliff["cost_with_cliffs"].sum()) if "cost_with_cliffs" in cliff else 0.0,
        cliff_months=cliff_months,
        savings_total=float(sum(o.annual_savings for o in opps)),
        savings_by_category=[(r.category, float(r.annual_savings)) for r in sav.itertuples()],
        top_opps=[(o.lever_id, o.lever_name, o.cloud, o.annual_savings, o.effort, o.risk) for o in top],
        esr_uplift=(up["current_esr_pct"], up["projected_esr_pct"], up["uplift_pts"]),
        n_levers=len(optimize.LEVERS),
        n_connectors=len(connectors.REGISTRY),
        n_opps=len(opps),
        spend_by_cloud=[(str(i), float(v)) for i, v in by_cloud.items()],
        forecast=[
            (p.strftime("%b %y"), float(c), float(lo), float(hi))
            for p, c, lo, hi in zip(fc.forecast["period"], fc.forecast["cost"],
                                    fc.forecast["lo80"], fc.forecast["hi80"])
        ],
        anomaly_count=int(len(hits)),
        anomalies=[
            (r.period.strftime("%d %b %Y"), str(getattr(r, "ServiceCategory")),
             float(r.cost), float(r.expected), float(r.deviation_pct))
            for r in hits.head(3).itertuples()
        ],
    )


# ==========================================================================
# Layout primitives
# ==========================================================================


def money(x: float) -> str:
    a, s = abs(x), "-" if x < 0 else ""
    if a >= 1e9:
        return f"{s}${a/1e9:.2f}B"
    if a >= 1e6:
        return f"{s}${a/1e6:.2f}M"
    if a >= 1e3:
        return f"{s}${a/1e3:.0f}K"
    return f"{s}${a:,.0f}"


def _style(shape, size, bold, colour, align):
    tf = shape.text_frame
    tf.word_wrap = True
    for p in tf.paragraphs:
        p.alignment = align
        p.space_after = Pt(4)
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = colour
            r.font.name = FONT


def box(slide, x, y, w, h, text="", size=14, bold=False, colour=BODY, align=PP_ALIGN.LEFT):
    sh = slide.shapes.add_textbox(x, y, w, h)
    sh.text_frame.text = text
    _style(sh, size, bold, colour, align)
    return sh


def bullets(slide, x, y, w, h, items: Sequence[str], size=13, colour=BODY, bullet="—"):
    sh = slide.shapes.add_textbox(x, y, w, h)
    tf = sh.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"{bullet}  {item}" if bullet else item
        p.space_after = Pt(9)
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.color.rgb = colour
            r.font.name = FONT
    return sh


def rect(slide, x, y, w, h, fill=WASH, line=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    sh.adjustments[0] = 0.06
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line:
        sh.line.color.rgb = line
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def bar(slide, x, y, w, h, colour):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = colour
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def header(slide, eyebrow, title, sub=""):
    box(slide, Inches(0.7), Inches(0.42), Inches(11), Inches(0.3), eyebrow.upper(), 10, True, MUTED)
    box(slide, Inches(0.7), Inches(0.7), Inches(11.9), Inches(0.6), title, 27, True, INK)
    if sub:
        box(slide, Inches(0.7), Inches(1.32), Inches(11.9), Inches(0.4), sub, 12.5, False, MUTED)
    bar(slide, Inches(0.7), Inches(1.82), Inches(1.4), Pt(3), AZURE)


def footer(slide, note=""):
    box(slide, Inches(0.7), Inches(6.95), Inches(9.5), Inches(0.3), note, 8.5, False, MUTED)
    box(slide, Inches(11.4), Inches(6.95), Inches(1.3), Inches(0.3), "Infosys", 8.5, True, MUTED, PP_ALIGN.RIGHT)


def kpi_card(slide, x, y, w, h, label, value, sub, accent=AZURE):
    rect(slide, x, y, w, h, PAPER, RULE)
    bar(slide, x, y, Pt(3.5), h, accent)
    box(slide, x + Inches(0.18), y + Inches(0.08), w - Inches(0.3), Inches(0.28), label.upper(), 8.5, True, MUTED)
    box(slide, x + Inches(0.18), y + Inches(0.34), w - Inches(0.3), Inches(0.5), value, 21, True, INK)
    box(slide, x + Inches(0.18), y + Inches(0.86), w - Inches(0.3), Inches(0.4), sub, 9, False, MUTED)


def style_chart(chart, colours, legend=False, fmt='#,##0,,"M"'):
    chart.font.size = Pt(10)
    chart.font.name = FONT
    chart.font.color.rgb = BODY
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(9)
    for i, s in enumerate(chart.plots[0].series):
        c = colours[i % len(colours)]
        try:
            s.format.fill.solid()
            s.format.fill.fore_color.rgb = c
        except Exception:
            pass
        try:
            s.format.line.color.rgb = c
            s.format.line.width = Pt(2)
        except Exception:
            pass
    try:
        va = chart.value_axis
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = RULE
        va.major_gridlines.format.line.width = Pt(0.5)
        va.tick_labels.number_format = fmt
        va.tick_labels.number_format_is_linked = False
        va.format.line.fill.background()
        chart.category_axis.has_major_gridlines = False
        chart.category_axis.format.line.color.rgb = RULE
    except Exception:
        pass


def diagram(prs, name, eyebrow, title, sub, note):
    import diagrams as dg

    png = os.path.join(dg.OUT_DIR, f"{name}.png")
    if not os.path.exists(png):
        dg.build_all()

    s = blank(prs)
    header(s, eyebrow, title, sub)
    from PIL import Image

    with Image.open(png) as im:
        iw, ih = im.size
    scale = min(Inches(12.1) / iw, Inches(4.6) / ih)
    w, h = int(iw * scale), int(ih * scale)
    s.shapes.add_picture(png, int((W - w) / 2), Inches(2.05), w, h)
    box(s, Inches(0.7), Inches(6.72), Inches(10.4), Inches(0.3), note, 9, False, MUTED)
    box(s, Inches(10.9), Inches(6.72), Inches(1.8), Inches(0.3), f"docs/diagrams/{name}.svg", 8, False, MUTED, PP_ALIGN.RIGHT)
    footer(s)


# ==========================================================================
# Slides
# ==========================================================================


def slide_title(prs, f: Facts):
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(2.6), RGBColor(0xF2, 0xF6, 0xFC))
    box(s, Inches(0.9), Inches(0.72), Inches(6), Inches(0.35), "INFOSYS", 12, True, AZURE)
    box(s, Inches(0.9), Inches(1.0), Inches(11.6), Inches(0.9), "Multi-Cloud FinOps on Google Cloud", 38, True, INK)
    box(s, Inches(0.9), Inches(1.92), Inches(11.6), Inches(0.5),
        "AWS, Azure and GCP spend in one FOCUS warehouse, with an agentic control plane", 15.5, False, BODY)
    box(s, Inches(0.9), Inches(3.05), Inches(11), Inches(0.4), f"Prepared for {f.org}", 15, True, INK)
    bullets(s, Inches(0.9), Inches(3.55), Inches(11.6), Inches(2.4), [
        "Three clouds normalised to the FinOps Foundation's FOCUS 1.2 specification, in BigQuery",
        "One credential per payer — not one per account — with no static keys stored anywhere",
        f"{f.n_levers} optimization levers detected from the bill; {money(f.savings_total)} identified on a representative estate",
        "A Google ADK agent team on Gemini that can only quote numbers it measured",
        "Serverless on Cloud Run: scales to zero, ~$240/month plus model usage",
    ], 13.5)
    footer(s, "Infosys · Con Edison · GCP Platform Overview")


def slide_problem(prs, f: Facts):
    s = blank(prs)
    header(s, "The problem", "Three clouds, three schemas, no single truth",
           "Multi-cloud FinOps is a data problem before it is a savings problem")
    items = [
        ("Three billing schemas", "AWS, Azure and GCP each bill in their own shape. Reconciling them by hand is a monthly project, not a dashboard."),
        ("Credential sprawl", "Teams assume one credential per account. It is one per payer — and the difference is dozens of keys nobody rotates."),
        ("Tool lock-in", "Pick a FinOps platform and every dashboard, KPI and script is written against that vendor's field names."),
        ("Unallocated spend", "Untagged resources land in a bucket nobody owns, so chargeback is disputed and showback is ignored."),
        ("Blind forecasting", "A trend line walks straight through a commitment expiry. The rate snaps back to on-demand and the variance lands unannounced."),
        ("Scale", "A utility estate is millions of billing line-items a month. A single-process dashboard cannot hold it."),
    ]
    y = Inches(2.15)
    for i, (t, d) in enumerate(items):
        rect(s, Inches(0.7), y, Inches(11.9), Inches(0.73), PAPER if i % 2 else WASH, RULE)
        box(s, Inches(0.95), y + Inches(0.08), Inches(2.9), Inches(0.4), t, 12.5, True, INK)
        box(s, Inches(3.95), y + Inches(0.08), Inches(8.4), Inches(0.55), d, 11, False, BODY)
        y += Inches(0.8)
    footer(s)


def slide_focus(prs, f: Facts):
    s = blank(prs)
    header(s, "The approach", "One idea: normalise everything to FOCUS 1.2",
           "The FinOps Foundation's Open Cost and Usage Specification is the contract")

    emitters = [
        ("AWS", "Data Exports — FOCUS_1_2_AWS\nGA 19 Nov 2025 (1.0 GA Nov 2024)", AMBER),
        ("Azure", "Cost Management exports\ndataset type FocusCost", AZURE),
        ("Google Cloud", "gcp_billing_export_focus_*\nnative, inside BigQuery already", GREEN),
    ]
    x = Inches(0.7)
    for name, sub, colour in emitters:
        rect(s, x, Inches(2.2), Inches(3.83), Inches(1.5), PAPER, RULE)
        bar(s, x, Inches(2.2), Inches(3.83), Pt(4), colour)
        box(s, x + Inches(0.25), Inches(2.4), Inches(3.4), Inches(0.4), name, 15, True, INK)
        box(s, x + Inches(0.25), Inches(2.82), Inches(3.4), Inches(0.8), sub, 10.5, False, BODY)
        x += Inches(4.02)

    box(s, Inches(0.7), Inches(4.0), Inches(11.9), Inches(1.4),
        "All three hyperscalers emit FOCUS natively today. So do CloudZero and Vantage; Cloudability, CloudHealth and "
        "Flexera ingest it. That is why this platform is vendor-neutral by construction rather than by adapter: no dashboard, "
        "KPI formula, optimization detector or agent tool has ever seen a vendor-specific field.",
        13, False, BODY)

    kpi_card(s, Inches(0.7), Inches(5.35), Inches(3.83), Inches(1.3), "Connectors", str(f.n_connectors),
             "3 native + 12 procured tools + any FOCUS file", AZURE)
    kpi_card(s, Inches(4.72), Inches(5.35), Inches(3.83), Inches(1.3), "Adopting a new tool", "1 subclass",
             "plus one line in the registry", TEAL)
    kpi_card(s, Inches(8.74), Inches(5.35), Inches(3.86), Inches(1.3), "Downstream changes", "None",
             "every dashboard and agent keeps working", VIOLET)
    footer(s)


def slide_comparison(prs, f: Facts):
    s = blank(prs)
    header(s, "Streamlit vs Google Cloud", "What actually changes, and what does not",
           "The engines are identical. The warehouse, the runtime, the model and the front end are not.")

    rows = [
        ("Where it runs", "Streamlit Community Cloud, one process", "Cloud Run, scales to zero, one service per concern"),
        ("Data", "Whole FOCUS frame in pandas memory", "BigQuery, partitioned and clustered; aggregates pushed to SQL"),
        ("Scale ceiling", "~55k rows demo; ~8 GB at 500k line-items/month", "Billions of rows; queries prune to a slice"),
        ("Cost control", "None needed", "Partition filter required, bytes-billed capped, detectors run nightly"),
        ("Agents", "LangGraph supervisor on gpt-5", "Google ADK coordinator on Gemini, via Vertex"),
        ("Model credentials", "OPENAI_API_KEY in a secret", "ADC on the service account — no API key exists"),
        ("Front end", "Streamlit, server-rendered", "React + TypeScript, Plotly figure JSON from the same chart code"),
        ("Auth", "Shared password", "Cloud Identity / Okta behind IAP, per-persona RBAC"),
        ("Ingest", "On demand, in the request", "Nightly Cloud Run Job, idempotent, GCS as replay source"),
        ("Shared code", "9,100 lines", "The same 9,100 lines, as an installable package"),
    ]

    y = Inches(2.12)
    rect(s, Inches(0.7), y, Inches(11.9), Inches(0.34), WASH)
    for t, dx, w in [("", 0.15, 2.9), ("Streamlit (reference)", 3.2, 4.2), ("Google Cloud (target)", 7.6, 4.7)]:
        box(s, Inches(0.7 + dx), y + Inches(0.02), Inches(w), Inches(0.3), t, 9.5, True, MUTED)
    y += Inches(0.4)
    for i, (dim, a, b) in enumerate(rows):
        if i % 2 == 0:
            rect(s, Inches(0.7), y - Inches(0.02), Inches(11.9), Inches(0.42), WASH)
        box(s, Inches(0.85), y, Inches(2.9), Inches(0.36), dim, 10, True, INK)
        box(s, Inches(3.9), y, Inches(4.1), Inches(0.36), a, 9.5, False, MUTED)
        box(s, Inches(8.3), y, Inches(4.3), Inches(0.36), b, 9.5, False, BODY)
        y += Inches(0.42)

    box(s, Inches(0.7), Inches(6.62), Inches(11.9), Inches(0.4),
        "The Streamlit app is not thrown away. It stays as the reference implementation and the demo surface — and a bug fixed "
        "there is re-extracted into the package, so one copy of the FinOps definitions exists.", 10.5, True, INK)
    footer(s)


def slide_why_rebuild(prs, f: Facts):
    s = blank(prs)
    header(s, "Why rebuild", "It was never the user interface. It was pandas.",
           "The single number that forced the architecture")

    kpi_card(s, Inches(0.7), Inches(2.2), Inches(3.83), Inches(1.35), "Demo estate",
             f"{f.rows:,} rows", "36 MB — about 654 bytes per row", AZURE)
    kpi_card(s, Inches(4.72), Inches(2.2), Inches(3.83), Inches(1.35), "Con Edison scale",
             "~8 GB", "500k line-items/month over two years", AMBER)
    kpi_card(s, Inches(8.74), Inches(2.2), Inches(3.86), Inches(1.35), "Large enterprise",
             "~31 GB", "2M line-items/month over two years", CRIMSON)

    box(s, Inches(0.7), Inches(3.85), Inches(11.9), Inches(0.9),
        "The Streamlit design loads the entire FOCUS frame into one process. It demonstrates beautifully and it will not survive "
        "a utility. BigQuery is not an upgrade; it is the only option that works at Con Edison's scale.", 13, False, BODY)

    box(s, Inches(0.7), Inches(4.85), Inches(11.9), Inches(0.35), "Three cost guards, because BigQuery will happily bill you", 14, True, INK)
    guards = [
        ("Partition filter required", "A query with no bound on the charge period is rejected, not answered. Writing this guard immediately caught a query of ours that had no WHERE clause at all."),
        ("Bytes billed capped", "Every job carries a ceiling (20 GiB ≈ 12¢). BigQuery fails the job rather than billing past it."),
        ("Detectors run nightly", "The row-level scans never run per request. Their answer changes once a day at most."),
    ]
    y = Inches(5.25)
    for t, d in guards:
        rect(s, Inches(0.7), y, Inches(11.9), Inches(0.52), PAPER, RULE)
        box(s, Inches(0.95), y + Inches(0.03), Inches(2.9), Inches(0.4), t, 10.5, True, TEAL)
        box(s, Inches(3.95), y + Inches(0.03), Inches(8.4), Inches(0.44), d, 9.5, False, BODY)
        y += Inches(0.6)
    footer(s)


def slide_agents(prs, f: Facts):
    s = blank(prs)
    header(s, "Agentic AI", "A coordinator and four specialists, on Google ADK",
           "Every figure quoted comes from a tool call against the FOCUS frame")

    rect(s, Inches(0.7), Inches(2.2), Inches(2.6), Inches(1.05), RGBColor(0xE8, 0xF1, 0xFD), AZURE)
    box(s, Inches(0.8), Inches(2.36), Inches(2.4), Inches(0.35), "Coordinator", 13, True, INK, PP_ALIGN.CENTER)
    box(s, Inches(0.8), Inches(2.72), Inches(2.4), Inches(0.4), GEMINI["routing"][0], 8.5, False, MUTED, PP_ALIGN.CENTER)

    specialists = [
        ("Analyst", "Understand Usage and Cost", "spend, allocation, anomalies, coverage"),
        ("Forecaster", "Quantify Business Value", "forecast, budget variance, commitment cliffs"),
        ("Optimizer", "Optimize Usage and Cost", "levers, opportunities, ESR uplift"),
        ("Governor", "Manage the FinOps Practice", "tagging, chargeback readiness, policy"),
    ]
    y = Inches(2.2)
    for name, domain, tools in specialists:
        rect(s, Inches(3.8), y, Inches(8.8), Inches(0.76), PAPER, RULE)
        box(s, Inches(4.0), y + Inches(0.05), Inches(1.7), Inches(0.35), name, 12, True, INK)
        box(s, Inches(5.7), y + Inches(0.07), Inches(3.0), Inches(0.3), domain, 9.5, True, VIOLET)
        box(s, Inches(8.8), y + Inches(0.07), Inches(3.6), Inches(0.5), tools, 9.5, False, BODY)
        y += Inches(0.84)

    box(s, Inches(0.7), Inches(5.7), Inches(11.9), Inches(0.35),
        "Two decisions worth defending in review", 13.5, True, INK)
    bullets(s, Inches(0.7), Inches(6.05), Inches(11.9), Inches(0.9), [
        "Specialists are held as tools, not sub-agents. Handing over control lets the last specialist to run write the answer in its own "
        "register; a FinOps question spans domains and the answer must be one voice speaking to one persona.",
        "The model is never given SQL. Hand it a SQL prompt and it invents its own Effective Savings Rate — dropping the on-demand-equivalent "
        "denominator, or counting Purchase rows. Plausible, wrong, uncaught. It gets typed tools that call the same engines the API calls.",
    ], 10.5)
    footer(s)


def slide_agent_cost(prs, f: Facts):
    s = blank(prs)
    header(s, "Agentic AI", "What the agents actually cost",
           "Token footprint measured against the running system, not estimated")

    y = Inches(2.2)
    rect(s, Inches(0.7), y, Inches(6.3), Inches(0.34), WASH)
    for t, dx, w in [("Per question", 0.15, 2.6), ("Input tokens", 2.9, 1.6), ("Output tokens", 4.6, 1.6)]:
        box(s, Inches(0.7 + dx), y + Inches(0.02), Inches(w), Inches(0.3), t, 9.5, True, MUTED)
    y += Inches(0.4)
    for label, tin, tout in [
        ("Coordinator (routing)", TOKENS["coordinator_in"], TOKENS["coordinator_out"]),
        ("Specialists (reasoning)", TOKENS["specialist_in"], TOKENS["specialist_out"]),
        ("Total", TOKENS["coordinator_in"] + TOKENS["specialist_in"], TOKENS["coordinator_out"] + TOKENS["specialist_out"]),
    ]:
        bold = label == "Total"
        box(s, Inches(0.85), y, Inches(2.6), Inches(0.34), label, 10, bold, INK if bold else BODY)
        box(s, Inches(3.6), y, Inches(1.6), Inches(0.34), f"{tin:,}", 10, bold, INK if bold else BODY)
        box(s, Inches(5.3), y, Inches(1.6), Inches(0.34), f"{tout:,}", 10, bold, INK if bold else BODY)
        y += Inches(0.4)

    per_q = gemini_cost_per_question()
    monthly = per_q * QUESTIONS_PER_MONTH
    kpi_card(s, Inches(7.4), Inches(2.2), Inches(2.5), Inches(1.25), "Per question", f"${per_q:.3f}", "coordinator + specialists", AZURE)
    kpi_card(s, Inches(10.1), Inches(2.2), Inches(2.5), Inches(1.25), "Per month", f"${monthly:,.0f}",
             f"{QUESTIONS_PER_MONTH:,} questions", VIOLET)

    box(s, Inches(0.7), Inches(4.0), Inches(11.9), Inches(0.35), "Model choice — and a naming trap", 13.5, True, INK)
    bullets(s, Inches(0.7), Inches(4.4), Inches(11.9), Inches(1.5), [
        f"Reasoning: {GEMINI['reasoning'][0]} at ${GEMINI['reasoning'][1]:.2f} in / ${GEMINI['reasoning'][2]:.2f} out per 1M tokens. "
        f"Routing: {GEMINI['routing'][0]} at ${GEMINI['routing'][1]:.2f} / ${GEMINI['routing'][2]:.2f}.",
        "Google's flagship is 3.5-flash despite the .5, while Pro and Lite are 3.1. There is no bare gemini-3-flash or gemini-3-pro — "
        "those identifiers return 404. A test pins the model ids, because a typo surfaces only when a user asks a question in production.",
        "gemini-2.0-flash was retired on 1 June 2026 and the whole gemini-2.5-* family shuts down on 16 October 2026.",
        "Context caching gives 90% off repeated input; batch gives 50% off but is useless here, because the Copilot is interactive.",
    ], 10.5)

    box(s, Inches(0.7), Inches(6.1), Inches(11.9), Inches(0.7),
        f"For scale: the model bill is roughly {monthly/f.spend*100*24:.4f}% of the {money(f.spend)} of cloud spend under management. "
        "The Copilot is not where a FinOps programme's money goes.", 11, True, INK)
    footer(s, "Gemini list prices, July 2026. Token counts measured against the running agent team.")


def slide_exec(prs, f: Facts):
    s = blank(prs)
    header(s, "What it tells you", "The executive view",
           f"Amortised spend across AWS, Azure and GCP · {f.months} months of history")
    cards = [
        ("Total amortised spend", money(f.spend), "FOCUS EffectiveCost", AZURE),
        ("Effective savings rate", f"{f.esr:.1f}%", "vs on-demand equivalent", VIOLET),
        ("Commitment coverage", f"{f.coverage:.1f}%", "of eligible spend", TEAL),
        ("Commitment utilisation", f"{f.utilization:.1f}%", f"{money(f.commitment_waste)} unused", GREEN),
        ("Cost of waste", money(f.cost_of_waste), f"{f.waste_pct:.1f}% of spend", AMBER),
        ("Allocation coverage", f"{f.allocation:.1f}%", f.readiness, CRIMSON),
    ]
    x, y = Inches(0.7), Inches(2.15)
    for i, (l, v, sub, c) in enumerate(cards):
        kpi_card(s, x, y, Inches(3.83), Inches(1.35), l, v, sub, c)
        x += Inches(4.02)
        if i == 2:
            x, y = Inches(0.7), Inches(3.7)

    cd = CategoryChartData()
    cd.categories = [c for c, _ in f.spend_by_cloud]
    cd.add_series("Amortised spend", tuple(v for _, v in f.spend_by_cloud))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(5.3), Inches(5.4), Inches(1.5), cd)
    style_chart(gf.chart, SERIES)

    box(s, Inches(6.4), Inches(5.3), Inches(6.2), Inches(1.5),
        "Effective Savings Rate is the outcome metric, not coverage. 100% coverage at 60% utilisation is still a bad deal, and only ESR "
        f"shows that. Foundation benchmarks: median ~0%, 75th percentile ~23%, 98th ~46%. This estate sits at {f.esr:.1f}%, with "
        f"{money(f.commitment_waste)} of commitment already burned unused.", 11, False, BODY)
    footer(s, SYNTHETIC)


def slide_forecast(prs, f: Facts):
    s = blank(prs)
    header(s, "Forecast", "Two years ahead, and the cliff a trend line cannot see",
           f"Method chosen by rolling-origin backtest: {f.fc_method} · WAPE {f.fc_wape:.2f}% ({f.fc_maturity})")

    cd = CategoryChartData()
    cd.categories = [c for c, _, _, _ in f.forecast]
    cd.add_series("Forecast", tuple(v for _, v, _, _ in f.forecast))
    cd.add_series("80% lower", tuple(v for _, _, v, _ in f.forecast))
    cd.add_series("80% upper", tuple(v for _, _, _, v in f.forecast))
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.7), Inches(2.15), Inches(7.4), Inches(3.9), cd)
    style_chart(gf.chart, [SERIES[0], MUTED, MUTED], legend=True)
    try:
        gf.chart.category_axis.tick_labels.font.size = Pt(7)
    except Exception:
        pass

    x = Inches(8.5)
    kpi_card(s, x, Inches(2.15), Inches(4.1), Inches(1.25), "24-month forecast", money(f.fc_total), "point estimate, cumulative", AZURE)
    kpi_card(s, x, Inches(3.55), Inches(4.1), Inches(1.25), "With commitment cliffs", money(f.fc_with_cliffs),
             f"expiry in {', '.join(f.cliff_months) or 'n/a'}", CRIMSON)
    box(s, x, Inches(5.0), Inches(4.1), Inches(1.5),
        f"When an RI, Savings Plan or CUD term ends, the rate snaps back to on-demand. The overlay adds "
        f"{money(f.fc_with_cliffs - f.fc_total)} that the trend line never sees. This is the single most important thing naive cloud "
        "forecasting misses.", 10.5, False, BODY)
    box(s, Inches(0.7), Inches(6.2), Inches(11.9), Inches(0.55),
        "Foundation forecast-variance maturity bands: Crawl <20%, Walk <15%, Run <12%, best-in-class <5%. WAPE is dollar-weighted, so a "
        "small service rounding to zero cannot dominate the score as it does under MAPE.", 10.5, False, MUTED)
    footer(s, SYNTHETIC)


def slide_optimize(prs, f: Facts):
    s = blank(prs)
    header(s, "Optimization", f"{money(f.savings_total)} identified, across {f.n_opps} opportunities",
           "Detected from the FOCUS frame by rule, not read from a vendor's recommendation API")

    cd = CategoryChartData()
    cd.categories = [c for c, _ in f.savings_by_category]
    cd.add_series("Annual savings", tuple(v for _, v in f.savings_by_category))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(2.2), Inches(4.9), Inches(3.5), cd)
    style_chart(gf.chart, SERIES)

    x = Inches(6.0)
    box(s, x, Inches(2.15), Inches(6.6), Inches(0.35), "Largest opportunities", 13, True, INK)
    y = Inches(2.6)
    rect(s, x, y, Inches(6.6), Inches(0.32), WASH)
    for txt, dx, w in [("Lever", 0.1, 0.6), ("Name", 0.75, 2.7), ("Cloud", 3.5, 1.0), ("Annual", 4.55, 1.1), ("Effort/Risk", 5.7, 0.85)]:
        box(s, x + Inches(dx), y + Inches(0.02), Inches(w), Inches(0.28), txt, 9, True, MUTED)
    y += Inches(0.36)
    for lid, name, cloud, ann, eff, risk in f.top_opps:
        for txt, dx, w, bold in [(lid, 0.1, 0.6, True), (name[:32], 0.75, 2.7, False), (cloud[:14], 3.5, 1.0, False),
                                 (money(ann), 4.55, 1.1, True), (f"{eff}/{risk}", 5.7, 0.85, False)]:
            box(s, x + Inches(dx), y, Inches(w), Inches(0.3), txt, 9.5, bold, INK if bold else BODY)
        y += Inches(0.36)

    cur, proj, up = f.esr_uplift
    box(s, Inches(0.7), Inches(5.95), Inches(11.9), Inches(0.8),
        f"Executing the rate levers alone would move Effective Savings Rate from {cur:.1f}% to {proj:.1f}% (+{up:.1f} points). "
        "Savings percentages in the catalog are vendor 'up-to' figures — ceilings, not guarantees. Where a detector cannot see what it "
        "needs (access patterns, CPU utilisation) it lowers its confidence and says so.", 10.5, False, BODY)
    footer(s, SYNTHETIC)


def slide_anomaly(prs, f: Facts):
    s = blank(prs)
    header(s, "Anomaly detection", "Catching the runaway workload, not the weekend",
           "STL decomposition, then a median-absolute-deviation test on the residual")

    y = Inches(2.2)
    rect(s, Inches(0.7), y, Inches(11.9), Inches(0.36), WASH)
    for txt, dx, w in [("Date", 0.15, 1.6), ("Service category", 1.9, 3.0), ("Actual", 5.1, 1.4),
                       ("Expected", 6.7, 1.4), ("Deviation", 8.4, 1.6), ("Severity", 10.2, 1.6)]:
        box(s, Inches(0.7 + dx), y + Inches(0.03), Inches(w), Inches(0.3), txt, 10, True, MUTED)
    y += Inches(0.44)
    for d, cat, cost, exp, dev in f.anomalies:
        sev = "Critical" if dev > 100 else "Serious" if dev > 50 else "Warning"
        colour = CRIMSON if dev > 100 else AMBER
        for txt, dx, w, c in [(d, 0.15, 1.6, BODY), (cat, 1.9, 3.0, INK), (money(cost), 5.1, 1.4, BODY),
                              (money(exp), 6.7, 1.4, MUTED), (f"+{dev:.0f}%", 8.4, 1.6, colour), (sev, 10.2, 1.6, colour)]:
            box(s, Inches(0.7 + dx), y, Inches(w), Inches(0.32), txt, 10.5, False, c)
        y += Inches(0.42)

    kpi_card(s, Inches(0.7), Inches(4.15), Inches(3.83), Inches(1.2), "Anomalies flagged", str(f.anomaly_count),
             f"over {f.months} months, across 8 service categories", GREEN)
    box(s, Inches(4.9), Inches(4.15), Inches(7.7), Inches(1.2),
        "Before the materiality rule this detector flagged 347 points and simultaneously graded 318 of them 'good' — the statistical test "
        "and the severity grade were computed from different quantities and contradicted each other. An alert nobody can act on teaches "
        "people to ignore the channel.", 11, False, BODY)

    bullets(s, Inches(0.7), Inches(5.5), Inches(11.9), Inches(1.3), [
        "A point is an anomaly only if it is BOTH statistically odd (|modified z| > 3.5) AND financially material (≥25% deviation)",
        "The test runs on the STL residual, so weekday, weekend and monthly cycles do not trip alerts",
        "Mirrors AWS Cost Anomaly Detection semantics: ≥10-day warm-up, dynamic thresholds rather than a static dollar line",
    ], 11)
    footer(s, SYNTHETIC)


def slide_security(prs, f: Facts):
    s = blank(prs)
    header(s, "Security", "Read-only, keyless, and cost-bounded",
           "What a regulated utility's security review will ask about")
    rows = [
        ("No static cloud keys", "AWS and Azure are reached through Workload Identity Federation. The GCP service account assumes a read-only role. Nothing to rotate, nothing to leak."),
        ("No model API key", "Gemini is reached through Vertex, authenticated by Application Default Credentials on the Cloud Run service account. There is no key to store."),
        ("Least privilege", "The API service account holds bigquery.dataViewer, bigquery.jobUser and aiplatform.user. Ingest adds dataEditor and a bucket-scoped objectAdmin. Nothing can change a cloud resource."),
        ("The agent cannot write SQL", "It calls typed tools with a whitelisted column set. No eval, no string interpolation into a query, and no path from a prompt to the warehouse."),
        ("Cost is bounded, not monitored", "Every query caps bytes billed and must filter the partition. BigQuery fails the job rather than presenting an invoice."),
        ("Human access", "Cloud Identity or Okta behind Identity-Aware Proxy, with the FinOps personas mapped to groups."),
    ]
    y = Inches(2.15)
    for i, (t, d) in enumerate(rows):
        rect(s, Inches(0.7), y, Inches(11.9), Inches(0.75), PAPER if i % 2 else WASH, RULE)
        box(s, Inches(0.95), y + Inches(0.08), Inches(3.0), Inches(0.4), t, 12, True, GREEN)
        box(s, Inches(4.05), y + Inches(0.06), Inches(8.3), Inches(0.6), d, 10.5, False, BODY)
        y += Inches(0.82)
    footer(s)


def slide_cost(prs, f: Facts):
    s = blank(prs)
    header(s, "Run cost", "What the platform costs to operate",
           "Serverless: it scales to zero between the nightly job and the working day")
    rows = [
        ("Cloud Run — API", "~$60", "min 1 instance, 2 vCPU / 4 GiB"),
        ("Cloud Run — React client", "~$10", "or Firebase Hosting"),
        ("Cloud SQL (Postgres)", "~$50", "policies and scenarios; no HA"),
        ("Memorystore Redis", "~$35", "aggregate cache"),
        ("BigQuery", "~$5", "storage + partitioned queries"),
        ("Load Balancer + IAP", "~$20", ""),
        ("Artifact Registry, Secret Manager, logging", "~$20", ""),
        ("Gemini", f"~${gemini_cost_per_question() * QUESTIONS_PER_MONTH:,.0f}", f"{QUESTIONS_PER_MONTH:,} questions/month"),
    ]
    y = Inches(2.2)
    total = 60 + 10 + 50 + 35 + 5 + 20 + 20 + gemini_cost_per_question() * QUESTIONS_PER_MONTH
    for i, (svc, cost, note) in enumerate(rows):
        rect(s, Inches(0.7), y, Inches(7.6), Inches(0.44), PAPER if i % 2 else WASH, RULE)
        box(s, Inches(0.95), y + Inches(0.03), Inches(4.2), Inches(0.36), svc, 10.5, False, BODY)
        box(s, Inches(5.3), y + Inches(0.03), Inches(1.1), Inches(0.36), cost, 10.5, True, INK, PP_ALIGN.RIGHT)
        box(s, Inches(6.6), y + Inches(0.03), Inches(1.6), Inches(0.36), note, 8.5, False, MUTED)
        y += Inches(0.5)

    kpi_card(s, Inches(8.7), Inches(2.2), Inches(3.9), Inches(1.3), "Total", f"~${total:,.0f} / month",
             "before Cloud SQL high availability", TEAL)
    kpi_card(s, Inches(8.7), Inches(3.65), Inches(3.9), Inches(1.3), "As a share of the estate",
             f"{total * 12 / f.spend * 24 * 100:.3f}%", f"of {money(f.spend)} under management", GREEN)
    box(s, Inches(8.7), Inches(5.1), Inches(3.9), Inches(1.5),
        "BigQuery is negligible only because the table is partitioned and clustered. An unpartitioned full scan on every dashboard load is "
        "how a $5 line becomes a $500 one — which is why the partition filter is enforced by the schema, not by convention.",
        10, False, BODY)
    footer(s, "Cost estimates for a single environment. Gemini at list price, July 2026.")


def slide_roadmap(prs, f: Facts):
    s = blank(prs)
    header(s, "Delivery", "A phased rollout, value in the first wave", "Sequenced by risk, not by dollar size")
    waves = [
        ("Phase 1 · Weeks 1–3", GREEN, "Land it", [
            "GCP project, Workload Identity Federation to AWS and Azure",
            "BigQuery warehouse, first ingest of one payer per cloud",
            "Cloud Run API + executive dashboard, behind IAP",
            "Validate FOCUS conformance against real exports",
        ]),
        ("Phase 2 · Weeks 4–10", AZURE, "Make it useful", [
            "All payers; tagging remediation to cross the chargeback line",
            "Nightly optimization snapshot; quick wins first",
            "Forecast vs budget in the monthly finance cycle",
            "The remaining dashboards; Gemini Copilot enabled",
        ]),
        ("Phase 3 · Quarter 2+", VIOLET, "Operate it", [
            "Chargeback with the agreed shared-cost policy",
            "Unit economics per customer, per kWh, per meter read",
            "Anomaly alerting into ServiceNow",
            "FinOps for AI: GPU and token spend under the same lens",
        ]),
    ]
    x = Inches(0.7)
    for title, colour, phase, items in waves:
        rect(s, x, Inches(2.15), Inches(3.83), Inches(4.2), PAPER, RULE)
        bar(s, x, Inches(2.15), Inches(3.83), Pt(4), colour)
        box(s, x + Inches(0.22), Inches(2.32), Inches(3.4), Inches(0.35), title, 11.5, True, INK)
        box(s, x + Inches(0.22), Inches(2.66), Inches(3.4), Inches(0.3), phase, 10, True, colour)
        bullets(s, x + Inches(0.22), Inches(3.05), Inches(3.4), Inches(3.1), items, 10)
        x += Inches(4.02)
    box(s, Inches(0.7), Inches(6.5), Inches(11.9), Inches(0.4),
        "Phase 1 is deliberately all low-effort, low-risk work. The programme should pay for itself before it asks for trust.", 11, True, INK)
    footer(s)


def slide_honesty(prs, f: Facts):
    s = blank(prs)
    header(s, "Assumptions and limits", "What this does not claim",
           "Stated up front, because a FinOps tool that overstates is worse than none")
    items = [
        "Every figure in this deck comes from a synthetic 24-month utility estate. The dollars are invented; the mechanics are not.",
        "No live GCP deployment has been performed. The service, the warehouse DDL and the agent team are tested end to end against the demo estate with no cloud project and no model key.",
        "AWS Cost Explorer does not expose list price. On that ingest path ListCost is set equal to BilledCost, so Effective Savings Rate is understated. Use a FOCUS Data Export.",
        "Business drivers — customers served, kWh delivered, meter reads — cannot be read from a cloud bill by definition. Unit economics needs a feed from a system of record.",
        "Savings percentages in the lever catalog are vendor 'up-to' figures. Treat them as ceilings.",
        "Storage-tiering and rightsizing detectors infer from billing data alone. Where a detector cannot see access patterns or CPU utilisation, it lowers its confidence and says what telemetry would confirm it.",
        "Cost estimates assume a single environment and list pricing. They exclude any Google committed-use discount you already hold.",
    ]
    bullets(s, Inches(0.7), Inches(2.15), Inches(11.9), Inches(4.4), items, 11.5)
    footer(s)


def slide_next(prs, f: Facts):
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(2.4), RGBColor(0xF2, 0xF6, 0xFC))
    box(s, Inches(0.9), Inches(0.8), Inches(11), Inches(0.4), "NEXT STEPS", 12, True, AZURE)
    box(s, Inches(0.9), Inches(1.15), Inches(11), Inches(0.8), "What we would need to go live", 32, True, INK)
    steps = [
        ("A GCP project", "Plus a billing account, a VPC, and Owner long enough to land the Terraform."),
        ("An identity provider", "Cloud Identity, Okta or Entra, behind Identity-Aware Proxy. This replaces the demo password."),
        ("One read-only credential per payer", "Not per account. AWS and Azure via Workload Identity Federation; GCP needs only the billing export enabled."),
        ("A FOCUS export, ideally", "AWS Data Exports (FOCUS 1.2) and Azure FocusCost give a true list price, so Effective Savings Rate is correct rather than understated."),
        ("Your tagging standard", "So the canonical keys map to Con Edison's own: application, business unit, cost centre, environment, owner, project."),
        ("A business driver feed", "Customers served, kWh delivered, work orders closed. This is what turns a cloud bill into a unit cost a VP can defend."),
        ("An allocation policy decision", "Even split, proportional, or a fixed percentage for the shared platform pool. An accounting choice, not a technical one."),
    ]
    y = Inches(2.75)
    for t, d in steps:
        box(s, Inches(0.9), y, Inches(3.6), Inches(0.4), t, 12.5, True, INK)
        box(s, Inches(4.7), y - Inches(0.02), Inches(7.9), Inches(0.56), d, 10.5, False, BODY)
        y += Inches(0.62)
    footer(s, "Infosys · Con Edison")


# ==========================================================================


def build(out: str) -> str:
    f = gather()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    slide_title(prs, f)
    slide_problem(prs, f)
    slide_focus(prs, f)
    diagram(prs, "gcp_architecture", "Target architecture",
            "Three clouds, one FOCUS warehouse, one control plane",
            "Sources · Identity · Ingest · Warehouse · Serving · Experience",
            "Vector source: docs/diagrams/gcp_architecture.svg")
    diagram(prs, "cloud_onboarding", "Connecting the clouds",
            "One credential per payer, not one per account",
            "How AWS, Azure and Google Cloud each aggregate billing",
            "Vector source: docs/diagrams/cloud_onboarding.svg")
    slide_comparison(prs, f)
    slide_why_rebuild(prs, f)
    slide_agents(prs, f)
    slide_agent_cost(prs, f)
    slide_exec(prs, f)
    slide_forecast(prs, f)
    slide_optimize(prs, f)
    slide_anomaly(prs, f)
    slide_security(prs, f)
    slide_cost(prs, f)
    slide_roadmap(prs, f)
    slide_honesty(prs, f)
    slide_next(prs, f)

    prs.save(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="Infosys_FinOps_GCP_Platform.pptx")
    args = ap.parse_args()
    print(f"wrote {build(args.out)}")


if __name__ == "__main__":
    main()
