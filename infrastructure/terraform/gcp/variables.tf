variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "GCP region"
}

variable "user_id" {
  type        = string
  description = "Unique user identifier"
}

variable "skill_docker_image" {
  type        = string
  description = "Docker image for the skill"
}
