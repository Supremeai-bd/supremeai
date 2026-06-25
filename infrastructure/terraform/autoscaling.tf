# infrastructure/terraform/autoscaling.tf
# Advanced Auto-scaling and Serverless Infrastructure for SupremeAI 2.0

#########################
# VARIABLES
#########################

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 1000
}

variable "target_cpu_utilization" {
  description = "Target CPU utilization percentage for autoscaling"
  type        = number
  default     = 60
}

variable "max_concurrent_requests" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 1000
}

#########################
# CLOUD RUN SERVICE
#########################

resource "google_cloud_run_service" "supremeai_api" {
  name     = "supremeai-api-${var.environment}"
  location = var.region

  template {
    spec {
      # Main application container
      containers {
        image = "${var.project_id}-docker.pkg.dev/${var.project_id}/supremeai/app:${var.environment}"
        
        resources {
          limits = {
            cpu    = "2000m"   # 2 CPU cores
            memory = "4Gi"     # 4 GB RAM
          }
          
          # Requests for better scheduling
          requests = {
            cpu    = "500m"    # 0.5 CPU cores
            memory = "1Gi"     # 1 GB RAM
          }
        }
        
        # Environment variables
        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }
        
        env {
          name  = "LOG_LEVEL"
          value = var.environment == "production" ? "info" : "debug"
        }
        
        # Add more environment variables as needed
      }
      
      # Autoscaling configuration
      autoscaling {
        # Max instances for burst traffic
        max_concurrency = var.max_concurrent_requests
        
        # Scale to zero when idle (cost optimization)
        max_instance_count = var.max_instances
        min_instance_count = var.min_instances
        
        # Scale based on concurrency (requests)
        # This is often better than CPU for API services
      }
      
      # Timeout and concurrency settings
      timeout_seconds = 300
      container_concurrency = var.max_concurrent_requests
      
      # Enable HTTP/2 for better performance
      protocol = "HTTP2"
    }
    
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = var.max_instances
        "autoscaling.knative.dev/minScale" = var.min_instances
        "autoscaling.knative.dev/targetUtilizationPercentage" = "${var.target_cpu_utilization}"
        "run.googleapis.com/cpu-throttling" = "false"
      }
    }
  }
  
  # Traffic allocation - 100% to latest revision
  traffic {
    percent         = 100
    latest_revision = true
  }
}

#########################
# CLOUD SQL (PostgreSQL) for Relational Data
#########################

resource "google_sql_database_instance" "supremeai_db" {
  name             = "supremeai-db-${var.environment}"
  database_version = "POSTGRES_15"
  region           = var.region
  
  settings {
    tier = "db-custom-2-7680"  # 2 vCPU, 7.5 GB RAM
    
    # Enable high availability for production
    availability_type = var.environment == "production" ? "REGIONAL" : "ZONAL"
    
    # Backup configuration
    backup_configuration {
      enabled           = true
      start_time        = "03:00"  # 3 AM UTC
      enabled           = true
      point_in_time_recovery_enabled = true
    }
    
    # Performance settings
    database_flags {
      name  = "max_connections"
      value = "200"
    }
    
    database_flags {
      name  = "shared_buffers"
      value = "256MB"
    }
    
    # Enable storage auto increase
    disk_size        = 20
    disk_type        = "PD_SSD"
    disk_autoresize  = true
    disk_autoresize_limit = 100
  }
  
  # Deletion protection for production
  deletion_protection = var.environment == "production"
}

# Database for application data
resource "google_sql_database" "app_db" {
  name     = "appdb"
  instance = google_sql_database_instance.supremeai_db.name
}

# Database for session storage
resource "google_sql_database" "session_db" {
  name     = "sessiondb"
  instance = google_sql_database_instance.supremeai_db.name
}

# Database user
resource "google_sql_user" "app_user" {
  name     = "appuser"
  instance = google_sql_database_instance.supremeai_db.name
  password = random_password.db_password.result
}

# Generate secure password for database
resource "random_password" "db_password" {
  length  = 16
  special = true
}

#########################
# MEMORYSTORE (Redis) for Caching
#########################

