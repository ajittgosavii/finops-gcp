import { useMemo, useState } from "react";

import { anomalyScatter } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import { StatusPill, severityToStatus } from "../components/StatusPill";
import type { AnomalyRow } from "../lib/api";
import { dayLabel, signedPct, usd } from "../lib/format";
import { useAnomalies } from "../lib/queries";
import { useScope } from "../lib/scope";
import { resolveColumn } from "../lib/tokens";
import { useTheme } from "../theme/ThemeContext";

const DIMENSIONS = ["service_category", "service", "cloud", "region", "application"];

export function Anomalies() {
  const scope = useScope();
  const { mode } = useTheme();
  const [dimension, setDimension] = useState("service_category");
  const q = useAnomalies(scope, dimension);
  const col = resolveColumn(dimension);

  const rows = useMemo(() => {
    const r = q.data?.rows ?? [];
    return [...r].sort((a, b) => String(a.period).localeCompare(String(b.period)));
  }, [q.data]);

  const fig = useMemo(() => {
    if (!rows.length) return null;
    const actual = rows.map((r) => ({ x: String(r.period), y: Number(r.cost), flagged: true }));
    const expected = rows.map((r) => ({ x: String(r.period), y: Number(r.expected) }));
    return anomalyScatter(actual, expected, mode, 360);
  }, [rows, mode]);

  const tableRows = rows.map((r) => ({
    period: String(r.period),
    entity: String(r[col] ?? ""),
    cost: Number(r.cost),
    expected: Number(r.expected),
    deviation_pct: Number(r.deviation_pct),
    severity: String(r.severity),
    method: String(r.method),
    _raw: r as AnomalyRow,
  }));

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Anomalies</h1>
        <p className="page-lede">Spend that is both statistically odd and materially large.</p>
      </div>

      <div className="row">
        <label className="muted">By dimension</label>
        <select className="dim-select" value={dimension} onChange={(e) => setDimension(e.target.value)}>
          {DIMENSIONS.map((d) => (
            <option key={d} value={d}>
              {d.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        {q.data && <span className="muted">{rows.length} flagged</span>}
      </div>

      <ChartWithTable
        title="Flagged points: observed vs expected"
        subtitle="Anomalies drawn as diamonds — a shape channel, never colour alone"
        figure={fig}
        ariaLabel="Scatter of anomalous spend points against their expected value"
        rows={tableRows}
        columns={[
          { key: "period", header: "Date", render: (r) => dayLabel(r.period) },
          { key: "entity", header: dimension.replace(/_/g, " ") },
          { key: "cost", header: "Observed", align: "right", render: (r) => usd(r.cost), value: (r) => r.cost },
          { key: "expected", header: "Expected", align: "right", render: (r) => usd(r.expected), value: (r) => r.expected },
          {
            key: "deviation_pct",
            header: "Deviation",
            align: "right",
            render: (r) => signedPct(r.deviation_pct),
            value: (r) => r.deviation_pct,
          },
          {
            key: "severity",
            header: "Severity",
            render: (r) => <StatusPill status={severityToStatus(r.severity)} label={r.severity} />,
            value: (r) => r.severity,
          },
        ]}
        csvName={`anomalies_${dimension}.csv`}
        isLoading={q.isLoading}
        isFetching={q.isFetching}
        error={q.error}
      />

      <Callout tone="method" title="Why so few?">
        Each series is STL-decomposed into trend + seasonality + residual, then a{" "}
        <strong>median-absolute-deviation (MAD)</strong> test runs on the residual. A point is flagged
        only if it is <em>both</em> statistically odd (a large robust z-score) <em>and</em> materially
        deviant (≥25% off expected). That “and” is deliberate: it is why a two-year utility estate
        surfaces ~29 anomalies worth a human’s attention, not 347 tiny wiggles. Only the flagged points
        are returned by the API — there is no full daily-series endpoint, so the chart plots each
        anomaly’s observed value against the model’s expected value.
      </Callout>
    </div>
  );
}
