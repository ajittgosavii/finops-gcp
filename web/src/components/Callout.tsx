import type { ReactNode } from "react";

/**
 * An explanatory note. The platform's method choices (showback vs chargeback,
 * why ~29 anomalies not 347, the 90% threshold's provenance) are stated in
 * plain language next to the number, not hidden in a tooltip.
 */
export function Callout({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "method" | "caution";
  title?: string;
  children: ReactNode;
}) {
  return (
    <aside className={`callout callout-${tone}`}>
      {title && <div className="callout-title">{title}</div>}
      <div className="callout-body">{children}</div>
    </aside>
  );
}
