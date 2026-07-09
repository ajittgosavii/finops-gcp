# Infosys — Multi-Cloud FinOps on GCP

The FinOps platform rebuilt for Google Cloud: **BigQuery** as the FOCUS warehouse,
**Google ADK** agents on **Gemini**, a **FastAPI** service on **Cloud Run**, and a **React**
client.

The Streamlit implementation in `../multicloud-finops` remains the reference. This is not
a rewrite of it — it is the same engines, given a warehouse that scales and an API that a
browser can talk to.

---

## What carried over, and why

`focus.py`, `kpi.py`, the five analytics engines and all 17 connectors — about **9,100
lines** — never imported Streamlit. They take pandas DataFrames and return pandas
DataFrames. So they moved wholesale into `packages/finops-core`, an installable package
that knows nothing about Streamlit, FastAPI, React, Google Cloud, or any LLM.

That extraction is **mechanical and reproducible**, not a hand-edit:

```bash
python tools/extract_core.py --src ../multicloud-finops
pytest packages/finops-core          # 36 tests
```

`tools/extract_core.py` rewrites the flat imports, strips the Streamlit secret lookup from
`config.py`, and then **fails the build** if any bare sibling import survives at any
indentation. A silent miss there becomes an `ImportError` inside a Cloud Run container,
which is a bad place to discover it.

Fix a bug in the Streamlit app, re-run the extractor, and it lands here too. There is one
copy of the FinOps definitions in the world.

---

## The thing that actually forced the rebuild

Not the UI. **pandas.**

The demo estate is 55k FOCUS rows / 36 MB — about 654 bytes per row. Extrapolate to a real
Con Edison estate at ~500k line-items per month over two years and that is **~8 GB in one
process**; a large enterprise at 2M/month is **~31 GB**. The Streamlit design loads the
whole frame into memory. It demos beautifully and it will not survive a utility.

So `app/repository.py` is the seam:

| | Demo | BigQuery |
|---|---|---|
| Source | synthetic estate, in-process | the FOCUS warehouse |
| Aggregates | pandas groupby | pushed into SQL |
| Row-level detectors | run per request | nightly Cloud Run Job → `opportunities` table |
| Credentials | none | ADC |

Both return the same shapes, so nothing above the repository knows which is active.

### Three cost guards, because BigQuery will happily bill you

1. **`require_partition_filter = TRUE`** on `focus_costs`. A query without a bound on
   `ChargePeriodStart` is *rejected*, not answered. Every query the repository issues
   supplies one — an unbounded scope means "the 25-month analysis window", never
   "everything". There is a test.
2. **`maximum_bytes_billed`** on every job (default 20 GiB ≈ 12¢). BigQuery **fails** the
   job rather than billing past the cap.
3. **The expensive detectors never run per request.** They scan resource ids and SKU
   strings; their answer changes once a day at most.

Partitioned on `DATE(ChargePeriodStart)`, clustered on
`ProviderName, ServiceCategory, tag_application` — the three columns the filter row
actually filters on. See `infra/bigquery/schema.sql`.

---

## The agent team, on ADK

A **coordinator** holding four specialists as `AgentTool`s, rather than handing control
away with `sub_agents=`.

