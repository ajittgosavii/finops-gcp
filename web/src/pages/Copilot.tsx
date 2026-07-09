import { useEffect, useMemo, useRef, useState } from "react";

import { Callout } from "../components/Callout";
import { Panel } from "../components/Panel";
import type { AgentCard } from "../lib/api";
import { useAgentTeam, useMeta } from "../lib/queries";
import { streamAsk } from "../lib/sse";

interface ToolTrace {
  agent: string;
  tool: string;
  args: Record<string, unknown>;
}
interface Turn {
  role: "user" | "agent";
  text: string;
  traces?: ToolTrace[];
  error?: boolean;
}

export function Copilot() {
  const { data: meta } = useMeta();
  const team = useAgentTeam();
  const personas = meta?.personas ?? ["Leadership"];
  const [persona, setPersona] = useState<string>("");
  const activePersona = persona || personas[0] || "Leadership";

  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const sessionId = useRef<string>(crypto.randomUUID());
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  const aiEnabled = team.data?.enabled ?? meta?.ai_enabled ?? false;

  async function ask() {
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    setTurns((t) => [...t, { role: "user", text: q }, { role: "agent", text: "", traces: [] }]);
    setBusy(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const patchAgent = (fn: (turn: Turn) => Turn) =>
      setTurns((t) => {
        const copy = [...t];
        for (let i = copy.length - 1; i >= 0; i--) {
          if (copy[i].role === "agent") {
            copy[i] = fn(copy[i]);
            break;
          }
        }
        return copy;
      });

    await streamAsk(
      { question: q, persona: activePersona, session_id: sessionId.current },
      (frame) => {
        let payload: Record<string, unknown> = {};
        try {
          payload = frame.data ? JSON.parse(frame.data) : {};
        } catch {
          payload = { text: frame.data };
        }
        if (frame.event === "tool") {
          patchAgent((turn) => ({
            ...turn,
            traces: [
              ...(turn.traces ?? []),
              {
                agent: String(payload.agent ?? ""),
                tool: String(payload.tool ?? ""),
                args: (payload.args as Record<string, unknown>) ?? {},
              },
            ],
          }));
        } else if (frame.event === "token") {
          patchAgent((turn) => ({ ...turn, text: turn.text + String(payload.text ?? "") }));
        } else if (frame.event === "final") {
          patchAgent((turn) => ({ ...turn, text: String(payload.text ?? turn.text) }));
        } else if (frame.event === "error") {
          patchAgent((turn) => ({ ...turn, text: String(payload.message ?? "Error"), error: true }));
        }
      },
      ctrl.signal,
    );
    setBusy(false);
  }

  return (
    <div className="copilot">
      <div className="chat-col">
        <Panel
          title="FinOps Copilot"
          subtitle={`Coordinator + 4 specialists · persona: ${activePersona}`}
          actions={
            <select
              className="persona-select"
              value={activePersona}
              onChange={(e) => setPersona(e.target.value)}
            >
              {personas.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          }
        >
          {!aiEnabled && (
            <Callout tone="caution" title="Gemini is not configured">
              The dashboards are fully live on demo data; only the Copilot needs a model. Set{" "}
              <code>GOOGLE_CLOUD_PROJECT</code> (Vertex, the default) — or{" "}
              <code>GOOGLE_API_KEY</code> with <code>GOOGLE_GENAI_USE_VERTEXAI=FALSE</code> — and
              restart the API. The agent team below is the roster that would answer.
            </Callout>
          )}

          <div className="chat-scroll" ref={scrollRef} style={{ marginTop: 12 }}>
            {turns.length === 0 && (
              <p className="muted">
                Ask about spend, forecast, savings or governance. Every answer streams its tool calls
                as a provenance trace, so you can see which engine function produced each number.
              </p>
            )}
            {turns.map((t, i) =>
              t.role === "user" ? (
                <div key={i} className="msg msg-user">
                  {t.text}
                </div>
              ) : (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {t.traces && t.traces.length > 0 && (
                    <div className="trace">
                      {t.traces.map((tr, j) => (
                        <div key={j} className="trace-line">
                          <b>{tr.agent}</b> called <b>{tr.tool}</b>
                          {Object.keys(tr.args).length ? ` (${JSON.stringify(tr.args)})` : ""}
                        </div>
                      ))}
                    </div>
                  )}
                  {(t.text || busy) && (
                    <div className={`msg msg-agent${t.error ? " error" : ""}`}>
                      {t.text || <span className="muted">thinking…</span>}
                    </div>
                  )}
                </div>
              ),
            )}
          </div>

          <div className="chat-input">
            <input
              value={input}
              placeholder={aiEnabled ? "Ask the FinOps team…" : "Copilot disabled — see note above"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              disabled={!aiEnabled || busy}
            />
            <button onClick={ask} disabled={!aiEnabled || busy || !input.trim()}>
              {busy ? "…" : "Send"}
            </button>
          </div>
        </Panel>
      </div>

      <div className="stack">
        {(team.data?.agents ?? []).map((a) => (
          <AgentCardView key={a.name} agent={a} />
        ))}
      </div>
    </div>
  );
}

function AgentCardView({ agent }: { agent: AgentCard }) {
  const tools = useMemo(() => agent.tools, [agent.tools]);
  return (
    <div className="agent-card">
      <div className="agent-domain">{agent.domain}</div>
      <h4>{agent.name}</h4>
      <div className="agent-desc">{agent.description}</div>
      <div>
        {tools.map((t) => (
          <span key={t.name} className="tool-chip" title={t.summary}>
            {t.name}
          </span>
        ))}
      </div>
      <div className="muted" style={{ marginTop: 6, fontSize: 11 }}>
        {agent.model}
      </div>
    </div>
  );
}
