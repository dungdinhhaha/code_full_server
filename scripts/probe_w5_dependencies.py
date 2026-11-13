"""Read-only MongoDB/MQTT probes for W5 dependency evidence."""
from __future__ import annotations
import argparse, json, os, socket
from datetime import datetime, timezone
from pathlib import Path

def utc(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def mongo_probe():
    try:
        from pymongo import MongoClient
        uri=os.getenv('MONGODB_URI')
        if not uri: return {'ok':False,'reason':'MONGODB_URI_not_set'}
        c=MongoClient(uri,serverSelectionTimeoutMS=2500); r=c.admin.command('ping'); c.close()
        return {'ok':r.get('ok')==1,'operation':'admin_ping'}
    except Exception as e: return {'ok':False,'reason':type(e).__name__}
def mqtt_probe(host,port):
    try:
        s=socket.create_connection((host,port),timeout=2.5); s.close()
        return {'ok':True,'operation':'tcp_connect','host':host,'port':port}
    except Exception as e: return {'ok':False,'reason':type(e).__name__,'host':host,'port':port}
ap=argparse.ArgumentParser(); ap.add_argument('--phase',choices=['before','after'],required=True); ap.add_argument('--output',type=Path,default=Path('outputs/evidence/w5_dependency_probe.json')); a=ap.parse_args()
r={'artifact':'smiot_w5_dependency_probe','synthetic':False,'phase':a.phase,'observed_at_utc':utc(),'mongo':mongo_probe(),'mqtt':mqtt_probe(os.getenv('MQTT_HOST','127.0.0.1'),int(os.getenv('MQTT_PORT','1883')))}
a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(r,ensure_ascii=False))
