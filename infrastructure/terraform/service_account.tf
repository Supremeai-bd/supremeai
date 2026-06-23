# ============================================================================
# terraform >> service_account.tf
# project >> SupremeAI 2.0
# purpose >> Business service
# module >> infrastructure
# ============================================================================
# ============================================================================
# terraform >> service_account.tf
# project >> SupremeAI 2.0
# purpose >> Business service
# module >> infrastructure
# ============================================================================
# ============================================================================\n# terraform >> service_account.tf\n# project >> SupremeAI 2.0\n# purpose >> General utility\n# module >> infrastructure\n# ============================================================================\n# ============================================================================
# terraform >> service_account.tf
# project >> SupremeAI 2.0
# purpose >> Business service logic
# module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> service_account.tf
# Project >> SupremeAI 2.0
# Purpose >> Business service logic
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> service_account.tf
# Project >> SupremeAI 2.0
# Purpose >> Business service logic
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform: service_account.tf
# Project: SupremeAI 2.0
# Purpose: Business service logic
# Module: infrastructure
# ============================================================================
# ============================================================================
# Terraform: service_account.tf
# Project: SupremeAI 2.0
# Purpose: General utility
# Module: infrastructure
# ============================================================================
resource "google_service_account" "api" {
  account_id   = "supremeai-api-sa"
  display_name = "SupremeAI API Service Account"
  project      = var.project_id
}
