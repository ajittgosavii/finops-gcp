"""The FinOps API.

A thin HTTP surface over `finops_core`. The service computes nothing: every
figure comes from the same engine functions the Streamlit app used and the agent
tools call. There is exactly one definition of Effective Savings Rate in this
system, and it lives in `finops_core/kpi.py`.

Charts are returned as **Plotly figure JSON**, produced by the same chart
vocabulary that encoded the rules -- one y-axis, entity-stable colours, a legend
whenever there are two or more series. The React client renders the figure; it
makes no chart-design decisions and therefore cannot break them.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from finops_core import CORE_PERSONAS, DOMAINS, focus
from finops_core.engines import allocation as allocation_engine
from finops_core.engines import anomaly as anomaly_engine
from finops_core.engines import forecast as forecast_engine
from finops_core.engines import optimize as optimize_engine

from app.repository import GROUPABLE, Repository, Scope, get_repository, resolve_dimension
from app.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Infosys Multi-Cloud FinOps API",
    version="1.0.0",
    description="FOCUS 1.2 in, executive answers out. Backed by finops_core.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ==========================================================================
# Scope as a dependency -- one filter row, applied identically everywhere
# ==========================================================================


def scope_params(
    start: Optional[dt.date] = Query(None),
    end: Optional[dt.date] = Query(None),
    clouds: Optional[List[str]] = Query(None),
    applications: Optional[List[str]] = Query(None),
    business_units: Optional[List[str]] = Query(None),
    environments: Optional[List[str]] = Query(None),
) -> Scope:
    return Scope.of(start, end, clouds, applications, business_units, environments)


def repo() -> Repository:
    return get_repository()


# ==========================================================================
# Meta
# ==========================================================================


@app.get("/healthz", tags=["meta"])
@app.get("/api/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness. Deliberately does no work: probes hit this constantly.

    Registered at BOTH paths because `/healthz` is unreachable on a Cloud Run
    `*.run.app` URL -- Google's front end answers it with its own 404 page and
    the request never reaches this process. Verified 2026-09-07 on
    finops-api-vldauvp5cq-uc.a.run.app: `/healthz` 404s while `/healthz/`,
    `/healthzz` and every other path reach the container normally. It is exactly
    that one string.

    So `/api/healthz` is the path to point a monitor or an uptime check at. The
    original is kept because it works behind a custom domain and in local
    development, and removing it would break anything already using it.
    """
    return {"ok": True, "version": app.version}


@app.get("/api/meta", tags=["meta"])
def meta(r: Repository = Depends(repo)) -> dict:
    """Dataset provenance: source, row count, period covered and the clouds present."""
    return {
        "organisation": settings.organisation,
        "environment": settings.environment,
        "source": r.describe(),
        "ai_enabled": settings.ai_enabled,
        "models": {"reasoning": settings.model_reasoning, "routing": settings.model_routing},
        "focus_version": focus.FOCUS_CANONICAL_VERSION,
        "personas": list(CORE_PERSONAS),
        "domains": DOMAINS,
        "groupable": sorted(GROUPABLE),
    }


@app.get("/api/dimensions", tags=["meta"])
def dimensions(r: Repository = Depends(repo)) -> dict:
    """The dimensions a caller may group or filter by. This is the whitelist."""
    return r.dimensions()


# ==========================================================================
# Executive
# ==========================================================================


@app.get("/api/kpis", tags=["executive"])
def kpis(scope: Scope = Depends(scope_params), r: Repository = Depends(repo)) -> dict:
    """Executive KPIs for the scope: spend, ESR, commitment coverage, waste, allocation."""
    data = r.executive_kpis(scope)
    if not data:
        raise HTTPException(404, "No charge rows in that scope.")
    return data


@app.get("/api/spend/monthly", tags=["executive"])
def spend_monthly(scope: Scope = Depends(scope_params), r: Repository = Depends(repo)) -> dict:
    """Amortised spend per month for the scope."""
    df = r.monthly(scope)
    return {"rows": df.assign(period=df["period"].astype(str)).to_dict("records") if len(df) else []}


@app.get("/api/spend/by", tags=["executive"])
def spend_by(
    dimension: str = Query("cloud"),
    scope: Scope = Depends(scope_params),
    r: Repository = Depends(repo),
) -> dict:
    """Amortised spend grouped by one whitelisted dimension."""
    try:
        col = resolve_dimension(dimension)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    df = r.monthly_by(scope, dimension)
    if df.empty:
        return {"dimension": dimension, "rows": []}
    df = df.assign(period=df["period"].astype(str))
    return {"dimension": dimension, "column": col, "rows": df.to_dict("records")}


