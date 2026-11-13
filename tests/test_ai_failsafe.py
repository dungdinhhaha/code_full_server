"""Test fail-safe cua AI (service/ai_service.py). Khong can Gemini, Mongo, MQTT.

ai_service import service.observability (tracing) va dotenv (doc .env) luc import,
nen stub hai module nay truoc khi import. Khong goi mang: _call_gemini_api duoc mock.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -v
"""

import sys
import types
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stub_dependencies():
    if "service.observability" not in sys.modules:
        obs = types.ModuleType("service.observability")

        def traced(operation, resource=None):
            def decorator(fn):
                return fn
            return decorator

        @contextmanager
        def trace_span(operation, resource=None, child_of=None, **tags):
            yield None

        @contextmanager
        def llm_observation(model_name, operation="generateContent"):
            yield None

        obs.traced = traced
        obs.trace_span = trace_span
        obs.llm_observation = llm_observation
        # Keep this import stub compatible with tests that import service.mqtt
        # later in the same unittest discovery process.
        obs.inject_mqtt_trace_context = lambda payload: payload
        obs.traced_mqtt_callback = lambda operation: (lambda fn: fn)
        sys.modules["service.observability"] = obs
    if "dotenv" not in sys.modules:
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda *args, **kwargs: False
        sys.modules["dotenv"] = dotenv


_stub_dependencies()
ai = __import__("service.ai_service", fromlist=["ai_service"])


class ClassifyAiPayloadTests(unittest.TestCase):
    def test_zero_ml_is_no_water_not_error(self):
        result = ai.classify_ai_payload({"amount_ml": 0})
        self.assertEqual(result["status"], "no_water")
        self.assertEqual(result["amount_ml"], 0.0)
        self.assertFalse(result["hold"])

    def test_positive_ml_is_ok(self):
        result = ai.classify_ai_payload({"amount_ml": 120})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["amount_ml"], 120.0)
        self.assertFalse(result["hold"])

    def test_provider_error_holds_without_amount(self):
        result = ai.classify_ai_payload({"ai_status": "provider_error", "amount_ml": 80})
        self.assertEqual(result["status"], "provider_error")
        self.assertIsNone(result["amount_ml"])
        self.assertTrue(result["hold"])

    def test_empty_payload_is_no_data_not_zero(self):
        result = ai.classify_ai_payload({})
        self.assertEqual(result["status"], "no_data")
        self.assertIsNone(result["amount_ml"])
        self.assertTrue(result["hold"])  # intentional: no data => HOLD

    def test_negative_or_bool_amount_is_not_irrigation(self):
        for payload in ({"amount_ml": -5}, {"amount_ml": True}):
            with self.subTest(payload=payload):
                result = ai.classify_ai_payload(payload)
                self.assertEqual(result["status"], "no_data")
                self.assertIsNone(result["amount_ml"])


class ParseAndClassifyTextTests(unittest.TestCase):
    def test_parse_zero_is_valid(self):
        self.assertEqual(ai.parse_amount_ml('{"amount_ml": 0}'), (0.0, None))

    def test_parse_fenced_json(self):
        self.assertEqual(ai.parse_amount_ml('```json\n{"amount_ml": 50}\n```'), (50.0, None))

    def test_parse_negative_is_invalid(self):
        self.assertEqual(ai.parse_amount_ml('{"amount_ml": -1}'), (None, "invalid_amount_ml"))

    def test_parse_free_text_is_not_structured(self):
        self.assertEqual(ai.parse_amount_ml("Hôm nay trời mát."), (None, None))

    def test_classify_text_zero_is_no_water(self):
        result = ai.classify_ai_text('{"amount_ml": 0}', ai.AI_MODEL)
        self.assertEqual(result.status, "no_water")
        self.assertEqual(result.action, "NO_WATER")

    def test_classify_empty_text_is_no_data(self):
        for text in (None, "", "   ", ai.NO_DATA_TEXT):
            with self.subTest(text=text):
                result = ai.classify_ai_text(text, ai.AI_MODEL)
                self.assertEqual(result.status, "no_data")
                self.assertIsNone(result.amount_ml)


