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
  api_url = "https://api.datadoghq.com/"
}

resource "datadog_workflow_automation" "w2_greenhouse_j" {
  name        = "SMIOT | W2 | Greenhouse J sensor flatline recovery"
  description = "Stops the exact greenhouse_j node1 flatline scenario and verifies a matching Velxio profile ACK and three fresh varying MongoDB samples before closing the incident. No pump or PLC action."
  published   = true
  tags        = ["env:demo", "project:smiot", "workflow:w2", "farm:greenhouse_j", "source:velxio_synthetic", "safety:scoped-profile-recovery"]
  spec_json   = file("${path.module}/w2-greenhouse-j.json")
}

resource "datadog_monitor" "w2_greenhouse_j_flatline" {
  name                = "SMIOT | W2 | Greenhouse J sensor flatline"
  type                = "query alert"
  query               = "max(last_5m):max:smiot.telemetry.sensor_flatline{farm:greenhouse_j,node:1,source:velxio_synthetic} > 0"
  message             = <<-EOT
    {{#is_alert}}Greenhouse J node 1 sensor readings are flatlined in the Mongo-backed detector. The workflow stops only the exact scenario and requests a normal profile from this sensor. The app requires the stop ACK, matching device ACK and three fresh varying MongoDB samples before closing the incident. Synthetic simulation only; no physical equipment is controlled.
    @workflow-smiot-w2-greenhouse-j-profile-recovery
    {{/is_alert}}
    {{#is_recovery}}The greenhouse J flatline signal cleared. Check the correlated incident record for the app's ACK and MongoDB recovery proof.{{/is_recovery}}
  EOT
  tags                = ["project:smiot", "env:demo", "farm:greenhouse_j", "scenario:soil-flatline", "source:velxio_synthetic", "workflow:w2"]
  priority            = 2
  include_tags        = true
  require_full_window = false
  evaluation_delay    = 0
  renotify_interval   = 0
  on_missing_data     = "resolve"
  monitor_thresholds {
    critical = "0"
  }
}