ADK offers both. `sub_agents=[…]` generates a `transfer_to_agent` tool and control *moves*
— the specialist then owns the conversation and writes the final answer in its own
register. `AgentTool` calls the specialist, takes its answer back, and the coordinator
keeps the floor. A FinOps question usually spans domains ("why did spend rise and what
should we do") and the answer must be one voice speaking to one persona. So: `AgentTool`.

| Agent | FinOps domain | Model |
|---|---|---|
| coordinator | routing only | `gemini-3.1-flash-lite` |
| analyst | Understand Usage and Cost | `gemini-3.5-flash` |
| forecaster | Quantify Business Value | `gemini-3.5-flash` |
| optimizer | Optimize Usage and Cost | `gemini-3.5-flash` |
| governor | Manage the FinOps Practice | `gemini-3.5-flash` |

Routing on the cheap model and reasoning on the flagship is the **small-model-first lever
(G3)** from our own catalog, applied to ourselves.

### Why the agents cannot run SQL

ADK ships an excellent first-party `BigQueryToolset` with `execute_sql` and a
`maximum_bytes_billed` cap. **We deliberately do not give it to these agents.**

The platform's whole claim is that a number on a dashboard and a number in a chat answer
are the same number, because both came from `kpi.py`. Give a model a SQL prompt and it will
invent its own Effective Savings Rate — one that drops the on-demand-equivalent
denominator, or counts `Purchase` rows, or averages what should be summed. It will be
plausible, it will be wrong, and nobody will catch it.

So the model gets **typed tools that call the same engine functions the REST endpoints
call**. It cannot compute. It can only ask. Every tool returns `{"status": ...}` and never
raises, because a tool that raises kills the agent loop.

ADK builds each tool's JSON schema from the **function signature, type hints and
docstring** — so those docstrings in `app/agents/tools.py` are the interface, not
commentary. A test asserts every tool has both.

### Model identifiers, verified

`gemini-3.5-flash` is the flagship (despite the `.5`), `gemini-3.1-pro-preview` is Pro,
`gemini-3.1-flash-lite` is cheapest. **There is no bare `gemini-3-flash` or
`gemini-3-pro`** — they 404. `gemini-2.0-flash` was retired **2026-06-01**, and the whole
`gemini-2.5-*` family shuts down **2026-10-16**. A test pins the identifiers, because a
typo here is only discovered when a user asks a question in production.

---

## Layout

```
packages/finops-core/     the contract: focus, kpi, engines, connectors  (36 tests)
  src/finops_core/
    focus.py              FOCUS 1.2 schema, enums, validation
    kpi.py                every executive formula, defined exactly once
    config.py             Mode, AppConfig, AccountBinding, DataContext
    engines/              forecast · budget · anomaly · allocation · optimize
    connectors/           17 sources, all returning a FOCUS 1.2 frame

services/api/             FastAPI on Cloud Run  (24 tests)
  app/settings.py         env-only config; model ids live here
  app/repository.py       Demo | BigQuery, behind one Protocol
  app/agents/tools.py     typed tools over finops_core -- the model cannot compute
  app/agents/team.py      ADK coordinator + 4 specialists
  app/agents/runner.py    SSE streaming, with tool-call provenance
  app/main.py             REST + POST /api/agent/ask

services/ingest/          Cloud Run Job: connectors -> GCS Parquet -> BigQuery   (todo)
web/                      React + TypeScript                                     (todo)
infra/bigquery/           the warehouse DDL
infra/terraform/                                                                 (todo)
tools/extract_core.py     regenerate finops-core from the Streamlit app
```

---

## Run it locally

```bash
pip install -e "packages/finops-core[dev]"
pip install -r services/api/requirements.txt

cd services/api
DATA_SOURCE=demo uvicorn app.main:app --reload --port 8080
# http://localhost:8080/docs
```

Demo Mode needs no GCP project and no Gemini key. The Copilot endpoint explains what is
missing rather than failing.

```bash
pytest packages/finops-core     # 36
cd services/api && pytest       # 24 -- no GCP, no key, no network
```

## Deploy

```bash
# Warehouse
bq query --use_legacy_sql=false < infra/bigquery/schema.sql   # after substituting ${PROJECT} etc.

# Service
gcloud run deploy finops-api \
  --source . --region us-central1 \
  --set-env-vars DATA_SOURCE=bigquery,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_GENAI_USE_VERTEXAI=TRUE \
  --service-account finops-api@$PROJECT.iam.gserviceaccount.com \
  --no-allow-unauthenticated
```

The service account needs `roles/bigquery.dataViewer`, `roles/bigquery.jobUser` and
`roles/aiplatform.user`. Vertex authenticates through ADC, so **there is no API key
anywhere** — strictly better than the OpenAI deployment it replaces.

---

## Honest limitations

- The React client and the ingest job are not built yet. The API is real and tested.
- `BigQueryRepository.budgets()` and `.drivers()` return empty frames. A cloud bill cannot
  contain a budget or a business driver, by definition — both need a feed from a system of
  record.
- `executive_kpis` on the BigQuery path recomputes the KPI components in SQL. If it ever
  disagrees with `kpi.py`, **`kpi.py` is right**, and the SQL is the bug.
- Cost Explorer has no list price. On that ingest path `ListCost = BilledCost`, so
  Effective Savings Rate is understated. Use a FOCUS Data Export.
- Demo data is synthetic. Every dollar in it is invented.
