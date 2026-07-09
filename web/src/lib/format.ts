/**
 * Presentation helpers ONLY. These never re-derive a KPI or re-round a currency
 * differently than the API did -- they format a number the API already produced.
 * A percentage displayed here is a percentage the engine computed.
 */

export function usd(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Compact currency for hero figures: $30.3M, $4.9M, $12.4k. */
export function usdCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}k`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

/** Signed percentage, for deltas: +4.3%, -0.6%. */
export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const s = value >= 0 ? "+" : "";
  return `${s}${value.toFixed(digits)}%`;
}

/** A savings-ceiling range like "10–66%" from two 0..1 fractions. */
export function pctRange(low: number, high: number): string {
  return `${Math.round(low * 100)}–${Math.round(high * 100)}%`;
}

export function monthLabel(iso: string): string {
  // "2026-07-01" or "2026-07" -> "Jul 2026"
  const parts = iso.split("-");
  const y = Number(parts[0]);
  const m = Number(parts[1]);
  if (!y || !m) return iso;
  const d = new Date(Date.UTC(y, m - 1, 1));
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function dayLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}
