output "cloud_run_url" {
  value       = google_cloud_run_service.api.status[0].url
  description = "Cloud Run service URL"
}

output "cloud_run_service_name" {
  value       = google_cloud_run_service.api.name
  description = "Cloud Run service name"
}

output "service_account_email" {
  value       = google_service_account.api.email
  description = "Cloud Run service account email"
}

output "cloud_function_url" {
  value       = google_cloudfunctions2_function.supremeai_ocr.url
  description = "Cloud Functions ocr-trigger HTTPS trigger URL"
}

output "cloud_function_name" {
  value       = google_cloudfunctions2_function.supremeai_ocr.name
  description = "Cloud Function name"
}

output "firestore_database" {
  value       = google_firestore_database.default.name
  description = "Firestore database name"
}

output "firebase_project_id" {
  value       = google_firebase_project.default.project
  description = "Firebase project ID"
}

output "firebase_hosting_url" {
  value       = "https://${google_firebase_hosting_site.default.site_id}.web.app"
  description = "Firebase Hosting default site URL"
}

output "artifact_registry_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/supremeai"
  description = "Artifact Registry repo URL for Docker images"
}