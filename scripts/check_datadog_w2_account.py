import json, time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

vals = {}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k, v = line.split(':', 1); vals[k.strip().lower()] = v.strip()
api = vals.get('api_keys') or vals.get('api_key') or vals.get('key_id')
app = vals.get('app_key') or vals.get('application_key')
headers = {'DD-API-KEY': api, 'DD-APPLICATION-KEY': app, 'Accept': 'application/json'}

def get(path, params=None):
    url = 'https://api.datadoghq.com' + path
    if params: url += '?' + urlencode(params)
    with urlopen(Request(url, headers=headers), timeout=30) as r:
        return json.loads(r.read().decode())

now = int(time.time()); start = now - 1800
validate = get('/api/v1/validate')
monitors = get('/api/v1/monitor', {'name': 'SMIOT'})
w2 = [m for m in monitors if 'flatline' in str(m.get('name','')).lower() or 'Node 2' in str(m.get('name',''))]
queries = {
    'flatline': 'max:smiot.telemetry.sensor_flatline{farm:greenhouse_a,node:2}',
    'app_active': 'avg:system.unit.active{host:i-00bf2d3591d3ee0a2,unit:smiot.service}',
}
metric_results = {}
for name, query in queries.items():
    try:
        metric_results[name] = get('/api/v1/query', {'from': start, 'to': now, 'query': query})
    except Exception as exc:
        metric_results[name] = {'error_type': type(exc).__name__}
print(json.dumps({
    'site': 'datadoghq.com',
    'api_key_valid': validate.get('valid'),
    'monitor_matches': [{'id': m.get('id'), 'name': m.get('name'), 'overall_state': m.get('overall_state'), 'query': m.get('query'), 'thresholds': (m.get('options') or {}).get('thresholds'), 'no_data_timeframe': (m.get('options') or {}).get('no_data_timeframe')} for m in w2],
    'metric_series_counts': {k: len(v.get('series', [])) if isinstance(v, dict) else None for k,v in metric_results.items()},
    'metric_results': metric_results,
}, ensure_ascii=False))
