import json
import unittest

from scripts.drill_device_a_series import (
    ACTUATOR_CONTROL_TOPIC,
    SCENARIO_CONTROL_TOPIC,
    build_drill_plan,
)
from scripts.velxio_mqtt_bridge import normalize_command

FARM = "greenhouse_j"
RUN = "run-drill-0001"
INCIDENT = "inc-drill-0001"


class DrillPayloadTests(unittest.TestCase):
    def test_w1_cases_send_only_a_correlated_start(self):
        for case in ("A2", "C10"):
            with self.subTest(case=case):
                plan = build_drill_plan(case, FARM, run_id=RUN, incident_id=INCIDENT, command_id="cmd-1")
                self.assertEqual([topic for topic, _ in plan], [SCENARIO_CONTROL_TOPIC])
                _, start = plan[0]
                self.assertEqual(start["action"], "START_SCENARIO")
                self.assertEqual(start["scenario_code"], case)
                self.assertEqual(start["scenario_run_id"], RUN)
                self.assertEqual(start["incident_id"], INCIDENT)
                self.assertEqual(start["command_id"], "cmd-1")
                self.assertEqual(start["farm_key"], FARM)
                self.assertTrue(start["synthetic"])

    def test_w9_case_adds_safe_off_command_on_actuator_channel(self):
        plan = build_drill_plan("A4", FARM, run_id=RUN, incident_id=INCIDENT, command_id="cmd-9")
        self.assertEqual([topic for topic, _ in plan], [SCENARIO_CONTROL_TOPIC, ACTUATOR_CONTROL_TOPIC])
        _, command = plan[1]
        self.assertEqual(command["action"], "SET_OUTPUTS")
        self.assertEqual(command["bit0"], 0)
        self.assertNotEqual(command["command_id"], plan[0][1]["command_id"])
        self.assertEqual(command["scenario_run_id"], RUN)
        self.assertEqual(command["scenario_code"], "A4")
        self.assertEqual(command["incident_id"], INCIDENT)

    def test_w9_command_is_accepted_by_bridge_contract(self):
        _, command = build_drill_plan("A4", FARM, run_id=RUN, incident_id=INCIDENT)[1]
        normalized = normalize_command(command, FARM)
        self.assertEqual(normalized["action"], "SET_OUTPUTS")
        self.assertEqual(normalized["bit0"], 0)
        self.assertEqual(normalized["command_id"], command["command_id"])
        self.assertEqual(normalized["scenario_run_id"], RUN)

    def test_generated_ids_are_unique_and_present(self):
        first = build_drill_plan("A4", FARM)
        second = build_drill_plan("A4", FARM)
        self.assertTrue(first[0][1]["scenario_run_id"])
        self.assertTrue(first[0][1]["incident_id"])
        self.assertNotEqual(first[0][1]["scenario_run_id"], second[0][1]["scenario_run_id"])
        self.assertNotEqual(first[0][1]["command_id"], second[0][1]["command_id"])

    def test_payloads_are_json_serialisable_and_free_of_secret_fields(self):
        for case in ("A2", "C10", "A4"):
            plan = build_drill_plan(case, FARM, run_id=RUN, incident_id=INCIDENT)
            text = json.dumps([payload for _, payload in plan]).lower()
            for banned in ("password", "passwd", "token", "secret", "username"):
                self.assertNotIn(banned, text)

    def test_unknown_case_and_empty_farm_are_rejected(self):
        with self.assertRaises(ValueError):
            build_drill_plan("A9", FARM)
        with self.assertRaises(ValueError):
            build_drill_plan("A4", "  ")


if __name__ == "__main__":
    unittest.main()
