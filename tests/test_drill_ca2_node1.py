import json
import unittest

from scripts.drill_ca2_node1_flatline import (
    CONTROL_TOPIC,
    build_start_scenario_payload,
)


class DrillCa2Node1PayloadTest(unittest.TestCase):
    def test_start_scenario_targets_node1_on_greenhouse_j(self):
        payload = build_start_scenario_payload(scenario_run_id="run-1", command_id="cmd-1")
        self.assertEqual(payload["action"], "START_SCENARIO")
        self.assertEqual(payload["node_id"], 1)
        self.assertEqual(payload["farm_key"], "greenhouse_j")
        self.assertEqual(payload["scenario_type"], "soil_flatline")
        self.assertEqual(payload["seed"], 17)
        self.assertEqual(payload["scenario_run_id"], "run-1")
        self.assertEqual(payload["command_id"], "cmd-1")

    def test_s1_code_is_accepted_as_scenario_type(self):
        payload = build_start_scenario_payload(scenario_type="S1")
        self.assertEqual(payload["scenario_type"], "S1")
        self.assertEqual(payload["node_id"], 1)

    def test_other_scenarios_are_rejected(self):
        with self.assertRaises(ValueError):
            build_start_scenario_payload(scenario_type="soil_spike")

    def test_generated_ids_are_present_and_unique(self):
        first = build_start_scenario_payload()
        second = build_start_scenario_payload()
        self.assertTrue(first["scenario_run_id"])
        self.assertTrue(first["command_id"])
        self.assertNotEqual(first["scenario_run_id"], second["scenario_run_id"])
        self.assertNotEqual(first["command_id"], second["command_id"])

    def test_payload_is_json_serialisable_and_topic_is_control(self):
        payload = build_start_scenario_payload()
        decoded = json.loads(json.dumps(payload))
        self.assertEqual(decoded, payload)
        self.assertEqual(CONTROL_TOPIC, "farm/demo/control")


if __name__ == "__main__":
    unittest.main()
