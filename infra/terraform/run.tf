# Cloud Run: the API service and the ingest job.
#
# Both authenticate to everything through ADC on their own service account.
# There is no Gemini API key anywhere: the API reaches Vertex as finops-api,
# which holds roles/aiplatform.user. GOOGLE_GENAI_USE_VERTEXAI=TRUE is the SDK
# switch that makes the google-genai client use ADC instead of a key.

locals {
  # Env common to both runtimes.
  common_env = {
    GOOGLE_CLOUD_PROJECT  = var.project_id
    GOOGLE_CLOUD_LOCATION = var.region
    BQ_DATASET            = var.dataset_id
    BQ_MAX_BYTES_BILLED   = tostring(var.bq_max_bytes_billed)
  }
}

# ---------------------------------------------------------------------------
# API service
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "api" {
  name     = "finops-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  # No allUsers invoker binding is created below, so the service is effectively
  # --no-allow-unauthenticated: a caller must present a Google identity.
  deletion_protection = false
  labels              = var.labels

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = local.api_image

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "DATA_SOURCE"
        value = "bigquery"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "MODEL_REASONING"
        value = var.model_reasoning
      }
      env {
        name  = "MODEL_ROUTING"
        value = var.model_routing
      }
      env {
        name  = "ALLOW_ORIGINS"
        value = var.allow_origins
      }

      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }

      # Vendor payer credentials, mounted from Secret Manager as an env var.
      env {
        name = "FINOPS_ACCOUNTS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.finops_accounts.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_secret_manager_secret_iam_member.api_secret_accessor,
  ]
}

# ---------------------------------------------------------------------------
# Ingest job. One job definition runs both subcommands: the default args are
# ["ingest"], and the opportunities scheduler overrides them to ["opportunities"]
# at run time (see scheduler.tf).
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_job" "ingest" {
  name     = "finops-ingest"
  location = var.region

  deletion_protection = false
  labels              = var.labels

  template {
    template {
      service_account = google_service_account.ingest.email
      max_retries     = 1
      timeout         = "3600s"

      containers {
        image = local.ingest_image
        args  = ["ingest"]

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }

        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.focus.name
        }
        env {
          name  = "INGEST_LOOKBACK_MONTHS"
          value = tostring(var.ingest_lookback_months)
        }
        env {
          name  = "OPPORTUNITIES_WINDOW_MONTHS"
          value = tostring(var.opportunities_window_months)
        }

        dynamic "env" {
          for_each = local.common_env
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name = "FINOPS_ACCOUNTS"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.finops_accounts.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_secret_manager_secret_iam_member.ingest_secret_accessor,
  ]
}

# The ingest identity is also what Cloud Scheduler authenticates as when it fires
# the job, so it needs to be able to run the job. Scoped to this job, not the
# project. (This is the only binding beyond the two named role sets, and it is
# the minimum to let the schedules execute.)
resource "google_cloud_run_v2_job_iam_member" "ingest_runner" {
  location = var.region
  name     = google_cloud_run_v2_job.ingest.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.ingest.email}"
}
