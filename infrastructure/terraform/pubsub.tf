resource "google_pubsub_topic" "tasks" {
  name    = "supremeai-tasks"
  project = var.project_id
}

resource "google_pubsub_subscription" "tasks" {
  name    = "supremeai-tasks-sub"
  project = var.project_id
  topic   = google_pubsub_topic.tasks.name
}
