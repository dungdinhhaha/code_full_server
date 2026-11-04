from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient, IndexModel


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a SMIOT MongoDB JSONL archive, preserving BSON values and time-series options.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--uri", default=os.getenv("MONGODB_URI"))
    parser.add_argument("--database", default="smiot")
    args = parser.parse_args()
    if not args.uri:
        parser.error("set MONGODB_URI or pass --uri")
    root = args.archive.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"), object_hook=json_util.object_hook)
    client = MongoClient(args.uri, appname="smiot-cloud-migration-import", serverSelectionTimeoutMS=15000)
    client.admin.command("ping")
    db = client[args.database]
    if db.list_collection_names():
        raise RuntimeError(f"Target database {args.database!r} is not empty; refusing to mix data")

    for item in manifest["collections"]:
        name = item["name"]
        options = item.get("options") or {}
        options.pop("uuid", None)
        options.pop("clusteredIndex", None)
        if name not in db.list_collection_names():
            db.create_collection(name, **options)
        collection = db[name]
        batch = []
        count = 0
        with gzip.open(root / f"{name}.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                batch.append(json_util.loads(line))
                if len(batch) >= 1000:
                    collection.insert_many(batch, ordered=False)
                    count += len(batch)
                    batch.clear()
        if batch:
            collection.insert_many(batch, ordered=False)
            count += len(batch)

        index_models = []
        is_timeseries = "timeseries" in options
        for spec in item.get("indexes", []):
            spec = dict(spec)
            name_value = spec.pop("name", None)
            key = list(spec.pop("key").items())
            spec.pop("v", None)
            spec.pop("ns", None)
            if name_value == "_id_" or (is_timeseries and name_value == "_id_"):
                continue
            if name_value:
                spec["name"] = name_value
            index_models.append(IndexModel(key, **spec))
        if index_models:
            collection.create_indexes(index_models)
        print(f"RESTORED {name}: {count} documents")

    stats = db.command("dbStats")
    print(f"TARGET_OK database={args.database} collections={len(manifest['collections'])} dataSize={stats.get('dataSize')} storageSize={stats.get('storageSize')}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
