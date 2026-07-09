import { useMemo, useState } from "react";

import { heatmap, stackedArea, treemap } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import { monthLabel, usd } from "../lib/format";
import { useSpendBy } from "../lib/queries";
import { useScope } from "../lib/scope";
import { foldTail } from "../lib/tokens";
import { useTheme } from "../theme/ThemeContext";

export function Applications() {
  const scope = useScope();
  const { mode } = useTheme();
  const byApp = useSpendBy(scope, "application");
  const [drillApp, setDrillApp] = useState<string>("");

  const col = byApp.data?.column;

  // Per-application totals (folded) for the treemap composition.
  const totals = useMemo(() => {
    if (!byApp.data || !col) return [] as Array<[string, number]>;
    const m = new Map<string, number>();
    for (const r of byApp.data.rows) {
      const k = String(r[col]);
      m.set(k, (m.get(k) ?? 0) + Number(r.cost));
    }
    return foldTail([...m.entries()], 8);
  }, [byApp.data, col]);

  const treeFig = totals.length
    ? treemap(
        totals.map(([application, value]) => ({ level1: application, level2: "", value })),
        mode,
        440,
      )
    : null;

  // Heatmap application x month (top apps only, so the palette stays legible).
  const { z, xLabels, yLabels, heatRows } = useMemo(() => {
    if (!byApp.data || !col)
      return { z: [] as number[][], xLabels: [] as string[], yLabels: [] as string[], heatRows: [] as Array<Record<string, unknown>> };
    const months = [...new Set(byApp.data.rows.map((r) => String(r.period)))].sort();
    const topApps = totals.filter(([a]) => a !== "Other").map(([a]) => a);
    const lookup = new Map<string, number>();
    for (const r of byApp.data.rows) lookup.set(`${r[col]}|${r.period}`, Number(r.cost));
    const matrix = topApps.map((a) => months.map((mth) => lookup.get(`${a}|${mth}`) ?? 0));
    const rows: Array<Record<string, unknown>> = [];
    topApps.forEach((a, i) => months.forEach((mth, j) => rows.push({ application: a, month: mth, cost: matrix[i][j] })));
    return { z: matrix, xLabels: months.map(monthLabel), yLabels: topApps, heatRows: rows };
  }, [byApp.data, col, totals]);

  const heatFig = z.length ? heatmap(z, xLabels, yLabels, mode, Math.max(280, yLabels.length * 34)) : null;

  // Per-app drill: monthly series for a chosen application, from data we have.
  const appOptions = totals.filter(([a]) => a !== "Other").map(([a]) => a);
  const activeApp = drillApp || appOptions[0] || "";
  const drillRows = useMemo(() => {
    if (!byApp.data || !col || !activeApp) return [];
    return byApp.data.rows
      .filter((r) => String(r[col]) === activeApp)
      .map((r) => ({ period: String(r.period), series: activeApp, cost: Number(r.cost) }));
  }, [byApp.data, col, activeApp]);
  const drillFig = drillRows.length ? stackedArea(drillRows, mode, 300) : null;

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Applications</h1>
        <p className="page-lede">
          Where the estate’s spend actually lands, by application.
        </p>
      </div>

      <Callout tone="info">
        Composition and the application×month heatmap come from{" "}
        <code>/api/spend/by?dimension=application</code>. A true cloud→application treemap needs a
        row-level cross-tab the API does not expose (only one dimension per call, by design — the
        expensive scans are kept off the request path), so the treemap is a single-level application
        composition.
      </Callout>

      <div className="grid grid-2">
        <ChartWithTable
          title="Spend composition by application"
          subtitle="Total in window (tail folded into Other)"
          figure={treeFig}
          ariaLabel="Treemap of spend by application"
          rows={totals.map(([application, cost]) => ({ application, cost }))}
          columns={[
            { key: "application", header: "Application" },
            { key: "cost", header: "Cost", align: "right", render: (r) => usd(r.cost), value: (r) => r.cost },
          ]}
          csvName="application_composition.csv"
          isLoading={byApp.isLoading}
          isFetching={byApp.isFetching}
          error={byApp.error}
        />
        <ChartWithTable
          title="Application drill"
          subtitle="Monthly spend for one application"
          figure={drillFig}
          ariaLabel={`Monthly spend for ${activeApp}`}
          rows={drillRows.map((r) => ({ month: r.period, cost: r.cost }))}
          columns={[
            { key: "month", header: "Month", render: (r) => monthLabel(r.month) },
            { key: "cost", header: "Cost", align: "right", render: (r) => usd(r.cost), value: (r) => r.cost },
          ]}
          csvName={`app_${activeApp}.csv`}
          isLoading={byApp.isLoading}
          isFetching={byApp.isFetching}
          error={byApp.error}
          extraActions={
            <select
              className="dim-select"
              value={activeApp}
              onChange={(e) => setDrillApp(e.target.value)}
            >
              {appOptions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          }
        />
      </div>

      <ChartWithTable
        title="Application × month heatmap"
        subtitle="Continuous magnitude, one hue light→dark"
        figure={heatFig}
        ariaLabel="Heatmap of spend by application and month"
        rows={heatRows}
        columns={[
          { key: "application", header: "Application" },
          { key: "month", header: "Month", render: (r) => monthLabel(String(r.month)) },
          { key: "cost", header: "Cost", align: "right", render: (r) => usd(Number(r.cost)), value: (r) => Number(r.cost) },
        ]}
        csvName="application_month_heatmap.csv"
        isLoading={byApp.isLoading}
        isFetching={byApp.isFetching}
        error={byApp.error}
      />
    </div>
  );
}
