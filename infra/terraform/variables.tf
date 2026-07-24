variable "cluster_name" {
  type        = string
  description = "Kind cluster name"
  default     = "ai-sre-copilot"
}

variable "enable_helm_release" {
  type        = bool
  description = "Install the platform Helm chart into Kind"
  default     = false
}

variable "kubeconfig_path" {
  type        = string
  description = "Optional kubeconfig path override"
  default     = ""
}
