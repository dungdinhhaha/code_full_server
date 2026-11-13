resource "datadog_service_level_objective" "slo_1" {
  name = "SMIOT | Trusted Telemetry Pipeline Availability"
  description = "Pilot 7-day monitor-based SLO for telemetry freshness and MongoDB/MQTT dependency health. Excludes the intentional Node 2 flatline demonstration: a sensor fault must not be confused with platform unavailability. Availability history starts at creation and must accumulate before reporting a mature objective."
  type = "monitor"
  monitor_ids = [339977703, 339990226, 339990232]
  tags = ["env:demo","project:smiot","region:aws-ap-southeast-2","sli:trusted-telemetry"]
  thresholds {
    timeframe = "7d"
    target = 99
    warning = 99.5
  }
}
