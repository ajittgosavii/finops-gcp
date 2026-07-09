import type { ReactNode } from "react";

import type { StatusKey } from "../lib/tokens";
import { StatusPill } from "./StatusPill";

interface KpiTileProps {
  label: string;
  value: string;
  sub?: ReactNode;
  status?: StatusKey;
  statusLabel?: string;
  hint?: string;
}

/** One executive KPI. The number is exactly what the API returned, formatted. */
export function KpiTile({ label, value, sub, status, statusLabel, hint }: KpiTileProps) {
  return (
    <div className="kpi-tile" title={hint}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        {status && statusLabel ? <StatusPill status={status} label={statusLabel} /> : null}
        {sub ? <span className="kpi-sub">{sub}</span> : null}
      </div>
    </div>
  );
}
