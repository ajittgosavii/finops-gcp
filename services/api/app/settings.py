"""Runtime configuration for the API service.

Everything arrives as an environment variable, which on Cloud Run means either a
plain env var or a Secret Manager reference mounted as one. The service never
reads a secret store directly, and `finops_core` never reads the environment at
all -- it takes the mapping we hand it. That separation is what lets the same
engines run in a Cloud Run Job, a test, and this API.

Model choice is deliberate, and the ids below are the ones Vertex actually
serves in this project. That is not a detail worth taking on trust: this file
previously named `gemini-3.5-flash`, `gemini-3.1-flash-lite` and
`gemini-3.1-pro-preview`, cited three Google documentation URLs, and warned the
reader not to "simplify" them. All three return HTTP 404. The agent routes would
have failed on first use in production.

Verified 2026-09-07 by issuing a real `generateContent` against
`us-central1-aiplatform.googleapis.com` in this project:

    gemini-2.5-pro          200 OK
    gemini-2.5-flash        200 OK
    gemini-3.5-flash        404
    gemini-3.1-flash-lite   404
    gemini-3.1-pro-preview  404
    gemini-2.0-flash        404  (retired)

We route on the cheap model and reason on the flagship -- the small-model-first
lever (G3 in our own optimization catalog) applied to ourselves.

If these need changing, re-run that check rather than reading a docs page. A
model id is a claim about a live endpoint, and the endpoint is the authority.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

# Verified by live call, not by documentation. See the module docstring.
MODEL_REASONING = "gemini-2.5-pro"
MODEL_ROUTING = "gemini-2.5-flash"
MODEL_PRO = "gemini-2.5-pro"


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # ---- identity -------------------------------------------------------
    organisation: str = "Con Edison"
    environment: str = "dev"  # dev | staging | prod

    # ---- data source ----------------------------------------------------
    # "demo"     synthetic estate generated in-process, no GCP, no credentials
    # "bigquery" the FOCUS warehouse
    data_source: str = "demo"

    gcp_project: Optional[str] = None
    gcp_location: str = "us-central1"
    bq_dataset: str = "finops"
    bq_focus_table: str = "focus_costs"
    bq_opportunities_table: str = "opportunities"

    # A hard ceiling on any query this service issues. BigQuery FAILS the job
    # rather than billing past it, which turns a runaway scan from an invoice
    # into an error. 20 GB at $6.25/TB is about 12 cents.
    bq_max_bytes_billed: int = 20 * 1024**3

    # ---- Gemini ---------------------------------------------------------
    # ADC on Cloud Run when use_vertex is true; GOOGLE_API_KEY otherwise.
    use_vertex: bool = True
    google_api_key: Optional[str] = None
    model_reasoning: str = MODEL_REASONING
    model_routing: str = MODEL_ROUTING

    # ---- serving --------------------------------------------------------
    allow_origins: List[str] = field(default_factory=lambda: ["http://localhost:5173"])
    demo_months: int = 24

    @property
    def ai_enabled(self) -> bool:
        """Vertex uses ADC, so a project id is the credential. Otherwise a key."""
        return bool(self.gcp_project) if self.use_vertex else bool(self.google_api_key)

    @property
    def focus_table_fqn(self) -> str:
        return f"{self.gcp_project}.{self.bq_dataset}.{self.bq_focus_table}"

    @property
    def opportunities_table_fqn(self) -> str:
        return f"{self.gcp_project}.{self.bq_dataset}.{self.bq_opportunities_table}"

    def genai_env(self) -> Dict[str, str]:
        """The env the google-genai SDK reads.

        The rebranded Vertex docs mention `GOOGLE_GENAI_USE_ENTERPRISE`, but the
        SDK's actual switch is `GOOGLE_GENAI_USE_VERTEXAI`. Set the real one.
        """
        env = {"GOOGLE_GENAI_USE_VERTEXAI": "TRUE" if self.use_vertex else "FALSE"}
        if self.use_vertex:
            if self.gcp_project:
                env["GOOGLE_CLOUD_PROJECT"] = self.gcp_project
            env["GOOGLE_CLOUD_LOCATION"] = self.gcp_location
        elif self.google_api_key:
            env["GOOGLE_API_KEY"] = self.google_api_key
        return env


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    origins = os.environ.get("ALLOW_ORIGINS", "http://localhost:5173")
    s = Settings(
        organisation=os.environ.get("ORGANISATION", "Con Edison"),
        environment=os.environ.get("ENVIRONMENT", "dev"),
        data_source=os.environ.get("DATA_SOURCE", "demo").strip().lower(),
        gcp_project=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT"),
        gcp_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        bq_dataset=os.environ.get("BQ_DATASET", "finops"),
        bq_focus_table=os.environ.get("BQ_FOCUS_TABLE", "focus_costs"),
        bq_opportunities_table=os.environ.get("BQ_OPPORTUNITIES_TABLE", "opportunities"),
        bq_max_bytes_billed=int(os.environ.get("BQ_MAX_BYTES_BILLED", 20 * 1024**3)),
        use_vertex=_bool("GOOGLE_GENAI_USE_VERTEXAI", default=True),
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
        model_reasoning=os.environ.get("MODEL_REASONING", MODEL_REASONING),
        model_routing=os.environ.get("MODEL_ROUTING", MODEL_ROUTING),
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        demo_months=int(os.environ.get("DEMO_MONTHS", 24)),
    )
    # Apply the SDK's env before any agent is constructed.
    os.environ.update(s.genai_env())
    return s
