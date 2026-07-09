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

TEAL = "#119B8A"
VIOLET = "#5B4BC4"
CRIMSON = "#C23333"

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
# 1. Three clouds into one GCP platform
# ==========================================================================


def gcp_architecture() -> List[str]:
    fig, ax = canvas(16, 11)
    title(ax, "Target architecture",
          "Three clouds, one FOCUS warehouse, one control plane on Google Cloud",
          "AWS and Azure authenticate through Workload Identity Federation. No static keys anywhere.")

    Y_SRC, Y_AUTH, Y_ING, Y_WH, Y_SRV, Y_UX = 12.5, 22.0, 29.5, 40.0, 49.0, 58.5

    band(ax, 2, Y_SRC - 1.3, 96, 8.0, "SOURCES", MUTED)
    band(ax, 2, Y_AUTH - 1.2, 96, 5.2, "IDENTITY", CRIMSON)
    band(ax, 2, Y_ING - 1.3, 96, 8.4, "INGEST", TEAL)
    band(ax, 2, Y_WH - 1.3, 96, 7.0, "WAREHOUSE", VIOLET)
    band(ax, 2, Y_SRV - 1.3, 96, 7.4, "SERVING", AZURE)
    band(ax, 2, Y_UX - 1.3, 96, 6.4, "EXPERIENCE", GCP)

    # Sources -- one box per cloud, plus the escape hatches
    srcs = [
        ("AWS", "Data Exports\nFOCUS_1_2_AWS -> S3", AWS),
        ("Azure", "Cost Management\nFocusCost export -> Blob", AZURE),
        ("Google Cloud", "gcp_billing_export_focus_*\nnative, in BigQuery", GCP),
        ("Procured tool", "Cloudability · CloudHealth\nFlexera · Finout · Vantage", MUTED),
        ("FOCUS file", "Any conformant\nCSV / Parquet", MUTED),
    ]
    src_cx = []
    x = 6.5
    for name, sub, colour in srcs:
        node(ax, x, Y_SRC, 16.6, 5.8, name, sub, colour, PAPER, 8.4, 5.2)
        src_cx.append(x + 8.3)
        x += 18.1

    # Identity
    node(ax, 6.5, Y_AUTH, 34.7, 3.6, "Workload Identity Federation",
         "AWS + Azure read-only roles, assumed by the GCP service account", CRIMSON, "#FDF1F1", 7.8, 5.2)
    node(ax, 43.5, Y_AUTH, 23.6, 3.6, "Application Default Credentials",
         "GCP billing export, BigQuery, Vertex", GCP, "#EDF7F1", 7.8, 5.2)
    node(ax, 69.5, Y_AUTH, 28.0, 3.6, "Secret Manager",
         "vendor API keys, when a procured tool is used", MUTED, WASH, 7.8, 5.2)
    # AWS/Azure -> WIF; GCP -> ADC; a procured tool -> Secret Manager.
    # A dropped FOCUS file carries no credential at all, so it bypasses the
    # identity band entirely rather than implying it needs a secret.
    for i, cx in enumerate(src_cx):
        if i < 2:
            arrow(ax, (cx, Y_SRC + 5.8), (24.0, Y_AUTH), MUTED, lw=0.8)
        elif i == 2:
            arrow(ax, (cx, Y_SRC + 5.8), (55.0, Y_AUTH), MUTED, lw=0.8)
        elif i == 3:
            arrow(ax, (cx, Y_SRC + 5.8), (83.0, Y_AUTH), MUTED, lw=0.8)
        else:
            arrow(ax, (cx, Y_SRC + 5.8), (62.0, Y_ING + 1.0), MUTED, lw=0.8, rad=-0.10, dashed=True)

    # Ingest
    node(ax, 8.0, Y_ING, 24.0, 5.6, "Cloud Scheduler",
         "nightly 03:15 America/New_York", TEAL, PAPER, 8.2, 5.2)
    node(ax, 35.0, Y_ING, 30.0, 5.6, "Cloud Run Job  ·  ingest",
         "17 connectors -> focus.normalize -> validate\na failing binding never fails the run", TEAL, PAPER, 8.2, 5.0)
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
         "nightly snapshot of the\n53-lever detectors", VIOLET, PAPER, 8.2, 5.2)
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
    return save(fig, "gcp_architecture")


# ==========================================================================
# 2. How each cloud actually connects
# ==========================================================================


def cloud_onboarding() -> List[str]:
    fig, ax = canvas(16, 9.5)
    title(ax, "Connecting the three clouds",
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
    ]

    hdrs = ["Cloud", "Where the credential points", "What one credential covers", "FOCUS source", "How many"]
    xs = [4.0, 15.0, 38.0, 60.0, 80.0]
    ws = [10.0, 22.0, 21.0, 19.0, 16.0]
    for h, x, w in zip(hdrs, xs, ws):
        ax.text(x + 0.4, 13.6, h, fontsize=6.6, color=MUTED, weight="bold", va="center")

    # Rows are sized to their content. The first cut used 8.4 with a 9.6 pitch,
    # which left a band of dead space in every row and pushed the closing bullets
    # off the bottom of the axis, straight through the caption.
    ROW_H, ROW_PITCH = 6.4, 7.4
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

    node(ax, 4.0, 39.4, 44.0, 5.8, "A second credential means a second PAYER",
         "Another AWS organization, another Azure tenant or billing account,\nanother GCP billing account.",
         CRIMSON, "#FDF1F1", 8.2, 5.4)
    node(ax, 52.0, 39.4, 44.0, 5.8, "A regulated utility has several",
         "Regulated and unregulated entities cannot share a bill.\nDeclare each as a binding; BillingAccountId keeps them apart.",
         CRIMSON, "#FDF1F1", 8.2, 5.4)

    for i, t in enumerate([
        "AWS and Azure are reached through Workload Identity Federation, so no static access key is ever stored.",
        "Prefer a FOCUS export over Cost Explorer: Cost Explorer has no list price, so Effective Savings Rate comes out understated.",
        "A binding that fails contributes zero rows and a reason. The page still renders the clouds that are wired.",
    ]):
        ax.text(4.0, 48.8 + i * 2.6, "—  " + t, fontsize=6.8, color=BODY, va="center")

    caption(ax, "Bindings are pulled independently and concatenated into one FOCUS frame.")
    return save(fig, "cloud_onboarding")


# ==========================================================================


def build_all() -> Dict[str, List[str]]:
    return {"gcp_architecture": gcp_architecture(), "cloud_onboarding": cloud_onboarding()}


if __name__ == "__main__":
    for name, paths in build_all().items():
        print(f"{name}: " + ", ".join(os.path.relpath(p) for p in paths))
