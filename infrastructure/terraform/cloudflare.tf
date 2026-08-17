terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# KV Namespace for Circuit Breaker state
resource "cloudflare_workers_kv_namespace" "circuit_breaker_kv" {
  account_id = var.cloudflare_account_id
  title      = "SUPREMEAI_KV_${var.environment}"
}

# Cloudflare Worker script deployment
resource "cloudflare_worker_script" "supremeai_worker" {
  account_id = var.cloudflare_account_id
  name       = "supremeai-worker-${var.environment}"
  content    = file("${path.module}/../cloudflare_worker.js")
  module     = false

  kv_namespace_binding {
    name         = "SUPREMEAI_KV"
    namespace_id = cloudflare_workers_kv_namespace.circuit_breaker_kv.id
  }

  plain_text_binding {
    name  = "USER_BACKEND_URL"
    text  = var.user_backend_url
  }

  plain_text_binding {
    name  = "ADMIN_BACKEND_URL"
    text  = var.admin_backend_url
  }
}

# Define route to map the worker to a domain
resource "cloudflare_worker_route" "supremeai_route" {
  zone_id     = var.cloudflare_zone_id
  pattern     = "api.supremeai.com/*" # Change this based on actual domain
  script_name = cloudflare_worker_script.supremeai_worker.name
}
