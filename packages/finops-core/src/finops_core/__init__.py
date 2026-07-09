"""finops_core -- the FOCUS contract, the KPI formulas, the engines, the connectors.

This package is deliberately boring. It knows nothing about Streamlit, FastAPI,
React, Google Cloud, or any LLM. It takes pandas DataFrames and returns pandas
DataFrames, and it reads configuration from a mapping the caller supplies.

That is what lets the same ~9,000 lines serve a Streamlit demo, a FastAPI service
on Cloud Run, and a nightly Cloud Run Job without a fork.

The contract, in dependency order:

    focus       FOCUS 1.2 schema, closed enums, validation, tag normalisation
    kpi         every executive formula -- ESR, coverage, waste, variance
    config      Mode, AppConfig, AccountBinding, DataContext, FinOps vocabulary
    engines/    forecast, budget, anomaly, allocation, optimize
    connectors/ 17 sources, all returning a FOCUS 1.2 frame

`focus.py` is the contract. Read it first.

Regenerate from the Streamlit app with:  python tools/extract_core.py
"""

from __future__ import annotations

__version__ = "1.0.0"

from finops_core import focus, kpi  # noqa: F401
from finops_core.config import (  # noqa: F401
    ALLIED_PERSONAS,
    CAPABILITIES,
    CLOUDS,
    CORE_PERSONAS,
    DOMAINS,
    FORECAST_VARIANCE_THRESHOLD,
    MATURITY,
    PHASES,
    SCOPES,
    AccountBinding,
    AppConfig,
    DataContext,
    Mode,
    SourceInfo,
    load_config,
    maturity_for_variance,
)

__all__ = [
    "focus", "kpi", "AccountBinding", "AppConfig", "DataContext", "Mode",
    "SourceInfo", "load_config", "maturity_for_variance", "CLOUDS", "DOMAINS",
    "CAPABILITIES", "PHASES", "MATURITY", "SCOPES", "CORE_PERSONAS",
    "ALLIED_PERSONAS", "FORECAST_VARIANCE_THRESHOLD", "__version__",
]
