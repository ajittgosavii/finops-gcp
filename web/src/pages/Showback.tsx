import { useMemo, useState } from "react";

import { stackedBar } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import type { AllocationMethod } from "../lib/api";
import { ALLOCATION_METHODS } from "../lib/api";
import { pct, usd } from "../lib/format";
import { useAllocation } from "../lib/queries";
import { useScope } from "../lib/scope";
import { resolveColumn, surface } from "../lib/tokens";
import { useTheme } from "../theme/ThemeContext";

const DIMENSIONS = ["business_unit", "application", "environment", "cost_center", "cloud", "service_category"];
const METHOD_LABEL: Record<AllocationMethod, string> = {
  direct: "Direct (tagged only)",
  even_split: "Even split",
  proportional: "Proportional",
  fixed_percentage: "Fixed percentage",
  usage_driver: "Usage driver",
};

export function Showback() {
  const scope = useScope();
  const { mode } = useTheme();
  const s = surface(mode);
  const [dimension, setDimension] = useState("business_unit");
  const [method, setMethod] = useState<AllocationMethod>("proportional");
  const alloc = useAllocation(scope, dimension, method);
  const col = resolveColumn(dimension);

  const { fig, tableRows } = useMemo(() => {
    const rows = alloc.data?.rows ?? [];
    if (!rows.length) return { fig: null, tableRows: [] as Array<Record<string, unknown>> };
    const entities = rows.map((r) => String(r[col]));
    const figure = stackedBar(
      entities,
      [
        { name: "Direct", values: rows.map((r) => r.direct_cost), colour: s.categorical[0] },
        { name: "Shared", values: rows.map((r) => r.shared_cost), colour: s.categorical[3] },
        { name: "Untagged", values: rows.map((r) => r.untagged_cost), colour: s.text_muted },
      ],
      mode,
      Math.max(320, entities.length * 42),
    );
    const t = rows.map((r) => ({
      entity: String(r[col]),
      direct: r.direct_cost,
      shared: r.shared_cost,
      untagged: r.untagged_cost,
      total: r.total_cost,
      pct_of_total: r.pct_of_total,
    }));
    return { fig: figure, tableRows: t };
  }, [alloc.data, col, mode, s]);

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Showback</h1>
        <p className="page-lede">Allocate every dollar to a dimension, including each unit’s share of shared cost.</p>
      </div>

      <Callout tone="method" title="Showback, not chargeback">
        Showback moves <em>information</em>: it tells a business unit what it consumed. Chargeback
        moves <em>money</em>: it posts that consumption to their ledger. Neither is “more mature” —
        it is an accounting-policy choice. The <strong>method</strong> selector below only changes how
        shared and untagged cost are split; direct cost is always the unit’s own tagged spend.
      </Callout>

      <div className="row">
        <label className="muted">Dimension</label>
        <select className="dim-select" value={dimension} onChange={(e) => setDimension(e.target.value)}>
          {DIMENSIONS.map((d) => (
            <option key={d} value={d}>
              {d.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <label className="muted">Method</label>
        <select className="dim-select" value={method} onChange={(e) => setMethod(e.target.value as AllocationMethod)}>
          {ALLOCATION_METHODS.map((m) => (
            <option key={m} value={m}>
              {METHOD_LABEL[m]}
            </option>
          ))}
        </select>
      </div>

      <ChartWithTable
        title={`Allocation by ${dimension.replace(/_/g, " ")}`}
        subtitle={`Method: ${METHOD_LABEL[method]} — direct · shared · untagged`}
        figure={fig}
        ariaLabel="Stacked bar of direct, shared and untagged cost per unit"
        rows={tableRows}
        columns={[
          { key: "entity", header: dimension.replace(/_/g, " ") },
          { key: "direct", header: "Direct", align: "right", render: (r) => usd(Number(r.direct)), value: (r) => Number(r.direct) },
          { key: "shared", header: "Shared", align: "right", render: (r) => usd(Number(r.shared)), value: (r) => Number(r.shared) },
          { key: "untagged", header: "Untagged", align: "right", render: (r) => usd(Number(r.untagged)), value: (r) => Number(r.untagged) },
          { key: "total", header: "Total", align: "right", render: (r) => usd(Number(r.total)), value: (r) => Number(r.total) },
          { key: "pct_of_total", header: "% of total", align: "right", render: (r) => pct(Number(r.pct_of_total)), value: (r) => Number(r.pct_of_total) },
        ]}
        csvName={`allocation_${dimension}_${method}.csv`}
        isLoading={alloc.isLoading}
        isFetching={alloc.isFetching}
        error={alloc.error}
      />
    </div>
  );
}
