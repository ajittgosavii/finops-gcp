/**
 * Chart builders. Each returns Plotly `{ data, layout }` following the rules in
 * charts.py. Components render these; they make no chart-design decisions.
 */

import type { Data, Layout } from "plotly.js-dist-min";

import type { Mode } from "../lib/tokens";
import { colourMap, providerColour, SEQUENTIAL_BLUE, STATUS, surface } from "../lib/tokens";
import {
  AREA_OPACITY,
  baseLayout,
  GAP_WIDTH,
  hexToRgba,
  LINE_WIDTH,
  MARKER_SIZE,
  moneyHover,
  RING_WIDTH,
} from "./layout";

export interface Figure {
  data: Data[];
  layout: Partial<Layout>;
}

// --------------------------------------------------------------------------
// Forecast fan chart -- actual, dashed forecast, 80/95% bands, optional cliffs
// --------------------------------------------------------------------------

export interface FanPoint {
  x: string;
  cost: number;
  lo80?: number;
  hi80?: number;
  lo95?: number;
  hi95?: number;
  cost_with_cliffs?: number;
}

export function forecastFan(
  history: Array<{ x: string; cost: number }>,
  forecast: FanPoint[],
  mode: Mode,
  height = 400,
): Figure {
  const s = surface(mode);
  const accent = s.categorical[0];
  const data: Data[] = [];
  const fx = forecast.map((f) => f.x);

  // 95% band (outer, faintest)
  if (forecast.every((f) => f.lo95 !== undefined && f.hi95 !== undefined)) {
    data.push({
      x: [...fx, ...fx.slice().reverse()],
      y: [...forecast.map((f) => f.hi95 as number), ...forecast.map((f) => f.lo95 as number).reverse()],
      fill: "toself",
      fillcolor: hexToRgba(accent, AREA_OPACITY * 0.6),
      line: { width: 0 },
      hoverinfo: "skip",
      name: "95% likely range",
      type: "scatter",
      mode: "lines",
      showlegend: true,
    } as Data);
  }
  // 80% band (inner)
  if (forecast.every((f) => f.lo80 !== undefined && f.hi80 !== undefined)) {
    data.push({
      x: [...fx, ...fx.slice().reverse()],
      y: [...forecast.map((f) => f.hi80 as number), ...forecast.map((f) => f.lo80 as number).reverse()],
      fill: "toself",
      fillcolor: hexToRgba(accent, AREA_OPACITY * 1.4),
      line: { width: 0 },
      hoverinfo: "skip",
      name: "80% likely range",
      type: "scatter",
      mode: "lines",
      showlegend: true,
    } as Data);
  }

  // Actuals
  data.push({
    x: history.map((h) => h.x),
    y: history.map((h) => h.cost),
    mode: "lines",
    name: "Actual",
    type: "scatter",
    line: { color: accent, width: LINE_WIDTH, shape: "linear" },
    hovertemplate: moneyHover("Actual  "),
  } as Data);

  // Point forecast -- dashed because it IS a projection
  data.push({
    x: fx,
    y: forecast.map((f) => f.cost),
    mode: "lines",
    name: "Forecast",
    type: "scatter",
    line: { color: accent, width: LINE_WIDTH, dash: "dash" },
    hovertemplate: moneyHover("Forecast  "),
  } as Data);

  // Commitment-cliff overlay -- second series, warm, only when present
  if (forecast.some((f) => f.cost_with_cliffs !== undefined)) {
    data.push({
      x: fx,
      y: forecast.map((f) => f.cost_with_cliffs ?? f.cost),
      mode: "lines",
      name: "With commitment cliffs",
      type: "scatter",
      line: { color: STATUS.serious, width: LINE_WIDTH, dash: "dot" },
      hovertemplate: moneyHover("With cliffs  "),
    } as Data);
  }

  // One selective direct label: the terminal forecast value.
  if (forecast.length) {
    const last = forecast[forecast.length - 1];
    data.push({
      x: [last.x],
      y: [last.cost],
      mode: "markers+text",
      type: "scatter",
      marker: { size: MARKER_SIZE, color: accent, line: { width: RING_WIDTH, color: s.surface } },
      text: [`  $${Math.round(last.cost).toLocaleString("en-US")}`],
      textposition: "middle right",
      textfont: { color: s.text_primary, size: 11 },
      showlegend: false,
      hoverinfo: "skip",
    } as unknown as Data);
  }

  const layout = baseLayout(mode, height);
  (layout.yaxis as Record<string, unknown>).tickprefix = "$";
  (layout.yaxis as Record<string, unknown>).tickformat = ",.0f";
  return { data, layout };
}

// --------------------------------------------------------------------------
// Stacked area of spend over time
// --------------------------------------------------------------------------

