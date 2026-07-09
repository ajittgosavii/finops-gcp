import type { ReactNode } from "react";

import { ApiError } from "../lib/api";

interface PanelProps {
  title: string;
  subtitle?: string;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "No data in the current filter scope.";
    if (error.status === 400) return `Request rejected: ${error.message}`;
    return `API error (${error.status}): ${error.message}`;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong loading this panel.";
}

/**
 * One panel. It owns loading + error locally so a failed panel shows a message
 * and never takes the page down. While refetching, the previous render is held
 * at reduced opacity -- no skeleton flash, no layout jump.
 */
export function Panel({
  title,
  subtitle,
  isLoading,
  isFetching,
  error,
  actions,
  children,
  className,
}: PanelProps) {
  return (
    <section className={`panel${className ? ` ${className}` : ""}`}>
      <header className="panel-head">
        <div>
          <h3 className="panel-title">{title}</h3>
          {subtitle && <p className="panel-sub">{subtitle}</p>}
        </div>
        {actions && <div className="panel-actions">{actions}</div>}
      </header>
      <div className="panel-body">
        {error ? (
          <div className="panel-error" role="alert">
            <span className="panel-error-icon" aria-hidden>
              ■
            </span>
            <span>{errorMessage(error)}</span>
          </div>
        ) : isLoading ? (
          <div className="panel-loading">Loading…</div>
        ) : (
          <div className={isFetching ? "is-fetching" : undefined}>{children}</div>
        )}
      </div>
    </section>
  );
}