class AIResultTests(unittest.TestCase):
    def test_provider_error_action_is_hold(self):
        result = ai.provider_error_result("http_429", "loi tam thoi")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.action, "HOLD")
        self.assertEqual(str(result), "loi tam thoi")

    def test_no_data_result_is_hold(self):
        result = ai.AIResult(ai.NO_DATA_TEXT, "no_data", None, "invalid_or_missing_output", ai.AI_MODEL)
        self.assertEqual(result.action, "HOLD")
        self.assertTrue(result.as_dict()["action"] == "HOLD")

    def test_ok_action_is_none(self):
        result = ai.AIResult("ok", "ok", 100.0, "recommendation", ai.AI_MODEL)
        self.assertEqual(result.action, "NONE")
        self.assertEqual(result.as_dict()["amount_ml"], 100.0)


class AskAiFailSafeTests(unittest.TestCase):
    """Moi nhanh loi phai tra provider_error + HOLD, khong bao gio ra lenh tuoi."""

    def test_ask_ai_emits_bounded_success_and_fallback_counters(self):
        with mock.patch.object(ai, "_ask_ai_impl", return_value=ai.AIResult("ok", "ok", 40, "recommendation", ai.AI_MODEL)), \
                mock.patch("service.datadog_metrics.emit_count") as emit_count:
            ai.ask_ai("question")
        emit_count.assert_any_call("smiot.ai.decision_result", ["status:ok", "action:NONE"])
        emit_count.assert_any_call("smiot.ai.provider_success", ["status:ok", "action:NONE"])

        with mock.patch.object(ai, "_ask_ai_impl", return_value=ai.AIResult(ai.NO_DATA_TEXT, "no_data", None, "invalid_output", ai.AI_MODEL)), \
                mock.patch("service.datadog_metrics.emit_count") as emit_count:
            result = ai.ask_ai("question")
        self.assertEqual(result.action, "HOLD")
        emit_count.assert_any_call("smiot.ai.decision_result", ["status:no_data", "action:HOLD"])
        emit_count.assert_any_call("smiot.ai.safe_fallback", ["status:no_data", "action:HOLD"])

    def test_ai_disabled_holds(self):
        with mock.patch.object(ai, "AI_ENABLED", False):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.action, "HOLD")
        self.assertIsNone(result.amount_ml)

    def test_missing_api_key_holds(self):
        with mock.patch.object(ai, "AI_ENABLED", True), mock.patch.object(ai, "API_KEY", None):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.reason, "missing_api_key")
        self.assertEqual(result.action, "HOLD")

    def test_network_timeout_holds(self):
        with mock.patch.object(ai, "AI_ENABLED", True), mock.patch.object(ai, "API_KEY", "unit-test-fake-key"), \
                mock.patch.object(ai, "_call_gemini_api", side_effect=urllib.error.URLError("timeout")):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.reason, "timeout_or_network")
        self.assertEqual(result.action, "HOLD")

    def test_unexpected_exception_holds(self):
        with mock.patch.object(ai, "AI_ENABLED", True), mock.patch.object(ai, "API_KEY", "unit-test-fake-key"), \
                mock.patch.object(ai, "_call_gemini_api", side_effect=RuntimeError("boom")):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.reason, "exception_RuntimeError")
        self.assertEqual(result.action, "HOLD")

    def test_empty_candidates_is_no_data_not_water(self):
        with mock.patch.object(ai, "AI_ENABLED", True), mock.patch.object(ai, "API_KEY", "unit-test-fake-key"), \
                mock.patch.object(ai, "_call_gemini_api", return_value={"candidates": []}):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "no_data")
        self.assertIsNone(result.amount_ml)
        self.assertEqual(result.action, "HOLD")


if __name__ == "__main__":
    unittest.main()
