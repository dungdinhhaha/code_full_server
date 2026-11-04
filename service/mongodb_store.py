from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
_client: MongoClient | None = None
_lock = threading.Lock()


def client() -> MongoClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                uri = os.getenv("MONGODB_URI")
                if not uri:
                    raise RuntimeError("MONGODB_URI is required for MongoDB primary mode")
                _client = MongoClient(uri, appname="smiot-smart-farm", serverSelectionTimeoutMS=5000)
    return _client


def database():
    return client()[os.getenv("MONGODB_DATABASE", "smiot")]


def collection(name: str):
    return database()[name]


def next_id(name: str) -> int:
    row = collection("_counters").find_one_and_update(
        {"_id": name}, {"$inc": {"value": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return int(row["value"])


def seed_counter(name: str, maximum: int) -> None:
    collection("_counters").update_one(
        {"_id": name}, {"$max": {"value": int(maximum)}}, upsert=True
    )


def as_dict(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result
