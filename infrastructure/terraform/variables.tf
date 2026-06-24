variable "gcp_project_id" {
  description = "GCP Project ID for SupremeAI"
  type        = string
}

variable "gcp_region" {
  description = "Primary Deployment Region"
  type        = string
  default     = "us-central1"
}
