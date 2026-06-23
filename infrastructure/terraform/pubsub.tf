# ============================================================================
# terraform >> pubsub.tf
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> infrastructure
# ============================================================================
# ============================================================================
# terraform >> pubsub.tf
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> infrastructure
# ============================================================================
# ============================================================================\n# terraform >> pubsub.tf\n# project >> SupremeAI 2.0\n# purpose >> General utility\n# module >> infrastructure\n# ============================================================================\n# ============================================================================
# terraform >> pubsub.tf
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> pubsub.tf
# Project >> SupremeAI 2.0
# Purpose >> General utility
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> pubsub.tf
# Project >> SupremeAI 2.0
# Purpose >> General utility
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform: pubsub.tf
# Project: SupremeAI 2.0
# Purpose: General utility
# Module: infrastructure
# ============================================================================
# ============================================================================
# Terraform: pubsub.tf
# Project: SupremeAI 2.0
# Purpose: General utility
# Module: infrastructure
# ============================================================================
resource "google_pubsub_topic" "tasks" {
  name    = "supremeai-tasks"
  project = var.project_id
}

resource "google_pubsub_subscription" "tasks" {
  name    = "supremeai-tasks-sub"
  project = var.project_id
  topic   = google_pubsub_topic.tasks.name
}
