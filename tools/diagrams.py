"""Architecture diagrams for the GCP platform.

Authored once, exported twice: `.svg` (the deliverable -- `svg.fonttype='none'`
keeps labels as real, searchable, editable text) and `.png` at 220 dpi, because
`python-pptx` cannot embed SVG.

    python tools/diagrams.py      # -> docs/diagrams/*.svg + *.png

The canvas y axis is INVERTED once, so every coordinate below reads as "distance
from the top". Architecture diagrams are read downward and matplotlib's y grows
upward; getting this wrong silently draws the source layer at the bottom.
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "diagrams")

INK = "#0B142A"
BODY = "#445066"
MUTED = "#7A8599"
RULE = "#E2E7EF"
PAPER = "#FFFFFF"
WASH = "#F5F8FC"

# Cloud identity colours, used ONLY for the provider boxes.
AWS = "#C9851F"
AZURE = "#1E6FD9"
GCP = "#0C7A3E"
# Violet, not Oracle red: CRIMSON below is the IDENTITY band and the alert hue,
# and AWS already owns the warm amber. A provider must not read as a warning.
ORACLE = "#6E3AA7"

TEAL = "#119B8A"
VIOLET = "#5B4BC4"
CRIMSON = "#C23333"
AMBER = "#C98500"
GREEN = "#0C7A3E"

matplotlib.rcParams["svg.fonttype"] = "none"
matplotlib.rcParams["font.family"] = "DejaVu Sans"


# ==========================================================================
# Primitives
# ==========================================================================


def canvas(w: float, h: float):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(100 * h / w, 0)  # inverted: y is distance from the top
    ax.axis("off")
    fig.patch.set_facecolor(PAPER)
    return fig, ax


def height(ax) -> float:
    return ax.get_ylim()[0]


def band(ax, x, y, w, h, label: str, colour: str) -> None:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                linewidth=1, edgecolor=RULE, facecolor=WASH, zorder=1))
    ax.add_patch(mpatches.Rectangle((x, y), 0.55, h, facecolor=colour, edgecolor="none", zorder=2))
    ax.text(x + 1.7, y + h / 2, label, fontsize=6.8, color=colour, weight="bold",
            rotation=90, ha="center", va="center", zorder=3)


def node(ax, x, y, w, h, title: str, sub: str = "", colour: str = AZURE,
         fill: str = PAPER, fs: float = 8.0, sub_fs: float = 5.4) -> Tuple[float, float]:
    """`y` is the TOP edge; the box extends downward."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.9",
                                linewidth=1.2, edgecolor=colour, facecolor=fill, zorder=4))
    if sub:
        ax.text(x + w / 2, y + h * 0.34, title, fontsize=fs, color=INK, weight="bold",
                ha="center", va="center", zorder=5)
        ax.text(x + w / 2, y + h * 0.70, sub, fontsize=sub_fs, color=MUTED,
                ha="center", va="center", zorder=5, linespacing=1.4)
    else:
        ax.text(x + w / 2, y + h / 2, title, fontsize=fs, color=INK, weight="bold",
                ha="center", va="center", zorder=5)
    return x + w / 2, y + h / 2


def arrow(ax, p1, p2, colour: str = MUTED, lw: float = 1.1, rad: float = 0.0, dashed: bool = False) -> None:
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=9, linewidth=lw,
                                 color=colour, zorder=3, linestyle="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=1, shrinkB=3))


def title(ax, eyebrow: str, text: str, sub: str = "") -> None:
    ax.text(2.0, 2.4, eyebrow.upper(), fontsize=6.5, color=MUTED, weight="bold", va="center")
    ax.text(2.0, 5.2, text, fontsize=13, color=INK, weight="bold", va="center")
    if sub:
        ax.text(2.0, 8.2, sub, fontsize=7.4, color=BODY, va="center")


def caption(ax, text: str) -> None:
    ax.text(2.0, height(ax) - 1.6, text, fontsize=6.0, color=MUTED, va="center")


