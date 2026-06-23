# ============================================================================
# terraform >> firebase.tf
# project >> SupremeAI 2.0
# purpose >> Firebase integration
# module >> infrastructure
# ============================================================================
# ============================================================================
# terraform >> firebase.tf
# project >> SupremeAI 2.0
# purpose >> Firebase integration
# module >> infrastructure
# ============================================================================
# ============================================================================\n# terraform >> firebase.tf\n# project >> SupremeAI 2.0\n# purpose >> Firebase integration\n# module >> infrastructure\n# ============================================================================\n# ============================================================================
# terraform >> firebase.tf
# project >> SupremeAI 2.0
# purpose >> Firebase integration
# module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> firebase.tf
# Project >> SupremeAI 2.0
# Purpose >> Firebase integration
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> firebase.tf
# Project >> SupremeAI 2.0
# Purpose >> Firebase integration
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform: firebase.tf
# Project: SupremeAI 2.0
# Purpose: Firebase integration
# Module: infrastructure
# ============================================================================
# ============================================================================
# Terraform: firebase.tf
# Project: SupremeAI 2.0
# Purpose: Firebase integration
# Module: infrastructure
# ============================================================================
resource "google_firebase_project" "default" {
  project  = var.project_id
}

resource "google_firebase_hosting_site" "default" {
  project  = var.project_id
  site_id  = var.firebase_hosting_site_id
}
