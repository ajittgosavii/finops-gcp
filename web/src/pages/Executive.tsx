import { useMemo } from "react";

import type { Figure } from "../charts/builders";
import { forecastFan, rankedBar, stackedArea } from "../charts/builders";
import { Callout } from "../components/Callout";
import { Chart } from "../components/Chart";
import { ChartWithTable } from "../components/ChartWithTable";
import type { Column } from "../components/DataTable";
import { DataTable, downloadCsv, toCsv } from "../components/DataTable";
import { KpiTile } from "../components/KpiTile";
import { Panel } from "../components/Panel";
import { bandFor, StatusPill } from "../components/StatusPill";
import type { OpportunityRow, SpendByRow } from "../lib/api";
import { monthLabel, pct, signedPct, usd, usdCompact } from "../lib/format";
import {
  useForecast,
  useKpis,
  useOpportunities,
  useSpendBy,
} from "../lib/queries";
import { useScope } from "../lib/scope";
import { foldTail } from "../lib/tokens";
import { useTheme } from "../theme/ThemeContext";

export function Executive() {
  const scope = useScope();
  const { mode } = useTheme();
  const kpis = useKpis(scope);
  const spendByCloud = useSpendBy(scope, "cloud");
  const spendByApp = useSpendBy(scope, "application");
  const forecast = useForecast(scope, 24);
  const opps = useOpportunities(scope, {});

  const k = kpis.data;

  // --- Stacked area by cloud ---
  const areaRows = useMemo(() => {
    const col = spendByCloud.data?.column;
    if (!spendByCloud.data || !col) return [];
    return spendByCloud.data.rows.map((r: SpendByRow) => ({
      period: String(r.period),
      series: String(r[col]),
      cost: Number(r.cost),
    }));
  }, [spendByCloud.data]);
  const areaFig = areaRows.length ? stackedArea(areaRows, mode, 320) : null;

  // --- Top applications ranked ---
  const appTotals = useMemo(() => {
    const col = spendByApp.data?.column;
    if (!spendByApp.data || !col) return [] as Array<[string, number]>;
    const totals = new Map<string, number>();
    for (const r of spendByApp.data.rows) {
      const key = String(r[col]);
      totals.set(key, (totals.get(key) ?? 0) + Number(r.cost));
    }
    return foldTail([...totals.entries()], 8);
  }, [spendByApp.data]);
  const rankFig = appTotals.length
    ? rankedBar(
        appTotals.map(([l]) => l),
        appTotals.map(([, v]) => v),
        mode,
        Math.max(240, appTotals.length * 34),
      )
    : null;

  // --- Forecast fan ---
  const fanFig = useMemo(() => {
    if (!forecast.data) return null;
    return forecastFan(
      forecast.data.history.map((h) => ({ x: h.period, cost: h.cost })),
      forecast.data.forecast.map((f) => ({
        x: f.period,
        cost: f.cost,
        lo80: f.lo80,
        hi80: f.hi80,
        lo95: f.lo95,
        hi95: f.hi95,
        cost_with_cliffs: f.cost_with_cliffs,
      })),
      mode,
      360,
    );
  }, [forecast.data, mode]);

  const oppColumns: Column<OpportunityRow>[] = [
    { key: "lever_name", header: "Opportunity", render: (r) => r.lever_name },
    { key: "category", header: "Category" },
    { key: "cloud", header: "Cloud" },
    {
      key: "annual_savings",
      header: "Annual savings",
      align: "right",
      render: (r) => usd(r.annual_savings),
      value: (r) => r.annual_savings,
    },
    {
      key: "confidence",
      header: "Confidence",
      align: "right",
      render: (r) => pct(r.confidence * 100, 0),
      value: (r) => r.confidence,
    },
  ];

  const momUp = (k?.mom_pct ?? 0) >= 0;

  return (
    <div className="stack">
      {/* Hero */}
      <div className="hero">
        <div>
          <div className="hero-label">Total amortised spend (window)</div>
          <div className="hero-value">{usdCompact(k?.total_spend)}</div>
          <div className="hero-delta">
            {k?.mom_pct != null ? (
              <span className={momUp ? "delta-up" : "delta-down"}>
                {signedPct(k.mom_pct)} month-on-month
              </span>
            ) : (
              <span className="muted">month-on-month n/a</span>
            )}
            {k?.run_rate != null && (
              <span className="muted"> · {usdCompact(k.run_rate)} annualised run-rate</span>
            )}
          </div>
        </div>
        <div className="pill-row">
          {k?.chargeback_readiness && (
            <StatusPill
              status={bandFor(k.allocation_coverage_pct, { good: 90, warning: 75 })}
              label={k.chargeback_readiness}
            />
          )}
        </div>
      </div>

      {/* KPI tiles */}
      <div className="kpi-grid">
        <KpiTile
          label="Effective Savings Rate"
          value={pct(k?.esr_pct)}
          status={bandFor(k?.esr_pct, { good: 25, warning: 12 })}
          statusLabel={k?.esr_pct != null ? "vs on-demand" : "n/a"}
          hint="Savings vs the on-demand-equivalent (ListCost) denominator."
        />
        <KpiTile
          label="Commitment coverage"
          value={pct(k?.coverage_pct)}
          status={bandFor(k?.coverage_pct, { good: 70, warning: 40 })}
          statusLabel="eligible spend"
        />
        <KpiTile
          label="Commitment utilisation"
          value={pct(k?.utilization_pct)}
          status={bandFor(k?.utilization_pct, { good: 95, warning: 85 })}
          statusLabel="of commitments used"
        />
        <KpiTile
          label="Cost of waste"
          value={usdCompact(k?.cost_of_waste)}
          status={bandFor(k?.waste_pct, { good: 3, warning: 8 }, false)}
          statusLabel={k?.waste_pct != null ? `${pct(k.waste_pct)} of spend` : "n/a"}
        />
        <KpiTile
          label="Allocation coverage"
          value={pct(k?.allocation_coverage_pct)}
          status={bandFor(k?.allocation_coverage_pct, { good: 90, warning: 75 })}
          statusLabel="tagged"
        />
        <KpiTile
          label="Baseline drift"
          value={pct(k?.baseline_drift_pct)}
          status={bandFor(k?.baseline_drift_pct, { good: 5, warning: 12 }, false)}
          statusLabel="vs prior baseline"
        />
      </div>

      {/* Forecast */}
      <Panel
        title="24-month forecast"
        subtitle={
          forecast.data
            ? `Method: ${forecast.data.method} · maturity ${forecast.data.maturity}`
            : undefined
        }
        isLoading={forecast.isLoading}
        isFetching={forecast.isFetching}
        error={forecast.error}
      >
        {fanFig ? (
          <>
            <div style={{ marginBottom: 8 }} />
            <ChartInline figure={fanFig} label="Spend forecast with prediction bands" />
            {forecast.data && forecast.data.cliff_months.length > 0 && (
              <Callout tone="caution" title="Commitment expiry cliff">
                A commitment term expires in{" "}
                <strong>{forecast.data.cliff_months.map(monthLabel).join(", ")}</strong>. If not
                renewed, rates snap back to on-demand, adding an estimated{" "}
                <strong>{usd(forecast.data.extra_from_cliffs_usd)}</strong> across the horizon (the
                dotted “with commitment cliffs” line).
              </Callout>
            )}
          </>
        ) : (
          <div className="panel-loading">No forecast in scope.</div>
        )}
      </Panel>

      {/* Spend by cloud + top apps */}
      <div className="grid grid-2">
        <ChartWithTable
          title="Spend by cloud"
          subtitle="Monthly amortised, stacked"
          figure={areaFig}
          ariaLabel="Stacked area of monthly spend by cloud"
          rows={areaRows}
          columns={[
            { key: "period", header: "Month", render: (r) => monthLabel(r.period) },
            { key: "series", header: "Cloud" },
            { key: "cost", header: "Cost", align: "right", render: (r) => usd(r.cost), value: (r) => r.cost },
          ]}
          csvName="spend_by_cloud.csv"
          isLoading={spendByCloud.isLoading}
          isFetching={spendByCloud.isFetching}
          error={spendByCloud.error}
        />
        <ChartWithTable
          title="Top applications"
          subtitle="Total spend in window (tail folded into Other)"
          figure={rankFig}
          ariaLabel="Ranked bar of spend by application"
          rows={appTotals.map(([application, cost]) => ({ application, cost }))}
          columns={[
            { key: "application", header: "Application" },
            { key: "cost", header: "Cost", align: "right", render: (r) => usd(r.cost), value: (r) => r.cost },
          ]}
          csvName="top_applications.csv"
          isLoading={spendByApp.isLoading}
          isFetching={spendByApp.isFetching}
          error={spendByApp.error}
        />
      </div>

      {/* Opportunities */}
      <Panel
        title="Largest opportunities"
        subtitle={
          opps.data ? `${opps.data.count} detected · ${usd(opps.data.total_annual_savings)}/yr total` : undefined
        }
        isLoading={opps.isLoading}
        isFetching={opps.isFetching}
        error={opps.error}
        actions={
          <button
            className="ghost-btn"
            disabled={!opps.data?.rows.length}
            onClick={() =>
              opps.data &&
              downloadCsv("opportunities.csv", toCsv(opps.data.rows.slice(0, 10), oppColumns))
            }
          >
            CSV
          </button>
        }
      >
        {opps.data?.rows.length ? (
          <DataTable rows={opps.data.rows.slice(0, 10)} columns={oppColumns} />
        ) : (
          <div className="panel-loading">No opportunities in scope.</div>
        )}
      </Panel>
    </div>
  );
}

function ChartInline({ figure, label }: { figure: Figure; label: string }) {
  return <Chart figure={figure} ariaLabel={label} />;
}
