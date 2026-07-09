"""Running the team, and streaming its answer to a browser.

ADK's `Runner.run_async` yields `Event`s. Two flags matter:

    event.partial            a streaming chunk, not the whole message
    event.is_final_response() no pending function calls, and not partial

We forward the coordinator's text and suppress the specialists'. A specialist's
answer is an intermediate result the coordinator will summarise; showing both
means the user reads the same finding twice, in two registers.

Tool calls are surfaced as their own SSE event type, because "which tool did that
number come from" is the single most important thing about this feature. The
React client renders them as a trace.

A provider error is a normal state, not a crash. `_explain` turns the three that
actually happen -- no access to the model, out of quota, bad credentials -- into
something an operator can act on, naming the setting to change.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.team import get_team
from app.settings import Settings, get_settings

APP_NAME = "finops"

# One runner per persona, reused across requests. Building it per request would
# rebuild four agents and their tool schemas on every question.
_runners: Dict[str, InMemoryRunner] = {}


def _runner(persona: str) -> InMemoryRunner:
    if persona not in _runners:
        _runners[persona] = InMemoryRunner(agent=get_team(persona), app_name=APP_NAME)
    return _runners[persona]


def _explain(exc: Exception, settings: Settings) -> str:
    text = f"{type(exc).__name__}: {exc}"
    low = text.lower()

    if "not found" in low and "model" in low or "does not exist" in low:
        return (
            f"The configured model `{settings.model_reasoning}` is not reachable. "
            "Google's current identifiers are `gemini-3.5-flash`, `gemini-3.1-flash-lite` "
            "and `gemini-3.1-pro-preview`; there is no bare `gemini-3-flash`. "
            "Set MODEL_REASONING / MODEL_ROUTING and redeploy."
        )
    if "quota" in low or "429" in low or "resource_exhausted" in low:
        return (
            "The Gemini quota is exhausted or rate-limited. Every dashboard still works; "
            "only the Copilot needs the model."
        )
    if "permission" in low or "401" in low or "403" in low or "credential" in low:
        return (
            "Gemini rejected our credentials. On Cloud Run this means the service account "
            "lacks `roles/aiplatform.user`, or GOOGLE_CLOUD_PROJECT is unset."
        )
    return f"The agent team could not complete that request. Dashboards are unaffected. ({text[:200]})"


def sse(event: str, data: Any) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_answer(
    question: str,
    persona: str = "Leadership",
    session_id: Optional[str] = None,
    user_id: str = "anonymous",
) -> AsyncGenerator[str, None]:
    """Yield SSE frames: `token`, `tool`, `done`, or `error`."""
    settings = get_settings()

    if not settings.ai_enabled:
        yield sse(
            "error",
            {
                "message": (
                    "Gemini is not configured. Set GOOGLE_CLOUD_PROJECT (Vertex, the default) "
                    "or GOOGLE_API_KEY with GOOGLE_GENAI_USE_VERTEXAI=FALSE."
                )
            },
        )
        yield sse("done", {"ok": False})
        return

    runner = _runner(persona)
    sid = session_id or str(uuid.uuid4())

    try:
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=sid,
            state={"organisation": settings.organisation},
        )
    except Exception:
        pass  # already exists; resuming a conversation is the normal case

    message = types.Content(role="user", parts=[types.Part(text=question)])

    try:
        async for event in runner.run_async(user_id=user_id, session_id=sid, new_message=message):
            # Surface every tool call: provenance is the point of this feature.
            for call in event.get_function_calls() or []:
                yield sse("tool", {"agent": event.author, "tool": call.name, "args": dict(call.args or {})})

            if event.author != "finops_coordinator":
                continue  # a specialist's prose is an intermediate result

            if not event.content or not event.content.parts:
                continue
            text = "".join(p.text or "" for p in event.content.parts)
            if not text:
                continue

            if event.partial:
                yield sse("token", {"text": text})
            elif event.is_final_response():
                yield sse("final", {"text": text})

        yield sse("done", {"ok": True, "session_id": sid})

    except Exception as exc:
        yield sse("error", {"message": _explain(exc, settings)})
        yield sse("done", {"ok": False, "session_id": sid})
