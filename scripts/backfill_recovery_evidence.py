"""Persist recovery summaries from saved, reviewed drill evidence.

These are explicitly scoped: a recovered card does not imply every Datadog
workflow step succeeded. The scope is stored beside the recovery record.
"""
import json
from datetime import datetime, timezone
from service.mongodb_store import collection

CASES=[
 {"id":"EVID-W1-565ab740","kind":"plc_safety_trip","monitor_id":"342734303","workflow_id":"b9e72b04-1580-45f8-ae1e-628124a19065","run_id":"565ab740-e2a7-4ad2-abc5-e69dc677c509","at":"2026-11-11T18:06:00Z","scope":"safe_stop_ack_mongodb_persisted","note":"Virtual PLC SAFE_STOP, matching ACK, outputs OFF, valve closed, MongoDB ACK persisted."},
 {"id":"EVID-W4-ff13ebe1","kind":"false_offline","monitor_id":"342585836","workflow_id":"ffd62026-6b63-40e4-9b46-6ac18d2d584f","run_id":"ff13ebe1-7f5a-41c3-9471-5a90bb643ddd","at":"2026-11-12T01:00:00Z","scope":"monitor_ok_cloudtrail_no_ssm","note":"Monitor OK and scoped CloudTrail audit found no Datadog recovery-role SSM invocation."},
 {"id":"EVID-W5-ba3b0184","kind":"dependency_degraded","monitor_id":"342585827","workflow_id":"d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9","run_id":"ba3b0184-d235-4d40-80fe-d04157b1bc35","at":"2026-11-11T17:45:47Z","scope":"mongo_mqtt_monitors_ok_workflow_success","note":"MongoDB/MQTT dependency monitors returned OK after recovery window; workflow Success."},
 {"id":"EVID-W7-2e137be3","kind":"soil_humidity_spike","monitor_id":"343594187","workflow_id":"bb86206c-6df8-4b1d-8016-175a2fc62e49","run_id":"2e137be3-3e6f-4c6e-8592-4bce06f4b1d5","at":"2026-11-11T13:54:52Z","scope":"advisory_monitor_ok_workflow_success","note":"Advisory-only W7 drill ended with monitor OK and workflow SUCCEEDED; no actuator called."},
 {"id":"EVID-W8-297e3e4b","kind":"soil_humidity_out_of_range","monitor_id":"343594185","workflow_id":"593a670c-d59c-4104-8658-df260245a21e","run_id":"297e3e4b-6afb-4db6-a1ed-99cd54315b53","at":"2026-11-11T14:03:52Z","scope":"advisory_monitor_ok_workflow_success","note":"Advisory-only W8 drill ended with monitor OK and workflow SUCCEEDED; no actuator called."},
 {"id":"EVID-W9-b00175ef","kind":"actuator_command_unacknowledged","monitor_id":"342734743","workflow_id":"47e95b24-db40-4cd5-b667-5b90e170b667","run_id":"b00175ef-7ac6-44da-9c7e-9f240c316544","at":"2026-11-12T18:48:43Z","scope":"app_verified_monitor_ok_workflow_rate_limited","note":"Late ACK matched command and farm; ledger acknowledged and monitor recovered. Workflow trigger was rate-limited."},
 {"id":"EVID-W10-98e002a9","kind":"ai_provider_failure","monitor_id":"342585824","workflow_id":"50b3dc85-dd20-4220-bda1-ec78d2a3d00f","run_id":"98e002a9-d634-41a5-b28e-e3322585ee42","at":"2026-11-11T14:31:00Z","scope":"monitor_alert_recovered_prior_success_run","note":"Provider failure monitor alert/recovery observed; prior successful workflow run proves safe HOLD notification path."},
 {"id":"EVID-W6-fed8800b","kind":"detector_heartbeat_missing","monitor_id":"343029221","workflow_id":"d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3","run_id":"fed8800b-8a87-4a85-8d40-4f21418624f7","at":"2026-11-11T19:25:24Z","scope":"all_farms_heartbeat_monitor_ok","note":"After greenhouse_b normal ACK, all ten farm groups emitted heartbeat=1 and monitor returned OK."},
]
def main():
 c=collection('operational_incidents'); out=[]
 for x in CASES:
  at=datetime.fromisoformat(x['at'].replace('Z','+00:00'))
  doc={'_id':x['id'],'kind':x['kind'],'status':'recovered','synthetic':True,'workflow_only':True,'opened_at':at,'detected_at':at,'recovered_at':at,'farm_key':'greenhouse_j','node_id':'node1','monitor_id':x['monitor_id'],'workflow_id':x['workflow_id'],'last_workflow_execution_id':x['run_id'],'scenario':'Recovery evidence imported from reviewed drill artifact','recovery_scope':x['scope'],'evidence':{'workflow_execution_ids':[x['run_id']],'workflow_observations':[{'source':'saved_drill_evidence','note':x['note'],'recovery_scope':x['scope']}]},'updated_at':at}
  r=c.update_one({'_id':x['id']},{'$setOnInsert':doc},upsert=True); out.append({'id':x['id'],'created':r.upserted_id is not None,'scope':x['scope']})
 print(json.dumps({'results':out,'created_count':sum(1 for x in out if x['created'])},ensure_ascii=False))
if __name__=='__main__': main()
