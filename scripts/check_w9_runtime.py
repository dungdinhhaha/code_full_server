from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json, time
KV={}
for line in Path(r'D:\attt\APP_KEY.txt').read_text(encoding='utf-8').splitlines():
    if ':' in line:
        k,v=line.split(':',1); KV[k.strip().upper()]=v.strip()
H={'DD-API-KEY':KV.get('API_KEY') or KV.get('API_KEYS'),'DD-APPLICATION-KEY':KV.get('APP_KEY'),'Accept':'application/json'}
base='https://api.datadoghq.com'
mid='342734743'; wid='47e95b24-db40-4cd5-b667-5b90e170b667'
with urlopen(Request(f'{base}/api/v1/monitor/{mid}?group_states=all',headers=H),timeout=30) as r: mon=json.load(r)
with urlopen(Request(f'{base}/api/v2/workflows/{wid}/instances?page[size]=5',headers=H),timeout=30) as r: wf=json.load(r)
now=int(time.time()); q=base+'/api/v1/query?'+urlencode({'from':now-600,'to':now,'query':'sum:smiot.actuator.command_unacknowledged{*} by {farm,actuator}'})
with urlopen(Request(q,headers=H),timeout=30) as r: metric=json.load(r)
print(json.dumps({'monitor':{'id':mid,'name':mon.get('name'),'state':mon.get('overall_state'),'state_modified':mon.get('overall_state_modified'),'query':mon.get('query'),'options':mon.get('options')},'metric_series':len(metric.get('series',[])),'series_tags':[s.get('scope') for s in metric.get('series',[])],'latest_points':[s.get('pointlist',[])[-3:] for s in metric.get('series',[])],'workflow_instances':[{'id':x.get('id'),'status':x.get('attributes',{}).get('status'),'instanceStatus':x.get('attributes',{}).get('instanceStatus'),'started':x.get('attributes',{}).get('startedAt'),'finished':x.get('attributes',{}).get('finishedAt'),'source':x.get('attributes',{}).get('source')} for x in wf.get('data',[])]},ensure_ascii=False))
