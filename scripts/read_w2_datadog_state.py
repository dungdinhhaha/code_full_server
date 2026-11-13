import json
from pathlib import Path
from urllib.request import Request, urlopen

vals = {}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k, v = line.split(':', 1); vals[k.strip().lower()] = v.strip()
api = vals.get('api_keys') or vals.get('api_key') or vals.get('key_id')
app = vals.get('app_key') or vals.get('application_key')
headers = {'DD-API-KEY': api, 'DD-APPLICATION-KEY': app, 'Accept': 'application/json'}
url = 'https://api.datadoghq.com/api/v1/monitor/342585819?group_states=all'
with urlopen(Request(url, headers=headers), timeout=30) as r:
    d = json.loads(r.read().decode())
groups = (d.get('state') or {}).get('groups') or {}
last = max((int(g.get('last_triggered_ts') or 0) for g in groups.values()), default=0)
print(json.dumps({'monitor_id': d.get('id'), 'name': d.get('name'), 'overall_state': d.get('overall_state'), 'group_count': len(groups), 'last_triggered_epoch': last}, ensure_ascii=False))
