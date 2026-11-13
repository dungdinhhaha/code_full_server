import unittest

from scripts.velxio_mqtt_bridge import (
    SOURCE,
    build_ack_payload,
    build_flow_envelope,
    build_node_envelope,
    build_profile_command,
    normalize_profile_ack,
    normalize_command,
    profile_commands,
    scenario_profile,
)


class VelxioContractTests(unittest.TestCase):
    def test_node_contract_has_provenance_and_sequence(self):
        result = build_node_envelope({
            "node_id": "node1", "device_id": "vx-node-1", "boot_id": "boot-7",
            "sequence": 12, "uptime_ms": 5000, "at": 29.2, "ah": 76.0,
            "st": 26.1, "sh": 43.0, "sec": 1.2,
        }, "node1", "greenhouse_j")
        self.assertEqual(result["farm_key"], "greenhouse_j")
        self.assertEqual(result["source"], SOURCE)
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["id6"]["node1"]["sh"], 43.0)
        self.assertEqual(result["sample_sequence"], 12)

    def test_flow_contract_has_id3(self):
        result = build_flow_envelope({"f1": 3, "f2": 0, "pressure_bar": 1.1,
                                      "t1": 20, "t2": 21}, "greenhouse_j")
        self.assertEqual(result["id3"]["f1"], 3.0)
        self.assertTrue(result["id3"]["synthetic"])
        self.assertEqual(result["source"], SOURCE)

    def test_command_and_ack_keep_correlation(self):
        command = normalize_command({"farm_key": "greenhouse_j", "command_id": "cmd-1",
                                     "incident_id": "inc-1", "scenario_run_id": "run-1",
                                     "action": "HOLD"}, "greenhouse_j")
        ack = build_ack_payload({"farm_key": "greenhouse_j", "command_id": "cmd-1",
                                 "virtual_output": {f"bit{i}": 0 for i in range(8)},
                                 "applied": True, "verified": True}, command, "greenhouse_j")
        self.assertEqual(ack["incident_id"], "inc-1")
        self.assertEqual(ack["scenario_run_id"], "run-1")
        self.assertTrue(ack["verified"])

    def test_wrong_farm_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_command({"farm_key": "greenhouse_a", "command_id": "cmd-1",
                               "action": "HOLD"}, "greenhouse_j")

    def test_fault_and_stop_select_datasets_for_all_three_devices(self):
        start = {"action": "START_SCENARIO", "farm_key": "greenhouse_j",
                 "scenario_code": "A1", "scenario_run_id": "run-1",
                 "incident_id": "inc-1", "command_id": "start-1"}
        stop = {**start, "action": "STOP_SCENARIO", "command_id": "stop-1"}
        self.assertIsNone(scenario_profile(start, "farm/demo/control"))
        self.assertIsNone(scenario_profile(stop, "farm/demo/control"))
        self.assertIsNone(scenario_profile({"event": "scenario_ack", "status": "rejected",
                                            "applied": False}, "farm/demo/status"))
        self.assertEqual(scenario_profile({"event": "scenario_ack", "status": "started",
                                           "applied": True}, "farm/demo/status"), "fault")
        self.assertEqual(scenario_profile({"event": "scenario_ack", "status": "stopped",
                                           "applied": True}, "farm/demo/status"), "normal")
        commands = [build_profile_command(start, "greenhouse_j", node, "fault")
                    for node in ("node1", "node2", "flow")]
        self.assertEqual([c["target_device_id"] for c in commands], ["node1", "node2", "flow"])
        self.assertTrue(all(c["incident_id"] == "inc-1" for c in commands))
        self.assertTrue(all(c["command_id"].endswith(":profile:" + c["target_device_id"])
                            for c in commands))

    def test_profile_ack_requires_exact_command_farm_device_and_state(self):
        expected = build_profile_command({"farm_key": "greenhouse_j", "command_id": "run-2",
                                          "incident_id": "inc-2"},
                                         "greenhouse_j", "node2", "normal")
        ack = normalize_profile_ack({"farm_key": "greenhouse_j", "command_id": expected["command_id"],
                                     "device_id": "velxio-virtual-pump-01", "node_id": "node2",
                                     "profile": "normal", "dataset_id": "node2-normal-v1",
                                     "applied": True, "verified": True}, expected, "greenhouse_j")
        self.assertEqual(ack["command_id"], "run-2")
        self.assertEqual(ack["profile_command_id"], expected["command_id"])
        self.assertTrue(ack["verified"])

    def test_profile_ack_rejects_wrong_command(self):
        expected = build_profile_command({"farm_key": "greenhouse_j", "command_id": "run-3"},
                                         "greenhouse_j", "flow", "fault")
        with self.assertRaises(ValueError):
            normalize_profile_ack({"farm_key": "greenhouse_j", "command_id": "another",
                                   "device_id": "velxio-flow-monitor-01", "profile": "fault"},
                                  expected, "greenhouse_j")

    def _started_profiles(self, code, scenario_type):
        payload = {"event": "scenario_ack", "status": "started", "applied": True,
                   "farm_key": "greenhouse_j", "command_id": f"run-{code}",
                   "incident_id": "inc-x", "scenario_run_id": "run-x",
                   "scenario_code": code, "scenario_type": scenario_type}
        profile = scenario_profile(payload, "farm/demo/status")
        return profile_commands(payload, "greenhouse_j", profile)

    def test_soil_spike_sends_profile_only_to_node1(self):
        commands = self._started_profiles("S2", "soil_spike")
        self.assertEqual([c["target_device_id"] for c in commands], ["node1"])
        self.assertEqual(commands[0]["profile"], "fault")

    def test_pump_pressure_zero_sends_profile_only_to_node2(self):
        commands = self._started_profiles("A2", "a2_pump_pressure_zero")
        self.assertEqual([c["target_device_id"] for c in commands], ["node2"])
        self.assertEqual(commands[0]["profile"], "fault")

    def test_c2_and_c6_send_profile_only_to_node1(self):
        for code in ("C2", "C6"):
            commands = self._started_profiles(code, "")
            self.assertEqual([c["target_device_id"] for c in commands], ["node1"], code)
            self.assertEqual(commands[0]["profile"], "fault")

    def test_unmapped_scenario_sends_no_profile(self):
        with self.assertLogs("smiot.velxio.bridge", level="WARNING") as logs:
            commands = self._started_profiles("ZZ9", "unknown_scenario")
        self.assertEqual(commands, [])
        self.assertIn("velxio_profile_unmapped", logs.output[0])


if __name__ == "__main__":
    unittest.main()
