locals {
  common_tags        = ["team:smiot"]
  email_notification = <<-EOM

  {{#is_alert}}
  SMIOT notification: monitor is ALERT. Check the linked workflow and incident record.
  {{/is_alert}}
  {{#is_recovery}}
  SMIOT notification: monitor has RECOVERED. Confirm the post-recovery evidence in the incident record.
  {{/is_recovery}}
  @${var.notification_email}
  EOM
  monitors = {
    status_mismatch = {
      name               = "SMIOT | telemetry status mismatch"
      query              = "max(last_5m):max:smiot.telemetry.status_mismatch{*} by {farm,node} > 0"
      message            = "UI status disagrees with fresh Mongo telemetry. Investigate farm/node; do not restart the app while samples are fresh.\n\n@workflow-smiot-ca1-refuse-restart-1"
      tags               = ["signal:status-mismatch", "severity:warning"]
      on_missing_data    = "default"
      critical_threshold = "0"
    }
    fresh = {
      name               = "SMIOT | telemetry not fresh"
      query              = "min(last_5m):min:smiot.telemetry.fresh{*} by {farm,node} < 1"
      message            = "Telemetry freshness gauge is 0 for {{farm.name}}/{{node.name}}. Verify sample age and ingestion path."
      tags               = ["signal:fresh", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "1"
    }
    flatline = {
      name               = "SMIOT | sensor flatline"
      query              = "max(last_5m):max:smiot.telemetry.sensor_flatline{*} by {farm,node} > 0"
      message            = "Sensor flatline detected for {{farm.name}}/{{node.name}}. Check the sensor and publisher.\n\n@workflow-smiot-ca2-confirm-local-interlock"
      tags               = ["signal:sensor-flatline", "severity:warning"]
      on_missing_data    = "default"
      critical_threshold = "0"
    }
    stale = {
      name               = "SMIOT | telemetry sample stale"
      query              = "max(last_5m):max:smiot.telemetry.sample_age_seconds{*} by {farm,node} > 120"
      message            = "Latest persisted sample is older than 120 seconds for {{farm.name}}/{{node.name}}.\n\n@workflow-smiot-w08-crop-risk-review(farm_key=\"{{farm.name}}\", node_id=\"{{node.name}}\")"
      tags               = ["signal:sample-age", "severity:warning"]
      on_missing_data    = "default"
      critical_threshold = "120"
    }
    ingest_lag = {
      name               = "SMIOT | telemetry ingest lag"
      query              = "max(last_5m):max:smiot.telemetry.ingest_lag_ms{*} by {farm,node} > 5000"
      message            = "Telemetry ingest lag exceeds 5 seconds for {{farm.name}}/{{node.name}}."
      tags               = ["signal:ingest-lag", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "5000"
    }
    samples_persisted = {
      name               = "SMIOT | persisted sample rate missing"
      query              = "sum(last_5m):sum:smiot.telemetry.samples_persisted{*} by {farm}.as_rate() < 0.001"
      message            = "No persisted telemetry sample rate observed for {{farm.name}}. Check Mongo and the consumer."
      tags               = ["signal:samples-persisted", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "0.001"
    }
    mongo = {
      name               = "SMIOT | MongoDB dependency unhealthy"
      query              = "min(last_5m):min:smiot.dependency.mongo.up{*} < 1"
      message            = "MongoDB dependency health is below 1. Verify ping and persistence before recovery actions.\n\n@workflow-smiot-w05-root-cause-triage"
      tags               = ["component:mongodb", "severity:critical"]
      on_missing_data    = "default"
      critical_threshold = "1"
    }
    mqtt = {
      name               = "SMIOT | MQTT dependency unhealthy"
      query              = "min(last_5m):min:smiot.dependency.mqtt.up{*} < 1"
      message            = "MQTT dependency health is below 1. Verify broker connectivity and consumer health.\n\n@workflow-smiot-w05-root-cause-triage"
      tags               = ["component:mqtt", "severity:critical"]
      on_missing_data    = "default"
      critical_threshold = "1"
    }
    systemd = {
      name = "SMIOT | smiot.service inactive"
      # Demo recovery monitor: the producer has a measured ~3m37s visibility
      # delay after a service stop. A 2-minute alert window plus zero evaluation
      # delay lets the guarded workflow react within a bounded demo drill.
      query              = "avg(last_2m):avg:systemd.unit.active{unit:smiot.service,host:${var.systemd_host}} <= 0"
      message            = "smiot.service is inactive. Check Mongo/MQTT guards before any restart.\n\n@workflow-smiot-guarded-ec2-recovery"
      tags               = ["component:systemd", "severity:critical"]
      on_missing_data    = "default"
      critical_threshold = "0"
      evaluation_delay   = 0
    }
    ai_latency = {
      name               = "SMIOT | AI ask latency high"
      query              = "avg(last_2m):avg:smiot.ai.ask_latency_ms{status:provider_error} > 5000"
      message            = "AI ask latency exceeds 5 seconds. Inspect trace.smiot.ai.ask dependencies and verify the app's fail-safe decision.\n\n@workflow-smiot-w10-ai-failure-safety"
      tags               = ["component:ai", "severity:warning"]
      on_missing_data    = "default"
      critical_threshold = "5000"
      evaluation_delay   = 0
    }
    plc_latency = {
      name               = "SMIOT | PLC command latency high"
      query              = "avg(last_10m):avg:smiot.plc.command_latency_ms{*} > 5000"
      message            = "p95 PLC command latency exceeds 5 seconds. Check command path and device acknowledgement."
      tags               = ["component:plc", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "5000"
    }
    soil_humidity = {
      name               = "SMIOT | soil humidity telemetry absent"
      query              = "sum(last_10m):sum:smiot.telemetry.soil_humidity{*} by {farm,node} < 1"
      message            = "No soil humidity telemetry was received for {{farm.name}}/{{node.name}} in 10 minutes.\n\n@workflow-smiot-w07-irrigation-schedule-review(farm_key=\"{{farm.name}}\", node_id=\"{{node.name}}\")"
      tags               = ["signal:soil-humidity", "severity:warning"]
      on_missing_data    = "show_no_data"
      critical_threshold = "1"
    }
    w7_review_required = {
      name               = "SMIOT | W7 | soil moisture advisory review required"
      query              = "sum(last_2m):sum:smiot.crop.soil_moisture.review_required{*} by {farm,node} > 0"
      message            = "W7 soil-moisture advisory requires human review for {{farm.name}}/{{node.name}}. Keep the existing safe schedule; no automatic irrigation command.\n\n@workflow-smiot-w07-irrigation-schedule-review(farm_key=\"{{farm.name}}\", node_id=\"{{node.name}}\")"
      tags               = ["signal:soil-moisture-advisory", "severity:warning", "workflow:w7"]
      on_missing_data    = "resolve"
      critical_threshold = "0"
      evaluation_delay   = 0
    }
    w8_review_required = {
      name               = "SMIOT | W8 | VPD and EC advisory review required"
      query              = "sum(last_2m):sum:smiot.crop.vpd_ec.review_required{*} by {farm,node} > 0"
      message            = "W8 VPD/EC advisory requires human review for {{farm.name}}/{{node.name}}. Do not issue automatic ventilation, drainage, spray, or nutrient commands.\n\n@workflow-smiot-w08-crop-risk-review(farm_key=\"{{farm.name}}\", node_id=\"{{node.name}}\")"
      tags               = ["signal:vpd-ec-advisory", "severity:warning", "workflow:w8"]
      on_missing_data    = "resolve"
      critical_threshold = "0"
      evaluation_delay   = 0
    }
    air_temperature = {
      name               = "SMIOT | air temperature telemetry absent"
      query              = "sum(last_10m):sum:smiot.telemetry.air_temperature{*} by {farm,node} < 1"
      message            = "No air temperature telemetry was received for {{farm.name}}/{{node.name}} in 10 minutes."
      tags               = ["signal:air-temperature", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "1"
    }
    soil_temperature = {
      name               = "SMIOT | soil temperature telemetry absent"
      query              = "sum(last_10m):sum:smiot.telemetry.soil_temperature{*} by {farm,node} < 1"
      message            = "No soil temperature telemetry was received for {{farm.name}}/{{node.name}} in 10 minutes."
      tags               = ["signal:soil-temperature", "severity:warning"]
      on_missing_data    = null
      critical_threshold = "1"
    }
  }
}

resource "datadog_monitor" "core" {
  for_each = local.monitors

  name                = each.value.name
  type                = "query alert"
  query               = each.value.query
  message             = "${each.value.message}\n${local.email_notification}"
  tags                = concat(local.common_tags, each.value.tags)
  include_tags        = true
  require_full_window = false
  evaluation_delay    = try(each.value.evaluation_delay, 60)
  renotify_interval   = 0
  on_missing_data     = each.value.on_missing_data
  lifecycle {
    ignore_changes = [monitor_thresholds]
  }
}

# W6 has its own no-data semantics; keep notify_no_data scoped to this monitor
# instead of enabling it for every monitor in the core for_each resource.
resource "datadog_monitor" "detector_heartbeat" {
  name                = "SMIOT | W6 | Detector evaluation stalled"
  type                = "query alert"
  query               = "min(last_5m):min:smiot.detector.evaluation_heartbeat{detector:agronomic_advisory} by {farm} < 1"
  message             = "The agronomic advisory evaluation is missing or stale for {{farm.name}}. Check the separate watchdog heartbeat, latest MongoDB input age, evaluation age, and service logs before remediation. Do not issue irrigation or actuator commands from this monitor.\n\n@workflow-smiot-w06-detector-heartbeat(farm_key=\"{{farm.name}}\")\n${local.email_notification}"
  tags                = ["project:smiot", "service:smiot-smart-farm", "env:demo", "component:detector", "severity:warning", "workflow:w6"]
  include_tags        = true
  on_missing_data     = "show_and_notify_no_data"
  priority            = 2
  new_group_delay     = 300
  require_full_window = false
  evaluation_delay    = 0
  renotify_interval   = 60
  monitor_thresholds {
    critical = "1"
  }
  lifecycle {
    ignore_changes = [monitor_thresholds, new_host_delay, notify_no_data]
  }
}
