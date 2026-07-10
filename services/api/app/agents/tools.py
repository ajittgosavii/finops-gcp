"""Tools the ADK agents may call.

ADK derives each tool's JSON schema from the **function signature, its type
hints and its docstring** -- the `Args:` block becomes the per-parameter
description the model reads. So the docstrings below are not commentary; they
are the interface. Keep them precise, name the units, and say what the tool will
refuse to do.

Two conventions ADK expects and we honour:
  * every parameter carries a type hint, and prefers primitives;
  * every tool returns a `dict` with a `status` key ("success" | "error").

Why we do NOT hand the model `BigQueryToolset.execute_sql`
----------------------------------------------------------
ADK ships a first-class BigQuery toolset with `execute_sql` and a
`maximum_bytes_billed` cost cap, and it is genuinely good. We deliberately do
not expose it to these agents.

The platform's whole claim is that a number on a dashboard and a number in a
chat answer are the same number, because both came from `kpi.py`. Give the model
a SQL prompt and it will happily invent its own definition of Effective Savings
Rate -- one that omits the on-demand-equivalent denominator, or counts Purchase
rows, or quietly averages what should be summed. It will be plausible and it
will be wrong, and nobody will catch it.

So the model gets typed tools that call the same engine functions the REST
endpoints call. It cannot compute; it can only ask.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import pandas as pd

from finops_core import kpi
from finops_core.engines import allocation as allocation_engine
from finops_core.engines import anomaly as anomaly_engine
from finops_core.engines import forecast as forecast_engine
from finops_core.engines import optimize as optimize_engine

from app.repository import GROUPABLE, Repository, Scope

_MONEY = 2


def _ok(**payload: Any) -> Dict[str, Any]:
    return {"status": "success", **payload}


def _err(message: str, **extra: Any) -> Dict[str, Any]:
    return {"status": "error", "error": message, **extra}


def _round(value: Any, digits: int = _MONEY) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    return value


def _records(df: pd.DataFrame, limit: int = 20) -> List[Dict[str, Any]]:
    """Top-N rows as clean records. Never hand a model a whole frame."""
    if df is None or df.empty:
        return []
    out = df.head(limit).to_dict("records")
    return [{k: _round(v) for k, v in row.items()} for row in out]


def _scope(
    clouds: Optional[List[str]] = None,
    applications: Optional[List[str]] = None,
    business_units: Optional[List[str]] = None,
    environments: Optional[List[str]] = None,
    months: Optional[int] = None,
) -> Scope:
    start = None
    if months:
        start = (dt.date.today().replace(day=1) - dt.timedelta(days=31 * months)).replace(day=1)
    return Scope.of(
        start=start,
        clouds=clouds,
        applications=applications,
        business_units=business_units,
        environments=environments,
    )


# ==========================================================================
# The tools. `build_tools(repo)` closes each over the live repository, so a
# tool can never read a frame the dashboards are not also reading.
# ==========================================================================


def build_tools(repo: Repository) -> Dict[str, List[Any]]:
    """Return the tool functions, grouped by which specialist may call them."""

    def get_executive_kpis(clouds: Optional[List[str]] = None) -> dict:
        """Return the headline FinOps KPIs for the whole estate, in USD.

        Costs are amortised (FOCUS EffectiveCost). Includes total spend,
        Effective Savings Rate %, commitment coverage % and utilisation %,
        commitment waste $, cost of waste $, waste %, allocation coverage % and
        chargeback readiness, and baseline drift %.

        Args:
            clouds: Optional list of cloud providers to scope to, e.g. ["AWS"].
                Omit for the whole estate.
        """
        try:
            data = repo.executive_kpis(_scope(clouds=clouds))
            if not data:
                return _err("No charge rows in that scope.")
            return _ok(kpis={k: _round(v) for k, v in data.items()})
        except Exception as exc:  # a tool must never crash the agent loop
            return _err(str(exc)[:300])

    def get_spend_summary(
        group_by: str = "cloud",
        months: int = 12,
        clouds: Optional[List[str]] = None,
    ) -> dict:
        """Total amortised spend broken down by one dimension, in USD.

        Args:
            group_by: One of: cloud, service_category, service, region,
                sub_account, application, business_unit, environment,
                cost_center, charge_category.
            months: How many trailing months to include. Default 12.
            clouds: Optional list of clouds to scope to.
        """
        try:
            scope = _scope(clouds=clouds, months=months)
            df = repo.monthly_by(scope, group_by)
            if df.empty:
                return _err("No spend in that scope.")
            col = [c for c in df.columns if c not in ("period", "cost")][0]
            totals = df.groupby(col, as_index=False, observed=True)["cost"].sum()
            totals = totals.sort_values("cost", ascending=False)
            return _ok(
                group_by=group_by,
                months=months,
                total_usd=_round(float(totals["cost"].sum())),
                breakdown=_records(totals),
            )
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_commitment_position(clouds: Optional[List[str]] = None) -> dict:
        """Commitment coverage, utilisation, Effective Savings Rate and the
        dollar value of commitment already burned unused.

        ESR is the outcome metric, not coverage: 100% coverage at 60%
        utilisation is still a bad deal, and only ESR shows that. FinOps
        Foundation benchmarks are median ~0%, 75th percentile ~23%, 98th ~46%.

        Args:
            clouds: Optional list of clouds to scope to.
        """
        try:
            df = repo.charges(_scope(clouds=clouds))
            if df.empty:
                return _err("No charge rows in that scope.")
            return _ok(
                coverage_pct=_round(kpi.commitment_coverage_pct(df)),
                utilization_pct=_round(kpi.commitment_utilization_pct(df)),
                esr_pct=_round(kpi.effective_savings_rate_pct(df)),
                esr_components={k: _round(v) for k, v in kpi.esr_components(df).items()},
                commitment_waste_usd=_round(kpi.commitment_waste(df)),
                on_demand_equivalent_usd=_round(kpi.on_demand_equivalent(df)),
            )
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_forecast(horizon_months: int = 24) -> dict:
        """Forecast total amortised spend, with 80% and 95% prediction bands.

        The method is chosen by rolling-origin backtest and reported. WAPE is the
        headline accuracy metric because it is dollar-weighted: a small service
        whose actual rounds to zero cannot dominate the score as it does under
        MAPE. The maturity band maps WAPE onto the FinOps Foundation's
        forecast-variance thresholds (Crawl <20%, Walk <15%, Run <12%,
        best-in-class <5%).

        Args:
            horizon_months: How many months ahead to forecast. Default 24.
        """
        try:
            monthly = repo.monthly(Scope())
            if len(monthly) < 3:
                return _err("Not enough history to forecast.")
            result = forecast_engine.forecast_spend(monthly, horizon=horizon_months, method="auto")
            fc = result.forecast
            return _ok(
                method=result.method,
                accuracy={k: _round(v) for k, v in result.accuracy.items()},
                maturity=result.maturity,
                horizon_months=horizon_months,
                total_forecast_usd=_round(float(fc["cost"].sum())),
                first_month=_round(float(fc["cost"].iloc[0])),
                last_month=_round(float(fc["cost"].iloc[-1])),
                notes=result.notes[:3],
            )
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_commitment_cliffs() -> dict:
        """Find months where a commitment term expires and the rate snaps back
        to on-demand, and report the extra spend a plain trend forecast misses.

        This is the single most important thing naive cloud forecasting gets
        wrong.
        """
        try:
            monthly = repo.monthly(Scope())
            charges = repo.charges(Scope())
            if monthly.empty or charges.empty:
                return _err("No data in scope.")
            base = forecast_engine.forecast_spend(monthly, horizon=24, method="auto")
            overlay = forecast_engine.commitment_expiry_overlay(charges, base.forecast)
            if "cost_with_cliffs" not in overlay:
                return _ok(cliff_months=[], extra_usd=0.0)
            months = overlay.loc[overlay["cliff"], "period"].dt.strftime("%Y-%m").tolist()
            extra = float(overlay["cost_with_cliffs"].sum() - base.forecast["cost"].sum())
            return _ok(
                cliff_months=months,
                extra_usd=_round(extra),
                baseline_forecast_usd=_round(float(base.forecast["cost"].sum())),
                with_cliffs_usd=_round(float(overlay["cost_with_cliffs"].sum())),
            )
        except Exception as exc:
            return _err(str(exc)[:300])

    def find_optimization_opportunities(
        min_annual_savings: float = 10000.0,
        category: Optional[str] = None,
    ) -> dict:
        """Detected optimization opportunities with annualised savings in USD.

        Detected from the billing data by rule, not read from a vendor's
        recommendation API. Savings percentages in the lever catalog are vendor
        "up-to" figures -- ceilings, not guarantees. Where a detector cannot see
        what it needs (access patterns, CPU utilisation) it lowers its confidence
        and says so in the evidence.

        Args:
            min_annual_savings: Ignore opportunities smaller than this, in USD.
            category: Optional filter -- one of Rate, Usage, Architecture, AI/GPU.
        """
        try:
            df = repo.opportunities(Scope())
            if df is None or df.empty:
                return _err("No opportunities detected.")
            if category:
                df = df[df["category"].str.lower() == category.strip().lower()]
            df = df[df["annual_savings"] >= float(min_annual_savings)]
            if df.empty:
                return _ok(count=0, total_annual_savings_usd=0.0, opportunities=[])
            cols = [c for c in ["lever_id", "lever_name", "category", "cloud", "scope",
                                "annual_savings", "effort", "risk", "confidence"] if c in df.columns]
            return _ok(
                count=int(len(df)),
                total_annual_savings_usd=_round(float(df["annual_savings"].sum())),
                opportunities=_records(df[cols], limit=12),
            )
        except Exception as exc:
            return _err(str(exc)[:300])

    def explain_lever(lever_id: str) -> dict:
        """Look up one optimization lever in the catalog.

        (This said "the catalog of 53" until the catalog grew to 59. A docstring
        is the ADK tool schema the model reads, so a stale count here is a lie
        told to the model on every call. Counts do not belong in it.)

        Returns its savings range, effort, risk, time-to-value, prerequisites,
        the signal used to detect it, and a citable source URL.

        Args:
            lever_id: The lever identifier, e.g. "R1", "U10", "G4".
        """
        try:
            lever = optimize_engine.LEVER_BY_ID.get(lever_id.strip().upper())
            if not lever:
                return _err(f"Unknown lever {lever_id!r}.",
                            known=sorted(optimize_engine.LEVER_BY_ID)[:12])
            return _ok(lever={
                "id": lever.id, "name": lever.name, "category": lever.category,
                "clouds": list(lever.clouds),
                "savings_range_pct": [lever.savings_low * 100, lever.savings_high * 100],
                "effort": lever.effort, "risk": lever.risk,
                "time_to_value": lever.time_to_value,
                "prerequisites": lever.prerequisites,
                "detection": lever.detection, "source_url": lever.source_url,
            })
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_anomalies(dimension: str = "service_category", lookback_days: int = 90) -> dict:
        """Spend anomalies, detected by STL decomposition plus a median-absolute-
        deviation test on the residual, so weekday and monthly cycles do not trip
        alerts.

        Args:
            dimension: Which dimension to detect within. One of cloud,
                service_category, service, application, business_unit.
            lookback_days: How far back to look. Default 90.
        """
        try:
            df = repo.charges(_scope())
            if df.empty:
                return _err("No charge rows in scope.")
            from app.repository import resolve_dimension

            col = resolve_dimension(dimension)
            flagged = anomaly_engine.detect_by_dimension(df, dim=col)
            hits = flagged[flagged["is_anomaly"]].sort_values("deviation_pct", ascending=False)
            cols = [c for c in ["period", col, "cost", "expected", "deviation_pct", "severity"] if c in hits.columns]
            records = _records(hits[cols], limit=10)
            for r in records:
                if isinstance(r.get("period"), pd.Timestamp):
                    r["period"] = r["period"].date().isoformat()
            return _ok(dimension=dimension, count=int(len(hits)), anomalies=records)
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_allocation(dimension: str = "business_unit", method: str = "proportional") -> dict:
        """Showback: allocate all cost to a dimension, including each unit's
        share of the shared platform pool.

        Showback moves information; chargeback moves money. Neither is "more
        mature" -- it is an accounting-policy choice.

        Args:
            dimension: business_unit, application or cost_center.
            method: direct, even_split, proportional, fixed_percentage or usage_driver.
        """
        try:
            from app.repository import resolve_dimension

            col = resolve_dimension(dimension)
            df = repo.charges(_scope())
            if df.empty:
                return _err("No charge rows in scope.")
            policy = allocation_engine.SharedCostPolicy(method=method)
            problems = policy.validate()
            if problems:
                return _err("; ".join(problems))
            result = allocation_engine.allocate(df, policy, dim=col)
            return _ok(dimension=dimension, method=method,
                       total_usd=_round(float(result["total_cost"].sum())),
                       allocation=_records(result, limit=15))
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:
            return _err(str(exc)[:300])

    def get_allocation_coverage() -> dict:
        """Per-tag allocation coverage and whether the estate is chargeback-ready.

        Practitioner consensus puts the chargeback line near 90% coverage. That
        is not a published FinOps Foundation number.
        """
        try:
            df = repo.charges(_scope())
            if df.empty:
                return _err("No charge rows in scope.")
            report = allocation_engine.coverage_report(df)
            coverage = kpi.allocation_coverage_pct(df)
            return _ok(
                overall_coverage_pct=_round(coverage),
                readiness=kpi.chargeback_readiness(coverage),
                per_tag=_records(report),
            )
        except Exception as exc:
            return _err(str(exc)[:300])

    def list_dimensions() -> dict:
        """The dimensions that can be grouped or filtered on, and their values.

        Call this before guessing a dimension name.
        """
        try:
            return _ok(groupable=sorted(GROUPABLE), values=repo.dimensions())
        except Exception as exc:
            return _err(str(exc)[:300])

    return {
        "analyst": [get_executive_kpis, get_spend_summary, get_anomalies,
                    get_allocation, get_allocation_coverage, list_dimensions],
        "forecaster": [get_forecast, get_commitment_cliffs, get_executive_kpis, get_spend_summary],
        "optimizer": [find_optimization_opportunities, explain_lever,
                      get_commitment_position, get_executive_kpis],
        "governor": [get_allocation_coverage, get_allocation, list_dimensions, get_executive_kpis],
    }
