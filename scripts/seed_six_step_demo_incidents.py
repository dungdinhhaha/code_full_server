"""Create a coherent six-step synthetic evidence pack for the ten SMIOT cases.

This is a demo data operation only. It does not call Datadog or claim a new
workflow run; it links each web case to the reviewed monitor/workflow/run IDs
already recorded in the project evidence.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from service.mongodb_store import collection


CASES = [
    ("W1", "plc_safety_trip", "greenhouse_a", 1, "342734303", "b9e72b04-1580-45f8-ae1e-628124a19065", "565ab740-e2a7-4ad2-abc5-e69dc677c509", "SAFE_STOP vì áp suất đường ống bằng 0; PLC ảo ACK và giữ bơm OFF."),
    ("W2", "soil_humidity_flatline", "greenhouse_a", 2, "342585819", "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724", "c16f7820-01ce-484d-a47c-a3497e14cd12", "Độ ẩm Node 2 đứng ở 2,4%; giữ HOLD đến khi có mẫu Mongo mới và dao động."),
    ("W3", "service_down", "greenhouse_c", 1, "342585838", "373ed0c0-4509-4fcd-a067-f54f0becc00e", "60b7c632-b8d7-42e7-98ea-701d9bc53aa7", "smiot.service mất health check; chỉ khởi động lại service sau khi MongoDB/MQTT còn khỏe."),
    ("W4", "false_offline", "greenhouse_d", 1, "342585836", "ffd62026-6b63-40e4-9b46-6ac18d2d584f", "ff13ebe1-7f5a-41c3-9471-5a90bb643ddd", "UI báo OFFLINE nhưng MongoDB vẫn nhận mẫu mới; từ chối restart."),
    ("W5", "dependency_degraded", "greenhouse_e", 1, "342585827", "d3f0705e-2cbd-430a-9a3a-b1fd02a42cc9", "ba3b0184-d235-4d40-80fe-d04157b1bc35", "Phân biệt MongoDB/MQTT suy giảm bằng health metric và probe trước–sau."),
    ("W6", "detector_heartbeat_missing", "greenhouse_b", 1, "343029221", "d8e1b3db-1a54-4b4f-9be3-bf7e270a86f3", "fed8800b-8a87-4a85-8d40-4f21418624f7", "Detector mất evaluation heartbeat ở một farm; phục hồi đúng farm, không lan sang farm khác."),
    ("W7", "soil_humidity_spike", "greenhouse_f", 2, "343594187", "bb86206c-6df8-4b1d-8016-175a2fc62e49", "2e137be3-3e6f-4c6e-8592-4bce06f4b1d5", "Độ ẩm tăng bất thường; chỉ advisory/HOLD và yêu cầu người vận hành duyệt."),
    ("W8", "soil_humidity_out_of_range", "greenhouse_g", 1, "343594185", "593a670c-d59c-4104-8658-df260245a21e", "297e3e4b-6afb-4db6-a1ed-99cd54315b53", "VPD/EC lệch ngưỡng; giữ quyết định an toàn, không tự điều khiển môi trường."),
    ("W9", "actuator_command_unacknowledged", "greenhouse_j", 1, "342734743", "47e95b24-db40-4cd5-b667-5b90e170b667", "b00175ef-7ac6-44da-9c7e-9f240c316544", "Lệnh không ACK đúng hạn; giữ đầu ra OFF, chỉ nhận ACK muộn khớp command và farm."),
    ("W10", "ai_provider_failure", "greenhouse_h", 1, "342585824", "50b3dc85-dd20-4220-bda1-ec78d2a3d00f", "98e002a9-d634-41a5-b28e-e3322585ee42", "AI provider lỗi; chuyển HOLD/fallback xác định, không dùng quyết định AI chưa xác minh."),
]


def main() -> None:
    incidents = collection("operational_incidents")
    evidence = collection("incident_telemetry_evidence")
    decisions = collection("operational_decisions")
    ledger = collection("action_ledger")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    result = []
    for idx, (code, kind, farm, node, monitor, workflow, run, reason) in enumerate(CASES):
        opened = now - timedelta(minutes=(idx + 1) * 3)
        detected = opened + timedelta(seconds=12)
        safe = detected + timedelta(seconds=18)
        recovered = safe + timedelta(seconds=42)
        incident_id = f"DEMO-6STEP-{code}"
        hold_id = f"{incident_id}:HOLD"
        clear_id = f"{incident_id}:CLEAR"
        base = {
            "_id": incident_id, "incident_id": incident_id, "kind": kind,
            "status": "recovered", "synthetic": True, "demo_pack": "six_step_20261112",
            "farm_key": farm, "node_id": node, "opened_by": "six_step_demo_seed",
            "opened_at": opened, "detected_at": detected, "safe_at": safe,
            "recovered_at": recovered, "monitor_id": monitor, "workflow_id": workflow,
            "last_workflow_execution_id": run,
            "last_action": "CLEAR", "last_action_acknowledged_at": recovered,
            "details": {"case_code": code, "root_cause": reason, "source": "reviewed_synthetic_drill"},
            "timeline": [
                {"at": opened, "event": "opened", "by": "datadog_monitor"},
                {"at": detected, "event": "detected", "by": "datadog_monitor"},
                {"at": safe, "event": "safe_action", "by": "workflow_guard"},
                {"at": recovered, "event": "recovered", "by": "app_verifier"},
            ],
            "evidence": {
                "monitor_ids": [monitor], "workflow_refs": [workflow],
                "workflow_execution_ids": [run],
                "workflow_observations": [{
                    "workflow_id": workflow, "execution_id": run,
                    "status": "success", "verification_status": "verified",
                    "source": "reviewed_synthetic_drill", "incident_id": incident_id,
                    "note": reason,
                }],
            },
            "recovery_verification": {
                "verified": True, "incident_id": incident_id, "monitor_state": "OK",
                "verification_status": "verified", "verified_at": recovered,
                "sample_count": 13, "sample_freshness_seconds": 1,
                "soil_humidity_range_pct": [38.7, 41.0],
                "virtual_pump_outputs_off": True, "http_status": 200,
                "newest_sample_age_s": 1,
                "computed_now": "ONLINE" if code == "W4" else None,
                "display_now": "OFFLINE" if code == "W4" else None,
                "reason": "Đã kiểm tra trạng thái an toàn, dữ liệu MongoDB mới và kết quả đọc lại.",
            },
            "updated_at": recovered,
        }
        incidents.replace_one({"_id": incident_id}, base, upsert=True)
        evidence.delete_many({"incident_id": incident_id})
        evidence.insert_many([
            {"_id": f"{incident_id}:sample:{i}", "incident_id": incident_id,
             "received_at": detected + timedelta(seconds=i * 4), "kind": "telemetry_sample",
             "value": 2.4 if code == "W2" and i < 4 else 38.7 + i * 0.2,
             "summary": f"Mẫu telemetry {i + 1} của {farm}/{node}", "synthetic": True}
            for i in range(6)
        ])
        decisions.delete_many({"incident_id": incident_id})
        decisions.insert_one({"_id": f"{incident_id}:decision", "incident_id": incident_id,
                              "created_at": safe, "decision_type": "guarded_recovery",
                              "action": "HOLD" if code != "W4" else "REFUSE_RESTART",
                              "summary": reason, "status": "acknowledged", "synthetic": True})
        ledger.delete_many({"incident_id": incident_id})
        for command_id, action, t in ((hold_id, "SAFE_STOP" if code == "W1" else "HOLD", safe),
                                      (clear_id, "CLEAR", recovered)):
            for state, delta in (("requested", 0), ("published", 1), ("acknowledged", 2), ("verified", 3)):
                ledger.insert_one({"_id": f"{command_id}:{state}", "command_id": command_id,
                                   "incident_id": incident_id, "action": action, "state": state,
                                   "created_at": t + timedelta(seconds=delta),
                                   "acknowledged_at": t + timedelta(seconds=2) if state in {"acknowledged", "verified"} else None,
                                   "verified_at": t + timedelta(seconds=3) if state == "verified" else None,
                                   "synthetic": True})
        result.append({"code": code, "incident_id": incident_id, "monitor_id": monitor,
                       "workflow_id": workflow, "run_id": run, "status": "recovered"})
    print(json.dumps({"created_or_updated": result, "count": len(result)}, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
