import { Callout } from "../components/Callout";
import { KpiTile } from "../components/KpiTile";
import { Panel } from "../components/Panel";
import { StatusPill } from "../components/StatusPill";
import { useMeta } from "../lib/queries";

export function Integrations() {
  const { data: meta, isLoading, error } = useMeta();
  const src = meta?.source;

  return (
    <div className="stack">
      <div>
        <h1 className="page-title">Integrations</h1>
        <p className="page-lede">What is feeding this instance, and how it is configured.</p>
      </div>

      <div className="grid grid-3">
        <KpiTile label="Data source" value={src ? (src.live ? "BigQuery (live)" : "Demo") : "—"} />
        <KpiTile label="Rows in scope" value={src?.rows ? src.rows.toLocaleString("en-US") : "—"} />
        <KpiTile label="FOCUS version" value={meta?.focus_version ?? "—"} />
      </div>

      <Panel title="Source" isLoading={isLoading} error={error}>
        {src && (
          <div className="stack">
            <div className="row">
              <StatusPill
                status={src.conformant ? "good" : "warning"}
                label={src.conformant ? "FOCUS conformant" : "conformance unknown"}
              />
              <span className="muted">{src.note}</span>
            </div>
            <table className="data-table">
              <tbody>
                <MetaRow k="Organisation" v={meta?.organisation} />
                <MetaRow k="Environment" v={meta?.environment} />
                <MetaRow k="Source" v={src.source} />
                <MetaRow k="Live" v={String(src.live)} />
                {src.period_start && <MetaRow k="Period" v={`${src.period_start} → ${src.period_end}`} />}
                {src.table && <MetaRow k="Table" v={src.table} />}
                {src.max_bytes_billed && (
                  <MetaRow k="Max bytes billed" v={`${(src.max_bytes_billed / 1024 ** 3).toFixed(0)} GiB`} />
                )}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="AI models in use" isLoading={isLoading} error={error}>
        {meta && (
          <div className="stack">
            <div className="row">
              <StatusPill
                status={meta.ai_enabled ? "good" : "warning"}
                label={meta.ai_enabled ? "Copilot enabled" : "Copilot disabled"}
              />
            </div>
            <table className="data-table">
              <tbody>
                <MetaRow k="Reasoning model" v={meta.models.reasoning} />
                <MetaRow k="Routing model" v={meta.models.routing} />
                <MetaRow k="Personas" v={meta.personas.join(", ")} />
                <MetaRow k="Domains" v={meta.domains.join(" · ")} />
                <MetaRow k="Groupable dimensions" v={meta.groupable.join(", ")} />
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Callout tone="info">
        Everything on this page comes from <code>/api/meta</code>. The client never assumes a source
        — it reports whichever one the API is bound to. Routing runs on the cheap model and reasoning
        on the flagship (the small-model-first lever, applied to ourselves).
      </Callout>
    </div>
  );
}

function MetaRow({ k, v }: { k: string; v?: string }) {
  return (
    <tr>
      <td className="muted" style={{ width: 200 }}>
        {k}
      </td>
      <td>{v ?? "—"}</td>
    </tr>
  );
}
