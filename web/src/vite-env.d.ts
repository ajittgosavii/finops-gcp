/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// plotly.js-dist-min is the pre-bundled build; its types are @types/plotly.js.
declare module "plotly.js-dist-min" {
  import * as Plotly from "plotly.js";
  export = Plotly;
}

// react-plotly.js ships a factory for bring-your-own bundle (we use the dist-min
// build). The published @types cover the default export but not the factory.
declare module "react-plotly.js/factory" {
  import type { PlotParams } from "react-plotly.js";
  import type { Component } from "react";
  const createPlotlyComponent: (plotly: unknown) => {
    new (props: PlotParams): Component<PlotParams>;
  };
  export default createPlotlyComponent;
}