export function stackedArea(
  rows: Array<{ period: string; series: string; cost: number }>,
  mode: Mode,
  height = 340,
): Figure {
  const entities = [...new Set(rows.map((r) => r.series))];
  const cmap = colourMap(entities, mode);
  const data: Data[] = entities.map((e) => {
    const sub = rows.filter((r) => r.series === e).sort((a, b) => a.period.localeCompare(b.period));
    const c = cmap[e];
    return {
      x: sub.map((r) => r.period),
      y: sub.map((r) => r.cost),
      name: e,
      mode: "lines",
      type: "scatter",
      stackgroup: "one",
      line: { width: LINE_WIDTH, color: c },
      fillcolor: hexToRgba(c, 0.35),
      hovertemplate: `${e}  $%{y:,.0f}<extra></extra>`,
    } as Data;
  });
  const layout = baseLayout(mode, height, entities.length >= 2);
  (layout.yaxis as Record<string, unknown>).tickprefix = "$";
  return { data, layout };
}

// --------------------------------------------------------------------------
// Ranked horizontal bar -- one series, one colour
// --------------------------------------------------------------------------

export function rankedBar(
  labels: string[],
  values: number[],
  mode: Mode,
  height = 360,
  valuePrefix = "$",
  valueSuffix = "",
  decimals = 0,
): Figure {
  const s = surface(mode);
  const accent = s.categorical[0];
  const data: Data[] = [
    {
      x: values,
      y: labels,
      orientation: "h",
      type: "bar",
      marker: { color: accent, line: { width: GAP_WIDTH, color: s.surface } },
      text: values.map(
        (v) =>
          `${valuePrefix}${v.toLocaleString("en-US", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          })}${valueSuffix}`,
      ),
      textposition: "outside",
      textfont: { color: s.text_secondary, size: 11 },
      hovertemplate: `%{y}  ${valuePrefix}%{x:,.${decimals}f}${valueSuffix}<extra></extra>`,
      cliponaxis: false,
    } as Data,
  ];
  const layout = baseLayout(mode, height, false);
  (layout.yaxis as Record<string, unknown>).autorange = "reversed";
  (layout.yaxis as Record<string, unknown>).showgrid = false;
  (layout.xaxis as Record<string, unknown>).showgrid = true;
  (layout.xaxis as Record<string, unknown>).gridcolor = s.grid;
  (layout as Record<string, unknown>).bargap = 0.45;
  (layout.margin as Record<string, unknown>).l = 180;
  return { data, layout };
}

// --------------------------------------------------------------------------
// Stacked bar (categorical x, stacked series)
// --------------------------------------------------------------------------

export function stackedBar(
  categories: string[],
  series: Array<{ name: string; values: number[]; colour?: string }>,
  mode: Mode,
  height = 340,
): Figure {
  const s = surface(mode);
  const names = series.map((x) => x.name);
  const cmap = colourMap(names, mode);
  const data: Data[] = series.map((ser) => ({
    x: categories,
    y: ser.values,
    name: ser.name,
    type: "bar",
    marker: {
      color: ser.colour ?? cmap[ser.name],
      line: { width: GAP_WIDTH, color: s.surface },
    },
    hovertemplate: `${ser.name}  $%{y:,.0f}<extra></extra>`,
  })) as Data[];
  const layout = baseLayout(mode, height, series.length >= 2);
  (layout as Record<string, unknown>).barmode = "stack";
  (layout as Record<string, unknown>).bargap = 0.35;
  (layout.yaxis as Record<string, unknown>).tickprefix = "$";
  return { data, layout };
}

// --------------------------------------------------------------------------
// Treemap (cloud -> application), coloured by cloud (a pinned entity)
// --------------------------------------------------------------------------

