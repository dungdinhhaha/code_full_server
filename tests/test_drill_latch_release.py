"""A finished drill releases the virtual PLC safety latch unless another run is still active."""
import json
import unittest

from service import demo_mode as dm


class _Client:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, payload))
        return None


class _Message:
    def __init__(self, body):
        self.payload = json.dumps(body).encode("utf-8")


class DrillLatchReleaseTests(unittest.TestCase):
    FARM = "greenhouse_j"

    def setUp(self):
        dm._active_scenarios.clear()
        state = dm._farm_actuator_state(self.FARM)
        state["safe_mode_active"] = True
        state["fault"] = "max_runtime"

    def _run(self, run_id, code="A1", scenario_type="water_overrun"):
        return {"farm_key": self.FARM, "scenario_type": scenario_type, "scenario_code": code,
                "scenario_run_id": run_id, "node_id": None, "lot_id": None, "seed": 17,
                "started_at": "2026-11-12T21:50:00Z"}

    def _stop(self, run_id):
        dm._on_virtual_control(_Client(), None, _Message({
            "action": "STOP_SCENARIO", "scenario_run_id": run_id, "command_id": "stop-" + run_id}))

    def test_stop_releases_latch_when_no_other_run_on_farm(self):
        dm._active_scenarios["r1"] = self._run("r1")
        self._stop("r1")
        state = dm._farm_actuator_state(self.FARM)
        self.assertFalse(state["safe_mode_active"])
        self.assertIsNone(state["fault"])

    def test_stop_keeps_latch_while_another_run_active_on_same_farm(self):
        dm._active_scenarios["r1"] = self._run("r1")
        dm._active_scenarios["r2"] = self._run("r2", code="A2", scenario_type="a2_pump_pressure_zero")
        self._stop("r1")
        state = dm._farm_actuator_state(self.FARM)
        self.assertTrue(state["safe_mode_active"])


if __name__ == "__main__":
    unittest.main()
