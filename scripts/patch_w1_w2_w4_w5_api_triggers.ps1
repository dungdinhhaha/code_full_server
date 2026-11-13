$ErrorActionPreference = 'Stop'
$repo = 'D:\IOT Trung\code_full_server'
$ids = [ordered]@{ W1='b9e72b04-1580-45f8-ae1e-628124a19065'; W2='2f9a3c1d-5292-4bc3-b4b9-cc03d4172724'; W4='ffd62026-6b63-40e4-9b46-6ac18d2d584f'; W5='d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9' }
$kv=@{}
Get-Content -LiteralPath 'D:\attt\APP_KEY.txt' | ForEach-Object { if ($_ -match '^\s*([^:=]+)\s*[:=]\s*(.*)$') { $kv[$matches[1].Trim()]=$matches[2].Trim() } }
$headers=@{'DD-API-KEY'=$kv['api_keys'];'DD-APPLICATION-KEY'=$kv['APP_KEY'];Accept='application/json';'Content-Type'='application/json'}
$out=Join-Path $repo 'outputs\workflow_imports\api_trigger_patch_20261110'; New-Item -ItemType Directory -Force -Path $out | Out-Null
$summary=@()
foreach($key in $ids.Keys){
  $id=$ids[$key]; $remote=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers
  $remote | ConvertTo-Json -Depth 100 | Set-Content (Join-Path $out "${key}_before.json") -Encoding utf8
  $attrs=$remote.data.attributes; $spec=$attrs.spec
  $triggers=@($spec.triggers)
  $monitor=@($triggers|Where-Object {$null -ne $_.monitorTrigger})[0]
  if($null -eq $monitor){ throw "Missing monitor trigger $key" }
  $api=@($triggers|Where-Object {$null -ne $_.apiTrigger})[0]
  if($null -eq $api){ $api=[pscustomobject]@{startStepNames=$monitor.startStepNames;apiTrigger=[pscustomobject]@{}} }
  $spec.triggers=@($monitor,$api)
  if($key -eq 'W4'){
    if($null -eq $spec.inputSchema){$spec|Add-Member -NotePropertyName inputSchema -NotePropertyValue ([pscustomobject]@{parameters=@()})}
    $existing=@($spec.inputSchema.parameters)
    foreach($name in @('farm_key','node_id','incident_id')){if(-not (@($existing|Where-Object {$_.name -eq $name}))){$existing += [pscustomobject]@{name=$name;type='STRING';defaultValue='greenhouse_a'}}}
    $spec.inputSchema.parameters=$existing
  }
  $payload=[ordered]@{data=[ordered]@{id=$remote.data.id;type='workflows';attributes=[ordered]@{name=$attrs.name;description=$attrs.description;published=$attrs.published;runAs=$attrs.runAs;sensitivePrivileges=$attrs.sensitivePrivileges;tags=$attrs.tags;spec=$spec}}}
  Invoke-RestMethod -Method Patch -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers -Body ($payload|ConvertTo-Json -Depth 100) | Out-Null
  $check=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $headers
  $check|ConvertTo-Json -Depth 100|Set-Content (Join-Path $out "${key}_after.json") -Encoding utf8
  $ct=@($check.data.attributes.spec.triggers); $summary += [pscustomobject]@{workflow=$key;published=$check.data.attributes.published;trigger_count=$ct.Count;has_api=([bool](@($ct|Where-Object {$null -ne $_.apiTrigger})));parameter_names=([string]::Join(',',@($check.data.attributes.spec.inputSchema.parameters|ForEach-Object {$_.name})))}
}
$summary|ConvertTo-Json -Compress
