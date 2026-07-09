import { useMemo, useState } from "react";

import { rankedBar } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import { DataTable, downloadCsv, toCsv } from "../components/DataTable";
import type { Column } from "../components/DataTable";
import { Panel } from "../components/Panel";
import type { LeverRow, OpportunityRow } from "../lib/api";
import { pct, pctRange, usd } from "../lib/format";
import { useLevers, useOpportunities } from "../lib/queries";
import { useScope } from "../lib/scope";
import { foldTail } from "../lib/tokens";
import { useTheme } from "../theme/ThemeContext";

const CATEGORIES = ["", "Rate", "Usage", "Architecture", "AI/GPU"];

export function Optimize() {
  const scope = useScope();
  const { mode } = useTheme();
  const [category, setCategory] = useState("");
  const [minSavings, setMinSavings] = useState(0);
  const [cloud, setCloud] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const opps = useOpportunities(scope, {
    min_annual_savings: minSavings || undefined,
    category: category || undefined,
  });
  const levers = useLevers();

  const rows = useMemo(() => {
    let r = opps.data?.rows ?? [];
    if (cloud) r = r.filter((o) => o.cloud.includes(cloud));
    return r;
  }, [opps.data, cloud]);

  // Savings by category -- one series, one colour.
  const byCategory = useMemo(() => {
    const m = new Map<string, number>();
    for (const o of rows) m.set(o.category, (m.get(o.category) ?? 0) + o.annual_savings);
    return foldTail([...m.entries()], 8);
  }, [rows]);
  const catFig = byCategory.length
    ? rankedBar(byCategory.map(([c]) => c), byCategory.map(([, v]) => v), mode, Math.max(220, byCategory.length * 44))
    : null;

  const leverColumns: Column<LeverRow>[] = [
    { key: "id", header: "ID" },
    { key: "name", header: "Lever" },
    { key: "category", header: "Category" },
    { key: "clouds", header: "Clouds" },
    {
      key: "savings",
      header: "Savings (up-to)",
      align: "right",
      render: (r) => pctRange(r.savings_low, r.savings_high),
      value: (r) => `${Math.round(r.savings_low * 100)}-${Math.round(r.savings_high * 100)}%`,
    },
    { key: "effort", header: "Effort" },
    { key: "risk", header: "Risk" },
    {
      key: "source_url",
      header: "Source",
      render: (r) => (
        <a className="src-link" href={r.source_url} target="_blank" rel="noreferrer">
          docs ↗
        </a>
      ),
      value: (r) => r.source_url,
    },
  ];

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Optimize</h1>
        <p className="page-lede">Costed opportunities now; the full lever catalog underneath.</p>
      </div>

      <div className="grid grid-2">
        <ChartWithTable
          title="Annual savings by category"
          subtitle="Detected opportunities in scope"
          figure={catFig}
          ariaLabel="Ranked bar of annual savings by optimization category"
          rows={byCategory.map(([categoryName, annual]) => ({ category: categoryName, annual }))}
          columns={[
            { key: "category", header: "Category" },
            { key: "annual", header: "Annual savings", align: "right", render: (r) => usd(r.annual), value: (r) => r.annual },
          ]}
          csvName="savings_by_category.csv"
          isLoading={opps.isLoading}
          isFetching={opps.isFetching}
          error={opps.error}
        />
        <Panel title="Backlog filters" subtitle="Narrow the opportunity list">
          <div className="stack">
            <div className="row">
              <label className="muted">Category</label>
              <select className="dim-select" value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c || "All"}
                  </option>
                ))}
              </select>
              <label className="muted">Cloud</label>
              <select className="dim-select" value={cloud} onChange={(e) => setCloud(e.target.value)}>
                {["", "AWS", "Azure", "GCP"].map((c) => (
                  <option key={c} value={c}>
                    {c || "All"}
                  </option>
                ))}
              </select>
            </div>
            <div className="row">
              <label className="muted">Min annual savings</label>
              <input
                type="number"
                className="dim-select"
                style={{ width: 130 }}
                value={minSavings}
                min={0}
                step={10000}
                onChange={(e) => setMinSavings(Number(e.target.value) || 0)}
              />
              <span className="muted">
                {rows.length} shown · {usd(rows.reduce((a, r) => a + r.annual_savings, 0))}/yr
              </span>
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="Opportunity backlog"
        subtitle="Click a row for the evidence"
        isLoading={opps.isLoading}
        isFetching={opps.isFetching}
        error={opps.error}
      >
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Opportunity</th>
                <th>Category</th>
                <th>Cloud</th>
                <th className="num">Monthly</th>
                <th className="num">Annual</th>
                <th className="num">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o, i) => (
                <OppRow
                  key={i}
                  o={o}
                  open={expanded === i}
                  onToggle={() => setExpanded(expanded === i ? null : i)}
                />
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No opportunities match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <Callout tone="caution">
        Savings percentages are vendor <em>“up-to”</em> ceilings — the best case a provider quotes,
        not a guarantee. The realised figure depends on your commitment term, utilisation and how much
        of the eligible footprint you actually move.
      </Callout>

      <Panel
        title="Optimization lever catalog"
        subtitle={levers.data ? `${levers.data.count} levers` : undefined}
        isLoading={levers.isLoading}
        error={levers.error}
        actions={
          <button
            className="ghost-btn"
            disabled={!levers.data?.rows.length}
            onClick={() =>
              levers.data && downloadCsv("lever_catalog.csv", toCsv(levers.data.rows, leverColumns))
            }
          >
            CSV
          </button>
        }
      >
        {levers.data && <DataTable rows={levers.data.rows} columns={leverColumns} />}
      </Panel>
    </div>
  );
}

function OppRow({ o, open, onToggle }: { o: OpportunityRow; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr onClick={onToggle} style={{ cursor: "pointer" }}>
        <td>
          <span className="muted" aria-hidden>
            {open ? "▾ " : "▸ "}
          </span>
          {o.lever_name} <span className="muted">({o.lever_id})</span>
        </td>
        <td>{o.category}</td>
        <td>{o.cloud}</td>
        <td className="num">{usd(o.monthly_savings)}</td>
        <td className="num">{usd(o.annual_savings)}</td>
        <td className="num">{pct(o.confidence * 100, 0)}</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} style={{ background: "var(--raised)" }}>
            <div className="row" style={{ gap: 20 }}>
              <span>
                <strong>Scope:</strong> {o.scope}
              </span>
              <span>
                <strong>Effort:</strong> {o.effort}
              </span>
              <span>
                <strong>Risk:</strong> {o.risk}
              </span>
              <span>
                <strong>Time to value:</strong> {o.time_to_value}
              </span>
              <span>
                <strong>Resources:</strong> {o.resource_count}
              </span>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