resource "google_redis_instance" "supremeai_cache" {
  provider        = google-beta
  name            = "supremeai-cache-${var.environment}"
  region          = var.region
  tier            = "STANDARD_HA"
  memory_size_gb  = 1
  
  # Enable persistence for production
  persistence_config {
    snapshot_period = 3600  # 1 hour
    snapshot_enabled = true
  }
  
  # Reserved memory for overhead
  reserved_memory_mb = 256
  
  # Authorized network (if using VPC)
  # authorized_network = "${google_compute_network.default.id}"
  
  depends_on = [google_service_networking_connection.default_vpc]
}

#########################
# PUB/SUB for Event Streaming
#########################

# Topic for user events
resource "google_pubsub_topic" "user_events" {
  name = "user-events-${var.environment}"
}

# Subscription for analytics processor
resource "google_pubsub_subscription" "analytics_processor" {
  name  = "analytics-processor-${var.environment}"
  topic = google_pubsub_topic.user_events.name
  
  ack_deadline_seconds = 20
  
  # Enable dead letter topic for error handling
  dead_letter_policy {
    dead_letter_topic = google_pubsub_topic.dlq.name
    max_delivery_attempts = 5
  }
}

# Topic for dead letter queue
resource "google_pubsub_topic" "dlq" {
  name = "dlq-${var.environment}"
}

# Topic for audit logs
resource "google_pubsub_topic" "audit_logs" {
  name = "audit-logs-${var.environment}"
}

#########################
# CLOUD FUNCTIONS for Event Processing
#########################

# Function to process user events
resource "google_cloudfunctions2_function" "user_event_processor" {
  name        = "user-event-processor-${var.environment}"
  location    = var.region
  description = "Processes user events for analytics and recommendations"

  build_config {
    runtime    = "python311"
    entry_point = "process_user_event"
    source {
      storage_source {
        bucket = google_storage_bucket.source_bucket.name
        object = google_storage_bucket_object.source_object.name
      }
    }
  }

  service_config {
    max_instance_count = 10
    min_instance_count = 0
    available_memory   = "256M"
    timeout_seconds    = 60
    
    # Environment variables
    environment_variables = {
      ENVIRONMENT = var.environment
      PROJECT_ID  = var.project_id
    }
    
    # Enable VPC connector for database access
    # vpc_connector {
    #   name  = google_compute_network_vpc_access_connector.vpc_connector.name
    #   egress_settings = "ALL_TRAFFIC"
    # }
  }
  
  # Trigger from Pub/Sub
  event_trigger {
    trigger_region = var.region
    trigger_location = "google.cloud_provider = "cloud"
    trigger {
      event_type = "google.cloud.pubsub.topic.v1.messagePublished"
      pubsub_topic = google_pubsub_topic.user_events.name
    }
  }
}

#########################
# CLOUD STORAGE for Assets
#########################

# Bucket for application assets (images, documents, etc.)
resource "google_storage_bucket" "assets" {
  name          = "supremeai-assets-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "production"  # Only allow force destroy in non-prod
  
  # Enable versioning for recovery
  versioning {
    enabled = true
  }
  
  # Lifecycle rules - delete old versions after 30 days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
      matches_storage_class = ["STANDARD", "NEARLINE"]
    }
  }
  
  # Uniform bucket-level access
  uniform_bucket_level_access = true
}

# Bucket for Terraform state (if using remote state)
resource "google_storage_bucket" "terraform_state" {
  name          = "supremeai-terraform-state-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "production"
  
  versioning {
    enabled = true
  }
}

# Upload source code for Cloud Functions
resource "google_storage_bucket" "source_bucket" {
  name          = "supremeai-source-${var.environment}"
  location      = var.region
  force_destroy = var.environment != "production"
}

resource "google_storage_bucket_object" "source_object" {
  name   = "source-code-${timestamp()}.zip"
  bucket = google_storage_bucket.source_bucket.name
  
  source = "${path.module}/../../function-source.zip"
}

#########################
# MONITORING & ALERTING
#########################

