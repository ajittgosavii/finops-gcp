# IAM, granted at the narrowest scope each role supports.
#
# BigQuery data roles (dataViewer / dataEditor) are dataset-scoped -- the API can
# read the warehouse and nothing else, the ingest job can write it and nothing
# else. Two roles cannot be scoped below the project, and it is called out where
# that is the case:
#   * roles/bigquery.jobUser is a project-level role by design (it authorises
#     *running* a query job, which is not a dataset-scoped action);
#   * roles/aiplatform.user has no resource-level binding for online prediction,
#     so Vertex access is a project grant.
# Storage and Secret grants ARE resource-scoped (this bucket, this secret).

# -- API service account ----------------------------------------------------

resource "google_bigquery_dataset_iam_member" "api_data_viewer" {
  dataset_id = google_bigquery_dataset.finops.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_job_user" {
  # Project-scoped: bigquery.jobUser cannot be granted on a dataset.
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_aiplatform_user" {
  # Project-scoped: Vertex online prediction has no narrower resource binding.
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# -- Ingest service account --------------------------------------------------

resource "google_bigquery_dataset_iam_member" "ingest_data_editor" {
  dataset_id = google_bigquery_dataset.finops.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_project_iam_member" "ingest_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_storage_bucket_iam_member" "ingest_object_admin" {
  # Bucket-scoped: the job may write and prune the landing zone, nothing else.
  bucket = google_storage_bucket.focus.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_secret_manager_secret_iam_member" "ingest_secret_accessor" {
  # Secret-scoped: only the FINOPS_ACCOUNTS secret, not the project's secrets.
  secret_id = google_secret_manager_secret.finops_accounts.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.ingest.email}"
}

# The API also reads FINOPS_ACCOUNTS (it lists configured payers on the
# Integrations view), so it needs accessor on the same secret. Secret-scoped.
resource "google_secret_manager_secret_iam_member" "api_secret_accessor" {
  secret_id = google_secret_manager_secret.finops_accounts.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}
