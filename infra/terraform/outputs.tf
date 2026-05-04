output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.api.uri
}

output "artifact_registry_repository" {
  description = "Full Artifact Registry repository URL for Docker pushes"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}"
}

output "service_account_email" {
  description = "Cloud Run runtime service account email"
  value       = google_service_account.cloud_run.email
}

output "deepseek_secret_id" {
  description = "Secret Manager secret ID for the DeepSeek API key"
  value       = google_secret_manager_secret.deepseek_api_key.secret_id
}
