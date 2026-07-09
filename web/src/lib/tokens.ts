/**
 * Design tokens for the Multi-Cloud FinOps Command Center.
 *
 * A DIRECT transcription of ../../multicloud-finops/theme.py. Nothing in this
 * codebase may define a hex value that is not here. If you change a hue,
 * re-run the dataviz validator in the Python source before changing it here.
 *
 * The categorical slot ORDER is not cosmetic. It maximises the minimum adjacent
 * colour distance under simulated colour-vision deficiency. Assign in fixed
 * order, never cycled, never by rank -- colour follows the entity, not its row.
 */

// --------------------------------------------------------------------------
// Categorical slots
// --------------------------------------------------------------------------

export const CATEGORICAL_DARK: string[] = [
  "#3987E5", // 1 blue
  "#D95926", // 2 orange
  "#199E70", // 3 aqua
  "#9085E9", // 4 violet
  "#C98500", // 5 yellow
  "#D55181", // 6 magenta
  "#008300", // 7 green
  "#E66767", // 8 red
];

export const CATEGORICAL_LIGHT: string[] = [
  "#2A78D6", // 1 blue
  "#EB6834", // 2 orange
  "#1BAF7A", // 3 aqua
  "#4A3AA7", // 4 violet
  "#EDA100", // 5 yellow
  "#E87BA4", // 6 magenta
  "#008300", // 7 green
  "#E34948", // 8 red
];

// Sequential ramp: ONE hue, light -> dark. Continuous magnitude only.
export const SEQUENTIAL_BLUE: string[] = [
  "#CDE2FB",
  "#9EC5F4",
  "#6DA7EC",
  "#3987E5",
  "#256ABF",
  "#184F95",
  "#0D366B",
];

export const ORDINAL_BLUE_LIGHT: string[] = SEQUENTIAL_BLUE.slice(1);
export const ORDINAL_BLUE_DARK: string[] = SEQUENTIAL_BLUE.slice(0, -1);

// Diverging pair: two OPPOSITE hues (warm/cool) with a NEUTRAL grey midpoint.
export const DIVERGING_MID_DARK = "#383835";
export const DIVERGING_MID_LIGHT = "#F0EFEC";

export const DIVERGING_DARK: string[] = [
  "#0D366B",
  "#256ABF",
  "#6DA7EC",
  DIVERGING_MID_DARK,
  "#E66767",
  "#D03B3B",
  "#8F2020",
];
export const DIVERGING_LIGHT: string[] = [
  "#0D366B",
  "#256ABF",
  "#9EC5F4",
  DIVERGING_MID_LIGHT,
  "#E87373",
  "#D03B3B",
  "#8F2020",
];

// Status palette: RESERVED. Never reused as a series colour. Always shipped
// with an icon + label so the colour never carries meaning alone.
export type StatusKey = "good" | "warning" | "serious" | "critical";

export const STATUS: Record<StatusKey, string> = {
  good: "#0CA30C",
  warning: "#FAB219",
  serious: "#EC835A",
  critical: "#D03B3B",
};

export const STATUS_ICON: Record<StatusKey, string> = {
  good: "●", // filled circle
  warning: "▲", // triangle
  serious: "◆", // diamond
  critical: "■", // square
};

// Brand -- identity only, NEVER a data mark.
export const BRAND = {
  azure: "#4FB3F5",
  teal: "#2FD8C4",
  violet: "#8B7BF0",
  glow: "#7FE3FF",
  deep: "#04070F",
} as const;

// --------------------------------------------------------------------------
// Surfaces
// --------------------------------------------------------------------------

export interface Surface {
  name: Mode;
  page: string;
  surface: string;
  surface_raised: string;
  text_primary: string;
  text_secondary: string;
  text_muted: string;
  grid: string;
  axis: string;
  border: string;
  categorical: string[];
  diverging: string[];
  diverging_mid: string;
  ordinal: string[];
}

export type Mode = "dark" | "light";

export const DARK: Surface = {
  name: "dark",
  page: "#0B1020",
  surface: "#141B34",
  surface_raised: "#1B2444",
  text_primary: "#FFFFFF",
  text_secondary: "#C3C2B7",
  text_muted: "#898781",
  grid: "#233056",
  axis: "#33406B",
  border: "rgba(255,255,255,0.10)",
  categorical: CATEGORICAL_DARK,
  diverging: DIVERGING_DARK,
  diverging_mid: DIVERGING_MID_DARK,
  ordinal: ORDINAL_BLUE_DARK,
};

