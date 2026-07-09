import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useMeta } from "../lib/queries";
import { useTheme } from "../theme/ThemeContext";
import { FilterBar } from "./FilterBar";

const NAV: Array<{ to: string; label: string; icon: string }> = [
  { to: "/", label: "Executive", icon: "◆" },
  { to: "/applications", label: "Applications", icon: "▤" },
  { to: "/showback", label: "Showback", icon: "◫" },
  { to: "/forecast", label: "Forecast", icon: "◈" },
  { to: "/optimize", label: "Optimize", icon: "↓" },
  { to: "/anomalies", label: "Anomalies", icon: "◇" },
  { to: "/governance", label: "Governance", icon: "▣" },
  { to: "/copilot", label: "Copilot", icon: "✦" },
  { to: "/integrations", label: "Integrations", icon: "⚙" },
];

function Masthead() {
  const { data: meta } = useMeta();
  const { mode, toggle } = useTheme();
  return (
    <header className="masthead">
      <div className="masthead-brand">
        <span className="wordmark">Infosys</span>
        <span className="brand-sep" aria-hidden>
          /
        </span>
        <span className="product">Multi-Cloud FinOps Command Center</span>
      </div>
      <div className="masthead-right">
        {meta && (
          <span className="env-chip" title="Data source and environment">
            {meta.source.live ? "Live" : "Demo"} · {meta.organisation} · FOCUS {meta.focus_version}
          </span>
        )}
        <button className="ghost-btn theme-toggle" onClick={toggle} aria-label="Toggle theme">
          {mode === "dark" ? "☾" : "☀"}
        </button>
      </div>
    </header>
  );
}

function Sidebar() {
  return (
    <nav className="sidebar" aria-label="Primary">
      {NAV.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === "/"}
          className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
        >
          <span className="nav-icon" aria-hidden>
            {n.icon}
          </span>
          <span className="nav-label">{n.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function Shell() {
  const { pathname } = useLocation();
  // The Copilot is a conversation, not a scoped report; the filter row would
  // only mislead there.
  const showFilter = pathname !== "/copilot";
  return (
    <div className="app-shell">
      <Masthead />
      <div className="app-body">
        <Sidebar />
        <main className="content">
          {showFilter && (
            <div className="filter-row">
              <FilterBar />
            </div>
          )}
          <div className="page">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
