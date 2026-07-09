# Multi-Cloud FinOps — Web client

React + TypeScript front end for the FinOps API. It **renders**; it never computes a KPI,
re-derives a percentage, or rounds a currency differently than the API did. Every figure comes
from `finops_core` through the API. If a number looks wrong, the bug is in the engine, not here.

## Stack

- Vite + React 18 + TypeScript (strict)
- `react-plotly.js` + `plotly.js-dist-min` for charts
- TanStack Query for fetching/caching
- `react-router-dom` for routing
- Plain CSS with custom properties (no component library, no Tailwind)

## Run against the API

1. Start the API (from the repo root) on port 8080:

   ```bash
   cd services/api && DATA_SOURCE=demo uvicorn app.main:app --port 8080
   ```

2. Point the client at it and start Vite:

   ```bash
   cd web
   cp .env.example .env        # VITE_API_BASE=http://localhost:8080
   npm install
   npm run dev                 # http://localhost:5173
   ```

`VITE_API_BASE` is the only configuration. In dev, Vite also proxies `/api` to that host, so the
browser makes same-origin requests. In production set it to the Cloud Run URL of the API.

## Verify

```bash
npm install
npx tsc --noEmit     # type-check (strict)
npm run build        # tsc + vite build
```

## How it is organised

```
src/
  lib/
    tokens.ts     design tokens, transcribed EXACTLY from ../../multicloud-finops/theme.py
    api.ts        every API response type + the fetch client (typed from real payloads)
    scope.ts      the one filter row, as URL state (a view is shareable)
    queries.ts    TanStack Query hooks (keyed on the scope)
    sse.ts        POST + Server-Sent-Events reader for the Copilot
    format.ts     presentation-only formatting (never re-derives a number)
  charts/
    layout.ts     Plotly base layout, ported from charts.py
    builders.ts   the chart vocabulary: fan chart, stacked area, ranked bar, treemap, heatmap…
  components/     Shell, FilterBar, Panel, Chart, ChartWithTable, DataTable, KpiTile, StatusPill…
  pages/          Executive, Applications, Showback, Forecast, Optimize, Anomalies,
                  Governance, Copilot, Integrations
  theme/          dark/light mode (dark-first)
```

## The rules the charts obey (from `charts.py` / `theme.py`)

- One y-axis, always. Two measures of different scale get two charts, never a dual axis.
- Colour follows the entity, not its rank. AWS→slot 0, Azure→slot 1, GCP→slot 2 are pinned, so
  filtering a cloud out never repaints the survivors.
- A legend whenever ≥2 series; none for one (the title names it).
- Only the endpoint or extreme is labelled — never every point.
- More than 8 categories fold the tail into a muted "Other"; a 9th hue is never generated.
- Sequential = one hue light→dark. Diverging = blue↔red with a neutral grey midpoint.
- Every chart has a **table-view twin** with a CSV download — no value is reachable only via a tooltip.
- Status is always colour **+ icon + label**, never colour alone.
- `prefers-reduced-motion` is respected.

## Known API-shape notes

- `/api/anomalies` and `/api/allocation` rows carry a **dynamic** dimension column key
  (e.g. `ServiceCategory`, `tag_business_unit`). The client resolves it from the same whitelist the
  API uses (`GROUPABLE` in `tokens.ts`).
- There is **no daily-spend-series endpoint**, so the Anomalies chart plots each flagged point's
  observed value against its model expected value, not a continuous daily line.
- There is **no row-level cross-tab endpoint** (only one dimension per `/spend/by` call, by design),
  so the Applications treemap is a single-level application composition rather than cloud→application.
