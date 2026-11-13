from __future__ import annotations
import argparse, json, os, socket
from datetime import datetime, timezone
from pathlib import Path

def line(metric: str, value: int, tags: list[str]) -> str:
    return f'{metric}:{value}|g|#{",".join(tags)}'

parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=['mongo_down','mqtt_down','normal'], required=True)
parser.add_argument('--send', action='store_true')
parser.add_argument('--output', type=Path, default=Path('outputs/evidence/w5_dependency_metric_manifest.json'))
args = parser.parse_args()
common=['project:smiot','env:demo','source:smiot_synthetic_drill']
mongo = 0 if args.mode == 'mongo_down' else 1
mqtt = 0 if args.mode == 'mqtt_down' else 1
metrics=[
 {'metric':'smiot.dependency.mongo.up','value':mongo,'tags':common},
 {'metric':'smiot.dependency.mqtt.up','value':mqtt,'tags':common},
]
artifact={'artifact':'smiot_w5_dependency_metric_manifest','generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'synthetic':True,'mode':args.mode,'sent':args.send,'metrics':metrics,'real_dependency_stopped':False}
args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if args.send:
    payload='\n'.join(line(m['metric'],m['value'],m['tags']) for m in metrics).encode()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as client: client.sendto(payload,(os.getenv('DD_AGENT_HOST','127.0.0.1'),int(os.getenv('DD_DOGSTATSD_PORT','8125'))))
print(json.dumps({'output':str(args.output),'mode':args.mode,'sent':args.send,'metric_count':len(metrics)}))
