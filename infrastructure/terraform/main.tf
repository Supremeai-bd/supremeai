terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------
# Firebase Project & Default Site
# -----------------------------------------------
resource "google_firebase_project" "default" {
  provider = google
  project  = var.project_id
}

resource "google_firebase_web_app" "default" {
  provider     = google
  project      = google_firebase_project.default.project
  display_name = "${var.project_id}-web"
}

resource "google_firebase_hosting_site" "default" {
  provider = google
  project  = var.project_id
  site_id  = var.project_id
}

# -----------------------------------------------
# Firestore Database (Native mode)
# -----------------------------------------------
resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "NATIVE"
  depends_on  = [google_firebase_project.default]
}

# -----------------------------------------------
# Cloud Functions v2
# -----------------------------------------------
resource "google_storage_bucket" "function_source" {
  name          = "${var.project_id}-function-source"
  location      = var.region
  project       = var.project_id
  force_destroy = true
}

resource "google_project_service" "cloudfunctions" {
  project = var.project_id
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "cloudbuild" {
  project = var.project_id
  service = "cloudbuild.googleapis.com"
}

data "archive_file" "ocr_trigger_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../firebase_functions"
  output_path = "${path.module}/ocr-trigger.zip"
}

resource "google_storage_bucket_object" "ocr_trigger_zip" {
  name       = "ocr-trigger-${data.archive_file.ocr_trigger_zip.output_md5}.zip"
  bucket     = google_storage_bucket.function_source.name
  source     = data.archive_file.ocr_trigger_zip.output_path
  depends_on = [data.archive_file.ocr_trigger_zip]
}

resource "google_cloudfunctions2_function" "ocr_trigger" {
  name        = "ocr-trigger"
  project     = var.project_id
  location    = var.region
  depends_on  = [google_project_service.cloudfunctions, google_project_service.cloudbuild]

  build_config {
    runtime          = var.cloud_function_runtime
    entry_point      = "ocrTrigger"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.ocr_trigger_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = var.cloud_function_max_instances
    min_instance_count    = var.cloud_function_min_instances
    available_memory      = "512Mi"
    timeout_seconds       = 60
    service_account_email = google_service_account.default.email
    environment_variables = {
      GOOGLE_CLOUD_PROJECT = var.project_id
    }
  }

  labels = {
    "env" = "production"
  }
}

# Cloud Functions IAM: allow invoker access
resource "google_cloudfunctions2_function_iam_member" "ocr_trigger_invoker" {
  project        = google_cloudfunctions2_function.ocr_trigger.project
  location       = google_cloudfunctions2_function.ocr_trigger.location
  cloud_function = google_cloudfunctions2_function.ocr_trigger.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

# -----------------------------------------------
# Cloud Run (existing)
# -----------------------------------------------
resource "google_cloud_run_service" "default" {
  name     = var.cloud_run_service_name
  location = var.region
  project  = var.project_id

  template {
    spec {
      service_account_name = google_service_account.default.name
      containers {
        image = var.cloud_run_image
        resources {
          limits = {
            cpu    = var.cloud_run_cpu
            memory = var.cloud_run_memory
          }
        }
      }
      timeout_seconds       = 600
      service_account_name  = google_service_account.default.name
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = tostring(var.cloud_run_max_instances)
        "autoscaling.knative.dev/minScale" = tostring(var.cloud_run_min_instances)
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

data "google_cloud_run_service" "existing" {
  count    = var.create_service ? 0 : 1
  name     = var.cloud_run_service_name
  location = var.region
  project  = var.project_id
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  service    = google_cloud_run_service.default.name
  location   = var.region
  project    = var.project_id
  policy_data = "{\"bindings\":[{\"role\":\"roles/run.invoker\",\"members\":[\"allUsers\"]}]}"
}

variable "create_service" {
  description = "Whether to create a new Cloud Run service"
  type        = bool
  default     = true
}

resource "google_service_account" "default" {
  account_id   = "${var.cloud_run_service_name}-sa"
  display_name = "SupremeAI Cloud Run Service Account"
  project      = var.project_id
}

data "google_project" "current" {}

resource "google_project_iam_custom_role" "supremeai" {
  project     = var.project_id
  role_id     = "supremeai.cloudRunRuntime"
  title       = "SupremeAI Cloud Run Runtime"
  description = "CR-scoped runtime permissions"
  permissions = [
    "run.routes.invoke",
    "artifactregistry.repositories.downloadArtifacts",
  ]
}

resource "google_project_iam_member" "run_sa_roles" {
  project = var.project_id
  role    = "projects/${var.project_id}/roles/${google_project_iam_custom_role.supremeai.role_id}"
  member  = "serviceAccount:${google_service_account.default.email}"
}