# ==========================================================================
# Forecast
# ==========================================================================


class ForecastResponse(BaseModel):
    method: str
    maturity: str
    accuracy: Dict[str, Optional[float]]
    notes: List[str]
    history: List[Dict[str, Any]]
    forecast: List[Dict[str, Any]]
    cliff_months: List[str] = Field(default_factory=list)
    extra_from_cliffs_usd: float = 0.0


@app.get("/api/forecast", response_model=ForecastResponse, tags=["forecast"])
def forecast(
    horizon: int = Query(24, ge=1, le=36),
    include_cliffs: bool = Query(True),
    scope: Scope = Depends(scope_params),
    r: Repository = Depends(repo),
) -> ForecastResponse:
    """24-month forecast, with the commitment-expiry cliff overlaid."""
    monthly = r.monthly(scope)
    if len(monthly) < 3:
        raise HTTPException(400, "Not enough history to forecast.")

    result = forecast_engine.forecast_spend(monthly, horizon=horizon, method="auto")
    fc = result.forecast.copy()

    cliff_months: List[str] = []
    extra = 0.0
    if include_cliffs:
        try:
            overlay = forecast_engine.commitment_expiry_overlay(r.charges(scope), result.forecast)
            if "cost_with_cliffs" in overlay:
                cliff_months = overlay.loc[overlay["cliff"], "period"].dt.strftime("%Y-%m").tolist()
                extra = float(overlay["cost_with_cliffs"].sum() - result.forecast["cost"].sum())
                fc["cost_with_cliffs"] = overlay["cost_with_cliffs"].values
        except Exception:
            pass  # the overlay is an enhancement; a missing one must not 500

    return ForecastResponse(
        method=result.method,
        maturity=result.maturity,
        accuracy=result.accuracy,
        notes=result.notes,
        history=result.history.assign(period=result.history["period"].astype(str)).to_dict("records"),
        forecast=fc.assign(period=fc["period"].astype(str)).to_dict("records"),
        cliff_months=cliff_months,
        extra_from_cliffs_usd=round(extra, 2),
    )


# ==========================================================================
# Optimize
# ==========================================================================


@app.get("/api/optimize/opportunities", tags=["optimize"])
def opportunities(
    min_annual_savings: float = Query(0.0, ge=0),
    category: Optional[str] = Query(None),
    scope: Scope = Depends(scope_params),
    r: Repository = Depends(repo),
) -> dict:
    """Detected optimization opportunities, read from the nightly snapshot."""
    df = r.opportunities(scope)
    if df is None or df.empty:
        return {"count": 0, "total_annual_savings": 0.0, "rows": []}
    if category:
        df = df[df["category"].str.lower() == category.lower()]
    df = df[df["annual_savings"] >= min_annual_savings]
    return {
        "count": int(len(df)),
        "total_annual_savings": round(float(df["annual_savings"].sum()), 2),
        "rows": df.to_dict("records"),
    }


@app.get("/api/optimize/levers", tags=["optimize"])
def levers() -> dict:
    """The full optimization lever catalog."""
    return {"count": len(optimize_engine.LEVERS),
            "rows": optimize_engine.lever_catalog_frame().to_dict("records")}


@app.get("/api/optimize/levers/{lever_id}", tags=["optimize"])
def lever(lever_id: str) -> dict:
    """One optimization lever: savings band, effort, risk, prerequisites and source."""
    lv = optimize_engine.LEVER_BY_ID.get(lever_id.upper())
    if not lv:
        raise HTTPException(404, f"Unknown lever {lever_id!r}")
    return {
        "id": lv.id, "name": lv.name, "category": lv.category, "clouds": list(lv.clouds),
        "savings_low": lv.savings_low, "savings_high": lv.savings_high,
        "effort": lv.effort, "risk": lv.risk, "time_to_value": lv.time_to_value,
        "prerequisites": lv.prerequisites, "detection": lv.detection, "source_url": lv.source_url,
    }


# ==========================================================================
# Anomalies / allocation
# ==========================================================================


