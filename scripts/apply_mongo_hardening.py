"""Ap dung thu cong (idempotent, additive) dot toi uu MongoDB cua SMIOT.

- Index bo sung + unique partial cho su co dang hoat dong (false_offline/service_down) + TTL ky thuat.
- $jsonSchema validator CHI o che do canh bao (moderate/warn) cho action_ledger, operational_incidents,
  notifications. Khong dung validationAction "error". Khong dat validator cho telemetry/MQTT.

Chay tren EC2:  cd /opt/smiot && PYTHONPATH=/opt/smiot .venv/bin/python scripts/apply_mongo_hardening.py
Khong xoa index/du lieu nao. Neu co ban sao trung cua su co active thi unique index se bao 'skipped'.
"""
import json

try:
    from dotenv import load_dotenv
    load_dotenv("/etc/smiot/app.env")
except Exception:
    pass

from service.incident_blackbox import apply_incident_validators, ensure_hardening_indexes
from service.mongodb_store import database

VALIDATED = ("action_ledger", "operational_incidents", "notifications")

if __name__ == "__main__":
    db = database()
    report = {
        "indexes": ensure_hardening_indexes(db),
        "validators": apply_incident_validators(db, only=VALIDATED),
    }
    print(json.dumps(report, default=str, ensure_ascii=True))