def notes(ax, lines: List[str], x: float = 3.0, pitch: float = 2.4, gap: float = 2.6) -> float:
    """A closing bullet block, anchored UPWARD from the caption.

    Anchoring to a magic top coordinate is how a bullet ends up printed through
    the caption the moment somebody adds one. Growing up from the caption cannot
    do that. Returns the block's top edge so a caller can check its clearance.
    """
    y0 = (height(ax) - 1.6) - gap - (len(lines) - 1) * pitch
    for i, line in enumerate(lines):
        ax.text(x, y0 + i * pitch, "—  " + line, fontsize=6.6, color=BODY, va="center")
    return y0


def save(fig, name: str) -> List[str]:
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    for ext, kw in (("svg", {}), ("png", {"dpi": 220})):
        p = os.path.join(OUT_DIR, f"{name}.{ext}")
        fig.savefig(p, bbox_inches="tight", facecolor=PAPER, **kw)
        paths.append(p)
    plt.close(fig)
    return paths


# ==========================================================================
# 1. High level design -- four clouds into one GCP platform
# ==========================================================================


def hld() -> List[str]:
    fig, ax = canvas(16, 11)
    title(ax, "High level design",
          "Four clouds, one FOCUS warehouse, one control plane on Google Cloud",
          "AWS and Azure federate through Workload Identity. OCI signs with an API key, so that one lives in Secret Manager.")

    Y_SRC, Y_AUTH, Y_ING, Y_WH, Y_SRV, Y_UX = 12.5, 22.0, 29.5, 40.0, 49.0, 58.5

    band(ax, 2, Y_SRC - 1.3, 96, 8.0, "SOURCES", MUTED)
    band(ax, 2, Y_AUTH - 1.2, 96, 5.2, "IDENTITY", CRIMSON)
    band(ax, 2, Y_ING - 1.3, 96, 8.4, "INGEST", TEAL)
    band(ax, 2, Y_WH - 1.3, 96, 7.0, "WAREHOUSE", VIOLET)
    band(ax, 2, Y_SRV - 1.3, 96, 7.4, "SERVING", AZURE)
    band(ax, 2, Y_UX - 1.3, 96, 6.4, "EXPERIENCE", GCP)

    # Sources -- one box per cloud, plus the escape hatches. Six boxes at width
    # 14.2 on a 15.2 pitch span 4.9..95.1 and stay inside the band.
    srcs = [
        ("AWS", "Data Exports\nFOCUS_1_2_AWS -> S3", AWS),
        ("Azure", "Cost Management\nFocusCost export -> Blob", AZURE),
        ("Google Cloud", "gcp_billing_export_focus_*\nnative, in BigQuery", GCP),
        ("OCI", "FOCUS Reports\n'bling' bucket -> gz CSV", ORACLE),
        ("Procured tool", "Cloudability · CloudHealth\nFlexera · Finout · Vantage", MUTED),
        ("FOCUS file", "Any conformant\nCSV / Parquet", MUTED),
    ]
    src_w = 14.2
    src_cx = []
    x = 4.9
    for name, sub, colour in srcs:
        node(ax, x, Y_SRC, src_w, 5.8, name, sub, colour, PAPER, 7.9, 4.8)
        src_cx.append(x + src_w / 2)
        x += 15.2

    # Identity
    node(ax, 4.9, Y_AUTH, 30.0, 3.6, "Workload Identity Federation",
         "AWS + Azure read-only roles, assumed by the GCP service account", CRIMSON, "#FDF1F1", 7.6, 4.9)
    node(ax, 37.0, Y_AUTH, 22.0, 3.6, "Application Default Credentials",
         "GCP billing export, BigQuery, Vertex", GCP, "#EDF7F1", 7.6, 4.9)
    node(ax, 61.0, Y_AUTH, 34.1, 3.6, "Secret Manager",
         "OCI API signing key · vendor API keys", MUTED, WASH, 7.6, 4.9)

    # AWS/Azure -> WIF; GCP -> ADC; OCI and a procured tool -> Secret Manager.
    #
    # OCI is the exception that the "no static keys anywhere" line glosses over.
    # There is no Workload Identity path from Google Cloud to OCI Object Storage:
    # the OCI SDK signs each request with an RSA private key. So that key is a
    # real secret, it lives in Secret Manager, and it is the one credential in
    # this diagram that somebody has to rotate.
    #
    # A dropped FOCUS file carries no credential at all, so it bypasses the
    # identity band entirely rather than implying it needs a secret.
    WIF_CX, ADC_CX, SM_CX = 19.9, 48.0, 78.0
    for i, cx in enumerate(src_cx):
        if i < 2:
            arrow(ax, (cx, Y_SRC + 5.8), (WIF_CX, Y_AUTH), MUTED, lw=0.8)
        elif i == 2:
            arrow(ax, (cx, Y_SRC + 5.8), (ADC_CX, Y_AUTH), MUTED, lw=0.8)
        elif i == 3:
            arrow(ax, (cx, Y_SRC + 5.8), (SM_CX - 7.0, Y_AUTH), CRIMSON, lw=0.9)
        elif i == 4:
            arrow(ax, (cx, Y_SRC + 5.8), (SM_CX + 7.0, Y_AUTH), MUTED, lw=0.8)
        else:
            arrow(ax, (cx, Y_SRC + 5.8), (62.0, Y_ING + 1.0), MUTED, lw=0.8, rad=-0.10, dashed=True)

    # Ingest
    node(ax, 8.0, Y_ING, 24.0, 5.6, "Cloud Scheduler",
         "nightly 03:15 America/New_York", TEAL, PAPER, 8.2, 5.2)
    node(ax, 35.0, Y_ING, 30.0, 5.6, "Cloud Run Job  ·  ingest",
         "18 connectors -> focus.normalize -> validate\na failing binding never fails the run", TEAL, PAPER, 8.2, 5.0)
    node(ax, 68.0, Y_ING, 24.0, 5.6, "Cloud Storage",
         "raw FOCUS Parquet\nthe replay source", TEAL, PAPER, 8.2, 5.2)
    arrow(ax, (20.0, Y_ING + 2.8), (35.0, Y_ING + 2.8), TEAL, lw=1.3)
    arrow(ax, (65.0, Y_ING + 2.8), (68.0, Y_ING + 2.8), TEAL, lw=1.3)
    arrow(ax, (50.0, Y_AUTH + 3.6), (50.0, Y_ING), CRIMSON, lw=0.9, dashed=True)

    # Warehouse
    node(ax, 20.0, Y_WH, 34.0, 4.6, "BigQuery  ·  focus_costs",
         "FOCUS 1.2 · partitioned on ChargePeriodStart\nclustered on cloud, service, application",
         VIOLET, "#F3F1FC", 8.6, 5.2)
    node(ax, 57.0, Y_WH, 26.0, 4.6, "BigQuery  ·  opportunities",
         "nightly snapshot of the\n59-lever detectors", VIOLET, PAPER, 8.2, 5.2)
    arrow(ax, (80.0, Y_ING + 5.6), (50.0, Y_WH), TEAL, lw=1.4, rad=0.12)
    arrow(ax, (50.0, Y_ING + 5.6), (37.0, Y_WH), TEAL, lw=1.4)
    arrow(ax, (54.0, Y_WH + 2.3), (57.0, Y_WH + 2.3), VIOLET, lw=1.0)

    # Serving
    node(ax, 10.0, Y_SRV, 30.0, 4.8, "Cloud Run  ·  FastAPI",
         "finops_core: kpi · forecast · budget\nanomaly · allocation · optimize", AZURE, PAPER, 8.4, 5.0)
    node(ax, 44.0, Y_SRV, 26.0, 4.8, "Google ADK",
         "coordinator + 4 specialists\ntyped tools, never SQL", AZURE, PAPER, 8.4, 5.0)
    node(ax, 73.0, Y_SRV, 22.0, 4.8, "Gemini via Vertex",
         "3.5-flash · 3.1-flash-lite\nADC, no API key", GCP, "#EDF7F1", 8.4, 5.0)
    arrow(ax, (37.0, Y_WH + 4.6), (25.0, Y_SRV), VIOLET, lw=1.2)
    arrow(ax, (70.0, Y_WH + 4.6), (57.0, Y_SRV), VIOLET, lw=1.0, rad=0.08)
    arrow(ax, (40.0, Y_SRV + 2.4), (44.0, Y_SRV + 2.4), AZURE, lw=1.1)
    arrow(ax, (70.0, Y_SRV + 2.4), (73.0, Y_SRV + 2.4), AZURE, lw=1.1)

    # Experience
    node(ax, 14.0, Y_UX, 26.0, 4.4, "React client", "12 dashboards · SSE chat", GCP, PAPER, 8.4, 5.2)
    node(ax, 44.0, Y_UX, 22.0, 4.4, "Cloud Load Balancer + IAP", "Cloud Identity / Okta", GCP, PAPER, 8.0, 5.2)
    node(ax, 70.0, Y_UX, 24.0, 4.4, "Cloud Trace · Logging", "per-agent spans, per-tool calls", GCP, PAPER, 8.0, 5.2)
    arrow(ax, (25.0, Y_SRV + 4.8), (27.0, Y_UX), AZURE, lw=1.0)
    arrow(ax, (55.0, Y_SRV + 4.8), (55.0, Y_UX), AZURE, lw=1.0)

    caption(ax, "Every source normalises to FOCUS 1.2 on ingest. Nothing above the warehouse has ever seen a vendor-specific field.")
    return save(fig, "hld")


