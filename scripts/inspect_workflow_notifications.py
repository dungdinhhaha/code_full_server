import json
import re
from service.mongodb_store import collection

def main():
    rows=[]
    for n in collection('notifications').find({'source':'datadog_workflow'}).sort('created_at',-1).limit(80):
        wid=' '.join(str(n.get(k) or '') for k in ('workflow_id','workflow_name','message')).lower()
        rows.append({'workflow_id':n.get('workflow_id'),'workflow_name':n.get('workflow_name'),'message_prefix':str(n.get('message') or '')[:80], 'regex_w6':bool(re.search(r'w0?6\\b',wid)), 'phrase': 'detector heartbeat' in wid, 'incident_id':n.get('incident_id')})
    print(json.dumps(rows, default=str, ensure_ascii=False))
if __name__=='__main__': main()
