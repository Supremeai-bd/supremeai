# BYOC Google Cloud Run Minimal Terraform module
# Infrastructure blueprint for deploying ephemeral user-hosted AI containers.

variable "project_id" {
  type        = string
  description = "The GCP Project ID where resources will be deployed"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The GCP Region to deploy the Cloud Run service"
}

variable "skill_name" {
  type        = string
  default     = "supremeai-sandbox"
  description = "The name of the skill being deployed"
}

variable "image_url" {
  type        = string
  default     = "gcr.io/supremeai/python-sandbox:latest"
  description = "The Docker image URL to deploy"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_cloud_run_service" "byoc_service" {
  name     = "byoc-skill-${var.skill_name}"
  location = var.region

  template {
    spec {
      containers {
        image = var.image_url
        resources {
          limits = {
            memory = "256Mi"
            cpu    = "1000m"
          }
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

output "service_url" {
  value       = google_cloud_run_service.byoc_service.status[0].url
  description = "The public URL of the deployed Cloud Run service"
}
