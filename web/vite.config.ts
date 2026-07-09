import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The client talks to the FinOps API. In dev we proxy /api to it so the browser
// makes same-origin requests; in production VITE_API_BASE points at Cloud Run.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE || "http://localhost:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    // Plotly is a large, single vendor bundle by nature; split it out so the
    // app code chunk stays small and the warning reflects reality, not a bug.
    chunkSizeWarningLimit: 5200,
    rollupOptions: {
      output: {
        manualChunks: {
          plotly: ["plotly.js-dist-min", "react-plotly.js"],
        },
      },
    },
  },
});
