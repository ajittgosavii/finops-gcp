output "api_url" {
  description = "HTTPS URL of the Cloud Run API service (requires an authenticated caller)."
  value       = google_cloud_run_v2_service.api.uri
}

output "focus_bucket" {
  description = "GCS bucket holding the FOCUS Parquet landing zone."
  value       = google_storage_bucket.focus.name
}

output "dataset" {
  description = "BigQuery dataset id for the FOCUS warehouse."
  value       = google_bigquery_dataset.finops.dataset_id
}

output "api_service_account" {
  description = "Email of the API service account (BigQuery reader + Vertex user)."
  value       = google_service_account.api.email
}

output "ingest_service_account" {
  description = "Email of the ingest service account (BigQuery writer + bucket admin)."
  value       = google_service_account.ingest.email
}

output "artifact_registry" {
  description = "Docker image path prefix for both images."
  value       = local.ar_base
}
