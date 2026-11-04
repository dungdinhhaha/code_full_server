"""Copy SMIOT's four SQLite telemetry tables into one MongoDB time-series collection.

The SQLite database is opened read-only and is never modified. Set MONGODB_URI in
the environment or the project's .env file before running without --dry-run. The
migration is resumable: each document keeps a source database id, table name, and
SQLite row id so a rerun skips rows already copied.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = PROJECT_ROOT / "farm_data.db"
TABLES = ("telemetry_sensor", "telemetry_node", "telemetry_water", "telemetry_flow")
TARGET_COLLECTION = "telemetry"
TIME_FIELD = "timestamp"
META_FIELD = "meta"
DEFAULT_DATABASE = "smiot"
DEFAULT_BATCH_SIZE = 1000

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def sqlite_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def source_database_id(path: Path) -> str:
    # Stable for repeated/incremental runs against this SQLite file as rows append.
    normalized_path = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()


def as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError(f"Unsupported SQLite timestamp value: {value!r}")
    # The application writes SQLite CURRENT_TIMESTAMP values, which are UTC.
    # Treat timezone-naive legacy timestamps as UTC and preserve their clock time.
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def table_bounds(connection: sqlite3.Connection, table: str) -> tuple[str | None, str | None]:
    row = connection.execute(
        f'SELECT MIN(timestamp), MAX(timestamp) FROM "{table}"'
    ).fetchone()
    return row[0], row[1]


def classify_measurement(table: str, row: sqlite3.Row) -> tuple[str, int | None]:
    if table == "telemetry_sensor":
        return "snapshot", None
    if table == "telemetry_node":
        return "node", int(row["node_id"])
    if table == "telemetry_water":
        return "water", None
    if table == "telemetry_flow":
        return "flow", None
    raise ValueError(f"Unexpected telemetry table: {table}")


def to_document(
    table: str,
    row: sqlite3.Row,
    database_id: str,
) -> dict[str, Any]:
    measurement_type, node_id = classify_measurement(table, row)
    meta: dict[str, Any] = {
        "farm_key": row["farm_key"],
        "source_table": table,
        "measurement_type": measurement_type,
    }
    if node_id is not None:
        meta["node_id"] = node_id

    excluded = {"id", "farm_key", "timestamp", "node_id"}
    readings = {key: row[key] for key in row.keys() if key not in excluded}
    return {
        TIME_FIELD: as_utc(row["timestamp"]),
        META_FIELD: meta,
        "source": {
            "database_id": database_id,
            "table": table,
            "row_id": int(row["id"]),
        },
        "readings": readings,
    }


def ensure_timeseries_collection(database: Any) -> Any:
    existing = database.list_collection_names()
    if TARGET_COLLECTION not in existing:
        database.create_collection(
            TARGET_COLLECTION,
            timeseries={"timeField": TIME_FIELD, "metaField": META_FIELD, "granularity": "seconds"},
        )
    else:
        info = next(
            database.list_collections(filter={"name": TARGET_COLLECTION}),
            None,
        )
        options = (info or {}).get("options", {})
        timeseries = options.get("timeseries")
        if not timeseries:
            raise RuntimeError(
                "MongoDB collection 'telemetry' already exists but is not a Time Series collection. "
                "No data was changed. Choose another database or rename the existing collection."
            )
        if timeseries.get("timeField") != TIME_FIELD or timeseries.get("metaField") != META_FIELD:
            raise RuntimeError(
                "Existing 'telemetry' collection uses different time/meta fields. "
                "No data was changed."
            )
    return database[TARGET_COLLECTION]


def migrate_table(
    connection: sqlite3.Connection,
    collection: Any,
    table: str,
    fingerprint: str,
    batch_size: int,
) -> tuple[int, int]:
    existing_ids = {
        document["source"]["row_id"]
        for document in collection.find(
            {"source.database_id": fingerprint, "source.table": table},
            {"source.row_id": 1},
        )
    }
    expected = table_count(connection, table)
    copied_before = len(existing_ids)
    cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY id')
    batch: list[dict[str, Any]] = []

    for row in cursor:
        row_id = int(row["id"])
        if row_id in existing_ids:
            continue
        batch.append(to_document(table, row, fingerprint))
        if len(batch) >= batch_size:
            collection.insert_many(batch, ordered=False)
            existing_ids.update(doc["source"]["row_id"] for doc in batch)
            batch.clear()

    if batch:
        collection.insert_many(batch, ordered=False)
        existing_ids.update(doc["source"]["row_id"] for doc in batch)

    copied_total = len(existing_ids)
    if copied_total != expected:
        raise RuntimeError(
            f"Count mismatch for {table}: SQLite={expected}, MongoDB source rows={copied_total}"
        )
    return copied_total - copied_before, copied_total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate SMIOT telemetry tables to MongoDB Time Series collection 'telemetry'."
    )
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE, help="SQLite database path")
    parser.add_argument("--database", default=os.getenv("MONGODB_DATABASE", DEFAULT_DATABASE))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="Read and report source counts only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_path = args.sqlite.resolve()
    if not sqlite_path.is_file():
        print(f"SQLite file not found: {sqlite_path}", file=sys.stderr)
        return 2
    if args.batch_size < 1:
        print("--batch-size must be greater than zero", file=sys.stderr)
        return 2

    fingerprint = source_database_id(sqlite_path)
    connection = sqlite_readonly(sqlite_path)
    try:
        counts: dict[str, int] = {}
        total = 0
        print(f"SQLite source: {sqlite_path}")
        print(f"Source database id: {fingerprint}")
        for table in TABLES:
            count = table_count(connection, table)
            first, last = table_bounds(connection, table)
            counts[table] = count
            total += count
            print(f"{table}: {count:,} rows; {first} .. {last}")
        print(f"Total telemetry documents to migrate: {total:,}")

        if args.dry_run:
            print("Dry run only; no MongoDB connection or writes were made.")
            return 0

        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            print(
                "MONGODB_URI is not set. Set it to the target MongoDB connection string, "
                "then rerun this migration.",
                file=sys.stderr,
            )
            return 2

        try:
            from pymongo import MongoClient
        except ImportError:
            print(
                "PyMongo is not installed. Install project dependencies before migrating.",
                file=sys.stderr,
            )
            return 2

        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
        try:
            client.admin.command("ping")
            database = client[args.database]
            collection = ensure_timeseries_collection(database)

            migrated = 0
            for table in TABLES:
                added, copied_total = migrate_table(
                    connection, collection, table, fingerprint, args.batch_size
                )
                migrated += added
                print(f"{table}: added {added:,}; present in MongoDB for this source {copied_total:,}")

            final_count = collection.count_documents({"source.database_id": fingerprint})
            expected_total = sum(counts.values())
            if final_count != expected_total:
                raise RuntimeError(
                    f"Final count mismatch: SQLite={expected_total}, MongoDB={final_count}"
                )
            print(
                f"Migration complete: added {migrated:,}; verified {final_count:,} documents "
                f"in {args.database}.{TARGET_COLLECTION}. SQLite source remains unchanged."
            )
        finally:
            client.close()
    except Exception as exc:
        print(f"Migration stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
