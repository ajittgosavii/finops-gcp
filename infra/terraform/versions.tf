# Pinned so a provider minor bump cannot silently change a resource's behaviour
# between a plan a human reviewed and the apply that runs in CI.

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.20"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
