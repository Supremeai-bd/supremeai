variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "supremeai-api"
}

variable "firebase_hosting_site_id" {
  description = "Firebase Hosting site id"
  type        = string
  default     = "supremeai"
}
