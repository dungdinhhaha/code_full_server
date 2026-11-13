terraform {
  required_version = ">= 1.5.0"

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 4.29"
    }
  }
}

provider "datadog" {
  api_url = var.datadog_api_url
  # DD_API_KEY and DD_APP_KEY must be supplied by the caller; never store them here.
}

variable "datadog_api_url" {
  type        = string
  description = "Datadog US1 API endpoint."
  default     = "https://api.datadoghq.com/"
}

variable "systemd_host" {
  type        = string
  description = "Host tag for the smiot.service systemd monitor."
  default     = "*"
}

variable "notification_email" {
  type        = string
  description = "Verified email recipient for SMIOT monitor alert and recovery notifications."
  default     = "dungyeuduyen08032004@gmail.com"
}
