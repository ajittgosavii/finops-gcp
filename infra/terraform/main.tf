# The warehouse, the landing zone, the registry, the identities and the secret.
# Cloud Run wiring is in run.tf; the nightly triggers are in scheduler.tf.

locals {
  bucket_name  = var.bucket_name != "" ? var.bucket_name : "${var.project_id}-finops-focus"
  ar_host      = "${var.region}-docker.pkg.dev"
  ar_base      = "${local.ar_host}/${var.project_id}/${var.artifact_repo}"
  api_image    = var.api_image != "" ? var.api_image : "${local.ar_base}/finops-api:latest"
  ingest_image = var.ingest_image != "" ? var.ingest_image : "${local.ar_base}/finops-ingest:latest"
}

# ---------------------------------------------------------------------------
# APIs. Everything below depends on these; a fresh project has them all off.
# ---------------------------------------------------------------------------

resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])
  service = each.value

  # Leaving the API enabled on destroy avoids breaking anything else in the
  # project that happens to use it.
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry: one Docker repo for both images.
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = var.artifact_repo
  description   = "FinOps container images (api, ingest)."
  format        = "DOCKER"
  labels        = var.labels

  depends_on = [google_project_service.services]
}

# ---------------------------------------------------------------------------
# BigQuery: the dataset and the two tables.
#
# The table schemas live in schema_focus_costs.json / schema_opportunities.json,
# which are GENERATED from finops_core.focus.SCHEMA and verified column-by-column
# against infra/bigquery/schema.sql (partitioning, clustering and
# require_partition_filter reproduced below to match that DDL exactly). Do not
# hand-edit the JSON; regenerate it if the FOCUS schema changes.
# ---------------------------------------------------------------------------

resource "google_bigquery_dataset" "finops" {
  dataset_id  = var.dataset_id
  location    = var.bq_location
  description = "FOCUS 1.2 warehouse. See infra/bigquery/schema.sql."
  labels      = var.labels

  depends_on = [google_project_service.services]
}

resource "google_bigquery_table" "focus_costs" {
  dataset_id          = google_bigquery_dataset.finops.dataset_id
  table_id            = "focus_costs"
  description         = "FOCUS 1.2 Cost and Usage. One row per charge."
  schema              = file("${path.module}/schema_focus_costs.json")
  deletion_protection = true

  # PARTITION BY DATE(ChargePeriodStart) -- a query for "last month" reads a
  # slice, not two years. require_partition_filter REJECTS an unbounded query.
  require_partition_filter = true

  time_partitioning {
    type  = "DAY"
    field = "ChargePeriodStart"
  }

  # The three columns the filter row filters on, most selective first.
  clustering = ["ProviderName", "ServiceCategory", "tag_application"]

  labels = var.labels
}

resource "google_bigquery_table" "opportunities" {
  dataset_id          = google_bigquery_dataset.finops.dataset_id
  table_id            = "opportunities"
  description         = "Nightly optimization snapshot. Read the MAX(as_of) partition."
  schema              = file("${path.module}/schema_opportunities.json")
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "as_of"
  }

  clustering = ["category", "cloud"]

  labels = var.labels
}

# ---------------------------------------------------------------------------
# GCS: the FOCUS Parquet landing zone and replay source.
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "focus" {
  name                        = local.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  labels                      = var.labels

  # The raw Parquet is a replay source, not a system of record -- BigQuery is.
  # 400 days keeps a couple of full ingest windows for replay, then reclaims it.
  lifecycle_rule {
    condition { age = 400 }
    action { type = "Delete" }
  }

  # Keep a prior object if a re-run overwrites a day's landing file.
  versioning {
    enabled = true
  }

  depends_on = [google_project_service.services]
}

# ---------------------------------------------------------------------------
# Secret: FINOPS_ACCOUNTS. The value comes from a sensitive tfvar; the two
# runtimes read it as a mounted env var, never from a secret store directly.
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "finops_accounts" {
  secret_id = "FINOPS_ACCOUNTS"
  labels    = var.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "finops_accounts" {
  secret      = google_secret_manager_secret.finops_accounts.id
  secret_data = var.finops_accounts
}

# ---------------------------------------------------------------------------
# Service accounts. Roles are granted at the narrowest scope each role permits;
# see iam.tf.
# ---------------------------------------------------------------------------

resource "google_service_account" "api" {
  account_id   = "finops-api"
  display_name = "FinOps API (Cloud Run service)"
}

resource "google_service_account" "ingest" {
  account_id   = "finops-ingest"
  display_name = "FinOps ingest (Cloud Run Job)"
}
