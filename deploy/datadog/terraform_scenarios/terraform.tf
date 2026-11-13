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

# Scenario monitors are opt-in and stay absent until their metrics have been
# observed in Datadog. Credentials are read from the local environment; never
# put API or application keys in this folder.

variable "enable_safety_trip_monitor" {
  description = "Create the virtual PLC protective-stop monitor only after its DogStatsD metric is confirmed in Datadog."
  type        = bool
  default     = false
}

variable "enable_safety_ack_imbalance_monitor" {
  description = "Create the aggregate trip/ACK count-imbalance monitor only after both metrics are confirmed in Datadog."
  type        = bool
  default     = false
}

variable "confirm_safety_trip_metric_ingested" {
  description = "Set true only after observing smiot.virtual_plc.safety_trip in Datadog Metrics Explorer."
  type        = bool
  default     = false
}

variable "confirm_safety_ack_metric_ingested" {
  description = "Set true only after observing smiot.virtual_plc.safety_ack in Datadog Metrics Explorer."
  type        = bool
  default     = false
}

variable "enable_reboot_monitor" {
  description = "Create a device reboot event-count monitor after its metric is observed in Datadog."
  type        = bool
  default     = false
}

variable "enable_sequence_gap_monitor" {
  description = "Create a missing-sequence count monitor after its metric is observed in Datadog."
  type        = bool
  default     = false
}

variable "enable_sequence_integrity_monitor" {
  description = "Create duplicate/regression event-count monitors after both metrics are observed in Datadog."
  type        = bool
  default     = false
}

variable "confirm_reboot_metric_ingested" {
  description = "Set true only after observing smiot.device.reboot_detected in Datadog Metrics Explorer."
  type        = bool
  default     = false
}

variable "confirm_sequence_gap_metric_ingested" {
  description = "Set true only after observing smiot.telemetry.sequence_gap in Datadog Metrics Explorer."
  type        = bool
  default     = false
}

variable "confirm_sequence_integrity_metrics_ingested" {
  description = "Set true only after observing duplicate and regression metrics in Datadog Metrics Explorer."
  type        = bool
  default     = false
}

