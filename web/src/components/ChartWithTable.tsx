import { useState } from "react";

import type { Figure } from "../charts/builders";
import { Chart } from "./Chart";
import type { Column } from "./DataTable";
import { DataTable, downloadCsv, toCsv } from "./DataTable";
import { Panel } from "./Panel";

interface Props<T> {
  title: string;
  subtitle?: string;
  figure: Figure | null;
  ariaLabel: string;
  rows: T[];
  columns: Column<T>[];
  csvName: string;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  extraActions?: React.ReactNode;
  height?: number;
}

/**
 * A chart and its table-view twin, with a CSV download. Every chart ships one:
 * no value is reachable only through a tooltip. The toggle is a secondary
 * control, not a colour.
 */
export function ChartWithTable<T>({
  title,
  subtitle,
  figure,
  ariaLabel,
  rows,
  columns,
  csvName,
  isLoading,
  isFetching,
  error,
  extraActions,
}: Props<T>) {
  const [view, setView] = useState<"chart" | "table">("chart");

  const actions = (
    <div className="seg-actions">
      {extraActions}
      <div className="segmented" role="tablist" aria-label="View">
        <button
          role="tab"
          aria-selected={view === "chart"}
          className={view === "chart" ? "active" : ""}
          onClick={() => setView("chart")}
        >
          Chart
        </button>
        <button
          role="tab"
          aria-selected={view === "table"}
          className={view === "table" ? "active" : ""}
          onClick={() => setView("table")}
        >
          Table
        </button>
      </div>
      <button
        className="ghost-btn"
        onClick={() => downloadCsv(csvName, toCsv(rows, columns))}
        disabled={!rows.length}
        title="Download CSV"
      >
        CSV
      </button>
    </div>
  );

  return (
    <Panel
      title={title}
      subtitle={subtitle}
      isLoading={isLoading}
      isFetching={isFetching}
      error={error}
      actions={actions}
    >
      {view === "chart" ? (
        figure ? (
          <Chart figure={figure} ariaLabel={ariaLabel} />
        ) : (
          <div className="panel-loading">No data in scope.</div>
        )
      ) : (
        <DataTable rows={rows} columns={columns} />
      )}
    </Panel>
  );
}
