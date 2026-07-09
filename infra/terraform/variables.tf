variable "project_id" {
  description = "The GCP project that hosts the warehouse, the service and the job."
  type        = string
}

variable "region" {
  description = "Cloud Run / Artifact Registry region. Vertex is reached from here too."
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location. Must match the dataset in infra/bigquery/schema.sql if it already exists."
  type        = string
  default     = "US"
}

variable "dataset_id" {
  description = "BigQuery dataset for the FOCUS warehouse."
  type        = string
  default     = "finops"
}

variable "artifact_repo" {
  description = "Artifact Registry Docker repository id for the two images."
  type        = string
  default     = "finops"
}

variable "bucket_name" {
  description = "GCS bucket for the FOCUS Parquet landing zone. Defaults to <project>-finops-focus."
  type        = string
  default     = ""
}

variable "api_image" {
  description = "Full image ref for the API service. Defaults to the Artifact Registry path at :latest."
  type        = string
  default     = ""
}

variable "ingest_image" {
  description = "Full image ref for the ingest job. Defaults to the Artifact Registry path at :latest."
  type        = string
  default     = ""
}

# -- Gemini model ids. Verified against Google's models page (see
#    services/api/app/settings.py). There is deliberately NO API key variable:
#    Vertex authenticates via ADC on the Cloud Run service account.
variable "model_reasoning" {
  description = "Flagship model for reasoning (despite the .5, this is the current flagship)."
  type        = string
  default     = "gemini-3.5-flash"
}

variable "model_routing" {
  description = "Cheapest model, used only for routing (small-model-first)."
  type        = string
  default     = "gemini-3.1-flash-lite"
}

variable "allow_origins" {
  description = "CORS origins the API accepts, comma-separated."
  type        = string
  default     = "http://localhost:5173"
}

variable "bq_max_bytes_billed" {
  description = "Hard ceiling on bytes billed per query/DML. BigQuery FAILS a job past it rather than billing. 20 GiB ~ 12c."
  type        = number
  default     = 21474836480 # 20 * 1024^3
}

variable "opportunities_window_months" {
  description = "Trailing window the nightly optimize job scans."
  type        = number
  default     = 24
}

variable "ingest_lookback_months" {
  description = "How many months back a nightly ingest re-pulls (catches late/corrected line-items)."
  type        = number
  default     = 2
}

variable "scheduler_timezone" {
  description = "Cloud Scheduler timezone. Con Edison is a New York utility, so the batch day is anchored to NY."
  type        = string
  default     = "America/New_York"
}

variable "ingest_schedule" {
  description = "Cron for the nightly ingest job."
  type        = string
  default     = "15 3 * * *" # 03:15 America/New_York
}

variable "opportunities_schedule" {
  description = "Cron for the nightly opportunities snapshot (after ingest lands)."
  type        = string
  default     = "45 3 * * *" # 03:45 America/New_York, 30 min after ingest
}

variable "finops_accounts" {
  description = "JSON array for the FINOPS_ACCOUNTS secret: the account bindings with their per-payer credentials. Sensitive."
  type        = string
  default     = "[]"
  sensitive   = true
}

variable "labels" {
  description = "Labels applied to labelable resources."
  type        = map(string)
  default = {
    app = "finops"
  }
}