resource "datadog_monitor" "virtual_plc_safety_trip" {
  count = var.enable_safety_trip_monitor ? 1 : 0

  name    = "SMIOT | Virtual PLC protective stop"
  type    = "metric alert"
  query   = "sum(last_5m):sum:smiot.virtual_plc.safety_trip{source:smiot_demo_stream} by {farm,fault_code} > 0"
  message = <<-EOT
    A local virtual PLC safety interlock stopped a pump and closed the valve. Inspect the farm and fault_code tags to distinguish a pressure/flow mismatch from a runtime/volume limit.
    This is a simulated operational safety event, not proof of a physical pipe leak or real-world equipment failure.
    Check correlated application logs and MongoDB scenario evidence; do not restart the pump automatically.

    {{#is_alert}}Confirm the device ACK and verify outputs are OFF and valve is closed.{{/is_alert}}
    {{#is_recovery}}The count window cleared. This does not itself prove the water system is safe to reopen.{{/is_recovery}}
  EOT

  tags                = ["project:smiot", "env:demo", "service:smiot-smart-farm", "component:virtual-plc", "scenario:water-safety"]
  priority            = 3
  include_tags        = true
  notify_no_data      = false
  on_missing_data     = "resolve"
  require_full_window = false
  evaluation_delay    = 60

  monitor_thresholds {
    critical = 0
  }

  lifecycle {
    precondition {
      condition     = var.confirm_safety_trip_metric_ingested
      error_message = "Do not enable this monitor until smiot.virtual_plc.safety_trip has been observed in Datadog Metrics Explorer."
    }
  }
}

resource "datadog_monitor" "virtual_plc_safety_ack_imbalance" {
  count = var.enable_safety_ack_imbalance_monitor ? 1 : 0

  name    = "SMIOT | Virtual PLC safety trip/ACK count imbalance"
  type    = "metric alert"
  query   = "sum(last_5m):sum:smiot.virtual_plc.safety_trip{source:smiot_demo_stream} by {farm,fault_code} - sum:smiot.virtual_plc.safety_ack{source:smiot_demo_stream} by {farm,fault_code} > 0"
  message = <<-EOT
    The number of protective-stop trips exceeds the number of safety ACKs in this farm/fault-code group during the evaluation window.
    This is an aggregate count check, not command-level correlation. Use structured logs with command_id and scenario_run_id to identify the exact missing ACK.
    Keep the virtual outputs in safe state; do not issue an automatic pump restart.
  EOT

  tags                = ["project:smiot", "env:demo", "service:smiot-smart-farm", "component:virtual-plc", "scenario:water-safety"]
  priority            = 2
  include_tags        = true
  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 60

  monitor_thresholds {
    critical = 0
  }

  lifecycle {
    precondition {
      condition     = var.confirm_safety_trip_metric_ingested && var.confirm_safety_ack_metric_ingested
      error_message = "Do not enable this monitor until both trip and ACK count metrics have been observed in Datadog Metrics Explorer."
    }
  }
}

resource "datadog_monitor" "device_reboot_event" {
  count = var.enable_reboot_monitor ? 1 : 0

  name    = "SMIOT | Device reboot observed"
  type    = "metric alert"
  query   = "sum(last_5m):sum:smiot.device.reboot_detected{source:smiot_demo_stream} by {farm,node} > 0"
  message = <<-EOT
    A reboot was observed for this farm/node. Reboots can be expected maintenance and do not by themselves prove a device fault.
    Inspect boot_id/uptime evidence, sequence continuity, the source/broker/app path, and the first fresh persisted sample.
    If telemetry is stale or unreliable, keep irrigation decisions in the configured safe state; do not restart pumps from this monitor.
  EOT

  tags                = ["project:smiot", "env:demo", "service:smiot-smart-farm", "component:device-provenance"]
  priority            = 3
  include_tags        = true
  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 60

  monitor_thresholds {
    critical = 0
  }

  lifecycle {
    precondition {
      condition     = var.confirm_reboot_metric_ingested
      error_message = "Do not enable until smiot.device.reboot_detected is emitted by the active ingest path and observed in Datadog."
    }
  }
}

resource "datadog_monitor" "telemetry_sequence_gap" {
  count = var.enable_sequence_gap_monitor ? 1 : 0

  name    = "SMIOT | Telemetry sequence gap"
  type    = "metric alert"
  query   = "sum(last_5m):sum:smiot.telemetry.sequence_gap{source:smiot_demo_stream} by {farm,node} > 0"
  message = <<-EOT
    The device sequence counter indicates one or more missing samples for this farm/node.
    This proves a sequence discontinuity, not whether loss occurred at the device, network, broker, app, or persistence layer.
    Compare producer sequence, broker receipt, app logs, and MongoDB timestamps before assigning a cause.
  EOT

  tags                = ["project:smiot", "env:demo", "service:smiot-smart-farm", "component:telemetry-provenance"]
  priority            = 2
  include_tags        = true
  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 60

  monitor_thresholds {
    critical = 0
  }

  lifecycle {
    precondition {
      condition     = var.confirm_sequence_gap_metric_ingested
      error_message = "Do not enable until smiot.telemetry.sequence_gap is emitted by the active ingest path and observed in Datadog."
    }
  }
}

resource "datadog_monitor" "telemetry_sequence_integrity" {
  count = var.enable_sequence_integrity_monitor ? 1 : 0

  name    = "SMIOT | Duplicate or regressing telemetry sequence"
  type    = "metric alert"
  query   = "sum(last_5m):sum:smiot.telemetry.sequence_duplicate{source:smiot_demo_stream} by {farm,node} + sum:smiot.telemetry.sequence_regression{source:smiot_demo_stream} by {farm,node} > 0"
  message = <<-EOT
    The device sequence is duplicated or moved backwards for this farm/node.
    Do not count duplicate replays as new sensor observations. Check boot_id and sequence provenance, MQTT delivery, and MongoDB idempotency evidence.
    A metric alert flags the condition; it does not assert physical device failure.
  EOT

  tags                = ["project:smiot", "env:demo", "service:smiot-smart-farm", "component:telemetry-provenance"]
  priority            = 2
  include_tags        = true
  notify_no_data      = false
  require_full_window = false
  evaluation_delay    = 60

  monitor_thresholds {
    critical = 0
  }

  lifecycle {
    precondition {
      condition     = var.confirm_sequence_integrity_metrics_ingested
      error_message = "Do not enable until duplicate and regression count metrics are emitted by the active ingest path and observed in Datadog."
    }
  }
}

