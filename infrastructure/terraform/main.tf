# ============================================================================
# terraform >> main.tf
# project >> SupremeAI 2.0
# purpose >> App main entry point
# module >> infrastructure
# ============================================================================
# ============================================================================
# terraform >> main.tf
# project >> SupremeAI 2.0
# purpose >> App main entry point
# module >> infrastructure
# ============================================================================
# ============================================================================\n# terraform >> main.tf\n# project >> SupremeAI 2.0\n# purpose >> App entry point\n# module >> infrastructure\n# ============================================================================\n# ============================================================================
# terraform >> main.tf
# project >> SupremeAI 2.0
# purpose >> Application main entry point
# module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> main.tf
# Project >> SupremeAI 2.0
# Purpose >> Python main entry point
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform >> main.tf
# Project >> SupremeAI 2.0
# Purpose >> Python main entry point
# Module >> infrastructure
# ============================================================================
# ============================================================================
# Terraform: main.tf
# Project: SupremeAI 2.0
# Purpose: Application entry point
# Module: infrastructure
# ============================================================================
# ============================================================================
# Terraform: main.tf
# Project: SupremeAI 2.0
# Purpose: Application entry point
# Module: infrastructure
# ============================================================================
terraform {
  required_version = ">= 1.5.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0.0, < 7.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0, < 4.0.0"
    }
    supabase = {
      source  = "supabase/supabase"
      version = ">= 1.0.0, < 2.0.0"
    }
    pinecone = {
      source  = "pinecone-io/pinecone"
      version = ">= 1.0.0, < 2.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "supabase" {
  # Note: Supabase is managed externally. Authenticate via SUPABASE_ACCESS_TOKEN env var.
  # No provider config needed at this time.
}

provider "pinecone" {
  # Note: Pinecone is managed externally. Authenticate via PINECONE_API_KEY env var.
}
