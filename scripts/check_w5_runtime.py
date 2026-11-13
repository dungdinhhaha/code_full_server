from pathlib import Path
from urllib.request import Request, urlopen
import json

kv = {}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k, v = line.split(':', 1)
        kv[k.strip().upper()] = v.strip()
headers = {
    'DD-API-KEY': kv.get('API_KEY') or kv.get('API_KEYS'),
    'DD-APPLICATION-KEY': kv.get('APP_KEY'),
    'Accept': 'application/json',
}
base = 'https://api.datadoghq.com'
monitor_ids = ['342585827', '342585828']
workflow_id = 'd3f0705e-2cbd-430a-9a3a-b1fd02a42cc9'
monitors = []
for monitor_id in monitor_ids:
    with urlopen(Request(f'{base}/api/v1/monitor/{monitor_id}?group_states=all', headers=headers), timeout=30) as response:
        monitor = json.load(response)
    monitors.append({'id': monitor_id, 'name': monitor.get('name'), 'state': monitor.get('overall_state'), 'query': monitor.get('query')})
with urlopen(Request(f'{base}/api/v2/workflows/{workflow_id}/instances?page[size]=10', headers=headers), timeout=30) as response:
    workflows = json.load(response)
instances = []
for item in workflows.get('data', [])[:10]:
    attrs = item.get('attributes') or {}
    instances.append({'id': item.get('id'), 'status': attrs.get('status') or attrs.get('instanceStatus'), 'start': attrs.get('startTime'), 'finish': attrs.get('finishTime'), 'source': attrs.get('source')})
print(json.dumps({'monitors': monitors, 'workflow_instances': instances}, ensure_ascii=False))
