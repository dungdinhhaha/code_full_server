"""Run deterministic, simulator-only positive drills for W9 and W10.

This script never calls a physical actuator, AWS, Gemini, or Datadog.  It feeds
the same synthetic overlays used by the virtual-device scenario catalog through
the domain evaluators and writes an auditable before/after JSON artifact.  The
artifact is suitable for wiring into a Datadog drill later: the fault and the
recovery proof carry one incident/scenario run ID.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Running a script by path sets sys.path to ``scripts/``; add the repository
# root so it imports the same service package as the application.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.scenario_domain_actuator_infra import (
    build_actuator_infra_overlay,
    evaluate_actuator_infra,
)
from service.scenario_recovery import evaluate_scenario_recovery


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_w9(run_id: str) -> dict:
    fault = build_actuator_infra_overlay("A4", {
        "command_id": f"{run_id}:command-1",
        "ack_received": False,
        "ack_timed_out": True,
    })
    finding = evaluate_actuator_infra("A4", fault["signals"])
    # The local virtual safety layer suppresses repeat sends.  This is an
    # assertion in the drill artifact, not a claim about a physical device.
    recovery_evidence = {
        "stable_samples": 1,
        "ack_received": True,
        "target_value": 1,
        "observed_value": 1,
        "command_id": f"{run_id}:command-1",
        "operator_reviewed": True,
    }
    recovery = evaluate_scenario_recovery("A4", recovery_evidence, run={"scenario_run_id": run_id})
    return {
        "workflow": "W9",
        "scenario_code": "A4",
        "scenario_run_id": run_id,
        "synthetic": True,
        "fault_injection": fault,
        "finding": finding,
        "safety_contract": {
            "retry_attempts": 0,
            "command_reissued": False,
            "safe_mode_active": True,
            "physical_actuator_called": False,
        },
        "recovery_evidence": recovery_evidence,
        "recovery": recovery,
        "generated_at_utc": _now(),
    }


def run_w10(run_id: str) -> dict:
    fault = build_actuator_infra_overlay("H6", {
        "provider_status": "error",
        "error_class": "provider_http_503",
        "latency_ms": 5000,
        "valid_output": False,
    })
    finding = evaluate_actuator_infra("H6", fault["signals"])
    recovery_evidence = {
        "stable_samples": 1,
        "provider_status": "ok",
        "valid_output": True,
        "decision_recorded": True,
        "fallback_used": True,
        "operator_reviewed": True,
    }
    recovery = evaluate_scenario_recovery("H6", recovery_evidence, run={"scenario_run_id": run_id})
    return {
        "workflow": "W10",
        "scenario_code": "H6",
        "scenario_run_id": run_id,
        "synthetic": True,
        "fault_injection": fault,
        "finding": finding,
        "safety_contract": {
            "provider_call_is_fake": True,
            "provider_error": "HTTP_503",
            "ai_decision_used_during_fault": False,
            "hold_or_deterministic_fallback": True,
            "gemini_called": False,
        },
        "recovery_evidence": recovery_evidence,
        "recovery": recovery,
        "generated_at_utc": _now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/evidence/w9_w10_simulated_positive_drill.json"))
    args = parser.parse_args()
    run_id = f"SIM-{uuid4()}"
    artifact = {
        "artifact": "smiot_w9_w10_simulated_positive_drill",
        "generated_at_utc": _now(),
        "no_external_calls": True,
        "runs": [run_w9(run_id + "-w9"), run_w10(run_id + "-w10")],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "runs": [r["scenario_run_id"] for r in artifact["runs"]],
                      "recovered": [r["recovery"].get("recovered") for r in artifact["runs"]]}, ensure_ascii=False))
    return 0 if all(r["recovery"].get("recovered") is True for r in artifact["runs"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
