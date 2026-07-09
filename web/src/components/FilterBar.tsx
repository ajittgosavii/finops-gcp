import { useDimensions } from "../lib/queries";
import { useScopeControls } from "../lib/scope";
import { MultiSelect } from "./MultiSelect";

/**
 * The one filter row above every page. It writes to the URL search params, so
 * the whole app reads the same Scope and a link reproduces the exact view.
 */
export function FilterBar() {
  const { scope, setMulti, setDate, clearAll } = useScopeControls();
  const { data: dims } = useDimensions();

  const hasFilters =
    scope.clouds.length ||
    scope.applications.length ||
    scope.business_units.length ||
    scope.environments.length ||
    scope.start ||
    scope.end;

  return (
    <div className="filter-bar">
      <MultiSelect
        label="Cloud"
        options={dims?.clouds ?? []}
        selected={scope.clouds}
        onChange={(v) => setMulti("clouds", v)}
      />
      <MultiSelect
        label="Application"
        options={dims?.applications ?? []}
        selected={scope.applications}
        onChange={(v) => setMulti("applications", v)}
      />
      <MultiSelect
        label="Business unit"
        options={dims?.business_units ?? []}
        selected={scope.business_units}
        onChange={(v) => setMulti("business_units", v)}
      />
      <MultiSelect
        label="Environment"
        options={dims?.environments ?? []}
        selected={scope.environments}
        onChange={(v) => setMulti("environments", v)}
      />
      <div className="date-field">
        <label>From</label>
        <input
          type="date"
          value={scope.start ?? ""}
          onChange={(e) => setDate("start", e.target.value)}
        />
      </div>
      <div className="date-field">
        <label>To</label>
        <input type="date" value={scope.end ?? ""} onChange={(e) => setDate("end", e.target.value)} />
      </div>
      {hasFilters ? (
        <button className="ghost-btn clear-scope" onClick={clearAll}>
          Reset
        </button>
      ) : null}
    </div>
  );
}