@app.get("/api/anomalies", tags=["anomalies"])
def anomalies(
    dimension: str = Query("service_category"),
    scope: Scope = Depends(scope_params),
    r: Repository = Depends(repo),
) -> dict:
    """Spend anomalies: statistically odd AND financially material."""
    try:
        col = resolve_dimension(dimension)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    df = r.charges(scope)
    if df.empty:
        return {"dimension": dimension, "rows": []}
    flagged = anomaly_engine.detect_by_dimension(df, dim=col)
    hits = flagged[flagged["is_anomaly"]].sort_values("deviation_pct", ascending=False)
    hits = hits.assign(period=hits["period"].astype(str))
    return {"dimension": dimension, "count": int(len(hits)), "rows": hits.to_dict("records")}


@app.get("/api/allocation", tags=["allocation"])
def allocation(
    dimension: str = Query("business_unit"),
    method: str = Query("proportional"),
    scope: Scope = Depends(scope_params),
    r: Repository = Depends(repo),
) -> dict:
    """Showback and chargeback: all cost allocated to one dimension."""
    if method not in allocation_engine.ALLOCATION_METHODS:
        raise HTTPException(400, f"method must be one of {allocation_engine.ALLOCATION_METHODS}")
    try:
        col = resolve_dimension(dimension)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    df = r.charges(scope)
    if df.empty:
        return {"rows": []}
    policy = allocation_engine.SharedCostPolicy(method=method)
    problems = policy.validate()
    if problems:
        raise HTTPException(400, "; ".join(problems))
    result = allocation_engine.allocate(df, policy, dim=col)
    return {"dimension": dimension, "method": method, "rows": result.to_dict("records")}


@app.get("/api/governance/coverage", tags=["governance"])
def coverage(scope: Scope = Depends(scope_params), r: Repository = Depends(repo)) -> dict:
    """How much spend carries an owner, and how much does not."""
    df = r.charges(scope)
    if df.empty:
        return {"rows": []}
    return {"rows": allocation_engine.coverage_report(df).to_dict("records")}


# ==========================================================================
# The agent team
# ==========================================================================


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    persona: str = "Leadership"
    session_id: Optional[str] = None


@app.get("/api/agent/team", tags=["agent"])
def agent_team() -> dict:
    """The agent team: the coordinator, its specialists and the tools each may call."""
    from app.agents.team import agent_cards

    return {"enabled": settings.ai_enabled, "agents": agent_cards()}


@app.post("/api/agent/ask", tags=["agent"])
async def agent_ask(body: AskRequest):
    """Stream the team's answer as Server-Sent Events.

    Frames: `tool` (provenance), `token` (partial text), `final`, `done`, `error`.
    SSE rather than a WebSocket because the payload is one-directional text;
    reserve `/run_live` semantics for voice.
    """
    from app.agents.runner import stream_answer

    if body.persona not in CORE_PERSONAS:
        raise HTTPException(400, f"persona must be one of {list(CORE_PERSONAS)}")

    return StreamingResponse(
        stream_answer(body.question, body.persona, body.session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ==========================================================================
# The single-page client
#
# The React client is built into this image (see services/api/Dockerfile) and
# served from the same origin as the API. That is the whole reason CORS is
# effectively dead code in production: the browser asks
# multicldfinops.aieksops.com for both /api/kpis and /assets/index.js, so there
# is no cross-origin request to allow. `web/src/lib/api.ts` falls back to an
# empty base URL when VITE_API_BASE is unset, which is how the build is made.
#
# Registered LAST, and that is load-bearing. FastAPI matches routes in
# definition order, so the catch-all below can only ever see a path that no
# API route claimed. Move it above the routes and it swallows the entire API.
# ==========================================================================

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

if _WEB_DIR.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_WEB_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Serve a real file if there is one, otherwise the SPA shell.

        A client-side route such as /optimize is not a file on disk, so the
        shell has to answer for it or a refresh on any deep link 404s.

        Two things this must NOT do:

        * **Answer for /api.** An unknown API path has to 404 as JSON. When this
          catch-all was first written it returned the SPA shell for anything
          unmatched, so `GET /api/healthz` came back 200 with HTML -- a health
          check or a client with a typo would have read that as success for
          ever. A wrong path must fail like a wrong path.
        * **Serve outside the web directory.** The candidate is resolved and
          checked to be inside `_WEB_DIR`; without that, a request for
          `../../../etc/passwd` is a file read.
        """
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"No API route /{full_path}")

        candidate = (_WEB_DIR / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_WEB_DIR):
            return FileResponse(candidate)
        return FileResponse(_WEB_DIR / "index.html")
