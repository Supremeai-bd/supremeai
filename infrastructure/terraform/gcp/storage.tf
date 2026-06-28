resource "google_storage_bucket" "skill_artifacts" {
  name     = "supremeai-skill-${var.user_id}"
  location = var.region
  uniform_bucket_level_access = true
}
