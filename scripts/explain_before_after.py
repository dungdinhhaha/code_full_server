"""Do explain truoc/sau khi tao index cho cac truy van hop den (executionStats).

Chay tren ban sao hoac khung gio it tai. --apply tao index tren DB that.
Mac dinh (khong --apply) la dry-run: chi doc (find_one + explain), KHONG tao va KHONG xoa index.
Ket qua mang nhan synthetic neu incident co synthetic=true.

Vi du:
  py -3.12 -X utf8 scripts/explain_before_after.py --incident-id INC-SMIOT-...
  py -3.12 -X utf8 scripts/explain_before_after.py --incident-id INC-SMIOT-... --apply
  py -3.12 -X utf8 scripts/explain_before_after.py --incident-id INC-SMIOT-... --apply --drop-first
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.incident_blackbox import (  # noqa: E402
    INCIDENT_INDEX_SPECS,
    compute_window,
    ensure_incident_indexes,
    hot_queries,
)
from service.mongodb_store import database  # noqa: E402

KEEP_STAGES = ("COLLSCAN", "IXSCAN", "FETCH")
logger = logging.getLogger("explain_before_after")


def _walk_stages(plan: Any, out: list[str]) -> None:
    """Duyet de quy winningPlan, lay ten COLLSCAN/IXSCAN/FETCH theo thu tu."""
    if isinstance(plan, list):
        for item in plan:
            _walk_stages(item, out)
        return
    if not isinstance(plan, dict):
        return
    stage = plan.get("stage")
    if stage in KEEP_STAGES:
        out.append(f"{stage}({plan['indexName']})" if plan.get("indexName") else stage)
    _walk_stages(plan.get("inputStage"), out)
    _walk_stages(plan.get("inputStages"), out)


def explain(db, q: dict[str, Any]) -> dict[str, Any]:
    """Explain mot truy van find (read-only). Loi duoc ghi vao ket qua, khong nem ra ngoai."""
    base = {"label": q["label"], "collection": q["collection"]}
    try:
        res = db.command("explain", {"find": q["collection"], "filter": q["filter"],
                                     "sort": dict(q["sort"])}, verbosity="executionStats")
    except Exception as exc:
        return {**base, "error": str(exc)[:300]}
    stats = res.get("executionStats", {}) or {}
    stages: list[str] = []
    _walk_stages(res.get("queryPlanner", {}).get("winningPlan"), stages)
    return {**base, "stages": stages,
            "totalDocsExamined": stats.get("totalDocsExamined"),
            "totalKeysExamined": stats.get("totalKeysExamined"),
            "nReturned": stats.get("nReturned"),
            "executionTimeMillis": stats.get("executionTimeMillis")}


def measure(db, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [explain(db, q) for q in queries]


def print_table(rows: list[dict[str, Any]], title: str) -> None:
    print(f"\n== {title} ==")
    for r in rows:
        if "error" in r:
            print(f"- {r['label']} [{r['collection']}]: LOI {r['error']}")
            continue
        plan = " > ".join(r["stages"]) or "?"
        print(f"- {r['label']} [{r['collection']}]: {plan} | docs={r['totalDocsExamined']} "
              f"keys={r['totalKeysExamined']} n={r['nReturned']} ms={r['executionTimeMillis']}")


def drop_named_indexes(db) -> list[dict[str, Any]]:
    """Chi xoa index co 'name' trong INCIDENT_INDEX_SPECS (khong xoa gi khac)."""
    report: list[dict[str, Any]] = []
    for coll_name, _keys, options in INCIDENT_INDEX_SPECS:
        name = options.get("name")
        if not name:
            continue
        try:
            db[coll_name].drop_index(name)
            report.append({"collection": coll_name, "index": name, "status": "dropped"})
        except Exception as exc:
            report.append({"collection": coll_name, "index": name, "status": "skipped", "error": str(exc)[:300]})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--incident-id", required=True, help="_id cua incident trong operational_incidents")
    parser.add_argument("--apply", action="store_true",
                        help="tao index tren DB that (mac dinh: dry-run, chi doc)")
    parser.add_argument("--drop-first", action="store_true",
                        help="chi voi --apply: xoa cac index co name trong INCIDENT_INDEX_SPECS truoc khi do 'truoc'")
    parser.add_argument("--out", default=None,
                        help="file JSON ket qua (mac dinh outputs/explain_<incident>_<UTC>.json), chi khi --apply")
    args = parser.parse_args()
    if args.drop_first and not args.apply:
        parser.error("--drop-first chi hop le khi co --apply")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    db = database()
    incident = db["operational_incidents"].find_one({"_id": args.incident_id})
    if not incident:
        print(json.dumps({"error": "khong tim thay incident", "incident_id": args.incident_id},
                         ensure_ascii=False))
        return 1

    window_start, window_end = compute_window(incident)
    queries = hot_queries(incident, window_start, window_end)
    synthetic = bool(incident.get("synthetic"))
    note = ("SYNTHETIC: incident diem tap, ket qua chi de chung minh ky thuat index"
            if synthetic else "Incident khong danh dau synthetic: day la du lieu that")
    print(f"Incident: {args.incident_id} | {note}")

    if not args.apply:
        rows = measure(db, queries)
        print_table(rows, "Hien tai (dry-run, chi doc)")
        print("\nSe tao index:")
        for coll_name, keys, options in INCIDENT_INDEX_SPECS:
            print(f"  - {coll_name} {keys} name={options.get('name', '(mac dinh)')}")
        print("\nDry-run: khong tao, khong xoa index nao. Them --apply de ap dung.")
        return 0

    dropped = drop_named_indexes(db) if args.drop_first else []
    before = measure(db, queries)
    index_report = ensure_incident_indexes(db, logger)
    after = measure(db, queries)

    now = datetime.now(timezone.utc)
    if args.out:
        out_path = Path(args.out)
    else:
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", args.incident_id)
        out_path = ROOT / "outputs" / f"explain_{safe_id}_{now:%Y%m%dT%H%M%SZ}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"incident_id": args.incident_id, "generated_at_utc": now.isoformat(),
               "before": before, "after": after, "index_report": index_report,
               "dropped": dropped, "synthetic_note": note}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    if dropped:
        print("\nXoa index (--drop-first):", json.dumps(dropped, ensure_ascii=False, default=str))
    print_table(before, "Truoc khi tao index")
    print_table(after, "Sau khi tao index")
    print(f"\nDa ghi ket qua: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
