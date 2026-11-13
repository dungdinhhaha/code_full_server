"""Contract checks for low-cardinality signals used by W6 and W10."""

import ast
import unittest
from pathlib import Path

from service.telemetry_findings import _emit_finding_telemetry
from service.detector_heartbeat import has_advisory_input
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _source_tree(relative_path):
    path = ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


class DetectorMetricContractTests(unittest.TestCase):
    def test_successful_scenario_evaluation_uses_distinct_metric(self):
        with mock.patch("service.datadog_metrics.emit_count") as emit:
            _emit_finding_telemetry(cycle_succeeded=True)
        emit.assert_any_call("smiot.detector.scenario_evaluation.completed")
        self.assertNotIn(
            mock.call("smiot.detector.heartbeat"),
            emit.call_args_list,
            "scenario-run evaluation must not masquerade as per-sample heartbeat",
        )

    def test_unsuccessful_scenario_cycle_does_not_emit_completion(self):
        with mock.patch("service.datadog_metrics.emit_count") as emit:
            _emit_finding_telemetry(cycle_succeeded=False)
        self.assertFalse(any("detector.scenario_evaluation.completed" in str(c) for c in emit.call_args_list))

    def test_advisory_evaluation_metric_follows_transition_persistence_with_fixed_tags(self):
        tree = _source_tree(Path("service") / "mqtt.py")
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            calls = [n for stmt in node.body for n in ast.walk(stmt) if isinstance(n, ast.Call)]
            transition_index = next((i for i, call in enumerate(calls)
                                     if isinstance(call.func, ast.Name) and call.func.id == "record_reading_transition"), None)
            heartbeat_index = next((i for i, call in enumerate(calls)
                                    if isinstance(call.func, ast.Name) and call.func.id == "emit_count"
                                    and call.args and isinstance(call.args[0], ast.Constant)
                                    and call.args[0].value == "smiot.detector.advisory_evaluation.completed"), None)
            if transition_index is None or heartbeat_index is None:
                continue
            self.assertLess(transition_index, heartbeat_index)
            heartbeat = calls[heartbeat_index]
            tag_values = ast.literal_eval(heartbeat.args[1])
            self.assertEqual(tag_values, ["detector:agronomic_advisory", "result:completed"])
            found = True
        self.assertTrue(found, "expected one guarded advisory-completion heartbeat emission")

    def test_advisory_evaluation_requires_numeric_reading(self):
        self.assertTrue(has_advisory_input({"air_temp": 25.5}))
        self.assertTrue(has_advisory_input({"air_hum": 70}))
        self.assertFalse(has_advisory_input({"soil_hum": 42}))
        self.assertFalse(has_advisory_input({"air_temp": True}))
        self.assertFalse(has_advisory_input({"air_temp": "bad"}))
        self.assertFalse(has_advisory_input({"air_temp": float("nan")}))

    def test_ai_latency_uses_fixed_status_tag_and_provider_failure_metric_exists(self):
        tree = _source_tree(Path("service") / "ai_service.py")
        strings = {node.value for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertIn("smiot.ai.ask_latency_ms", strings)
        self.assertIn("smiot.ai.provider_failure", strings)

        ask_ai = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "ask_ai")
        status_allowlist = {"ok", "no_water", "no_data", "provider_error"}
        allowlist_found = any(
            isinstance(node, ast.Set)
            and {elt.value for elt in node.elts if isinstance(elt, ast.Constant)} == status_allowlist
            for node in ast.walk(ask_ai)
        )
        self.assertTrue(allowlist_found, "AI metric status tags must remain bounded")


if __name__ == "__main__":
    unittest.main()
