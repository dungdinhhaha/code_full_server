import json
from pathlib import Path
from urllib.request import Request, urlopen

values = {}
for line in Path(r"D:\attt\APP_KEY.txt").read_text(encoding="utf-8").splitlines():
    if ":" in line:
        key, value = line.split(":", 1)
        values[key.strip().lower()] = value.strip()
headers = {
    "DD-API-KEY": values.get("api_keys") or values.get("key_id"),
    "DD-APPLICATION-KEY": values.get("app_key"),
}
for monitor_id in ("342585836", "342734303"):
    with urlopen(Request(f"https://api.datadoghq.com/api/v1/monitor/{monitor_id}?group_states=all", headers=headers), timeout=30) as response:
        monitor = json.loads(response.read().decode())
    groups = (monitor.get("state") or {}).get("groups") or {}
    print(json.dumps({
        "id": monitor_id,
        "name": monitor.get("name"),
        "overall_state": monitor.get("overall_state"),
        "groups": {name: state.get("status") for name, state in groups.items()},
    }, ensure_ascii=False))
