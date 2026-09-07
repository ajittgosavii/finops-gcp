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

# -- Gemini model ids. Verified by a live generateContent call against Vertex in
#    this project on 2026-09-07, not from a documentation page -- the previous
#    defaults (gemini-3.5-flash / gemini-3.1-flash-lite) return 404. See the
#    module docstring in services/api/app/settings.py for the full result table.
#    There is deliberately NO API key variable: Vertex authenticates via ADC on
#    the Cloud Run service account.
variable "model_reasoning" {
  description = "Model used for reasoning. Must be one Vertex serves in var.region."
  type        = string
  default     = "gemini-2.5-pro"
}

variable "model_routing" {
  description = "Cheaper model, used only for routing (small-model-first)."
  type        = string
  default     = "gemini-2.5-flash"
}

variable "data_source" {
  description = <<-EOT
    Where the API reads from: "demo" (synthetic estate generated in-process, no
    credentials, no warehouse) or "bigquery" (the FOCUS warehouse).

    Defaults to demo deliberately. The warehouse exists as soon as this
    Terraform is applied, but it is EMPTY until a FOCUS export from a real payer
    has been ingested -- and a console wired to an empty warehouse looks broken
    rather than looking honest. Flip this to "bigquery" when focus_costs has
    data in it, not when the table has been created.
  EOT
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["demo", "bigquery"], var.data_source)
    error_message = "data_source must be \"demo\" or \"bigquery\"."
  }
}

variable "allow_public_access" {
  description = <<-EOT
    Grant roles/run.invoker to allUsers, making the service reachable by a
    browser without a Google identity.

    This UNDOES a deliberate property. The service was written with no public
    invoker so that a caller must authenticate; that is the correct posture the
    moment real Con Edison billing data is in the warehouse. It is set true only
    while data_source is "demo" and the estate is synthetic.

    Turning this on with data_source = "bigquery" is almost certainly a mistake,
    so the plan below refuses that combination outright.
  EOT
  type        = bool
  default     = true
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
