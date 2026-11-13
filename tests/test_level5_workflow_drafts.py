"""Static contract checks for the local SMIOT workflow hardening drafts.

These checks do not call Datadog, AWS, MongoDB, or the running application.
They verify that the reviewable JSON drafts preserve their known workflow IDs,
fail closed when evidence is missing, and route every referenced step to a real
step in the same workflow graph.
"""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "outputs" / "workflow_imports"
DRAFTS = IMPORTS / "level5_drafts"
MANIFEST = IMPORTS / "20261110_published_10_workflows.json"

IMPORT_FILES = {
    "W1": "w1_w01_smiot-w01-plc-safety-trip.json",
    "W2": "w2_ca2_sensor_hold_verify.json",
    "W4": "w4_ca1_refuse_restart.json",
    "W5": "w5_w05_smiot-w05-root-cause-triage.json",
    "W6": "w6_w06_smiot-w06-detector-heartbeat.json",
    "W7": "w7_w07_smiot-w07-irrigation-schedule-review.json",
    "W8": "w8_w08_smiot-w08-crop-risk-review.json",
    "W9": "w9_w09_smiot-w09-actuator-ack-verify.json",
    "W10": "w10_w10_smiot-w10-ai-failure-safety.json",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Level5WorkflowDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST)
        cls.by_case = {item["case"]: item for item in cls.manifest["workflows"]}

    def test_all_local_import_drafts_have_a_manifest_workflow(self):
        self.assertEqual(set(IMPORT_FILES), {"W1", "W2", "W4", "W5", "W6", "W7", "W8", "W9", "W10"})
        for case, filename in IMPORT_FILES.items():
            with self.subTest(case=case):
                draft = load_json(DRAFTS / filename)
                self.assertEqual(draft["spec"]["handle"], self.by_case[case]["handle"])

    def test_every_workflow_has_a_reachable_fail_closed_evidence_gate(self):
        for case, filename in IMPORT_FILES.items():
            with self.subTest(case=case):
                draft = load_json(DRAFTS / filename)
                spec = draft["spec"]
                steps = spec["steps"]
                by_name = {step["name"]: step for step in steps}
                self.assertEqual(len(by_name), len(steps), "step names must be unique")

                query = next(s for s in steps if s["actionId"] == "com.datadoghq.dd.metrics.queryScalarData")
                gate = by_name["verify_evidence_available"]
                self.assertIn(
                    "verify_evidence_available",
                    [edge["nextStepName"] for edge in query.get("outboundEdges", [])],
                )
                gate_edges = {edge["branchName"]: edge["nextStepName"] for edge in gate["outboundEdges"]}
                self.assertIn("true", gate_edges)
                self.assertEqual(gate_edges.get("false"), "escalate_missing_evidence")
                self.assertIn("escalate_missing_evidence", by_name)

                for step in steps:
                    for edge in step.get("outboundEdges", []):
                        self.assertIn(edge["nextStepName"], by_name)

                # All authored steps must be reachable from the configured trigger.
                starts = set()
                for trigger in spec.get("triggers", []):
                    starts.update(trigger.get("startStepNames", []))
                pending, seen = list(starts), set()
                while pending:
                    name = pending.pop()
                    if name in seen:
                        continue
                    seen.add(name)
                    pending.extend(e["nextStepName"] for e in by_name[name].get("outboundEdges", []))
                    pending.extend(
                        handler["fallbackStepName"]
                        for handler in by_name[name].get("errorHandlers", [])
                    )
                self.assertEqual(seen, set(by_name), "all steps should be reachable from a trigger")

    def test_case_specific_multi_signal_classifiers_remain_distinct(self):
        w5 = load_json(DRAFTS / IMPORT_FILES["W5"])
        w5_names = {step["name"] for step in w5["spec"]["steps"]}
        self.assertTrue({"classify_mongo", "classify_mqtt", "classify_ingest"}.issubset(w5_names))

        w10 = load_json(DRAFTS / IMPORT_FILES["W10"])
        w10_names = {step["name"] for step in w10["spec"]["steps"]}
        self.assertTrue({"classify_provider_error", "classify_latency"}.issubset(w10_names))

    def test_w3_is_explicitly_design_only_until_full_export_exists(self):
        w3 = load_json(DRAFTS / "w3_guarded_ec2_app_recovery_design.json")
        self.assertEqual(w3["format"], "smiot.workflow.level5.design.v1")
        self.assertIn("do not import duplicate", w3["live_state"])
        self.assertIn("post-action verification branches", " ".join(w3["level5_gates"]))


if __name__ == "__main__":
    unittest.main()
