output "parameter_name" {
  description = "Encrypted Parameter Store name consumed by the EC2 instance role."
  value       = aws_ssm_parameter.datadog_api_key.name
}

output "app_parameter_name" {
  description = "Encrypted Parameter Store name for the Datadog application key."
  value       = aws_ssm_parameter.datadog_app_key.name
}

output "runbook_name" {
  description = "SSM Command document to apply and verify the app telemetry configuration."
  value       = aws_ssm_document.apply_telemetry.name
}

output "target_count" {
  description = "Number of running SMIOT hosts selected by the exact Name tag."
  value       = length(data.aws_instances.smiot.ids)
}
