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
    'Content-Type': 'application/json',
}
url = 'https://api.datadoghq.com/api/v1/monitor/342734743'
with urlopen(Request(url, headers=headers), timeout=30) as response:
    monitor = json.load(response)
monitor['query'] = 'sum(last_5m):sum:smiot.actuator.command_unacknowledged{event:unacknowledged} by {farm,actuator} > 0'
monitor.setdefault('options', {})['on_missing_data'] = 'resolve'
payload = json.dumps({
    'name': monitor['name'],
    'type': monitor['type'],
    'query': monitor['query'],
    'message': monitor.get('message', ''),
    'tags': monitor.get('tags', []),
    'options': monitor.get('options', {}),
}).encode('utf-8')
with urlopen(Request(url, data=payload, headers=headers, method='PUT'), timeout=30) as response:
    updated = json.load(response)
print(json.dumps({'id': updated.get('id'), 'name': updated.get('name'), 'query': updated.get('query'), 'state': updated.get('overall_state')}, ensure_ascii=False))
