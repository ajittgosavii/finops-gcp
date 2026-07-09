/**
 * TanStack Query hooks. Every scoped query keys on `scopeKey(scope)` so that
 * changing the filter row refetches, and two views with the same scope share a
 * cache entry. `placeholderData: keepPreviousData` holds the last render at
 * reduced opacity while the next arrives -- no skeleton flash, no layout jump.
 */

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "./api";
import type { Scope } from "./scope";
import { scopeKey } from "./scope";

const keep = { placeholderData: keepPreviousData } as const;

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: ({ signal }) => api.meta(signal) });
}

export function useDimensions() {
  return useQuery({ queryKey: ["dimensions"], queryFn: ({ signal }) => api.dimensions(signal) });
}

export function useKpis(scope: Scope) {
  return useQuery({
    queryKey: ["kpis", scopeKey(scope)],
    queryFn: ({ signal }) => api.kpis(scope, signal),
    ...keep,
  });
}

export function useSpendMonthly(scope: Scope) {
  return useQuery({
    queryKey: ["spendMonthly", scopeKey(scope)],
    queryFn: ({ signal }) => api.spendMonthly(scope, signal),
    ...keep,
  });
}

export function useSpendBy(scope: Scope, dimension: string) {
  return useQuery({
    queryKey: ["spendBy", dimension, scopeKey(scope)],
    queryFn: ({ signal }) => api.spendBy(scope, dimension, signal),
    ...keep,
  });
}

export function useForecast(scope: Scope, horizon: number) {
  return useQuery({
    queryKey: ["forecast", horizon, scopeKey(scope)],
    queryFn: ({ signal }) => api.forecast(scope, horizon, signal),
    ...keep,
  });
}

export function useOpportunities(
  scope: Scope,
  opts: { min_annual_savings?: number; category?: string },
) {
  return useQuery({
    queryKey: ["opportunities", opts.min_annual_savings ?? 0, opts.category ?? "", scopeKey(scope)],
    queryFn: ({ signal }) => api.opportunities(scope, opts, signal),
    ...keep,
  });
}

export function useLevers() {
  return useQuery({ queryKey: ["levers"], queryFn: ({ signal }) => api.levers(signal) });
}

export function useAnomalies(scope: Scope, dimension: string) {
  return useQuery({
    queryKey: ["anomalies", dimension, scopeKey(scope)],
    queryFn: ({ signal }) => api.anomalies(scope, dimension, signal),
    ...keep,
  });
}

export function useAllocation(scope: Scope, dimension: string, method: string) {
  return useQuery({
    queryKey: ["allocation", dimension, method, scopeKey(scope)],
    queryFn: ({ signal }) => api.allocation(scope, dimension, method, signal),
    ...keep,
  });
}

export function useCoverage(scope: Scope) {
  return useQuery({
    queryKey: ["coverage", scopeKey(scope)],
    queryFn: ({ signal }) => api.coverage(scope, signal),
    ...keep,
  });
}

export function useAgentTeam() {
  return useQuery({ queryKey: ["agentTeam"], queryFn: ({ signal }) => api.agentTeam(signal) });
}
