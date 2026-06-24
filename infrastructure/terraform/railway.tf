resource "null_resource" "railway_deployment_hook" {
  triggers = {
    deployment_sync = timestamp()
  }

  provisioner "local-exec" {
    command = "echo '🚀 Railway node deployment is delegated to GitHub Actions (railway-cli) for zero-downtime rollouts.'"
  }
}
