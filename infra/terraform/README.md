# Terraform — FinOps on GCP

Provisions the warehouse, the landing zone, the two Cloud Run runtimes and the
nightly schedules for the platform in `../..`.

## What it creates

- **BigQuery** dataset + `focus_costs` and `opportunities` tables. Their schemas
  (`schema_focus_costs.json`, `schema_opportunities.json`) are generated from
  `finops_core.focus.SCHEMA` and verified column-by-column against
  `infra/bigquery/schema.sql` — same partitioning, clustering and
  `require_partition_filter`. Do not hand-edit the JSON; regenerate it.
- **GCS** bucket for the FOCUS Parquet landing zone (uniform access, versioned,
  raw Parquet deleted after 400 days).
- **Artifact Registry** Docker repo for the `finops-api` and `finops-ingest`
  images.
- **Cloud Run** service (API) and job (ingest), each with its own service
  account and least-privilege IAM.
- **Cloud Scheduler** — ingest at 03:15 and the opportunities snapshot at 03:45
  America/New_York (Con Edison is a NY utility).
- **Secret Manager** secret `FINOPS_ACCOUNTS` from a sensitive tfvar.

There is **no Gemini API key** anywhere: the API reaches Vertex through ADC on
the `finops-api` service account (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`).

## What you set

Copy `terraform.tfvars.example` to `terraform.tfvars` and set at least
`project_id`. Provide `finops_accounts` (the payer bindings + credentials) out of
band — `TF_VAR_finops_accounts` or an uncommitted `*.auto.tfvars` — never in a
committed file. Images default to the Artifact Registry `:latest` path that
`cloudbuild.yaml` pushes.

## Run

```bash
terraform init
terraform plan
terraform apply
```

The images must exist in Artifact Registry before the Cloud Run resources can
come up healthy, so the usual order on a clean project is: `apply` (registry +
dataset + bucket + SAs), run `cloudbuild.yaml` to build and push, then `apply`
again for the Run resources — or build/push first if the repo already exists.

## Two IAM roles a human needs

Terraform grants the service accounts their runtime roles. The **person or CI
identity running `terraform apply`** additionally needs, at the project:

- `roles/owner` (or the narrower set of `roles/run.admin`,
  `roles/bigquery.admin`, `roles/storage.admin`,
  `roles/artifactregistry.admin`, `roles/secretmanager.admin`,
  `roles/cloudscheduler.admin`, `roles/iam.serviceAccountAdmin` and
  `roles/resourcemanager.projectIamAdmin`), and
- `roles/serviceusage.serviceUsageAdmin` to enable the APIs in
  `google_project_service`.

## Validation status

`terraform fmt -recursive -check` and `terraform validate` were run with
Terraform 1.14.3 — see the repository report for results.
