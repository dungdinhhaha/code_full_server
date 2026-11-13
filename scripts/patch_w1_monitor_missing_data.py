import json
from pathlib import Path
from urllib.request import Request, urlopen

monitor_id = "342734303"
values = {}
for line in Path(r"D:\attt\APP_KEY.txt").read_text(encoding="utf-8").splitlines():
    if ":" in line:
        key, value = line.split(":", 1)
        values[key.strip().lower()] = value.strip()
headers = {
    "DD-API-KEY": values.get("api_keys") or values.get("key_id"),
    "DD-APPLICATION-KEY": values.get("app_key"),
    "Content-Type": "application/json",
}
base = "https://api.datadoghq.com/api/v1/monitor/" + monitor_id
with urlopen(Request(base + "?group_states=all", headers=headers), timeout=30) as response:
    monitor = json.loads(response.read().decode())
options = monitor.get("options") or {}
options["on_missing_data"] = "resolve"
payload = {
    "name": monitor.get("name"),
    "type": monitor.get("type"),
    "query": monitor.get("query"),
    "message": monitor.get("message"),
    "tags": monitor.get("tags") or [],
    "options": options,
    "priority": monitor.get("priority"),
}
request = Request(base, data=json.dumps(payload).encode(), headers=headers, method="PUT")
with urlopen(request, timeout=30) as response:
    updated = json.loads(response.read().decode())
print(json.dumps({"id": updated.get("id"), "name": updated.get("name"), "on_missing_data": (updated.get("options") or {}).get("on_missing_data")}, ensure_ascii=False))
