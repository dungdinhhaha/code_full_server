$ErrorActionPreference='Stop'
$repo='D:\IOT Trung\code_full_server';$id='b9e72b04-1580-45f8-ae1e-628124a19065'
$kv=@{};Get-Content 'D:\attt\APP_KEY.txt'|ForEach-Object{if($_ -match '^\s*([^:=]+)\s*[:=]\s*(.*)$'){$kv[$matches[1].Trim()]=$matches[2].Trim()}}
$h=@{'DD-API-KEY'=$kv['api_keys'];'DD-APPLICATION-KEY'=$kv['APP_KEY'];Accept='application/json';'Content-Type'='application/json'}
$out=Join-Path $repo 'outputs\workflow_imports\w1_query_patch_20261110';New-Item -ItemType Directory -Force -Path $out|Out-Null
$remote=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $h;$remote|ConvertTo-Json -Depth 100|Set-Content (Join-Path $out 'before.json') -Encoding utf8
$attrs=$remote.data.attributes;$st=@($attrs.spec.steps|Where-Object {$_.name -eq 'read_operational_signals'})[0];$q=@($st.parameters|Where-Object {$_.name -eq 'queries'})[0];$q.value[0].query='sum:smiot.virtual_plc.safety_trip{source:smiot_demo_stream}'
$payload=[ordered]@{data=[ordered]@{id=$remote.data.id;type='workflows';attributes=[ordered]@{name=$attrs.name;description=$attrs.description;published=$attrs.published;runAs=$attrs.runAs;sensitivePrivileges=$attrs.sensitivePrivileges;tags=$attrs.tags;spec=$attrs.spec}}}
Invoke-RestMethod -Method Patch -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $h -Body ($payload|ConvertTo-Json -Depth 100)|Out-Null
$check=Invoke-RestMethod -Method Get -Uri "https://api.datadoghq.com/api/v2/workflows/$id" -Headers $h;$check|ConvertTo-Json -Depth 100|Set-Content (Join-Path $out 'after.json') -Encoding utf8
$c=@($check.data.attributes.spec.steps|Where-Object {$_.name -eq 'read_operational_signals'})[0];$qc=@($c.parameters|Where-Object {$_.name -eq 'queries'})[0].value[0].query;[pscustomobject]@{workflow='W1';published=$check.data.attributes.published;query=$qc}|ConvertTo-Json -Compress
