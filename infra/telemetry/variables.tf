variable "aws_region" {
  description = "AWS region containing the SMIOT EC2 instance."
  type        = string
  default     = "ap-southeast-2"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used only by the Terraform AWS provider."
  type        = string
  default     = "aws-moi"
}

variable "datadog_api_key" {
  description = "Datadog US API key; passed ephemerally to the write-only SSM parameter."
  type        = string
  sensitive   = true
  ephemeral   = true
}

variable "datadog_app_key" {
  description = "Datadog US application key used by the workflow bridge; passed ephemerally to a write-only SSM parameter."
  type        = string
  sensitive   = true
  ephemeral   = true
}

variable "ec2_name_tag" {
  description = "Exact EC2 Name tag for the single SMIOT host."
  type        = string
  default     = "SMIOT-Smart-Farm-Demo"
}

variable "datadog_monitor_id" {
  description = "Current-account monitor that drives the Wokwi workflow bridge."
  type        = string
  default     = "342585819"
}

variable "datadog_workflow_id" {
  description = "Current-account W2/Ca 2 workflow consumed by the Wokwi workflow bridge."
  type        = string
  default     = "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724"
}

variable "expected_account_id" {
  description = "Expected AWS account for a fail-closed Terraform preflight; supplied only in the local process environment."
  type        = string
  sensitive   = true
}
