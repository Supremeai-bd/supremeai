variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location"
  type        = string
  default     = "nam5"
}

variable "cloud_function_runtime" {
  description = "Cloud Functions v2 runtime"
  type        = string
  default     = "nodejs22"
}

variable "cloud_function_max_instances" {
  description = "Cloud Functions max instances"
  type        = number
  default     = 100
}

variable "cloud_function_min_instances" {
  description = "Cloud Functions min instances"
  type        = number
  default     = 0
}

variable "supabase_project_ref" {
  description = "Supabase project ref"
  type        = string
  default     = ""
}

variable "supabase_db_password" {
  description = "Supabase database password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "upstash_redis_url" {
  description = "Upstash Redis REST endpoint"
  type        = string
  default     = ""
}

variable "upstash_redis_token" {
  description = "Upstash Redis token"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "supremeai"
}

variable "cloud_run_image" {
  description = "Container image for Cloud Run"
  type        = string
  default     = "gcr.io/PROJECT_ID/supremeai:latest"
}

variable "cloud_run_cpu" {
  description = "Cloud Run CPU allocation"
  type        = string
  default     = "1"
}

variable "cloud_run_memory" {
  description = "Cloud Run memory allocation"
  type        = string
  default     = "512Mi"
}

variable "cloud_run_concurrency" {
  description = "Cloud Run max concurrency"
  type        = number
  default     = 80
}

variable "cloud_run_min_instances" {
  description = "Cloud Run minimum instances"
  type        = number
  default     = 0
}

variable "create_service" {
  description = "Whether to create a new Cloud Run service"
  type        = bool
  default     = true
}

variable "cloud_run_max_instances" {
  description = "Cloud Run maximum instances"
  type        = number
  default     = 100
}
