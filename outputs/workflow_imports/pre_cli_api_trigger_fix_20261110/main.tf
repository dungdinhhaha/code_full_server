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

resource "datadog_workflow_automation" "w1" {
  name        = "SMIOT | W1 | Verify PLC safety trip evidence"
  description = "Read-only review after a virtual PLC safety-trip signal. Confirms Datadog evidence only; local PLC interlock remains the safety authority. No actuator command."
  published   = true
  tags        = ["env:demo", "plan:workflow-01", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w1.json")

  # Keep the API-trigger throttle from the JSON source. Provider 4.30 rejects this valid API field.
  lifecycle {
    ignore_changes = [spec_json]
  }
}

resource "datadog_workflow_automation" "w10" {
  name        = "SMIOT | W10 | AI failure safety verification"
  description = "Checks provider failure and AI latency evidence, then asks operator to verify app fail-safe HOLD and action ledger. No AI-generated irrigation action is issued."
  published   = true
  tags        = ["env:demo", "plan:workflow-10", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w10.json")
}

resource "datadog_workflow_automation" "w2" {
  name        = "SMIOT | Ca 2 | Confirm local interlock"
  description = "Read-only workflow for the soil humidity flatline monitor. It confirms the backend flatline signal only. App/virtual PLC HOLD acknowledgement must be verified from the app action ledger; this workflow never sends HOLD/CLEAR or actuator commands."
  published   = true
  tags        = ["env:demo", "project:smiot", "safety:read-only", "scenario:soil-humidity-flatline", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w2.json")
}

resource "datadog_workflow_automation" "w3" {
  name        = "SMIOT | Guarded EC2 app recovery"
  description = "Starts only the SMIOT web application after the inactive-service monitor fires. SSM checks MongoDB, MQTT, disk, deduplication, HTTP health, and fresh MongoDB telemetry; it never restarts MongoDB or MQTT."
  published   = true
  tags        = ["env:demo", "project:smiot", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w3.json")

  # Datadog normalizes terminal edges in the read-back; the deployed graph is verified via API.
  lifecycle {
    ignore_changes = [spec_json]
  }
}

resource "datadog_workflow_automation" "w4" {
  name        = "SMIOT | Ca 1 | Refuse restart when samples are fresh"
  description = "Read-only guard for the Ca 1 status-mismatch monitor. Confirms the mismatch is still present and checks farm-wide data freshness. It never restarts the app or any device."
  published   = true
  tags        = ["case:ca1", "env:demo", "project:smiot", "safety:no-restart", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w4.json")
}

resource "datadog_workflow_automation" "w5" {
  name        = "SMIOT | W5 | Root cause dependency triage"
  description = "Read-only correlation of MongoDB, MQTT, ingest lag and sample age. Classifies an evidence gap for human follow-up; does not restart infrastructure."
  published   = true
  tags        = ["env:demo", "plan:workflow-05", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w5.json")
}

resource "datadog_workflow_automation" "w6" {
  name        = "SMIOT | W6 | Detector heartbeat review"
  description = "Read-only check of the detector heartbeat signal. Missing metric is treated as unknown and escalated; workflow does not restart processes."
  published   = true
  tags        = ["env:demo", "plan:workflow-06", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w6.json")
}

resource "datadog_workflow_automation" "w7" {
  name        = "SMIOT | W7 | Irrigation schedule evidence review"
  description = "Checks soil-moisture input freshness before a human reviews the next irrigation turn. No crop envelope is assumed and no schedule is edited."
  published   = true
  tags        = ["env:demo", "plan:workflow-07", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w7.json")
}

resource "datadog_workflow_automation" "w8" {
  name        = "SMIOT | W8 | Crop climate and EC evidence review"
  description = "Reads VPD and soil EC evidence for crop-risk triage. No unapproved thresholds, pollination inference, pesticide advice, or automatic ventilation/drainage action."
  published   = true
  tags        = ["env:demo", "plan:workflow-08", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w8.json")
}

resource "datadog_workflow_automation" "w9" {
  name        = "SMIOT | W9 | Actuator acknowledgement verification"
  description = "Reads explicit command-unacknowledged telemetry and escalates for inspection. It never retries commands or claims physical actuator recovery."
  published   = true
  tags        = ["env:demo", "plan:workflow-09", "project:smiot", "safety:read-only", "service:smiot-smart-farm"]
  spec_json   = file("${path.module}/specs/w9.json")
}




