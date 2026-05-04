locals {
  required_apis = [
    "run.googleapis.com",
    "firestore.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "api" {
  location      = var.region
  repository_id = var.artifact_registry_repository
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_firestore_database" "default" {
  name        = var.firestore_database_name
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_service_account" "cloud_run" {
  account_id   = "${var.service_name}-sa"
  display_name = "Cloud Run runtime SA for ${var.service_name}"
}

resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret" "deepseek_api_key" {
  secret_id = var.deepseek_secret_name

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "deepseek_accessor" {
  secret_id = google_secret_manager_secret.deepseek_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = var.service_name
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = var.api_image

      ports {
        container_port = 8080
      }

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }

      env {
        name  = "REPOSITORY_PROVIDER"
        value = "firestore"
      }

      env {
        name  = "LLM_PROVIDER"
        value = "deepseek"
      }

      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "FIRESTORE_DATABASE"
        value = var.firestore_database_name
      }

      env {
        name = "DEEPSEEK_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.deepseek_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.deepseek_accessor,
  ]
}
