terraform {
  required_version = ">= 1.5.0"

  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 4.21"
    }
  }
}

provider "datadog" {
  api_url = var.datadog_api_url
  # Credentials are intentionally supplied by the standard DD_API_KEY and
  # DD_APP_KEY environment variables. Never store them in this directory.
}

variable "datadog_api_url" {
  description = "Datadog API endpoint for the target site. The current account is US1."
  type        = string
  default     = "https://api.datadoghq.com/"
}

# This module creates five new dashboards only. The existing dashboard
# nkc-685-vw8 is deliberately not imported, edited, or destroyed here.
locals {
  dashboard_files = fileset(path.module, "dashboards/*.json")
}

resource "datadog_dashboard_json" "smiot_additional" {
  for_each  = local.dashboard_files
  dashboard = file("${path.module}/${each.key}")
}
