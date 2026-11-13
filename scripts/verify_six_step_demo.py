import json
from service.incident_blackbox import build_incident_timeline
from pages.incident import case_file_state

out = []
for i in range(1, 11):
    iid = f"DEMO-6STEP-W{i}"
    tl = build_incident_timeline(iid)
    st = case_file_state(tl)
    out.append({"id": iid, "states": [x["state"] for x in st["chain"]], "has": st["has"], "verdict": st["verdict"][0]})
print(json.dumps(out, default=str, ensure_ascii=False))
