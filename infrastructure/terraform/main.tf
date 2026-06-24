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
