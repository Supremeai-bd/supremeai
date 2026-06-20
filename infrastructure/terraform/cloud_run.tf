resource "google_cloud_run_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.api.email

      containers {
        image = "gcr.io/${var.project_id}/supremeai:latest"

        ports {
          container_port = 8000
        }

        env {
          name  = "PORT"
          value = "8000"
        }
        env {
          name  = "ENV"
          value = "production"
        }
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
