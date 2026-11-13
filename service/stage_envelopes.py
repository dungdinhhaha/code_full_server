"""Versioned, effective-dated crop stage target envelopes.

This module stores agronomic bands as sourced data. It deliberately ships with
no numeric defaults: callers must treat a missing approved envelope as unknown
and fail safe instead of embedding thresholds in control code.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from service.mongodb_store import collection

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
STAGE_ENVELOPE_INDEXES = (
    (("crop_key", 1), ("stage_code", 1), ("cultivar", 1), ("version", 1)),
    (("crop_key", 1), ("stage_code", 1), ("approval_status", 1),
     ("calibration_status", 1),
     ("cultivar", 1), ("effective_from", -1), ("version", -1)),
)


def canonical_crop_key(value: str | None) -> str | None:
    """Resolve the current product's display name or an already canonical key."""
    normalized = str(value or "").strip().lower()
    if _KEY_RE.fullmatch(normalized):
        return normalized
    if normalized in {"dưa lưới", "dua luoi", "muskmelon", "cantaloupe"}:
        return "melon"
    return None


def _utc(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def validate_stage_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize an envelope before insert; this does not write DB."""
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be an object")
    crop = str(envelope.get("crop_key", "")).strip().lower()
    stage = str(envelope.get("stage_code", "")).strip().lower()
    if not _KEY_RE.fullmatch(crop) or not _KEY_RE.fullmatch(stage):
        raise ValueError("crop_key and stage_code must be canonical lowercase keys")
    if isinstance(envelope.get("version"), bool):
        raise ValueError("version must be a positive integer")
    try:
        version = int(envelope["version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("version must be a positive integer") from exc
    if version < 1 or version != envelope["version"]:
        raise ValueError("version must be a positive integer")

    effective_from = _utc(envelope.get("effective_from"), "effective_from")
    effective_to_value = envelope.get("effective_to")
    effective_to = _utc(effective_to_value, "effective_to") if effective_to_value else None
    if effective_to is not None and effective_to <= effective_from:
        raise ValueError("effective_to must be later than effective_from")

    bands = envelope.get("bands")
    if not isinstance(bands, dict) or not bands:
        raise ValueError("bands must be a non-empty object with units and sourced limits")
    for name, band in bands.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(band, dict):
            raise ValueError("each band must be a named object")
        if not isinstance(band.get("unit"), str) or not band["unit"].strip():
            raise ValueError(f"band {name} must define a unit")
        for bound in ("min", "max"):
            value = band.get(bound)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"band {name}.{bound} must be a finite number")
        if band["min"] > band["max"]:
            raise ValueError(f"band {name}.min must be <= max")
    source = envelope.get("source")
    if not isinstance(source, dict) or not str(source.get("citation", "")).strip():
        raise ValueError("source.citation is required for every target envelope")
    status = envelope.get("approval_status", "draft")
    if status not in {"draft", "approved", "retired"}:
        raise ValueError("approval_status must be draft, approved, or retired")
    calibration = envelope.get("calibration_status", "unverified")
    if calibration not in {"unverified", "reference_only", "field_calibrated"}:
        raise ValueError("unsupported calibration_status")
    if status == "approved" and calibration != "field_calibrated":
        raise ValueError("operational approval requires field_calibrated status")

    normalized = dict(envelope)
    normalized.update({
        "crop_key": crop,
        "stage_code": stage,
        "version": version,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "bands": {key: dict(value) for key, value in bands.items()},
        "source": dict(source),
        "approval_status": status,
        "calibration_status": calibration,
    })
    if normalized.get("cultivar") is not None:
        cultivar = str(normalized["cultivar"]).strip()
        if not cultivar:
            raise ValueError("cultivar must be a non-empty string or null")
        normalized["cultivar"] = cultivar
    return normalized


def insert_stage_envelope(envelope: dict[str, Any]) -> str:
    """Insert an immutable version. Existing version IDs are never overwritten."""
    normalized = validate_stage_envelope(envelope)
    cultivar_key = normalized.get("cultivar") or "all"
    doc_id = f"{normalized['crop_key']}:{normalized['stage_code']}:{cultivar_key}:v{normalized['version']}"
    normalized["_id"] = doc_id
    normalized["created_at"] = datetime.now(timezone.utc)
    collection("stage_envelopes").insert_one(normalized)
    return doc_id


def ensure_stage_envelope_indexes() -> None:
    """Create lookup indexes on explicit deployment/setup; never called implicitly."""
    coll = collection("stage_envelopes")
    coll.create_index(list(STAGE_ENVELOPE_INDEXES[0]), unique=True,
                      name="uq_stage_envelope_crop_stage_cultivar_version")
    coll.create_index(list(STAGE_ENVELOPE_INDEXES[1]),
                      name="ix_stage_envelope_effective_lookup")


def get_effective_stage_envelope(
    crop: str,
    stage: str,
    effective_at: datetime | None = None,
    cultivar: str | None = None,
    allow_drill: bool = False,
) -> dict[str, Any] | None:
    """Return the most recent approved, effective envelope for crop/stage.

    Return contract: ``{bands, version, source, effective_from,
    calibration_status}``. Prefer an exact cultivar; only use a generic envelope
    when no exact-cultivar version is effective. No fallback thresholds are
    synthesized.

    ``allow_drill=True`` additionally accepts synthetic rehearsal envelopes
    (status "drill", synthetic true, calibration "drill_synthetic"). Callers may
    set it only when the input data itself is synthetic; such envelopes are
    marked ``drill: True`` in the result and are not agronomic approvals.
    """
    crop_key = canonical_crop_key(crop)
    stage_code = str(stage or "").strip().lower()
    if not crop_key or not _KEY_RE.fullmatch(stage_code):
        return None
    at = _utc(effective_at, "effective_at") if effective_at is not None else datetime.now(timezone.utc)
    cultivar = str(cultivar).strip() if cultivar else None
    cultivar_filter = [cultivar, None] if cultivar else [None]
    query = {
        "crop_key": crop_key,
        "stage_code": stage_code,
        "cultivar": {"$in": cultivar_filter},
        "approval_status": "approved",
        "calibration_status": "field_calibrated",
        "effective_from": {"$lte": at},
        "$or": [{"effective_to": None}, {"effective_to": {"$gt": at}}],
    }
    if allow_drill:
        approved_clause = {"approval_status": "approved", "calibration_status": "field_calibrated"}
        drill_clause = {"$or": [{"approval_status": "drill"}, {"status": "drill"}],
                        "synthetic": True, "calibration_status": "drill_synthetic"}
        for key in ("approval_status", "calibration_status"):
            query.pop(key)
        query = {
            "crop_key": crop_key,
            "stage_code": stage_code,
            "cultivar": {"$in": cultivar_filter},
            "effective_from": {"$lte": at},
            "$and": [
                {"$or": [approved_clause, drill_clause]},
                {"$or": [{"effective_to": None}, {"effective_to": {"$gt": at}}]},
            ],
        }
    candidates = list(collection("stage_envelopes").find(query, {"_id": 0}).sort(
        [("effective_from", -1), ("version", -1)]
    ).limit(100))
    if not candidates:
        return None
    exact = [doc for doc in candidates if cultivar and doc.get("cultivar") == cultivar]
    selected = exact[0] if exact else next((doc for doc in candidates if doc.get("cultivar") is None), None)
    if selected is None:
        return None
    result = {
        "bands": selected["bands"],
        "version": int(selected["version"]),
        "source": selected["source"],
        "effective_from": selected["effective_from"],
        "effective_to": selected.get("effective_to"),
        "calibration_status": selected.get("calibration_status", "unverified"),
    }
    if selected.get("calibration_status") == "drill_synthetic":
        result["drill"] = True
    return result
