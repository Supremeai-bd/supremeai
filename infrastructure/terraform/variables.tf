variable "gcp_project_id" {
  description = "GCP Project ID for SupremeAI"
  type        = string
}

variable "gcp_region" {
  description = "Primary Deployment Region"
  type        = string
  default     = "us-central1"
}

variable "render_api_key" {
  description = "Secure Render API Key for Multi-Cloud Auth"
  type        = string
  sensitive   = true
}
