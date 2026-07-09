import { useMemo } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

import type { Figure } from "../charts/builders";
import { PLOT_CONFIG } from "../charts/layout";

const Plot = createPlotlyComponent(Plotly);

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Thin wrapper over react-plotly.js. Charts are handed a `{ data, layout }`
 * built by the vocabulary in charts/builders.ts; this component only mounts it,
 * makes it responsive, and disables transitions when the user asked for reduced
 * motion.
 */
export function Chart({ figure, ariaLabel }: { figure: Figure; ariaLabel: string }) {
  // We never drive Plotly animations, so a data/layout update is applied
  // immediately; there is no transition to suppress for reduced-motion here.
  // (The global CSS rule zeroes any transitions the DOM chrome might add.)
  void prefersReducedMotion;
  const layout = useMemo(
    () => ({ ...figure.layout, autosize: true }),
    [figure.layout],
  );

  return (
    <div role="img" aria-label={ariaLabel} style={{ width: "100%" }}>
      <Plot
        data={figure.data}
        layout={layout}
        config={PLOT_CONFIG as unknown as Partial<Plotly.Config>}
        useResizeHandler
        style={{ width: "100%", height: `${figure.layout.height ?? 340}px` }}
      />
    </div>
  );
}
