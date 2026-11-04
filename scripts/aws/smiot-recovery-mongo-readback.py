#!/opt/smiot/.venv/bin/python
"""Read the newest SMIOT telemetry timestamp without exposing app credentials."""

import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient


if len(sys.argv) != 1:
    raise SystemExit("This helper accepts no arguments.")

if not load_dotenv("/etc/smiot/app.env") or not os.getenv("MONGODB_URI"):
    raise SystemExit("MongoDB verifier configuration is unavailable.")

client = MongoClient(
    os.environ["MONGODB_URI"],
    appname="smiot-datadog-recovery-verifier",
    serverSelectionTimeoutMS=5000,
)
try:
    client.admin.command("ping")
    db = client[os.getenv("MONGODB_DATABASE", "smiot")]
    row = db.telemetry.find_one({}, {"timestamp": 1}, sort=[("timestamp", -1)])
    timestamp = row.get("timestamp") if row else None
    if timestamp is None:
        print(0)
    else:
        print(int(timestamp.timestamp() * 1000))
finally:
    client.close()
