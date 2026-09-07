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

  # Whether a public invoker exists is var.allow_public_access, granted at the
  # bottom of this file. With it false the service is effectively
  # --no-allow-unauthenticated: a caller must present a Google identity.
  deletion_protection = false
  labels              = var.labels

  lifecycle {
    # Public access is acceptable over a synthetic estate and is not acceptable
    # over a customer's billing data. Rather than leave that as a sentence in a
    # README, the apply refuses the combination.
    precondition {
      condition = !(var.allow_public_access && var.data_source == "bigquery")
      error_message = join(" ", [
        "Refusing to expose the FOCUS warehouse publicly.",
        "allow_public_access = true serves real billing data to anyone with the URL.",
        "Set allow_public_access = false and put IAP in front, or keep data_source = \"demo\".",
      ])
    }
  }

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
        value = var.data_source
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
# Public access. The service also serves the React client from the same origin
# (see services/api/Dockerfile), so this binding is what lets a browser load the
# console at all -- there is no separate front end to make public instead.
#
# It is a variable rather than a constant because it is a decision with a date
# on it: true while the estate is synthetic, false before a real payer's data
# lands. The precondition on the service above enforces that pairing.
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.allow_public_access ? 1 : 0

  project  = google_cloud_run_v2_service.api.project
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
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