# ==========================================================================
# 2. How each cloud actually connects (supplement to the HLD)
# ==========================================================================


def cloud_onboarding() -> List[str]:
    fig, ax = canvas(16, 9.5)
    title(ax, "Connecting the four clouds",
          "One credential per payer, not one per account",
          "That is how the providers aggregate billing. A second credential is only for a second payer.")

    rows = [
        (AWS, "AWS",
         "Cost Explorer / Data Exports at the\nPAYER (management) account",
         "Every linked account,\nas SubAccountId",
         "FOCUS_1_2_AWS\nData Export -> S3",
         "One per AWS organization"),
        (AZURE, "Azure",
         "Cost Management at\nBILLING-ACCOUNT scope",
         "Every subscription beneath it,\nas SubAccountId",
         "FocusCost export\n-> Blob Storage",
         "One per tenant"),
        (GCP, "Google Cloud",
         "BigQuery billing export,\nDetailed + Pricing enabled",
         "Every project the account pays for,\nas SubAccountId",
         "gcp_billing_export_focus_*\nnative, no copy",
         "One per billing account"),
        (ORACLE, "OCI",
         "API signing key for a user in the\nTENANCY; endorse policy required",
         "Every compartment beneath it,\nas SubAccountId",
         "FOCUS Reports in the\nOracle-owned 'bling' bucket",
         "One per tenancy"),
    ]

    hdrs = ["Cloud", "Where the credential points", "What one credential covers", "FOCUS source", "How many"]
    xs = [4.0, 15.0, 38.0, 60.0, 80.0]
    ws = [10.0, 22.0, 21.0, 19.0, 16.0]
    for h, x, w in zip(hdrs, xs, ws):
        ax.text(x + 0.4, 13.6, h, fontsize=6.6, color=MUTED, weight="bold", va="center")

    # Rows are sized to their content. The first cut used 8.4 with a 9.6 pitch,
    # which left a band of dead space in every row and pushed the closing bullets
    # off the bottom of the axis, straight through the caption. The fourth row
    # (OCI) then needed the pitch tightened again -- at 7.4 it ran into the
    # callouts below.
    ROW_H, ROW_PITCH = 5.5, 6.35
    y = 15.2
    for colour, cloud, points, covers, source, count in rows:
        ax.add_patch(FancyBboxPatch((4.0, y), 92.0, ROW_H, boxstyle="round,pad=0,rounding_size=1.0",
                                    linewidth=1, edgecolor=RULE, facecolor=PAPER, zorder=2))
        ax.add_patch(mpatches.Rectangle((4.0, y), 0.7, ROW_H, facecolor=colour, edgecolor="none", zorder=3))
        mid = y + ROW_H / 2
        ax.text(6.2, mid, cloud, fontsize=9.5, color=colour, weight="bold", va="center", zorder=4)
        for txt, x in [(points, 15.4), (covers, 38.4), (source, 60.4), (count, 80.4)]:
            ax.text(x, mid, txt, fontsize=6.6, color=BODY, va="center", zorder=4, linespacing=1.6)
        y += ROW_PITCH

    node(ax, 4.0, 41.4, 44.0, 5.8, "A second credential means a second PAYER",
         "Another AWS organization, another Azure tenant or billing account,\nanother GCP billing account, another OCI tenancy.",
         CRIMSON, "#FDF1F1", 8.2, 5.4)
    node(ax, 52.0, 41.4, 44.0, 5.8, "A regulated utility has several",
         "Regulated and unregulated entities cannot share a bill.\nDeclare each as a binding; BillingAccountId keeps them apart.",
         CRIMSON, "#FDF1F1", 8.2, 5.4)

    notes(ax, [
        "AWS and Azure federate through Workload Identity, so no static key is stored. OCI signs with an RSA key -- the one credential that must be rotated.",
        "OCI's report bucket lives in Oracle's own tenancy: tenancy admin is not enough, you must 'endorse' your group into it.",
        "Prefer a FOCUS export over Cost Explorer: Cost Explorer has no list price, so Effective Savings Rate comes out understated.",
        "A binding that fails contributes zero rows and a reason. The page still renders the clouds that are wired.",
    ], x=4.0, pitch=2.3)

    caption(ax, "Bindings are pulled independently and concatenated into one FOCUS frame.")
    return save(fig, "cloud_onboarding")


