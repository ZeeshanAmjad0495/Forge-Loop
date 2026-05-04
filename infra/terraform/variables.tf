variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region for all resources"
  default     = "us-central1"
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name"
  default     = "incidentpilot-api"
}

variable "artifact_registry_repository" {
  type        = string
  description = "Artifact Registry repository ID"
  default     = "incidentpilot"
}

variable "api_image" {
  type        = string
  description = "Initial container image for Cloud Run (deploy workflow updates this)"
  default     = "gcr.io/cloudrun/hello"
}

variable "firestore_database_name" {
  type        = string
  description = "Firestore database name"
  default     = "(default)"
}

variable "deepseek_secret_name" {
  type        = string
  description = "Secret Manager secret ID for the DeepSeek API key"
  default     = "incidentpilot-deepseek-api-key"
}

variable "llm_model" {
  type        = string
  description = "LLM model name passed to the API service"
  default     = "deepseek-chat"
}
