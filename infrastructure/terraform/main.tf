terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_cloud_run_service" "supremeai_core" {
  name     = "supremeai-backend-core"
  location = var.gcp_region

  template {
    spec {
      containers {
        # ক্লাউড বিল্ড থেকে পুশ হওয়া ইমেজের ডাইনামিক রেফারেন্স
        image = "gcr.io/${var.gcp_project_id}/supremeai-backend:latest"
        ports {
          container_port = 8000
        }
      }
    }
  }
}

resource "google_artifact_registry_repository" "supreme_repo" {
  location      = var.gcp_region
  repository_id = "supremeai-repo"
  description   = "SupremeAI Docker Container Images (Cost Optimized)"
  format        = "DOCKER"

  # 🗑️ বাংলা মন্তব্য: ৭ দিনের পুরনো এবং ট্যাগ ছাড়া ডেড ইমেজগুলো অটো-ডিলিট করার পলিসি
  cleanup_policies {
    id     = "prune-old-images"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "604800s" # 7 Days in seconds
    }
  }

  cleanup_policy_dry_run = false
}