# ==========================================================================
# 3. End user view
# ==========================================================================


# The nine React routes, from web/src/pages. A page named here that no longer
# exists is a diagram that lies, so `tests/test_diagrams.py` reads the directory.
PAGES = [
    "Executive", "Forecast", "Optimize", "Anomalies", "Applications",
    "Showback", "Governance", "Integrations", "Copilot",
]


def end_user_view() -> List[str]:
    fig, ax = canvas(16, 10)
    title(ax, "End user view",
          "Who asks what, and where the answer lives",
          "One scope -- cloud, application, business unit, environment, period -- governs every panel on a page")

    steps = [
        ("Sign in", "Cloud Identity / Okta"),
        ("Scope", "cloud · app · BU · env · period"),
        ("Read", f"{len(PAGES) - 1} dashboards"),
        ("Drill", "every chart has a table twin"),
        ("Ask", "Copilot, streamed over SSE"),
    ]
    x, y = 3.5, 12.5
    for i, (name, sub) in enumerate(steps):
        node(ax, x, y, 16.8, 5.2, name, sub, AZURE, PAPER, 8.2, 5.0)
        if i:
            arrow(ax, (x - 1.5, y + 2.6), (x, y + 2.6), AZURE, lw=1.2)
        x += 18.4

    # Personas are the FinOps Foundation's. Each maps to the pages that answer
    # its question -- not to every page it is technically allowed to open.
    personas = [
        ("Leadership", "Spend, forecast vs budget,\nESR, unit cost",
         ["Executive", "Forecast", "Applications"], CRIMSON),
        ("Finance", "Variance, chargeback,\ninvoice reconciliation",
         ["Showback", "Forecast", "Governance"], VIOLET),
        ("FinOps practitioner", "Coverage, anomalies,\nsavings realised",
         ["Optimize", "Anomalies", "Governance"], TEAL),
        ("Engineering", "Cost per service,\nrightsizing signals",
         ["Applications", "Optimize", "Anomalies"], AMBER),
        ("Procurement", "Commitment coverage,\nutilisation, renewals",
         ["Executive", "Optimize", "Integrations"], GREEN),
    ]
    y_p, y_t = 24.5, 33.5
    x = 3.0
    for name, wants, pages, colour in personas:
        node(ax, x, y_p, 17.8, 6.8, name, wants, colour, PAPER, 8.0, 5.2)
        arrow(ax, (x + 8.9, y_p + 6.8), (x + 8.9, y_t), colour, lw=0.9)
        ty = y_t
        for p in pages:
            ax.add_patch(
                FancyBboxPatch((x + 1.3, ty), 15.2, 2.8, boxstyle="round,pad=0,rounding_size=0.7",
                               linewidth=0.9, edgecolor=RULE, facecolor=WASH, zorder=4)
            )
            ax.text(x + 8.9, ty + 1.4, p, fontsize=6.3, color=BODY, ha="center", va="center", zorder=5)
            ty += 3.4
        x += 18.8

    notes(ax, [
        "Every chart has a table-view twin (ChartWithTable), so no value is reachable only through a tooltip.",
        "Status is carried by an icon and a label as well as colour. Colour follows the entity, never its rank.",
        "The Copilot answers in outcome terms and names the tool each figure came from. It cannot compute a number itself.",
        "Sign-in is TARGET STATE. IAP is not yet in Terraform and the API ships today with no auth.",
    ], pitch=2.7)

    caption(ax, "Personas are the FinOps Foundation's. The page list is read from web/src/pages, so a renamed route fails the build.")
    return save(fig, "end_user_view")


