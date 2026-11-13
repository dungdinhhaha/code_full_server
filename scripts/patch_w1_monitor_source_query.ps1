$ErrorActionPreference='Stop'
$repo='D:\IOT Trung\code_full_server';$id='342734303'
$kv=@{};Get-Content 'D:\attt\APP_KEY.txt'|ForEach-Object{if($_ -match '^\s*([^:=]+)\s*[:=]\s*(.*)$'){$kv[$matches[1].Trim()]=$matches[2].Trim()}}
$h=@{'DD-API-KEY'=$kv['api_keys'];'DD-APPLICATION-KEY'=$kv['APP_KEY'];Accept='application/json';'Content-Type'='application/json'}
$out=Join-Path $repo 'outputs\workflow_imports\w1_monitor_patch_20261110';New-Item -ItemType Directory -Force -Path $out|Out-Null
$m=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v1/monitor/$id" -Headers $h;$m|ConvertTo-Json -Depth 100|Set-Content (Join-Path $out 'before.json') -Encoding utf8
$m.query='sum(last_5m):sum:smiot.virtual_plc.safety_trip{source:smiot_demo_stream} > 0'
$m.options.PSObject.Properties.Remove('new_group_delay')
$payload=[ordered]@{name=$m.name;type=$m.type;query=$m.query;message=$m.message;tags=$m.tags;options=$m.options;priority=$m.priority}
Invoke-RestMethod -Method Put -Uri "https://api.datadoghq.com/api/v1/monitor/$id" -Headers $h -Body ($payload|ConvertTo-Json -Depth 100)|Out-Null
$check=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v1/monitor/$id" -Headers $h;$check|ConvertTo-Json -Depth 100|Set-Content (Join-Path $out 'after.json') -Encoding utf8
[pscustomobject]@{id=$check.id;name=$check.name;overall_state=$check.overall_state;query=$check.query}|ConvertTo-Json -Compress
