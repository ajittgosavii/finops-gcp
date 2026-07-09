import type { StatusKey } from "../lib/tokens";
import { STATUS, STATUS_ICON } from "../lib/tokens";

/**
 * A status is colour + icon + label, never colour alone. The icon and label are
 * the primary channel so the pill is legible under any colour-vision deficiency
 * and in a screen reader.
 */
export function StatusPill({ status, label }: { status: StatusKey; label: string }) {
  return (
    <span className="status-pill" style={{ ["--pill" as string]: STATUS[status] }}>
      <span className="status-icon" aria-hidden>
        {STATUS_ICON[status]}
      </span>
      <span>{label}</span>
    </span>
  );
}

/** Map an arbitrary metric to a status band. Higher-is-better by default. */
export function bandFor(
  value: number | null | undefined,
  thresholds: { good: number; warning: number },
  higherIsBetter = true,
): StatusKey {
  if (value === null || value === undefined || Number.isNaN(value)) return "warning";
  if (higherIsBetter) {
    if (value >= thresholds.good) return "good";
    if (value >= thresholds.warning) return "warning";
    return "critical";
  }
  if (value <= thresholds.good) return "good";
  if (value <= thresholds.warning) return "warning";
  return "critical";
}

/** The API's own severity strings map straight onto our reserved status keys. */
export function severityToStatus(severity: string): StatusKey {
  const s = severity.toLowerCase();
  if (s === "good" || s === "critical" || s === "serious" || s === "warning") return s as StatusKey;
  return "warning";
}
