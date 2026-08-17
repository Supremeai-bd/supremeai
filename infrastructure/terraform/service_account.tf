resource "google_service_account" "api" {
  account_id   = "supremeai-api-sa"
  display_name = "SupremeAI API Service Account"
  project      = var.project_id
}