# Alert policy for high error rates
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "High Error Rate - SupremeAPI"
  combiner     = "OR"
  
  conditions {
    display_name = "Error rate > 5%"
    condition_threshold {
      filter = sprintf(
        'metric.type="run.googleapis.com/request_count" AND resource.label."service_name"="%s" AND metric.label."response_code_code">="400"',
        google_cloud_run_service.supremeai_api.name
      )
      
      comparison = "COMPARISON_GT"
      threshold_value = 0.05  # 5% error rate
      
      duration = "300s"  # 5 minutes
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
  
  # Notification channel (would need to be configured separately)
  # notification_channels = [google_monitoring_notification_channel.email.id]
}

# Alert policy for high latency
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "High Latency - SupremeAPI"
  combiner     = "OR"
  
  conditions {
    display_name = "95th percentile latency > 2s"
    condition_threshold {
      filter = sprintf(
        'metric.type="run.googleapis.com/request_latencies" AND resource.label."service_name"="%s"',
        google_cloud_run_service.supremeai_api.name
      )
      
      comparison = "COMPARISON_GT"
      threshold_value = 2.0  # 2 seconds
      
      duration = "300s"  # 5 minutes
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
}

#########################
# IAM & SERVICE ACCOUNTS
#########################

# Service account for Cloud Run
resource "google_service_account" "cloudrun_invoker" {
  account_id   = "cloudrun-invoker-${var.environment}"
  display_name = "Cloud Run Invoker - SupremeAI"
}

# Service account for Cloud Functions
resource "google_service_account" "cloudfunctions_invoker" {
  account_id   = "cloudfunctions-invoker-${var.environment}"
  display_name = "Cloud Functions Invoker - SupremeAI"
}

# Grant Cloud Run invoker role to the service account
resource "google_project_iam_member" "cloudrun_invoker_binding" {
  role   = "roles/run.invoker"
  member = "serviceAccount:${google_service_account.cloudrun_invoker.email}"
}

# Grant Cloud Functions invoker role
resource "google_project_iam_member" "cloudfunctions_invoker_binding" {
  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.cloudfunctions_invoker.email}"
}

# Grant necessary permissions to access databases and other services
resource "google_project_iam_member" "cloudrun_database_access" {
  role   = "roles/cloudsql.client"
  member = "serviceAccount:${google_service_account.cloudrun_invoker.email}"
}

resource "google_project_iam_member" "cloudrun_pubsub_publisher" {
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.cloudrun_invoker.email}"
}

#########################
# NETWORKING (Optional - for VPC access)
#########################

# Uncomment and configure if you need VPC access for private IPs

# resource "google_compute_network" "default" {
#   name                    = "supremeai-vpc-${var.environment}"
#   auto_create_subnetworks = false
# }

# resource "google_compute_subnetwork" "default" {
#   name          = "subnet-${var.environment}"
#   ip_cidr_range = "10.0.0.0/16"
#   region        = var.region
#   network       = google_compute_network.default.id
# }

# resource "google_service_networking_connection" "default_vpc" {
#   network                 = google_compute_network.default.id
#   service                 = "servicenetworking.googleapis.com"
#   reserved_peering_ranges = [google_compute_global_address.default_vpc_peering.name]
# }

# resource "google_compute_global_address" "default_vpc_peering" {
#   name          = "google-managed-services-${var.environment}"
#   purpose       = "VPC_PEERING"
#   address_type  = "INTERNAL"
#   prefix_length = 16
#   network       = google_compute_network.default.id
# }

# VPC Connector for Cloud Functions to access private resources
# resource "google_compute_network_vpc_access_connector" "vpc_connector" {
#   name          = "vpc-connector-${var.environment}"
#   region        = var.region
#   subnet        = google_compute_subnetwork.default.id
#   
#   # Throughput settings
#   min_throughput = 200  # Mbps
#   max_throughput = 300  # Mbps
# }

#########################
# OUTPUTS
#########################

output "cloud_run_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_service.supremeai_api.status[0].url
}

output "database_connection_name" {
  description = "Connection name for Cloud SQL instance"
  value       = google_sql_database_instance.supremeai_db.connection_name
}

output "redis_host" {
  description = "Hostname for Redis instance"
  value       = google_redis_instance.supremeai_cache.host_ip
}

output "redis_port" {
  description = "Port for Redis instance"
  value       = google_redis_instance.supremeai_cache.port
}

output "pubsub_topic_user_events" {
  description = "Pub/Sub topic for user events"
  value       = google_pubsub_topic.user_events.id
}

output "storage_bucket_assets" {
  description = "Storage bucket for application assets"
  value       = google_storage_bucket.assets.name
}