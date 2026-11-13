$ErrorActionPreference = 'Stop'
$repo = 'D:\IOT Trung\code_full_server'
$ids = [ordered]@{
  W1 = 'b9e72b04-1580-45f8-ae1e-628124a19065'
  W2 = '2f9a3c1d-5292-4bc3-b4b9-cc03d4172724'
  W4 = 'ffd62026-6b63-40e4-9b46-6ac18d2d584f'
  W5 = 'd3f0705e-2cbd-430a-9a3a-b1fd02a42cc9'
}
$messages = @{
  W1 = 'PLC safety trip evidence reviewed. Local interlock remains the immediate safety authority; Datadog issued no actuator command. Open this workflow run for evidence and acknowledgement.'
  W2 = 'Sensor flatline and local interlock evidence reviewed. Keep the farm in HOLD until fresh telemetry is confirmed; no remote actuator command was issued.'
  W4 = 'Fresh telemetry was confirmed from the evidence sources. Restart was refused safely; keep the incident open until the operator reviews the linked evidence.'
  W5 = 'MongoDB, MQTT, and ingest signals were triaged. The selected dependency branch is advisory only; verify the matching farm evidence before any recovery action.'
}
$kv = @{}
Get-Content -LiteralPath 'D:\attt\APP_KEY.txt' | ForEach-Object {
  if ($_ -match '^\s*([^:=]+)\s*[:=]\s*(.*)$') { $kv[$matches[1].Trim()] = $matches[2].Trim() }
}
$headers = @{'DD-API-KEY' = $kv['api_keys']; 'DD-APPLICATION-KEY' = $kv['APP_KEY']; Accept = 'application/json'; 'Content-Type' = 'application/json'}
$out = Join-Path $repo 'outputs\workflow_imports\notification_contract_patch_20261110'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary = @()
foreach ($key in $ids.Keys) {
  $id = $ids[$key]
  $remote = Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers
  $remote | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath (Join-Path $out "${key}_before.json") -Encoding utf8
  $attrs = $remote.data.attributes
  $step = @($attrs.spec.steps | Where-Object { $_.name -eq 'notify_smiot_app' })[0]
  if ($null -eq $step) { throw "Missing notification step $key" }
  $bodyObj = [ordered]@{event_id='{{InstanceId}}'; workflow_name='{{WorkflowName}}'; workflow_id='{{WorkflowId}}'; message=$messages[$key]; category='datadog'; severity='info'}
  $body = $bodyObj | ConvertTo-Json -Compress
  $param = @($step.parameters | Where-Object { $_.name -eq 'body' })[0]
  if ($null -eq $param) { throw "Missing body parameter $key" }
  $param.value = $body
  $payload = [ordered]@{data=[ordered]@{id=$remote.data.id; type='workflows'; attributes=[ordered]@{name=$attrs.name; description=$attrs.description; published=$attrs.published; runAs=$attrs.runAs; sensitivePrivileges=$attrs.sensitivePrivileges; tags=$attrs.tags; spec=$attrs.spec}}}
  Invoke-RestMethod -Method Patch -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers -Body ($payload | ConvertTo-Json -Depth 100) | Out-Null
  $check = Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers
  $check | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath (Join-Path $out "${key}_after.json") -Encoding utf8
  $checkStep = @($check.data.attributes.spec.steps | Where-Object { $_.name -eq 'notify_smiot_app' })[0]
  $checkBody = [string](@($checkStep.parameters | Where-Object { $_.name -eq 'body' })[0].value)
  $summary += [pscustomobject]@{workflow=$key; id=$id; published=$check.data.attributes.published; message_updated=$checkBody.Contains($messages[$key])}
}
$summary | ConvertTo-Json -Compress