# ==========================================================================
# 4. Low level design
# ==========================================================================


# Modules the LLD names. The test imports every one of them.
LLD_MODULES = [
    "finops_core.focus",
    "finops_core.kpi",
    "finops_core.engines.optimize",
    "finops_core.engines.forecast",
    "finops_core.engines.allocation",
    "finops_core.engines.anomaly",
]


def lld() -> List[str]:
    fig, ax = canvas(16, 10)
    title(ax, "Low level design",
          "One request, and one question, through the system",
          "Where the scope becomes SQL, where the cost guards bite, and why the model never sees a query")

    col = [3.0, 26.0, 51.0, 76.0]

    # --- edge / client -----------------------------------------------------
    node(ax, col[0], 13.0, 19, 4.6, "web/  React + TS", "9 pages · TanStack Query", AZURE, PAPER, 8.0, 5.2)
    node(ax, col[0], 20.0, 19, 4.6, "Load Balancer + IAP", "target state — no auth today", MUTED, WASH, 7.6, 5.0)
    node(ax, col[0], 27.0, 19, 4.6, "Cloud Run · FastAPI", "app/main.py", AZURE, "#EAF2FD", 7.8, 5.2)
    arrow(ax, (12.5, 17.6), (12.5, 20.0), AZURE)
    arrow(ax, (12.5, 24.6), (12.5, 27.0), AZURE)

    # --- request path ------------------------------------------------------
    node(ax, col[1], 13.0, 21, 4.6, "scope_params()", "the one filter row -> Scope", TEAL, PAPER, 7.8, 5.0)
    node(ax, col[1], 20.0, 21, 4.6, "resolve_dimension()", "GROUPABLE whitelist · never eval", TEAL, PAPER, 7.4, 5.0)
    node(ax, col[1], 27.0, 21, 4.6, "BigQueryRepository", "_where() always prunes the partition", TEAL, "#E9F7F5", 7.4, 5.0)
    arrow(ax, (col[0] + 19, 29.3), (col[1], 29.3), AZURE)
    arrow(ax, (36.5, 17.6), (36.5, 20.0), TEAL)
    arrow(ax, (36.5, 24.6), (36.5, 27.0), TEAL)

    # The boundary that matters here is not the secret one -- it is the SQL one.
    ax.add_patch(mpatches.Rectangle((col[1] - 1.5, 11.4), 24.0, 21.8, linewidth=1.1,
                                    edgecolor=CRIMSON, facecolor="none", linestyle="--", zorder=2))
    ax.text(col[1] + 10.5, 34.8, "SQL boundary — a dimension becomes an identifier here, so it is whitelisted, never interpolated",
            fontsize=5.4, color=CRIMSON, ha="center")

    # --- warehouse ---------------------------------------------------------
    # Stacked in the order the data actually moves: the nightly Job READS
    # focus_costs and WRITES opportunities. Drawing focus_costs -> opportunities
    # directly would claim the warehouse derives one from the other by itself.
    node(ax, col[2], 13.0, 21, 5.8, "BigQuery · focus_costs",
         "require_partition_filter = TRUE\nmaximum_bytes_billed = 20 GiB", VIOLET, "#F3F1FC", 7.8, 5.0)
    node(ax, col[2], 21.5, 21, 4.6, "Cloud Run Job · ingest",
         "optimize.detect_all() nightly", TEAL, PAPER, 7.4, 5.0)
    node(ax, col[2], 29.0, 21, 4.6, "BigQuery · opportunities",
         "API reads the MAX(as_of) partition", VIOLET, PAPER, 7.4, 5.0)
    arrow(ax, (61.5, 18.8), (61.5, 21.5), VIOLET)   # job reads the bill
    arrow(ax, (61.5, 26.1), (61.5, 29.0), TEAL)     # job writes the snapshot
    arrow(ax, (col[1] + 21, 29.3), (col[2], 15.9), TEAL, rad=0.12)
    arrow(ax, (col[1] + 21, 30.6), (col[2], 31.3), TEAL, rad=-0.06)

    # --- engines (request time) --------------------------------------------
    # optimize.detect_all() is deliberately absent: it is the nightly Job above,
    # never a request-time call.
    y = 13.0
    for name, sub in [("kpi.executive_kpis()", "amortised EffectiveCost"),
                      ("forecast.forecast_spend()", "auto-selected by WAPE backtest"),
                      ("allocation.allocate()", "shared-cost policy"),
                      ("anomaly.detect()", "STL + MAD on the residual")]:
        node(ax, col[3], y, 21, 4.2, name, sub, AMBER, PAPER, 7.2, 4.9)
        arrow(ax, (col[2] + 21, 15.9), (col[3], y + 2.1), VIOLET, rad=0.16, lw=0.7)
        y += 5.0

    # --- the agent path ----------------------------------------------------
    node(ax, col[0], 39.0, 19, 5.0, "agents/runner.py",
         "SSE frames\ntool · token · final · done · error", GREEN, PAPER, 7.4, 4.9)
    node(ax, col[2], 37.5, 21, 5.6, "agents/team.py",
         "coordinator (3.1-flash-lite)\n4 specialists as AgentTool (3.5-flash)", GREEN, "#EDF7F1", 7.8, 5.0)
    node(ax, col[3], 38.0, 21, 4.6, "agents/tools.py",
         "11 typed tools · never execute_sql", GREEN, PAPER, 7.2, 4.9)

    arrow(ax, (12.5, 31.6), (12.5, 39.0), AZURE, dashed=True)     # POST /api/agent/ask
    arrow(ax, (col[0] + 19, 41.5), (col[2], 40.3), GREEN)          # runner drives the team
    arrow(ax, (col[2] + 21, 40.3), (col[3], 40.3), GREEN)          # coordinator calls a tool
    arrow(ax, (86.5, 38.0), (86.5, 32.2), GREEN, dashed=True)      # tools call the same engines

    notes(ax, [
        "The two cost guards live in the DDL, not in convention: a query with no bound on the partition key FAILS rather than scanning two years.",
        "Row-level detectors never run per request. The nightly Job materialises `opportunities`; the API reads one partition.",
        "The agents are not given ADK's BigQuery `execute_sql` toolset. Hand a model SQL and it invents its own ESR -- plausible, wrong, uncaught.",
    ], pitch=2.7)

    caption(ax, "Agent tools call the same repository the REST endpoints call, so the Copilot cannot quote a number the dashboard disagrees with.")
    return save(fig, "lld")


# ==========================================================================


def build_all() -> Dict[str, List[str]]:
    return {
        "hld": hld(),
        "end_user_view": end_user_view(),
        "lld": lld(),
        "cloud_onboarding": cloud_onboarding(),
    }


if __name__ == "__main__":
    for name, paths in build_all().items():
        print(f"{name}: " + ", ".join(os.path.relpath(p) for p in paths))
