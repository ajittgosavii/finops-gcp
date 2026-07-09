"""The data seam: BigQuery in production, the synthetic estate in demo.

Both implementations return the *same shapes*, so nothing above this file knows
which is active. That is the same bet `data.py` made in the Streamlit app, moved
down a layer and given a real warehouse behind it.

Why a repository at all, rather than handing the engines a DataFrame
---------------------------------------------------------------------
Because the frame does not fit. A utility estate at ~500k FOCUS line-items per
month is roughly 8 GB of pandas over two years; at 2M/month it is ~31 GB. The
Streamlit app loads the whole thing into one process, which is exactly why it
demos well and would not survive Con Edison.

So the repository returns *aggregates*, and the engines -- which already take
small frames -- keep working untouched. `kpi.executive_kpis` wants one row per
charge; `forecast_spend` wants one row per month. Only the first needs pushing
down into SQL, and it is the only one that does.

Cost guards, because a dashboard that scans a partitioned table wrong is how a
$5/month line becomes $500:
  * every query sets `maximum_bytes_billed`; BigQuery FAILS the job rather than
    billing past it,
  * the FOCUS table is partitioned on ChargePeriodStart and clustered on
    (ProviderName, ServiceCategory, tag_application), so a scoped dashboard
    reads a slice, not the table,
  * the expensive row-level detectors do not run here at all. A nightly Cloud
    Run Job materialises `opportunities`, and this service reads that table.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Protocol, Sequence

import pandas as pd

from finops_core import focus, kpi

from app.settings import Settings, get_settings

COST = "EffectiveCost"


# ==========================================================================
# Scope -- the one filter row, expressed as a value object
# ==========================================================================


@dataclass(frozen=True)
class Scope:
    """What the user has filtered to. Immutable, hashable, cacheable."""

    start: Optional[dt.date] = None
    end: Optional[dt.date] = None
    clouds: tuple = ()
    applications: tuple = ()
    business_units: tuple = ()
    environments: tuple = ()

    @classmethod
    def of(
        cls,
        start: Optional[dt.date] = None,
        end: Optional[dt.date] = None,
        clouds: Optional[Sequence[str]] = None,
        applications: Optional[Sequence[str]] = None,
        business_units: Optional[Sequence[str]] = None,
        environments: Optional[Sequence[str]] = None,
    ) -> "Scope":
        return cls(
            start=start,
            end=end,
            clouds=tuple(clouds or ()),
            applications=tuple(applications or ()),
            business_units=tuple(business_units or ()),
            environments=tuple(environments or ()),
        )


class Repository(Protocol):
    """Everything the API and the agent tools may ask for."""

    def charges(self, scope: Scope) -> pd.DataFrame:
        """FOCUS rows for the scope. Only callers that genuinely need row-level
        detail should use this -- on BigQuery it is the expensive one."""

    def monthly(self, scope: Scope) -> pd.DataFrame:
        """period, cost."""

    def monthly_by(self, scope: Scope, dimension: str) -> pd.DataFrame:
        """period, <dimension>, cost."""

    def daily(self, scope: Scope) -> pd.DataFrame:
        """period, cost -- for anomaly detection."""

    def executive_kpis(self, scope: Scope) -> Dict[str, Any]:
        ...

    def opportunities(self, scope: Scope) -> pd.DataFrame:
        ...

    def budgets(self, scope: Scope) -> pd.DataFrame:
        ...

    def drivers(self, scope: Scope) -> pd.DataFrame:
        ...

    def dimensions(self) -> Dict[str, List[str]]:
        """Distinct values for the filter row."""

    def describe(self) -> Dict[str, Any]:
        """Provenance, for the Integrations view."""


# Columns a client may group or filter on. A whitelist, not a suggestion: the
# agent's query tool and the REST layer both build SQL identifiers from this,
# and an unchecked string here is an injection.
GROUPABLE: Dict[str, str] = {
    "cloud": "ProviderName",
    "service_category": "ServiceCategory",
    "service": "ServiceName",
    "region": "RegionId",
    "sub_account": "SubAccountId",
    "application": "tag_application",
    "business_unit": "tag_business_unit",
    "environment": "tag_environment",
    "cost_center": "tag_cost_center",
    "charge_category": "ChargeCategory",
}


def resolve_dimension(name: str) -> str:
    """Map a client-facing dimension name to a physical column, or refuse."""
    key = (name or "").strip().lower()
    if key in GROUPABLE:
        return GROUPABLE[key]
    if name in GROUPABLE.values():
        return name
    raise ValueError(f"Unknown dimension {name!r}. Allowed: {', '.join(sorted(GROUPABLE))}")


# ==========================================================================
# Demo -- the synthetic estate, in process
# ==========================================================================


@lru_cache(maxsize=2)
def _demo_estate(months: int, seed: int):
    from finops_core.connectors.demo import build_demo_dataset

    return build_demo_dataset(months=months, seed=seed)


class DemoRepository:
    """The synthetic estate. No GCP, no credentials, no network.

    This is not a mock: it runs the same `Connector` interface and produces a
    frame that passes `focus.validate()`, containing real commitment waste,
    untagged spend, idle resources, a migration step-change and two anomalies.
    """

    def __init__(self, settings: Settings, seed: int = 20260708) -> None:
        self.settings = settings
        self._df, self._budgets, self._drivers = _demo_estate(settings.demo_months, seed)

    # -- scoping ---------------------------------------------------------

    def _scoped(self, scope: Scope) -> pd.DataFrame:
        df = self._df
        if scope.clouds:
            df = df[df["ProviderName"].isin(scope.clouds)]
        if scope.applications:
            df = df[df["tag_application"].isin(scope.applications)]
        if scope.business_units:
            df = df[df["tag_business_unit"].isin(scope.business_units)]
        if scope.environments:
            df = df[df["tag_environment"].isin(scope.environments)]
        if scope.start:
            df = df[df["ChargePeriodStart"] >= pd.Timestamp(scope.start)]
        if scope.end:
            df = df[df["ChargePeriodStart"] <= pd.Timestamp(scope.end)]
        return df

    # -- reads -----------------------------------------------------------

    def charges(self, scope: Scope) -> pd.DataFrame:
        return self._scoped(scope)

    def monthly(self, scope: Scope) -> pd.DataFrame:
        df = self._scoped(scope).copy()
        if df.empty:
            return pd.DataFrame(columns=["period", "cost"])
        df["period"] = df["ChargePeriodStart"].dt.to_period("M").dt.to_timestamp()
        return df.groupby("period", as_index=False, observed=True)[COST].sum().rename(columns={COST: "cost"})

    def monthly_by(self, scope: Scope, dimension: str) -> pd.DataFrame:
        col = resolve_dimension(dimension)
        df = self._scoped(scope).copy()
        if df.empty:
            return pd.DataFrame(columns=["period", col, "cost"])
        df["period"] = df["ChargePeriodStart"].dt.to_period("M").dt.to_timestamp()
        return (
            df.groupby(["period", col], as_index=False, observed=True)[COST]
            .sum()
            .rename(columns={COST: "cost"})
        )

    def daily(self, scope: Scope) -> pd.DataFrame:
        df = self._scoped(scope).copy()
        if df.empty:
            return pd.DataFrame(columns=["period", "cost"])
        df["period"] = df["ChargePeriodStart"].dt.normalize()
        return df.groupby("period", as_index=False, observed=True)[COST].sum().rename(columns={COST: "cost"})

    def executive_kpis(self, scope: Scope) -> Dict[str, Any]:
        import dataclasses

        from finops_core.engines import optimize

        df = self._scoped(scope)
        if df.empty:
            return {}
        usage_waste_monthly = optimize.usage_waste_total(optimize.detect_all(df))
        return dataclasses.asdict(kpi.executive_kpis(df, usage_waste_monthly=usage_waste_monthly))

    def opportunities(self, scope: Scope) -> pd.DataFrame:
        from finops_core.engines import optimize

        df = self._scoped(scope)
        if df.empty:
            return pd.DataFrame()
        return optimize.opportunities_frame(optimize.detect_all(df))

    def budgets(self, scope: Scope) -> pd.DataFrame:
        b = self._budgets
        if scope.clouds and "cloud" in b.columns:
            b = b[b["cloud"].isin(scope.clouds)]
        if scope.applications and "application" in b.columns:
            b = b[b["application"].isin(scope.applications)]
        return b

    def drivers(self, scope: Scope) -> pd.DataFrame:
        return self._drivers

    def dimensions(self) -> Dict[str, List[str]]:
        d = self._df
        return {
            "clouds": sorted(d["ProviderName"].dropna().unique().tolist()),
            "applications": sorted(d["tag_application"].dropna().unique().tolist()),
            "business_units": sorted(d["tag_business_unit"].dropna().unique().tolist()),
            "environments": sorted(d["tag_environment"].dropna().unique().tolist()),
        }

    def describe(self) -> Dict[str, Any]:
        lo, hi = self._df["ChargePeriodStart"].min(), self._df["ChargePeriodStart"].max()
        validation = focus.validate(self._df)
        return {
            "source": "demo",
            "live": False,
            "rows": int(len(self._df)),
            "focus_version": focus.FOCUS_CANONICAL_VERSION,
            "conformant": validation.ok,
            "period_start": lo.date().isoformat(),
            "period_end": hi.date().isoformat(),
            "note": "Synthetic FOCUS 1.2 estate. Every dollar is invented.",
        }


# ==========================================================================
# BigQuery -- the warehouse
# ==========================================================================


class BigQueryRepository:
    """Aggregates pushed into SQL; engines still see small frames.

    Two rules hold everywhere below:

    * Never interpolate a client string into SQL. Dimensions come from the
      `GROUPABLE` whitelist and everything else is a query parameter.
    * Every job carries `maximum_bytes_billed`. A query that would scan more
      than the ceiling fails; it does not quietly cost money.
    """

    def __init__(self, settings: Settings, client: Optional[Any] = None) -> None:
        self.settings = settings
        self._client = client

    # -- plumbing --------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery  # lazy: the demo path must not need it

            self._client = bigquery.Client(project=self.settings.gcp_project)
        return self._client

    def _run(self, sql: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=params or [],
            maximum_bytes_billed=self.settings.bq_max_bytes_billed,
            labels={"app": "finops", "env": self.settings.environment},
            use_query_cache=True,
        )
        return self.client.query(sql, job_config=job_config).to_dataframe()

    # The FOCUS table is declared `require_partition_filter = TRUE`, so a query
    # with no bound on ChargePeriodStart FAILS rather than scanning two years.
    # That guard only works if we always supply one, so an unbounded Scope means
    # "the analysis window", not "everything".
    DEFAULT_WINDOW_MONTHS = 25

    def _where(self, scope: Scope) -> tuple:
        """Build a parameterised WHERE clause. Returns (sql, params).

        The partition predicate comes first, and is never optional, so BigQuery
        prunes before it reads.
        """
        from google.cloud import bigquery

        clauses: List[str] = []
        params: List[Any] = []

        if scope.start:
            clauses.append("ChargePeriodStart >= @start")
            params.append(bigquery.ScalarQueryParameter("start", "TIMESTAMP", scope.start))
        else:
            clauses.append(
                "ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), "
                f"INTERVAL {self.DEFAULT_WINDOW_MONTHS} MONTH))"
            )
        if scope.end:
            clauses.append("ChargePeriodStart <= @end")
            params.append(bigquery.ScalarQueryParameter("end", "TIMESTAMP", scope.end))

        for values, column, name in (
            (scope.clouds, "ProviderName", "clouds"),
            (scope.applications, "tag_application", "applications"),
            (scope.business_units, "tag_business_unit", "business_units"),
            (scope.environments, "tag_environment", "environments"),
        ):
            if values:
                clauses.append(f"{column} IN UNNEST(@{name})")
                params.append(bigquery.ArrayQueryParameter(name, "STRING", list(values)))

        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    # -- reads -----------------------------------------------------------

    def charges(self, scope: Scope) -> pd.DataFrame:
        where, params = self._where(scope)
        sql = f"SELECT * FROM `{self.settings.focus_table_fqn}`{where} LIMIT 1000000"
        return self._run(sql, params)

    def monthly(self, scope: Scope) -> pd.DataFrame:
        where, params = self._where(scope)
        sql = f"""
            SELECT TIMESTAMP_TRUNC(ChargePeriodStart, MONTH) AS period,
                   SUM({COST}) AS cost
            FROM `{self.settings.focus_table_fqn}`{where}
            GROUP BY period ORDER BY period
        """
        return self._run(sql, params)

    def monthly_by(self, scope: Scope, dimension: str) -> pd.DataFrame:
        col = resolve_dimension(dimension)  # whitelist -> safe to interpolate
        where, params = self._where(scope)
        sql = f"""
            SELECT TIMESTAMP_TRUNC(ChargePeriodStart, MONTH) AS period,
                   {col}, SUM({COST}) AS cost
            FROM `{self.settings.focus_table_fqn}`{where}
            GROUP BY period, {col} ORDER BY period
        """
        return self._run(sql, params)

    def daily(self, scope: Scope) -> pd.DataFrame:
        where, params = self._where(scope)
        sql = f"""
            SELECT TIMESTAMP_TRUNC(ChargePeriodStart, DAY) AS period,
                   SUM({COST}) AS cost
            FROM `{self.settings.focus_table_fqn}`{where}
            GROUP BY period ORDER BY period
        """
        return self._run(sql, params)

    def executive_kpis(self, scope: Scope) -> Dict[str, Any]:
        """Pushed down to one scan.

        `kpi.py` remains the definition of every formula -- this query computes
        the same components it does, and the arithmetic is reassembled below by
        calling into it. If the two ever disagree, `kpi.py` is right.
        """
        where, params = self._where(scope)
        sql = f"""
            WITH base AS (SELECT * FROM `{self.settings.focus_table_fqn}`{where})
            SELECT
              SUM(EffectiveCost)                                                       AS total_spend,
              SUM(IF(ChargeCategory = 'Usage', ListCost, 0))                           AS ode,
              SUM(IF(ChargeCategory = 'Usage', EffectiveCost, 0))                      AS usage_effective,
              SUM(IF(CommitmentDiscountStatus = 'Unused', EffectiveCost, 0))           AS commitment_waste,
              SUM(IF(CommitmentDiscountId IS NOT NULL AND CommitmentDiscountStatus = 'Used',
                     EffectiveCost, 0))                                                AS commitment_used,
              SUM(IF(tag_application != 'Unallocated', EffectiveCost, 0))              AS allocated,
              MIN(ChargePeriodStart)                                                   AS period_start,
              MAX(ChargePeriodEnd)                                                     AS period_end
            FROM base
        """
        row = self._run(sql, params)
        if row.empty or pd.isna(row.at[0, "total_spend"]):
            return {}
        r = row.iloc[0]

        total = float(r["total_spend"])
        ode = float(r["ode"] or 0)
        usage_effective = float(r["usage_effective"] or 0)
        used, unused = float(r["commitment_used"] or 0), float(r["commitment_waste"] or 0)

        esr = ((ode - usage_effective) / ode * 100.0) if ode else None
        utilisation = (used / (used + unused) * 100.0) if (used + unused) else None
        allocation = (float(r["allocated"] or 0) / total * 100.0) if total else None

        return {
            "total_spend": total,
            "esr_pct": esr,
            "utilization_pct": utilisation,
            "commitment_waste": unused,
            "allocation_coverage_pct": allocation,
            "chargeback_readiness": kpi.chargeback_readiness(allocation),
            "period_start": str(r["period_start"]),
            "period_end": str(r["period_end"]),
        }

    def opportunities(self, scope: Scope) -> pd.DataFrame:
        """Read the snapshot the nightly job materialised.

        The row-level detectors are far too expensive to run per request, and
        their answer changes once a day at most. The snapshot is keyed by
        `as_of`, not by the charge period, so the request scope does not filter
        it -- a cloud filter is applied client-side on a table of tens of rows.
        """
        from google.cloud import bigquery

        table = self.settings.opportunities_table_fqn
        sql = f"""
            SELECT * FROM `{table}`
            WHERE as_of = (SELECT MAX(as_of) FROM `{table}`)
              AND (@clouds IS NULL OR ARRAY_LENGTH(@clouds) = 0 OR cloud IN UNNEST(@clouds))
            ORDER BY annual_savings DESC
        """
        params = [bigquery.ArrayQueryParameter("clouds", "STRING", list(scope.clouds))]
        return self._run(sql, params)

    def budgets(self, scope: Scope) -> pd.DataFrame:
        return pd.DataFrame(columns=["period", "cloud", "application", "budget"])

    def drivers(self, scope: Scope) -> pd.DataFrame:
        # A cloud bill cannot contain business drivers, by definition.
        return pd.DataFrame(columns=["period", "metric", "value"])

    def dimensions(self) -> Dict[str, List[str]]:
        """Distinct filter values.

        Scans one partition-pruned window and only the four clustered columns,
        so it reads a fraction of the table. Without the partition predicate the
        table's `require_partition_filter` would reject the query outright --
        which is the guard doing its job.
        """
        where, params = self._where(Scope())
        table = self.settings.focus_table_fqn
        sql = f"""
            WITH scoped AS (
              SELECT ProviderName, tag_application, tag_business_unit, tag_environment
              FROM `{table}`{where}
            )
            SELECT 'clouds' AS k, ProviderName AS v FROM scoped GROUP BY v
            UNION ALL SELECT 'applications', tag_application FROM scoped GROUP BY 2
            UNION ALL SELECT 'business_units', tag_business_unit FROM scoped GROUP BY 2
            UNION ALL SELECT 'environments', tag_environment FROM scoped GROUP BY 2
        """
        df = self._run(sql, params)
        empty = {"clouds": [], "applications": [], "business_units": [], "environments": []}
        if df.empty or "k" not in df.columns:
            return empty  # a freshly created table has no rows yet
        out: Dict[str, List[str]] = dict(empty)
        for key, group in df.groupby("k"):
            out[str(key)] = sorted(v for v in group["v"].dropna().tolist())
        return out

    def describe(self) -> Dict[str, Any]:
        return {
            "source": "bigquery",
            "live": True,
            "table": self.settings.focus_table_fqn,
            "focus_version": focus.FOCUS_CANONICAL_VERSION,
            "max_bytes_billed": self.settings.bq_max_bytes_billed,
            "note": "Partitioned on ChargePeriodStart, clustered on ProviderName, ServiceCategory, tag_application.",
        }


# ==========================================================================


@lru_cache(maxsize=1)
def get_repository() -> Repository:
    settings = get_settings()
    if settings.data_source == "bigquery":
        return BigQueryRepository(settings)
    return DemoRepository(settings)
