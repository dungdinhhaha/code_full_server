terraform {
  required_providers {
    datadog = { source = "DataDog/datadog", version = "~> 4.21" }
  }
}

provider "datadog" {
  api_url = "https://api.datadoghq.com/"
}
