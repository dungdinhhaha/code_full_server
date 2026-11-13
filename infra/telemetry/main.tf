data "aws_instances" "smiot" {
  filter {
    name   = "instance-state-name"
    values = ["running"]
  }

  filter {
    name   = "tag:Name"
    values = [var.ec2_name_tag]
  }
}

data "aws_caller_identity" "current" {}

locals {
  parameter_name = "/smiot/datadog/api-key"
  ec2_role_name  = "smiot-demo-ec2-role"
}

resource "aws_ssm_parameter" "datadog_api_key" {
  name             = local.parameter_name
  description      = "Datadog US API key used by the SMIOT app; managed as a write-only Terraform value."
  type             = "SecureString"
  tier             = "Standard"
  value_wo         = var.datadog_api_key
  value_wo_version = 1

  lifecycle {
    precondition {
      condition     = length(data.aws_instances.smiot.ids) == 1 && data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "Expected the configured AWS account and exactly one running SMIOT EC2 instance with the configured Name tag."
    }
  }

  tags = {
    Project     = "smiot"
    Environment = "demo"
    ManagedBy   = "terraform"
    Purpose     = "datadog-telemetry"
  }
}

resource "aws_ssm_parameter" "datadog_app_key" {
  name             = "/smiot/datadog/app-key"
  description      = "Datadog US application key used by the SMIOT workflow bridge; managed as a write-only Terraform value."
  type             = "SecureString"
  tier             = "Standard"
  value_wo         = var.datadog_app_key
  value_wo_version = 1

  lifecycle {
    precondition {
      condition     = length(data.aws_instances.smiot.ids) == 1 && data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "Expected the configured AWS account and exactly one running SMIOT EC2 instance with the configured Name tag."
    }
  }

  tags = {
    Project     = "smiot"
    Environment = "demo"
    ManagedBy   = "terraform"
    Purpose     = "datadog-workflow-bridge"
  }
}

resource "aws_iam_role_policy" "datadog_parameter_read" {
  name = "SMIOTDatadogTelemetryParameterRead"
  role = local.ec2_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadOnlySmiotDatadogApiKey"
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = [aws_ssm_parameter.datadog_api_key.arn, aws_ssm_parameter.datadog_app_key.arn]
      },
      {
        Sid      = "DecryptOnlySmiotDatadogParameterThroughSsm"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
          ArnEquals = {
            "kms:EncryptionContext:PARAMETER_ARN" = [aws_ssm_parameter.datadog_api_key.arn, aws_ssm_parameter.datadog_app_key.arn]
          }
        }
      }
    ]
  })
}

resource "aws_ssm_document" "apply_telemetry" {
  name            = "SMIOT-ApplyDatadogTelemetry"
  document_type   = "Command"
  document_format = "JSON"
  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Safely refreshes the SMIOT app Datadog key from an encrypted Parameter Store value, validates it, and restores service health. The Datadog Agent key is changed only if it differs."
    mainSteps = [
      {
        action = "aws:runShellScript"
        name   = "applySmiotDatadogTelemetry"
        inputs = {
          runCommand = ["set -eu\nexport SMIOT_DD_MONITOR_ID='${var.datadog_monitor_id}'\nexport SMIOT_DD_WORKFLOW_ID='${var.datadog_workflow_id}'\n/opt/smiot/.venv/bin/python - <<'PY'\n${file("${path.module}/apply_telemetry.py")}\nPY"]
        }
      }
    ]
  })

  lifecycle {
    precondition {
      condition     = length(data.aws_instances.smiot.ids) == 1 && data.aws_caller_identity.current.account_id == var.expected_account_id
      error_message = "Expected the configured AWS account and exactly one running SMIOT EC2 instance before creating the telemetry runbook."
    }
  }

  tags = {
    Project   = "smiot"
    ManagedBy = "terraform"
  }
}
