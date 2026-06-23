# ============================================================================
# terraform >> variables.tf
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> infrastructure
# ============================================================================
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

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
}

variable "supabase_anon_key" {
  description = "Supabase anon/public API key"
  type        = string
  sensitive   = true
}

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  sensitive   = true
}

variable "pinecone_index" {
  description = "Pinecone index name"
  type        = string
}

variable "qdrant_url" {
  description = "Qdrant cluster URL"
  type        = string
}

variable "qdrant_api_key" {
  description = "Qdrant API key"
  type        = string
  sensitive   = true
}

variable "vercel_team_id" {
  description = "Vercel team ID"
  type        = string
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}