export const LIGHT: Surface = {
  name: "light",
  page: "#F7F9FC",
  surface: "#FFFFFF",
  surface_raised: "#FFFFFF",
  text_primary: "#0B0B0B",
  text_secondary: "#52514E",
  text_muted: "#898781",
  grid: "#E6EAF2",
  axis: "#C3C2B7",
  border: "rgba(11,11,11,0.10)",
  categorical: CATEGORICAL_LIGHT,
  diverging: DIVERGING_LIGHT,
  diverging_mid: DIVERGING_MID_LIGHT,
  ordinal: ORDINAL_BLUE_LIGHT,
};

export const SURFACES: Record<Mode, Surface> = { dark: DARK, light: LIGHT };
export const DEFAULT_MODE: Mode = "dark";

export function surface(mode: Mode = DEFAULT_MODE): Surface {
  return SURFACES[mode] ?? DARK;
}

// --------------------------------------------------------------------------
// Stable entity -> colour bindings
// --------------------------------------------------------------------------

export const PROVIDER_SLOT: Record<string, number> = { AWS: 0, Azure: 1, GCP: 2 };
export const PROVIDERS: string[] = ["AWS", "Azure", "GCP"];
export const OTHER_LABEL = "Other";

export function providerColour(provider: string, mode: Mode = DEFAULT_MODE): string {
  const s = surface(mode);
  const slot = PROVIDER_SLOT[provider];
  if (slot === undefined) return s.text_muted;
  return s.categorical[slot];
}

/**
 * Bind entities to categorical slots in fixed order. Past 8 entities we do not
 * generate or cycle hues -- the caller must have folded the tail into
 * `OTHER_LABEL`, which is painted in muted ink so it recedes.
 */
export function colourMap(entities: string[], mode: Mode = DEFAULT_MODE): Record<string, string> {
  const s = surface(mode);
  const out: Record<string, string> = {};
  let slot = 0;
  const used = new Set<string>();
  for (const e of entities) {
    if (e === OTHER_LABEL) {
      out[e] = s.text_muted;
      continue;
    }
    if (e in PROVIDER_SLOT) {
      const c = s.categorical[PROVIDER_SLOT[e]];
      out[e] = c;
      used.add(c);
      continue;
    }
    while (slot < s.categorical.length && used.has(s.categorical[slot])) slot += 1;
    const c = slot < s.categorical.length ? s.categorical[slot] : s.text_muted;
    out[e] = c;
    used.add(c);
    slot += 1;
  }
  return out;
}

/**
 * Collapse everything past `limit-1` entities into a single `Other` row.
 * Prevents the 9th-hue anti-pattern at the source rather than in the chart.
 */
export function foldTail(
  labelsAndValues: Array<[string, number]>,
  limit = 8,
): Array<[string, number]> {
  const rows = [...labelsAndValues].sort((a, b) => b[1] - a[1]);
  if (rows.length <= limit) return rows;
  const head = rows.slice(0, limit - 1);
  const tailTotal = rows.slice(limit - 1).reduce((acc, [, v]) => acc + v, 0);
  return [...head, [OTHER_LABEL, tailTotal]];
}

// --------------------------------------------------------------------------
// Typography -- system sans everywhere, including hero figures.
// --------------------------------------------------------------------------

export const FONT_STACK =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif';
export const FONT_MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace';

// The client-side mirror of finops_core repository.GROUPABLE. A whitelist, not
// a suggestion: it is how we know which column key an aggregate row carries
// (e.g. anomalies keyed by `ServiceCategory`, allocation by `tag_business_unit`).
export const GROUPABLE: Record<string, string> = {
  cloud: "ProviderName",
  service_category: "ServiceCategory",
  service: "ServiceName",
  region: "RegionId",
  sub_account: "SubAccountId",
  application: "tag_application",
  business_unit: "tag_business_unit",
  environment: "tag_environment",
  cost_center: "tag_cost_center",
  charge_category: "ChargeCategory",
};

export function resolveColumn(dimension: string): string {
  return GROUPABLE[dimension] ?? dimension;
}
