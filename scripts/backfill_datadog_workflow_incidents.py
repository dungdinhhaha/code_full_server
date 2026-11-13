"""Backfill workflow-only observation headers; never mark recovery."""
import hashlib, json
from datetime import datetime, timezone
from service.mongodb_store import collection
MONITOR_KIND={"342585836":"false_offline","342585819":"soil_humidity_flatline","340356283":"service_down","343594187":"soil_humidity_spike","343594185":"soil_humidity_out_of_range","342585827":"dependency_degraded","343029221":"detector_heartbeat_missing","342734303":"plc_safety_trip","342734743":"actuator_command_unacknowledged","342585824":"ai_provider_failure"}
WORKFLOW_KIND={"d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3":"detector_heartbeat_missing","47e95b24-db40-4cd5-b667-5b90e170b667":"actuator_command_unacknowledged","50b3dc85-dd20-4220-bda1-ec78d2a3d00f":"ai_provider_failure","d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9":"dependency_degraded","b9e72b04-1580-45f8-ae1e-628124a19065":"plc_safety_trip","ffd62026-6b63-40e4-9b46-6ac18d2d584f":"false_offline","2f9a3c1d-5292-4bc3-b4b9-cc03d4172724":"soil_humidity_flatline"}
def utc(v): return v if isinstance(v,datetime) and v.tzinfo else (v.replace(tzinfo=timezone.utc) if isinstance(v,datetime) else datetime.now(timezone.utc))
def main():
 ns,inc=collection("notifications"),collection("operational_incidents"); created=[]; skipped=0
 for n in ns.find({"source":"datadog_workflow","incident_id":None}).sort("created_at",1).limit(500):
  monitor=str(n.get("monitor_id") or ""); wf=str(n.get("workflow_id") or ""); kind=MONITOR_KIND.get(monitor) or WORKFLOW_KIND.get(wf)
  if not kind:
   text=" ".join(str(n.get(k) or "") for k in ("workflow_name","message")).lower()
   for token,mapped in (("w6","detector_heartbeat_missing"),("w9","actuator_command_unacknowledged"),("w10","ai_provider_failure"),("w5","dependency_degraded"),("w7","soil_humidity_spike"),("w8","soil_humidity_out_of_range"),("w1","plc_safety_trip"),("w2","soil_humidity_flatline"),("w3","service_down"),("ca 1","false_offline"),("ca 2","soil_humidity_flatline")):
    if token in text: kind=mapped; break
  if not kind: skipped+=1; continue
  event=str(n.get("event_id") or n.get("_id")); iid="DDOBS-"+hashlib.sha256(event.encode()).hexdigest()[:24].upper(); at=utc(n.get("created_at"))
  doc={"_id":iid,"kind":kind,"status":"observed","synthetic":True,"workflow_only":True,"opened_at":at,"detected_at":at,"recovered_at":None,"farm_key":n.get("farm_key"),"node_id":n.get("node_id"),"monitor_id":monitor or None,"workflow_id":wf or None,"last_workflow_execution_id":n.get("workflow_run_id") or event,"scenario":"Datadog workflow evidence imported from app notification","evidence":{"workflow_execution_ids":[n.get("workflow_run_id") or event],"workflow_observations":[{"event_id":event,"status":n.get("workflow_status"),"verification_status":n.get("verification_status"),"source":"datadog_notification"}]},"updated_at":at}
  r=inc.update_one({"_id":iid},{"$setOnInsert":doc},upsert=True)
  if r.upserted_id is not None: created.append({"incident_id":iid,"kind":kind,"workflow_run_id":n.get("workflow_run_id") or event})
 print(json.dumps({"created":created,"created_count":len(created),"skipped":skipped},default=str))
if __name__=="__main__": main()
