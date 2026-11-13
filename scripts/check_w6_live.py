import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

vals = {}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k, v = line.split(':', 1); vals[k.strip().lower()] = v.strip()
headers = {'DD-API-KEY': vals.get('api_keys') or vals.get('key_id'), 'DD-APPLICATION-KEY': vals.get('app_key'), 'Accept': 'application/json'}
base = 'https://api.datadoghq.com'
def get(url):
    with urlopen(Request(url, headers=headers), timeout=30) as r:
        return json.loads(r.read().decode())
ids = ['d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3']
found = []
for wid in ids:
    try:
        d = get(f'{base}/api/v2/workflows/{wid}')
        a = d.get('data', {}).get('attributes', {}); spec = a.get('spec') or {}
        qs = []
        for s in spec.get('steps', []):
            for p in s.get('parameters', []):
                v = p.get('value')
                if isinstance(v, list): qs += [x.get('query') for x in v if isinstance(x, dict) and x.get('query')]
        found.append({'id': wid, 'name': a.get('name'), 'published': a.get('published'), 'handle': spec.get('handle'), 'queries': qs, 'steps': len(spec.get('steps', []))})
    except Exception as e:
        found.append({'id': wid, 'error_type': type(e).__name__})
monitors = []
for mid in ['343029221','339977691']:
    try:
        m = get(f'{base}/api/v1/monitor/{mid}?group_states=all')
        groups = (m.get('state') or {}).get('groups') or {}
        monitors.append({'id': mid, 'name': m.get('name'), 'overall_state': m.get('overall_state'), 'query': m.get('query'), 'groups': {k: {'status': v.get('status'), 'last_triggered_ts': v.get('last_triggered_ts')} for k,v in groups.items()}})
    except Exception as e:
        monitors.append({'id': mid, 'error_type': type(e).__name__})
now = __import__('time').time(); metric = get(base + '/api/v1/query?' + urlencode({'from': int(now)-1800, 'to': int(now), 'query': 'max:smiot.detector.evaluation_heartbeat{detector:agronomic_advisory} by {farm}'}))
series = metric.get('series', []) if isinstance(metric, dict) else []
print(json.dumps({'workflow_checks': found, 'monitor_checks': monitors, 'evaluation_series': [{'scope': s.get('scope'), 'points': s.get('pointlist', [])[-5:]} for s in series]}, ensure_ascii=False))
