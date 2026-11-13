import json
from pathlib import Path
from urllib.request import Request,urlopen
v={}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k,x=line.split(':',1); v[k.strip().lower()]=x.strip()
h={'DD-API-KEY':v.get('api_keys') or v.get('key_id'),'DD-APPLICATION-KEY':v.get('app_key')}
with urlopen(Request('https://api.datadoghq.com/api/v1/dashboard?count=1000',headers=h),timeout=30) as r: data=json.load(r)
for x in data.get('dashboards',[]):
    text=str(x).lower()
    if 'smiot' in text or 'farm' in text:
        print(json.dumps({k:x.get(k) for k in ('id','title','url','is_read_only')},ensure_ascii=False))
