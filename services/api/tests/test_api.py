"""API tests. No GCP project, no Gemini key, no network.

The demo repository is the same `Connector` the Streamlit app used, so these
tests also pin the contract between the two: if the API ever reports a different
total spend than `finops_core.kpi` computes, one of them is wrong and it is not
`kpi`.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATA_SOURCE", "demo")
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("GOOGLE_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from finops_core.config import CLOUDS  # noqa: E402
from finops_core.engines import optimize  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------- meta


def test_healthz_does_no_work(client: TestClient) -> None:
    assert client.get("/healthz").json()["ok"] is True


def test_meta_reports_a_conformant_demo_estate(client: TestClient) -> None:
    m = client.get("/api/meta").json()
    assert m["source"]["source"] == "demo"
    assert m["source"]["conformant"] is True
    assert m["source"]["rows"] > 10_000
    assert m["focus_version"] == "1.2"
    assert m["ai_enabled"] is False  # no project, no key


def test_models_are_ones_that_actually_exist(client: TestClient) -> None:
    """`gemini-3-flash` and `gemini-3-pro` do not exist and 404. `gemini-2.0-*`
    was retired 2026-06-01. Guard the identifiers, because a typo here is only
    discovered when a user asks a question in production."""
    m = client.get("/api/meta").json()["models"]
    valid = {"gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-pro-preview"}
    assert m["reasoning"] in valid
    assert m["routing"] in valid


# ---------------------------------------------------------------- executive


def test_kpis_match_the_engine(client: TestClient) -> None:
    from app.repository import Scope, get_repository

    api = client.get("/api/kpis").json()
    direct = get_repository().executive_kpis(Scope())
    assert api["total_spend"] == pytest.approx(direct["total_spend"])
    assert api["esr_pct"] == pytest.approx(direct["esr_pct"])
    # Cost of waste scales the monthly usage-waste run-rate onto the window.
    assert api["cost_of_waste"] > api["commitment_waste"]


def test_spend_by_dimension(client: TestClient) -> None:
    r = client.get("/api/spend/by", params={"dimension": "cloud"}).json()
    assert r["column"] == "ProviderName"
    clouds = {row["ProviderName"] for row in r["rows"]}
    assert clouds == set(CLOUDS)


# ---------------------------------------------------------------- security


@pytest.mark.parametrize(
    "dimension",
    ["; DROP TABLE focus_costs", "ProviderName); SELECT 1--", "__class__", "cost UNION ALL SELECT"],
)
def test_dimension_whitelist_rejects_injection(client: TestClient, dimension: str) -> None:
    """Dimensions become SQL identifiers on the BigQuery path, so they are a
    whitelist, not a suggestion."""
    for endpoint in ("/api/spend/by", "/api/anomalies", "/api/allocation"):
        r = client.get(endpoint, params={"dimension": dimension})
        assert r.status_code == 400, f"{endpoint} accepted {dimension!r}"


def test_allocation_method_is_validated(client: TestClient) -> None:
    r = client.get("/api/allocation", params={"method": "rm -rf"})
    assert r.status_code == 400


# ---------------------------------------------------------------- forecast


def test_forecast_has_ordered_prediction_bands(client: TestClient) -> None:
    f = client.get("/api/forecast", params={"horizon": 24}).json()
    assert len(f["forecast"]) == 24
    assert f["accuracy"]["wape"] is not None
    for row in f["forecast"]:
        assert 0 <= row["lo95"] <= row["lo80"] <= row["cost"] <= row["hi80"] <= row["hi95"]


def test_forecast_surfaces_the_commitment_cliff(client: TestClient) -> None:
    """When a commitment term ends the rate snaps back to on-demand. A trend
    line walks straight through it; this is the number that does not."""
    f = client.get("/api/forecast", params={"horizon": 24, "include_cliffs": True}).json()
    assert f["cliff_months"], "the demo estate has a 1-year commitment purchase"
    assert f["extra_from_cliffs_usd"] > 0


# ---------------------------------------------------------------- optimize


def test_opportunities_and_levers(client: TestClient) -> None:
    o = client.get("/api/optimize/opportunities").json()
    assert o["count"] > 8
    assert o["total_annual_savings"] > 1_000_000

    catalog = client.get("/api/optimize/levers").json()
    assert catalog["count"] == len(optimize.LEVERS)

    r1 = client.get("/api/optimize/levers/R1").json()
    assert "Savings Plan" in r1["name"]
    assert r1["source_url"].startswith("http")
    assert client.get("/api/optimize/levers/NOPE").status_code == 404


# ---------------------------------------------------------------- anomalies


def test_an_anomaly_is_never_graded_good(client: TestClient) -> None:
    """`is_anomaly` and `severity` are computed from different quantities and
    used to disagree: 347 flagged rows, 318 of them graded `good`."""
    a = client.get("/api/anomalies").json()
    assert 0 < a["count"] < 60, f"{a['count']} anomalies is noise, not signal"
    assert all(row["severity"] != "good" for row in a["rows"])
    critical = {row["ServiceCategory"] for row in a["rows"] if row["severity"] == "critical"}
    assert {"Analytics", "Networking"} <= critical  # the two planted spikes


# ---------------------------------------------------------------- agent


def test_agent_team_is_described_from_the_real_tools(client: TestClient) -> None:
    t = client.get("/api/agent/team").json()
    assert t["enabled"] is False  # no credentials in a test
    names = {a["name"] for a in t["agents"]}
    assert names == {"analyst", "forecaster", "optimizer", "governor", "finops_coordinator"}
    analyst = next(a for a in t["agents"] if a["name"] == "analyst")
    tool_names = {x["name"] for x in analyst["tools"]}
    assert "get_executive_kpis" in tool_names
    assert all(x["summary"] for x in analyst["tools"]), "ADK reads the docstring as the tool spec"


def test_agent_explains_missing_credentials_rather_than_crashing(client: TestClient) -> None:
    with client.stream(
        "POST", "/api/agent/ask", json={"question": "why did spend rise?", "persona": "Leadership"}
    ) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "GOOGLE_CLOUD_PROJECT" in body
    assert "event: done" in body


def test_agent_rejects_an_unknown_persona(client: TestClient) -> None:
    r = client.post("/api/agent/ask", json={"question": "hello there", "persona": "Wizard"})
    assert r.status_code == 400


# ---------------------------------------------------------------- tools


# Tools whose parameters are all optional can be invoked bare. `explain_lever`
# legitimately requires an id -- a lookup with no key is meaningless.
_TOOL_ARGS = {"explain_lever": {"lever_id": "R1"}}


def test_agent_tools_never_raise_and_always_report_status() -> None:
    """ADK expects a dict with a `status` key. A tool that raises kills the
    agent loop, so every one of ours catches."""
    import inspect

    from app.agents.tools import build_tools
    from app.repository import get_repository

    groups = build_tools(get_repository())
    seen = set()
    for tools in groups.values():
        for tool in tools:
            if tool.__name__ in seen:
                continue
            seen.add(tool.__name__)

            assert tool.__doc__, f"{tool.__name__} has no docstring -- ADK uses it as the tool spec"
            sig = inspect.signature(tool)
            for pname, param in sig.parameters.items():
                assert param.annotation is not inspect.Parameter.empty, (
                    f"{tool.__name__}.{pname} has no type hint -- ADK builds the schema from it"
                )

            result = tool(**_TOOL_ARGS.get(tool.__name__, {}))
            assert isinstance(result, dict), f"{tool.__name__} must return a dict"
            assert result.get("status") in {"success", "error"}, tool.__name__
    assert len(seen) >= 10


def test_explain_lever_returns_a_citable_source() -> None:
    from app.agents.tools import build_tools
    from app.repository import get_repository

    tools = {t.__name__: t for group in build_tools(get_repository()).values() for t in group}
    good = tools["explain_lever"](lever_id="r1")  # case-insensitive
    assert good["status"] == "success"
    assert good["lever"]["source_url"].startswith("http")

    bad = tools["explain_lever"](lever_id="ZZ9")
    assert bad["status"] == "error" and "known" in bad


def test_query_tools_reject_an_unknown_dimension() -> None:
    from app.agents.tools import build_tools
    from app.repository import get_repository

    tools = {t.__name__: t for group in build_tools(get_repository()).values() for t in group}
    r = tools["get_spend_summary"](group_by="'; DROP TABLE--")
    assert r["status"] == "error"
    assert "Unknown dimension" in r["error"]


# ---------------------------------------------------------------- bigquery SQL


class _FakeJob:
    def __init__(self, sql, config):
        self.sql, self.config = sql, config

    def to_dataframe(self):
        import pandas as pd
        # `executive_kpis` reads a single aggregate row; `dimensions` reads k/v.
        # A frame with the right columns keeps the double honest.
        if "total_spend" in self.sql:
            return pd.DataFrame([{c: 0.0 for c in
                ["total_spend","ode","usage_effective","commitment_waste","commitment_used","allocated"]}
                | {"period_start": None, "period_end": None}])
        if "'clouds' AS k" in self.sql:
            return pd.DataFrame(columns=["k", "v"])
        return pd.DataFrame(columns=["period", "cost"])


class _FakeBQ:
    """Captures the SQL and the job config without touching Google."""

    def __init__(self):
        self.jobs = []

    def query(self, sql, job_config=None):
        job = _FakeJob(sql, job_config)
        self.jobs.append(job)
        return job


def _bq_repo():
    from app.repository import BigQueryRepository
    from app.settings import Settings

    s = Settings(data_source="bigquery", gcp_project="proj", bq_dataset="finops")
    fake = _FakeBQ()
    return BigQueryRepository(s, client=fake), fake


def test_every_bigquery_query_prunes_the_partition() -> None:
    """The table is `require_partition_filter = TRUE`. A query without a bound on
    ChargePeriodStart is rejected by BigQuery, so we must always supply one --
    including for the unbounded `dimensions()` lookup."""
    pytest.importorskip("google.cloud.bigquery")
    from app.repository import Scope

    repo, fake = _bq_repo()
    repo.monthly(Scope())
    repo.daily(Scope())
    repo.monthly_by(Scope(), "cloud")
    repo.executive_kpis(Scope())
    repo.dimensions()

    assert len(fake.jobs) == 5
    for job in fake.jobs:
        assert "ChargePeriodStart >=" in job.sql, job.sql[:120]


def test_every_bigquery_query_caps_bytes_billed() -> None:
    """BigQuery FAILS a job that would exceed the cap rather than billing for it."""
    pytest.importorskip("google.cloud.bigquery")
    from app.repository import Scope

    repo, fake = _bq_repo()
    repo.monthly(Scope())
    cfg = fake.jobs[0].config
    assert cfg.maximum_bytes_billed == 20 * 1024**3


def test_bigquery_filters_are_parameterised_not_interpolated() -> None:
    pytest.importorskip("google.cloud.bigquery")
    from app.repository import Scope

    repo, fake = _bq_repo()
    repo.monthly(Scope.of(clouds=["AWS'; DROP TABLE focus_costs--"]))
    job = fake.jobs[0]
    assert "DROP TABLE" not in job.sql
    assert "IN UNNEST(@clouds)" in job.sql
    assert any(p.name == "clouds" for p in job.config.query_parameters)


def test_bigquery_dimension_is_whitelisted_before_interpolation() -> None:
    pytest.importorskip("google.cloud.bigquery")
    from app.repository import Scope

    repo, _ = _bq_repo()
    with pytest.raises(ValueError, match="Unknown dimension"):
        repo.monthly_by(Scope(), "cost); DROP TABLE focus_costs--")
