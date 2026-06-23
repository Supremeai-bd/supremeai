# ============================================================================
# terraform >> outputs.tf
# project >> SupremeAI 2.0
# purpose >> Output validation
# module >> infrastructure
# ============================================================================
# ============================================================================
# terraform >> outputs.tf
# project >> SupremeAI 2.0
# purpose >> Output validation
# module >> infrastructure
# ============================================================================
# ============================================================================\n# terraform >> outputs.tf\n# project >> SupremeAI 2.0\n# purpose >> Output validation\n# module >> infrastructure\n# ============================================================================\n  description = "Artifact Registry repo URL for Docker images"
}

output "supabase_project_ref" {
  value       = var.supabase_url
  description = "Supabase project reference URL"
}

output "pinecone_index_name" {
  value       = var.pinecone_index
  description = "Pinecone index name"
}

output "qdrant_cluster_url" {
  value       = var.qdrant_url
  description = "Qdrant cluster URL"
}

output "vercel_project_url" {
  value       = var.vercel_team_id
  description = "Vercel team/project identifier"
}

output "cloudflare_zone_id" {
  value       = var.cloudflare_account_id
  description = "Cloudflare account/zone identifier"
}
