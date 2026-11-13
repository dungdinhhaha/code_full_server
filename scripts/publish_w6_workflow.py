"""Publish the reviewed W6 spec to the existing Datadog workflow only."""
from __future__ import annotations
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'outputs' / 'workflow_imports' / 'w06_smiot-w06-detector-heartbeat.json'
SPEC_SOURCE = ROOT / 'infra' / 'datadog-workflows' / 'specs' / 'w6.json'
WORKFLOW_ID = 'd8e1b3db-1a54-4b4f-9be3-bf7e270a86f3'
API = 'https://api.datadoghq.com/api/v2/workflows/' + WORKFLOW_ID

def load_keys() -> tuple[str, str]:
    path = Path(r'D:\attt\APP_KEY.txt')
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            values[k.strip().lower()] = v.strip()
    api = values.get('api_keys') or values.get('api_key') or values.get('key_id')
    app = values.get('app_key') or values.get('application_key')
    if not api or not app:
        raise RuntimeError('APP_KEY.txt does not contain the expected key labels')
    return api, app

def request(method: str, payload: dict | None = None) -> dict:
    api, app = load_keys()
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(API, method=method, data=body, headers={
        'DD-API-KEY': api, 'DD-APPLICATION-KEY': app,
        'Accept': 'application/json', 'Content-Type': 'application/json',
    })
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))

def main() -> int:
    local = json.loads(LOCAL.read_text(encoding='utf-8'))
    local['spec'] = json.loads(SPEC_SOURCE.read_text(encoding='utf-8'))
    remote = request('GET')
    data = remote['data']
    attrs = data['attributes']
    attrs['spec'] = local['spec']
    attrs['description'] = local.get('description', attrs.get('description', ''))
    attrs['tags'] = local.get('tags', attrs.get('tags', []))
    attrs['published'] = True
    payload = {'data': {'id': data['id'], 'type': data.get('type', 'workflows'), 'attributes': attrs}}
    updated = request('PATCH', payload)
    check = request('GET')
    live = check['data']['attributes']
    steps = live.get('spec', {}).get('steps', [])
    queries = []
    for step in steps:
        for param in step.get('parameters', []) if isinstance(step, dict) else []:
            value = param.get('value') if isinstance(param, dict) else None
            if isinstance(value, list):
                queries.extend(item.get('query') for item in value if isinstance(item, dict) and item.get('query'))
    print(json.dumps({'id': check['data']['id'], 'published': live.get('published'), 'steps': len(steps), 'queries': queries}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
