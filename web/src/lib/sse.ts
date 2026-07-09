/**
 * POST + Server-Sent-Events reader.
 *
 * EventSource cannot POST, so we drive `fetch()` with a ReadableStream reader
 * and parse `event:`/`data:` frames by hand. Frames can split across network
 * chunks, so we keep a buffer and only dispatch on a blank-line boundary.
 *
 * The FinOps API emits: tool | token | final | done | error.
 */

import { API_BASE } from "./api";

export type SseEvent = "tool" | "token" | "final" | "done" | "error" | "message";

export interface SseFrame {
  event: SseEvent;
  data: string;
}

export interface AskBody {
  question: string;
  persona: string;
  session_id?: string | null;
}

/**
 * Stream `/api/agent/ask`. Calls `onFrame` per parsed frame. Resolves when the
 * stream ends (or a `done`/`error` frame arrives). Abort via the signal.
 */
export async function streamAsk(
  body: AskBody,
  onFrame: (frame: SseFrame) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/agent/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j?.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    onFrame({ event: "error", data: JSON.stringify({ message: detail }) });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (raw: string) => {
    const lines = raw.split("\n");
    let event: SseEvent = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith(":")) continue; // comment / heartbeat
      if (line.startsWith("event:")) {
        event = line.slice(6).trim() as SseEvent;
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }
    if (dataLines.length || event !== "message") {
      onFrame({ event, data: dataLines.join("\n") });
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Frames are separated by a blank line. Split on the boundary, keep the
      // trailing partial frame in the buffer.
      let idx: number;
      // Normalise CRLF so the boundary test is simple.
      buffer = buffer.replace(/\r\n/g, "\n");
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        if (frame.trim()) dispatch(frame);
      }
    }
    if (buffer.trim()) dispatch(buffer);
  } catch (err) {
    if ((err as Error)?.name !== "AbortError") {
      onFrame({ event: "error", data: JSON.stringify({ message: String(err) }) });
    }
  } finally {
    reader.releaseLock();
  }
}
