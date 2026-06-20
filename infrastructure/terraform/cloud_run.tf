resource "google_cloud_run_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.api.email

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/supremeai/supremeai-api:latest"

        ports {
          container_port = 8000
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "PORT"
          value = "8000"
        }
        env {
          name  = "ENV"
          value = "production"
        }
        env {
          name = "SUPABASE_URL"
          value = var.supabase_url
        }
        env {
          name = "SUPABASE_ANON_KEY"
          value = var.supabase_anon_key
        }
        env {
          name = "PINECONE_API_KEY"
          value = var.pinecone_api_key
        }
        env {
          name = "PINECONE_INDEX"
          value = var.pinecone_index
        }
        env {
          name = "QDRANT_URL"
          value = var.qdrant_url
        }
        env {
          name = "QDRANT_API_KEY"
          value = var.qdrant_api_key
        }
      }

      timeout_seconds       = 300
      service_account_name  = google_service_account.api.email
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "10"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "public" {
  service  = google_cloud_run_service.api.name
  location = google_cloud_run_service.api.location
  policy   = data.google_iam_policy.noauth.policy
}
