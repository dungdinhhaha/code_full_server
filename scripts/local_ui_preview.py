"""Local-only UI preview with an in-memory MongoDB substitute.

Run from the repository root. This never writes to the cloud database.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update({
    "APP_ENV": "development",
    "SMIOT_DEMO_MODE": "false",
    "DATADOG_METRICS_ENABLED": "false",
    "DATADOG_APM_ENABLED": "false",
    "AI_ENABLED": "false",
    "MONGODB_URI": "mongodb://preview.invalid",
    "SMIOT_BOOTSTRAP_ADMIN_PASSWORD": "preview-only",
})

import mongomock
import pymongo

_original_client = pymongo.MongoClient
_memory_client = mongomock.MongoClient()
pymongo.MongoClient = lambda *args, **kwargs: _memory_client

import service.mongodb_store as store
store.MongoClient = pymongo.MongoClient

# UI-only preview: leave all publishers, callbacks and scheduled actions off.
import service.mqtt as mqtt_service
import service.scheduler as scheduler_service
import service.demo_mode as demo_service
import service.telemetry_health as health_service
import service.detector_heartbeat as detector_service
mqtt_service.start_mqtt = lambda: None
scheduler_service.start_background_scheduler = lambda: None
demo_service.start_demo_mode = lambda: None
health_service.start_telemetry_health_watchdog = lambda: None
detector_service.start_detector_heartbeat = lambda: None

import main
from nicegui import ui
ui.run(
    title="SMIOT UI Preview",
    host="127.0.0.1",
    port=8080,
    reload=False,
    storage_secret="smiot-local-ui-preview-only",
    reconnect_timeout=90,
)
