/**
 * The one filter row, expressed as URL state so a view is shareable.
 *
 * Mirrors finops_core repository.Scope: clouds, applications, business_units,
 * environments, start, end. Every page reads the same Scope from the search
 * params, so a link reproduces exactly what the sender saw.
 */

import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export interface Scope {
  start?: string; // ISO date
  end?: string;
  clouds: string[];
  applications: string[];
  business_units: string[];
  environments: string[];
}

export const EMPTY_SCOPE: Scope = {
  clouds: [],
  applications: [],
  business_units: [],
  environments: [],
};

const MULTI_KEYS = ["clouds", "applications", "business_units", "environments"] as const;
type MultiKey = (typeof MULTI_KEYS)[number];

export function scopeFromSearch(sp: URLSearchParams): Scope {
  const scope: Scope = { ...EMPTY_SCOPE };
  const start = sp.get("start");
  const end = sp.get("end");
  if (start) scope.start = start;
  if (end) scope.end = end;
  for (const k of MULTI_KEYS) {
    const vals = sp.getAll(k);
    if (vals.length) scope[k] = vals;
  }
  return scope;
}

/** A stable string key for query caching -- two scopes with the same contents
 *  must produce the same key regardless of insertion order. */
export function scopeKey(scope: Scope): string {
  return JSON.stringify({
    start: scope.start ?? null,
    end: scope.end ?? null,
    clouds: [...scope.clouds].sort(),
    applications: [...scope.applications].sort(),
    business_units: [...scope.business_units].sort(),
    environments: [...scope.environments].sort(),
  });
}

export function useScope(): Scope {
  const [sp] = useSearchParams();
  return useMemo(() => scopeFromSearch(sp), [sp]);
}

/**
 * Read + write the shared scope. Writing preserves any non-scope params (none
 * today, but the page-local selectors keep their own keys and must survive).
 */
export function useScopeControls() {
  const [sp, setSp] = useSearchParams();
  const scope = useMemo(() => scopeFromSearch(sp), [sp]);

  function setMulti(key: MultiKey, values: string[]) {
    const next = new URLSearchParams(sp);
    next.delete(key);
    for (const v of values) next.append(key, v);
    setSp(next, { replace: false });
  }

  function setDate(key: "start" | "end", value: string) {
    const next = new URLSearchParams(sp);
    if (value) next.set(key, value);
    else next.delete(key);
    setSp(next, { replace: false });
  }

  function clearAll() {
    const next = new URLSearchParams(sp);
    for (const k of [...MULTI_KEYS, "start", "end"]) next.delete(k);
    setSp(next, { replace: false });
  }

  return { scope, setMulti, setDate, clearAll };
}
