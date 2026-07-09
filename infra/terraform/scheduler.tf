# The two nightly triggers.
#
# Cloud Scheduler calls the Cloud Run Admin API's jobs:run endpoint with an OAuth
# token minted for the ingest service account. The opportunities schedule reuses
# the SAME job image and overrides the container args to ["opportunities"], so
# there is one job to build and deploy, invoked two ways.
#
# Times are America/New_York because Con Edison is a New York utility and the
# batch day should track when its billing data settles, not UTC.

locals {
  job_run_url = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingest.name}:run"
}

resource "google_cloud_scheduler_job" "ingest" {
  name      = "finops-ingest-nightly"
  region    = var.region
  schedule  = var.ingest_schedule
  time_zone = var.scheduler_timezone

  http_target {
    http_method = "POST"
    uri         = local.job_run_url

    oauth_token {
      service_account_email = google_service_account.ingest.email
    }
  }

  depends_on = [
    google_project_service.services,
    google_cloud_run_v2_job_iam_member.ingest_runner,
  ]
}

resource "google_cloud_scheduler_job" "opportunities" {
  name      = "finops-opportunities-nightly"
  region    = var.region
  schedule  = var.opportunities_schedule
  time_zone = var.scheduler_timezone

  http_target {
    http_method = "POST"
    uri         = local.job_run_url

    # Override the job's default args for this run only.
    body = base64encode(jsonencode({
      overrides = {
        containerOverrides = [{ args = ["opportunities"] }]
      }
    }))

    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.ingest.email
    }
  }

  depends_on = [
    google_project_service.services,
    google_cloud_run_v2_job_iam_member.ingest_runner,
  ]
}