export function treemap(
  rows: Array<{ level1: string; level2: string; value: number }>,
  mode: Mode,
  height = 460,
): Figure {
  const s = surface(mode);
  const labels: string[] = [];
  const parents: string[] = [];
  const values: number[] = [];
  const colours: string[] = [];
  const ids: string[] = [];

  const root = "All spend";
  labels.push(root);
  parents.push("");
  ids.push(root);
  values.push(rows.reduce((a, r) => a + r.value, 0));
  colours.push(s.surface_raised);

  const l1names = [...new Set(rows.map((r) => r.level1))];
  const cmap = colourMap([...l1names].sort(), mode);

  for (const name of l1names) {
    const total = rows.filter((r) => r.level1 === name).reduce((a, r) => a + r.value, 0);
    labels.push(name);
    parents.push(root);
    ids.push(name);
    values.push(total);
    colours.push(name in cmap ? cmap[name] : providerColour(name, mode));
  }

  // Level 2 only when the rows carry it. A single-level treemap (level2 = "")
  // is a valid composition: each level-1 node is a leaf under the root.
  for (const r of rows) {
    if (!r.level2) continue;
    const id = `${r.level1}/${r.level2}`;
    labels.push(r.level2);
    parents.push(r.level1);
    ids.push(id);
    values.push(r.value);
    colours.push(hexToRgba(cmap[r.level1] ?? s.categorical[0], 0.55));
  }

  const data: Data[] = [
    {
      type: "treemap",
      labels,
      parents,
      ids,
      values,
      branchvalues: "total",
      marker: { colors: colours, line: { width: GAP_WIDTH, color: s.surface } },
      texttemplate: "<b>%{label}</b><br>$%{value:,.0f}",
      hovertemplate: "%{label}<br>$%{value:,.0f}<br>%{percentParent} of parent<extra></extra>",
      tiling: { pad: 2 },
      pathbar: { visible: true },
      insidetextfont: { color: "#FFFFFF", size: 12 },
    } as unknown as Data,
  ];
  const layout = baseLayout(mode, height, false);
  delete (layout as Record<string, unknown>).xaxis;
  delete (layout as Record<string, unknown>).yaxis;
  (layout as Record<string, unknown>).hovermode = "closest";
  return { data, layout };
}

// --------------------------------------------------------------------------
// Heatmap -- continuous magnitude, one hue light -> dark
// --------------------------------------------------------------------------

export function heatmap(
  z: number[][],
  xLabels: string[],
  yLabels: string[],
  mode: Mode,
  height = 380,
  valuePrefix = "$",
): Figure {
  const s = surface(mode);
  let ramp = SEQUENTIAL_BLUE;
  if (mode === "dark") ramp = [...SEQUENTIAL_BLUE].reverse(); // dark surface: light = high
  const stops: Array<[number, string]> = ramp.map((c, i) => [i / (ramp.length - 1), c]);

  const data: Data[] = [
    {
      type: "heatmap",
      z,
      x: xLabels,
      y: yLabels,
      colorscale: stops,
      xgap: GAP_WIDTH,
      ygap: GAP_WIDTH,
      hovertemplate: `%{y} · %{x}<br>${valuePrefix}%{z:,.0f}<extra></extra>`,
      colorbar: {
        tickfont: { color: s.text_muted, size: 10 },
        outlinewidth: 0,
        thickness: 10,
      },
    } as Data,
  ];
  const layout = baseLayout(mode, height, false);
  (layout.yaxis as Record<string, unknown>).showgrid = false;
  (layout as Record<string, unknown>).hovermode = "closest";
  (layout.margin as Record<string, unknown>).l = 150;
  return { data, layout };
}

// --------------------------------------------------------------------------
// Anomaly scatter -- daily line + flagged DIAMOND markers (secondary channel)
// --------------------------------------------------------------------------

export function anomalyScatter(
  actual: Array<{ x: string; y: number; flagged: boolean }>,
  expected: Array<{ x: string; y: number }>,
  mode: Mode,
  height = 340,
): Figure {
  const s = surface(mode);
  const data: Data[] = [];

  // Expected baseline (muted) -- gives the anomalies something to deviate from.
  if (expected.length) {
    data.push({
      x: expected.map((p) => p.x),
      y: expected.map((p) => p.y),
      mode: "markers",
      type: "scatter",
      name: "Expected",
      marker: { size: 6, color: s.text_muted, symbol: "circle-open" },
      hovertemplate: "Expected  $%{y:,.0f}<extra></extra>",
    } as Data);
  }

  // Actual value at each flagged point (line connects them chronologically).
  data.push({
    x: actual.map((p) => p.x),
    y: actual.map((p) => p.y),
    mode: "lines",
    type: "scatter",
    name: "Observed",
    line: { color: s.categorical[0], width: LINE_WIDTH },
    hovertemplate: "Observed  $%{y:,.0f}<extra></extra>",
  } as Data);

  const flagged = actual.filter((p) => p.flagged);
  if (flagged.length) {
    data.push({
      x: flagged.map((p) => p.x),
      y: flagged.map((p) => p.y),
      mode: "markers",
      type: "scatter",
      name: "Anomaly",
      marker: {
        size: MARKER_SIZE + 3,
        symbol: "diamond",
        color: STATUS.critical,
        line: { width: RING_WIDTH, color: s.surface },
      },
      hovertemplate: "Anomaly  $%{y:,.0f}<extra></extra>",
    } as Data);
  }

  const layout = baseLayout(mode, height, true);
  (layout.yaxis as Record<string, unknown>).tickprefix = "$";
  return { data, layout };
}
