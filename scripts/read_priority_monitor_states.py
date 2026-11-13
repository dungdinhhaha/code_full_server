import json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
v={}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k,x=line.split(':',1); v[k.strip().lower()]=x.strip()
h={'DD-API-KEY':v.get('api_keys') or v.get('api_key') or v.get('key_id'),'DD-APPLICATION-KEY':v.get('app_key') or v.get('application_key'),'Accept':'application/json'}
base='https://api.datadoghq.com'; now=int(time.time()); out={}
for mid in ('342585824','342734743','342585836'):
    with urlopen(Request(f'{base}/api/v1/monitor/{mid}?group_states=all',headers=h),timeout=30) as r:d=json.load(r)
    groups=(d.get('state') or {}).get('groups') or {}
    out[mid]={'name':d.get('name'),'state':d.get('overall_state'),'modified':d.get('overall_state_modified'),'groups':{k:{'state':z.get('status'),'last_triggered':z.get('last_triggered_ts')} for k,z in groups.items()}}
print(json.dumps(out,ensure_ascii=False))
