import { useMemo, useState } from "react";

import { forecastFan } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import { KpiTile } from "../components/KpiTile";
import { Panel } from "../components/Panel";
import { bandFor } from "../components/StatusPill";
import { monthLabel, pct, usd } from "../lib/format";
import { useForecast } from "../lib/queries";
import { useScope } from "../lib/scope";
import { useTheme } from "../theme/ThemeContext";

const HORIZONS = [12, 18, 24, 36];

/** WAPE maturity bands, per the FinOps forecasting capability. */
function maturityFor(wape: number | null): string {
  if (wape == null) return "—";
  if (wape < 5) return "Best-in-class (<5%)";
  if (wape < 12) return "Run (<12%)";
  if (wape < 15) return "Walk (<15%)";
  if (wape < 20) return "Crawl (<20%)";
  return "Below Crawl (≥20%)";
}

export function Forecast() {
  const scope = useScope();
  const { mode } = useTheme();
  const [horizon, setHorizon] = useState(24);
  const q = useForecast(scope, horizon);
  const d = q.data;

  const fig = useMemo(() => {
    if (!d) return null;
    return forecastFan(
      d.history.map((h) => ({ x: h.period, cost: h.cost })),
      d.forecast.map((f) => ({
        x: f.period,
        cost: f.cost,
        lo80: f.lo80,
        hi80: f.hi80,
        lo95: f.lo95,
        hi95: f.hi95,
        cost_with_cliffs: f.cost_with_cliffs,
      })),
      mode,
      460,
    );
  }, [d, mode]);

  const wape = d?.accuracy.wape ?? null;

  const tableRows = (d?.forecast ?? []).map((f) => ({
    period: f.period,
    cost: f.cost,
    lo80: f.lo80,
    hi80: f.hi80,
    lo95: f.lo95,
    hi95: f.hi95,
    cost_with_cliffs: f.cost_with_cliffs ?? null,
  }));

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Forecast</h1>
        <p className="page-lede">Where the estate is heading, with honest uncertainty.</p>
      </div>

      <div className="row">
        <label className="muted">Horizon</label>
        <select className="dim-select" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
          {HORIZONS.map((h) => (
            <option key={h} value={h}>
              {h} months
            </option>
          ))}
        </select>
        {d && <span className="muted">Auto-selected method: <strong>{d.method}</strong></span>}
      </div>

      <ChartWithTable
        title="Spend forecast"
        subtitle="Actual · dashed point forecast · 80% and 95% likely ranges"
        figure={fig}
        ariaLabel="Forecast fan chart with 80 and 95 percent prediction bands"
        rows={tableRows}
        columns={[
          { key: "period", header: "Month", render: (r) => monthLabel(String(r.period)) },
          { key: "cost", header: "Forecast", align: "right", render: (r) => usd(Number(r.cost)), value: (r) => Number(r.cost) },
          { key: "lo80", header: "Lo 80%", align: "right", render: (r) => usd(Number(r.lo80)), value: (r) => Number(r.lo80) },
          { key: "hi80", header: "Hi 80%", align: "right", render: (r) => usd(Number(r.hi80)), value: (r) => Number(r.hi80) },
          { key: "lo95", header: "Lo 95%", align: "right", render: (r) => usd(Number(r.lo95)), value: (r) => Number(r.lo95) },
          { key: "hi95", header: "Hi 95%", align: "right", render: (r) => usd(Number(r.hi95)), value: (r) => Number(r.hi95) },
          {
            key: "cost_with_cliffs",
            header: "With cliffs",
            align: "right",
            render: (r) => (r.cost_with_cliffs == null ? "—" : usd(Number(r.cost_with_cliffs))),
            value: (r) => (r.cost_with_cliffs == null ? "" : Number(r.cost_with_cliffs)),
          },
        ]}
        csvName={`forecast_${horizon}m.csv`}
        isLoading={q.isLoading}
        isFetching={q.isFetching}
        error={q.error}
      />

      <div className="grid grid-3">
        <KpiTile
          label="Backtest WAPE"
          value={pct(wape)}
          status={bandFor(wape, { good: 12, warning: 20 }, false)}
          statusLabel="lower is better"
          hint="Weighted absolute percentage error from rolling backtests."
        />
        <KpiTile label="MAPE" value={pct(d?.accuracy.mape ?? null)} hint="Mean absolute percentage error." />
        <KpiTile label="sMAPE" value={pct(d?.accuracy.smape ?? null)} hint="Symmetric MAPE." />
      </div>

      <Panel title="Forecast accuracy & maturity" isLoading={q.isLoading} error={q.error}>
        {d && (
          <div className="stack">
            <div>
              <span className="maturity-badge">{maturityFor(wape)}</span>
              <span className="muted" style={{ marginLeft: 12 }}>
                across {d.accuracy.folds ?? "—"} backtest folds
              </span>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Maturity bands follow the FinOps forecasting capability: Crawl &lt;20%, Walk &lt;15%,
              Run &lt;12%, best-in-class &lt;5% — measured on WAPE, not on a single lucky month.
            </p>
            {d.notes.map((n, i) => (
              <p key={i} className="muted" style={{ margin: 0 }}>
                {n}
              </p>
            ))}
          </div>
        )}
      </Panel>

      <Callout tone="caution" title="Commitment-cliff overlay">
        {d && d.cliff_months.length > 0 ? (
          <>
            The dotted line adds the effect of commitments expiring in{" "}
            <strong>{d.cliff_months.map(monthLabel).join(", ")}</strong>. When a Reserved Instance,
            Savings Plan or CUD term ends and is not renewed, the covered usage reprices to
            on-demand — a step up the point forecast does not otherwise see. Estimated added cost over
            this horizon: <strong>{usd(d.extra_from_cliffs_usd)}</strong>.
          </>
        ) : (
          <>No commitment terms expire within this horizon, so there is no cliff overlay to show.</>
        )}
      </Callout>
    </div>
  );
}
