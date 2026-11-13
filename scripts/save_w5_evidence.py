from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone
import json

kv = {}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k, v = line.split(':', 1)
        kv[k.strip().upper()] = v.strip()
headers = {'DD-API-KEY': kv.get('API_KEY') or kv.get('API_KEYS'), 'DD-APPLICATION-KEY': kv.get('APP_KEY'), 'Accept': 'application/json'}
base = 'https://api.datadoghq.com'
monitor_ids = ['342585827', '342585828']
workflow_id = 'd3f0705e-2cbd-430a-9a3a-b1fd02a42cc9'
monitors = []
for monitor_id in monitor_ids:
    with urlopen(Request(f'{base}/api/v1/monitor/{monitor_id}?group_states=all', headers=headers), timeout=30) as response:
        data = json.load(response)
    monitors.append({'id': monitor_id, 'name': data.get('name'), 'state': data.get('overall_state'), 'query': data.get('query')})
with urlopen(Request(f'{base}/api/v2/workflows/{workflow_id}/instances?page[size]=10', headers=headers), timeout=30) as response:
    workflow_data = json.load(response)
runs = []
for item in workflow_data.get('data', []):
    attrs = item.get('attributes') or {}
    source = item.get('attributes', {}).get('source') or {}
    handle = source.get('handle') or {}
    if handle.get('id') in monitor_ids:
        status = attrs.get('instanceStatus') or attrs.get('status') or {}
        runs.append({'id': item.get('id'), 'status': status.get('displayName'), 'monitor_id': handle.get('id')})
artifact = {'artifact': 'smiot_w5_dependency_drill', 'generated_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'synthetic': True, 'real_dependencies_stopped': False, 'monitors': monitors, 'workflow_id': workflow_id, 'workflow_runs': runs[:6], 'modes': ['mongo_down', 'mqtt_down', 'normal']}
output = Path('outputs/evidence/w5_dependency_drill_runtime.json')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': str(output), 'monitor_states': [m['state'] for m in monitors], 'run_count': len(runs)}))
