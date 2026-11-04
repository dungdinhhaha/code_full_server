from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the configured SMIOT Mongo database to a compressed BSON-preserving archive.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    uri = os.environ["MONGODB_URI"]
    database_name = os.getenv("MONGODB_DATABASE", "smiot")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    client = MongoClient(uri, appname="smiot-cloud-migration-export", serverSelectionTimeoutMS=15000)
    db = client[database_name]
    client.admin.command("ping")
    metadata: list[dict] = []
    for info in db.list_collections():
        name = info["name"]
        if name.startswith("system."):
            continue
        collection = db[name]
        indexes = list(collection.list_indexes())
        info.pop("info", None)
        metadata.append({"name": name, "options": info.get("options", {}), "indexes": indexes})
        path = output / f"{name}.jsonl.gz"
        count = 0
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as stream:
            # Some Atlas tiers prohibit noTimeout cursors, so use the standard
            # bounded cursor and finish each collection before its timeout.
            for doc in collection.find({}).batch_size(2000):
                stream.write(json_util.dumps(doc, json_options=json_util.RELAXED_JSON_OPTIONS))
                stream.write("\n")
                count += 1
        print(f"EXPORTED {name}: {count} documents, {path.stat().st_size} compressed bytes")

    with (output / "manifest.json").open("w", encoding="utf-8") as stream:
        json.dump({"database": database_name, "collections": metadata}, stream, default=json_util.default, ensure_ascii=False, indent=2)
    stats = db.command("dbStats")
    print(f"SOURCE_OK database={database_name} collections={len(metadata)} dataSize={stats.get('dataSize')} storageSize={stats.get('storageSize')}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
