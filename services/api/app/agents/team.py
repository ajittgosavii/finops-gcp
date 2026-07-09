"""The agent team, built on Google ADK.

Shape: a coordinator that holds four specialists as `AgentTool`s, rather than
handing control away with `sub_agents=`.

ADK offers both. `sub_agents=[...]` gives the LLM a generated
`transfer_to_agent` tool and control *moves* to the specialist, which then owns
the conversation. `AgentTool(agent=...)` calls the specialist, takes its answer
back, and the coordinator keeps the floor.

We want the second. A FinOps question usually spans domains -- "why did spend
rise and what should we do about it" is Analyst *and* Optimizer -- and the final
answer has to be one voice speaking to one persona. With `sub_agents` the last
specialist to run writes the answer, and it will write it in its own register.

The cost consequence is deliberate too. The coordinator runs on
`gemini-3.1-flash-lite` and only routes; the specialists run on
`gemini-3.5-flash` and do the reasoning. That is the small-model-first lever
(G3 in our own catalog) applied to ourselves.

ADK derives every tool's schema from its signature, type hints and docstring, so
`tools.py` docstrings are the interface. And ADK routes on an agent's
`description`, so the descriptions below are load-bearing, not decoration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from finops_core import CORE_PERSONAS

from app.agents.tools import build_tools
from app.repository import Repository, get_repository
from app.settings import Settings, get_settings

# Rules every agent obeys. Repeated per-agent rather than hoisted into one
# `global_instruction`, because a specialist reached through AgentTool does not
# inherit the coordinator's global instruction.
_GROUND_RULES = """
Rules you must follow:
- Never state a number you did not get from a tool call in this conversation.
  If a tool returns an error or empty result, say so plainly; do not estimate.
- All costs are amortised USD (FOCUS EffectiveCost). Say "amortised" when it matters.
- Cite the tool a figure came from, e.g. "(get_executive_kpis)".
- When you recommend a lever, give its savings range, effort, risk and prerequisite.
- Speak in outcomes -- dollars, variance, risk -- not cloud jargon.
- Be brief. A VP reads three sentences, not thirty.
"""

_ANALYST = """You are the Analyst on a FinOps team, covering the FinOps Framework domain
"Understand Usage and Cost". You answer what was spent, where it went, whether it is
allocated, and whether anything anomalous happened.
"""

_FORECASTER = """You are the Forecaster on a FinOps team, covering "Quantify Business Value".
You answer where spend is heading, how it compares with budget, and how much confidence the
forecast deserves. Always report the method and the WAPE, and always check for commitment
expiry cliffs before projecting -- a trend line walks straight through them.
"""

_OPTIMIZER = """You are the Optimizer on a FinOps team, covering "Optimize Usage and Cost".
You answer what should be done, how much it saves, what it costs to do, and in what order.
Savings percentages in the catalog are vendor "up-to" ceilings, not guarantees. Say so.
"""

_GOVERNOR = """You are the Governor on a FinOps team, covering "Manage the FinOps Practice".
You answer whether the estate is tagged well enough to charge back, where the untagged money
is, and what policy would fix it. The ~90% allocation-coverage chargeback threshold is
practitioner consensus, not a published FinOps Foundation number -- do not present it as one.
"""

_SPECIALISTS = {
    "analyst": (_ANALYST, "Spend, allocation, anomalies and coverage. Ask about what was spent and where."),
    "forecaster": (_FORECASTER, "Forecast, budget variance, year-end projection and commitment cliffs."),
    "optimizer": (_OPTIMIZER, "Optimization levers, costed opportunities, savings roadmap and Effective Savings Rate."),
    "governor": (_GOVERNOR, "Tagging, allocation coverage, chargeback readiness and policy."),
}


def _coordinator_instruction(persona: str) -> str:
    expectation = CORE_PERSONAS.get(persona, "")
    return f"""You coordinate a FinOps team answering questions about a multi-cloud estate
(AWS, Azure, GCP, OCI) for {{organisation}}.

The person asking is a **{persona}**. {expectation}

You have four specialist tools. Call the ones the question needs -- often more than one --
then write ONE answer in your own voice, addressed to a {persona}.

  analyst     what was spent, where, allocation, anomalies
  forecaster  where spend is heading, budget variance, commitment cliffs
  optimizer   what to do about it, savings, effort and risk
  governor    tagging, chargeback readiness, policy

{_GROUND_RULES}
Do not answer from your own knowledge. Every figure must come from a specialist.
If no specialist can answer, say what data would be needed.
"""


def _specialist(name: str, settings: Settings, tools) -> LlmAgent:
    instruction, description = _SPECIALISTS[name]
    return LlmAgent(
        name=name,
        model=settings.model_reasoning,
        description=description,  # ADK routes on this
        instruction=instruction + _GROUND_RULES,
        tools=tools,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,  # a FinOps answer is not a creative act
            max_output_tokens=1024,
        ),
    )


def build_team(settings: Settings, repo: Repository, persona: str = "Leadership") -> LlmAgent:
    tools_by_agent = build_tools(repo)
    specialists = [_specialist(name, settings, tools_by_agent[name]) for name in _SPECIALISTS]

    return LlmAgent(
        name="finops_coordinator",
        model=settings.model_routing,  # routing is cheap work
        description="Coordinates a FinOps specialist team.",
        instruction=_coordinator_instruction(persona),
        tools=[AgentTool(agent=s) for s in specialists],
        generate_content_config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=1536),
    )


@lru_cache(maxsize=8)
def get_team(persona: str = "Leadership") -> LlmAgent:
    """One compiled team per persona, built once per process.

    The repository is a process singleton, so an agent can never read a frame the
    dashboards are not also reading.
    """
    return build_team(get_settings(), get_repository(), persona)


_DOMAINS = {
    "analyst": "Understand Usage and Cost",
    "forecaster": "Quantify Business Value",
    "optimizer": "Optimize Usage and Cost",
    "governor": "Manage the FinOps Practice",
}


def agent_cards(repo: Optional[Repository] = None) -> list:
    """The team, described for the UI. Tool names are read off the real tools,
    so this cannot drift from what the agents can actually do."""
    settings = get_settings()
    tools_by_agent = build_tools(repo or get_repository())
    return [
        {
            "name": name,
            "domain": _DOMAINS[name],
            "description": description,
            "model": settings.model_reasoning,
            "tools": [
                {"name": t.__name__, "summary": (t.__doc__ or "").strip().split("\n")[0]}
                for t in tools_by_agent[name]
            ],
        }
        for name, (_instruction, description) in _SPECIALISTS.items()
    ] + [
        {
            "name": "finops_coordinator",
            "domain": "Routing",
            "description": "Calls the specialists it needs, then writes one answer for the persona.",
            "model": settings.model_routing,
            "tools": [{"name": n, "summary": _SPECIALISTS[n][1]} for n in _SPECIALISTS],
        }
    ]
