import json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
v={}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k,x=line.split(':',1); v[k.strip().lower()]=x.strip()
h={'DD-API-KEY':v.get('api_keys') or v.get('api_key') or v.get('key_id'),'DD-APPLICATION-KEY':v.get('app_key') or v.get('application_key'),'Accept':'application/json'}
now=int(time.time()); q='avg:smiot.ai.ask_latency_ms{status:provider_error} by {host,source}'; u='https://api.datadoghq.com/api/v1/query?'+urlencode({'from':now-600,'to':now,'query':q})
with urlopen(Request(u,headers=h),timeout=30) as r:d=json.load(r)
print(json.dumps({'from':now-600,'to':now,'series':[{'scope':s.get('scope'),'points':s.get('pointlist',[])[-4:]} for s in d.get('series',[])]}))
