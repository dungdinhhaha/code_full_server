param(
    [Parameter(Mandatory = $true)]
    [string]$DatadogExternalId,
    [string]$Profile = "aws-moi",
    [string]$Region = "ap-southeast-2"
)

$ErrorActionPreference = "Stop"
$accountId = "920235987407"
$roleName = "DatadogSMIOTServiceRecoveryRole"
$documentName = "SMIOT-GuardedStartApp"
$policyName = "SMIOTGuardedSSMCommand"
$instanceId = "i-00bf2d3591d3ee0a2"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$documentPath = Join-Path $PSScriptRoot "ssm\SMIOT-GuardedStartApp.json"
$permissionsPath = Join-Path $PSScriptRoot "ssm\SMIOT-GuardedStartApp-Policy.json"

if ($DatadogExternalId -notmatch '^[A-Za-z0-9-]{20,80}$') {
    throw "The Datadog-generated external ID format is invalid."
}

$identity = & aws --profile $Profile sts get-caller-identity --query Account --output text
if ($LASTEXITCODE -ne 0 -or $identity.Trim() -ne $accountId) {
    throw "AWS profile '$Profile' is not authenticated to the expected SMIOT account."
}

$documentStatus = & aws --profile $Profile --region $Region ssm describe-document `
    --name $documentName --query Document.Status --output text 2>$null
if ($LASTEXITCODE -ne 0 -or $documentStatus.Trim() -ne "Active") {
    throw "Create and validate SSM document '$documentName' before creating the Datadog role."
}

$trust = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Effect = "Allow"
            Principal = @{ AWS = "arn:aws:iam::464622532012:root" }
            Action = "sts:AssumeRole"
            Condition = @{ StringEquals = @{ "sts:ExternalId" = $DatadogExternalId } }
        }
    )
} | ConvertTo-Json -Depth 8

$tempRoot = Join-Path $env:TEMP ("smiot-dd-ssm-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$trustPath = Join-Path $tempRoot "trust.json"
[System.IO.File]::WriteAllText($trustPath, $trust, [System.Text.UTF8Encoding]::new($false))

try {
    & aws --profile $Profile iam get-role --role-name $roleName --query Role.RoleName --output text 2>$null | Out-Null
    $roleExists = $LASTEXITCODE -eq 0

    if ($roleExists) {
        & aws --profile $Profile iam update-assume-role-policy `
            --role-name $roleName --policy-document "file://$trustPath" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not update the Datadog role trust policy." }
    } else {
        & aws --profile $Profile iam create-role `
            --role-name $roleName `
            --description "Least-privilege Datadog action role for guarded SMIOT app recovery on one EC2 instance." `
            --assume-role-policy-document "file://$trustPath" `
            --tags Key=Project,Value=SMIOT Key=Purpose,Value=DatadogGuardedRecovery `
            --query Role.Arn --output text | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not create the Datadog recovery role." }
    }

    & aws --profile $Profile iam put-role-policy `
        --role-name $roleName `
        --policy-name $policyName `
        --policy-document "file://$permissionsPath" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not attach the scoped SSM policy." }

    $roleArn = & aws --profile $Profile iam get-role --role-name $roleName --query Role.Arn --output text
    if ($LASTEXITCODE -ne 0) { throw "The recovery role could not be read back." }
    Write-Output "Role ready: $($roleArn.Trim())"
    Write-Output "Scope: SSM SendCommand for $documentName on $instanceId; command-result read only."
} finally {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
