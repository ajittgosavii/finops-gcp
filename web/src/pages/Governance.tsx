import { useMemo } from "react";

import { rankedBar } from "../charts/builders";
import { Callout } from "../components/Callout";
import { ChartWithTable } from "../components/ChartWithTable";
import { KpiTile } from "../components/KpiTile";
import { StatusPill, severityToStatus } from "../components/StatusPill";
import { pct, usd } from "../lib/format";
import { useCoverage, useKpis } from "../lib/queries";
import { useScope } from "../lib/scope";
import { useTheme } from "../theme/ThemeContext";

export function Governance() {
  const scope = useScope();
  const { mode } = useTheme();
  const cov = useCoverage(scope);
  const kpis = useKpis(scope);

  const rows = cov.data?.rows ?? [];
  const fig = useMemo(() => {
    if (!rows.length) return null;
    return rankedBar(
      rows.map((r) => r.tag_key),
      rows.map((r) => r.coverage_pct),
      mode,
      Math.max(220, rows.length * 40),
      "",
      "%",
      1,
    );
  }, [rows, mode]);

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Governance</h1>
        <p className="page-lede">Tag coverage per key, and whether the estate is chargeback-ready.</p>
      </div>

      <div className="grid grid-3">
        <KpiTile
          label="Allocation coverage"
          value={pct(kpis.data?.allocation_coverage_pct ?? null)}
          hint="Share of spend attributable to an owner."
        />
        <KpiTile label="Chargeback readiness" value={kpis.data?.chargeback_readiness ?? "—"} />
        <KpiTile
          label="Untagged (worst key)"
          value={usd(rows.length ? Math.max(...rows.map((r) => r.unallocated_cost)) : null)}
        />
      </div>

      <ChartWithTable
        title="Coverage by tag key"
        subtitle="Percent of spend carrying each governance tag"
        figure={fig}
        ariaLabel="Ranked bar of tag coverage percentage by key"
        rows={rows}
        columns={[
          { key: "tag_key", header: "Tag key" },
          { key: "coverage_pct", header: "Coverage", align: "right", render: (r) => pct(r.coverage_pct), value: (r) => r.coverage_pct },
          {
            key: "unallocated_cost",
            header: "Unallocated",
            align: "right",
            render: (r) => usd(r.unallocated_cost),
            value: (r) => r.unallocated_cost,
          },
          {
            key: "status",
            header: "Status",
            render: (r) => <StatusPill status={severityToStatus(r.status)} label={r.status} />,
            value: (r) => r.status,
          },
        ]}
        csvName="tag_coverage.csv"
        isLoading={cov.isLoading}
        isFetching={cov.isFetching}
        error={cov.error}
      />

      <Callout tone="method" title="On the ~90% threshold">
        The “chargeback-ready at ~90% allocation” line these statuses use is{" "}
        <strong>practitioner consensus</strong>, not a published FinOps Foundation number. The
        Foundation defines the Allocation capability and its maturity, but does not stamp a single
        percentage as the pass mark — treat 90% as a widely used rule of thumb, and the real bar as
        “enough of the bill lands on an owner that a chargeback would not start an argument.”
      </Callout>
    </div>
  );
}
