resource "google_cloudfunctions2_function" "supremeai_ocr" {
  project  = var.project_id
  region   = var.region
  name     = "supremeai-ocr-trigger"
  
  build_config {
    runtime           = "python311"
    entry_point       = "handle"
    source {
      storage_source {
        bucket = google_storage_bucket.functions.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }
  
  service_config {
    max_instance_count = 1
    available_memory   = "256Mi"
    timeout_seconds    = 60
  }
}

resource "google_storage_bucket" "functions" {
  name     = "${var.project_id}-supremeai-functions"
  location = var.region
}

resource "google_storage_bucket_object" "function_source" {
  name   = "function-source.zip"
  bucket = google_storage_bucket.functions.name
  source = "./functions/placeholder.zip"
}
