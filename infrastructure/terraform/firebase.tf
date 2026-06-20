resource "google_firebase_project" "default" {
  project  = var.project_id
}

resource "google_firebase_hosting_site" "default" {
  project  = var.project_id
  site_id  = var.firebase_hosting_site_id
}
