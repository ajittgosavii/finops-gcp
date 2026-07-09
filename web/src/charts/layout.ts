/**
 * Plotly chart vocabulary, ported from ../../multicloud-finops/charts.py.
 *
 * The rules the Python encoded must survive the port:
 *   - one y-axis, always -- never a dual-scale plot
 *   - colour follows the entity, not its rank (tokens.colourMap)
 *   - a legend whenever >= 2 series; none for one (the title names it)
 *   - selective direct labels -- endpoint / extreme only
 *   - thin marks, hairline gridlines, area washes at ~10% opacity
 *   - sequential = one hue light->dark; diverging = two hues + neutral grey
 */

import type { Layout } from "plotly.js-dist-min";

import type { Mode } from "../lib/tokens";
import { FONT_STACK, surface } from "../lib/tokens";

// Mark specs (mirrors charts.py)
export const BAR_MAX_PX = 24;
export const LINE_WIDTH = 2;
export const MARKER_SIZE = 9;
export const RING_WIDTH = 2;
export const GAP_WIDTH = 2;
export const AREA_OPACITY = 0.1;

export function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export function moneyHover(prefix = ""): string {
  return `${prefix}$%{y:,.0f}<extra></extra>`;
}

export function baseLayout(mode: Mode, height = 340, showlegend = true): Partial<Layout> {
  const s = surface(mode);
  return {
    height,
    margin: { l: 56, r: 16, t: 30, b: 36 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: FONT_STACK, size: 12, color: s.text_secondary },
    showlegend,
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.02,
      xanchor: "left",
      x: 0,
      font: { color: s.text_secondary, size: 11 },
      bgcolor: "rgba(0,0,0,0)",
    },
    xaxis: {
      showgrid: false,
      zeroline: false,
      linecolor: s.axis,
      linewidth: 1,
      tickfont: { color: s.text_muted, size: 11 },
    },
    yaxis: {
      showgrid: true,
      gridcolor: s.grid,
      gridwidth: 1,
      zeroline: false,
      linecolor: "rgba(0,0,0,0)",
      tickfont: { color: s.text_muted, size: 11 },
    },
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: s.surface_raised,
      bordercolor: s.border,
      font: { family: FONT_STACK, color: s.text_primary, size: 12 },
    },
  };
}

// Config shared by every chart: no modebar clutter, responsive, honour
// prefers-reduced-motion by disabling transitions is handled in the component.
export const PLOT_CONFIG = {
  displayModeBar: false,
  responsive: true,
  displaylogo: false,
} as const;
