"""Unit tests for optional Datadog LLM Observability on the Gemini calls (service/ai_service.py).

Khong can Gemini, Mongo, MQTT, ddtrace that cai san hay Datadog that. Moi goi mang bi mock.
Test patch ten o muc module cua service.ai_service nen khong phu thuoc thu tu load cua test khac.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -p "test_*.py"
"""

import contextlib
import io
import json
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

FAKE_KEY = "AIza-unit-test-fake-key-0000"
MODEL = "gemini-3.5-flash-lite"


def _text_body(text='{"amount_ml": 120}'):
    return {
        "candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
    }


def _tool_call_body(farm_key="greenhouse_a"):
    return {
        "candidates": [{
            "content": {"role": "model", "parts": [
                {"functionCall": {"name": "get_current_telemetry", "args": {"farm_key": farm_key}}}
            ]},
        }]
    }


def _fake_urlopen(*bodies):
    """urlopen gia lap; moi lan goi tra ve body tiep theo."""
    responses = []
    for body in bodies:
        cm = mock.MagicMock()
        cm.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
        cm.__exit__.return_value = False
        responses.append(cm)
    return mock.MagicMock(side_effect=responses)


class FakeLLMObs:
    """Ghi lai span/annotate de kiem tra. Mo phong ddtrace.llmobs.LLMObs."""

    def __init__(self, annotate_error=None):
        self.spans = []
        self.annotations = []
        self._annotate_error = annotate_error

    @contextmanager
    def llm(self, model_name, name, model_provider):
        span = {"model_name": model_name, "name": name, "provider": model_provider, "error": None}
        self.spans.append(span)
        try:
            yield span
        except Exception as exc:
            span["error"] = type(exc).__name__
            raise

    def annotate(self, span, **kwargs):
        if self._annotate_error is not None:
            raise self._annotate_error
        self.annotations.append((span, kwargs))


class _Base(unittest.TestCase):
    def setUp(self):
        self._stack = contextlib.ExitStack()
        self.addCleanup(self._stack.close)
        self._stack.enter_context(mock.patch.object(ai, "API_KEY", FAKE_KEY))
        self._stack.enter_context(mock.patch.object(ai, "AI_ENABLED", True))
        # Tracing cua app khong duoc chay trong unit test.
        self._stack.enter_context(mock.patch.object(ai, "trace_span", lambda *a, **k: contextlib.nullcontext()))
        self.stdout = io.StringIO()
        self._stack.enter_context(contextlib.redirect_stdout(self.stdout))

    def enable_llmobs(self, fake_obs):
        """Bat LLMObs gia: llm_observation tra span that, va ddtrace.llmobs.LLMObs la fake."""
        llmobs_mod = types.ModuleType("ddtrace.llmobs")
        llmobs_mod.LLMObs = fake_obs
        ddtrace_mod = types.ModuleType("ddtrace")
        ddtrace_mod.llmobs = llmobs_mod

        @contextmanager
        def fake_llm_observation(model_name, operation="generateContent"):
            with fake_obs.llm(model_name=model_name, name=operation, model_provider="google") as span:
                yield span

        self._stack.enter_context(mock.patch.dict(sys.modules, {"ddtrace": ddtrace_mod,
                                                                "ddtrace.llmobs": llmobs_mod}))
        self._stack.enter_context(mock.patch.object(ai, "llm_observation", fake_llm_observation))

    def disable_llmobs(self):
        """Dung dung cach app chay khi DATADOG_LLMOBS_ENABLED khong bat: llm_observation tra None."""
        self._stack.enter_context(mock.patch.object(ai, "llm_observation",
                                                    lambda *a, **k: contextlib.nullcontext()))


class LlmObsDisabledTests(_Base):
    """(a) Khi LLMObs khong bat, ham goi mo hinh hoat dong y nhu cu."""

    def test_disabled_returns_same_result_and_no_annotation(self):
        self.disable_llmobs()
        urlopen = _fake_urlopen(_text_body(), _text_body())
        with mock.patch.object(ai.urllib.request, "urlopen", urlopen):
            raw = ai._call_gemini_model({"contents": []}, MODEL)
            result = ai.ask_ai("tuoi bao nhieu?")

        self.assertEqual(raw, _text_body())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.amount_ml, 120.0)
        self.assertEqual(urlopen.call_count, 2)

    def test_disabled_provider_error_still_holds(self):
        self.disable_llmobs()
        with mock.patch.object(ai.urllib.request, "urlopen",
                               side_effect=urllib.error.URLError("timeout")):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.reason, "timeout_or_network")
        self.assertEqual(result.action, "HOLD")


class LlmObsEnabledTests(_Base):
    """(b) Khi LLMObs bat: span duoc tao, loi mo hinh khong lam vo ham."""

    def test_enabled_creates_llm_span_with_model_and_usage(self):
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        with mock.patch.object(ai.urllib.request, "urlopen", _fake_urlopen(_text_body())):
            result = ai._call_gemini_model({"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}, MODEL)

        self.assertEqual(result, _text_body())
        self.assertEqual(len(fake.spans), 1)
        self.assertEqual(fake.spans[0]["model_name"], MODEL)
        self.assertEqual(fake.spans[0]["provider"], "google")
        self.assertIsNone(fake.spans[0]["error"])
        self.assertEqual(len(fake.annotations), 1)
        _, kwargs = fake.annotations[0]
        self.assertEqual(kwargs["metadata"]["model_name"], MODEL)
        self.assertEqual(kwargs["metrics"], {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        self.assertTrue(kwargs["input_data"]["content_redacted"])
        self.assertTrue(kwargs["output_data"]["content_redacted"])

    def test_enabled_model_error_is_recorded_and_request_still_holds(self):
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        http_err = urllib.error.HTTPError("https://example.invalid", 429, "Too Many", {},
                                          io.BytesIO(b"quota exceeded"))
        with mock.patch.object(ai.urllib.request, "urlopen", side_effect=http_err):
            result = ai.ask_ai("tuoi bao nhieu?")

        self.assertEqual(result.status, "provider_error")
        self.assertEqual(result.reason, "http_429")
        self.assertEqual(result.action, "HOLD")
        self.assertEqual(len(fake.spans), 1)
        self.assertEqual(fake.spans[0]["error"], "HTTPError")

    def test_enabled_annotate_failure_does_not_fail_request(self):
        fake = FakeLLMObs(annotate_error=RuntimeError("datadog down"))
        self.enable_llmobs(fake)
        with mock.patch.object(ai.urllib.request, "urlopen", _fake_urlopen(_text_body())):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.amount_ml, 120.0)

    def test_ddtrace_missing_is_silently_skipped(self):
        # ddtrace.llmobs = None lam import bi loi ImportError ben trong ham; app phai van chay.
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        self._stack.enter_context(mock.patch.dict(sys.modules, {"ddtrace.llmobs": None}))
        with mock.patch.object(ai.urllib.request, "urlopen", _fake_urlopen(_text_body())):
            result = ai.ask_ai("tuoi bao nhieu?")
        self.assertEqual(result.status, "ok")
        self.assertEqual(fake.annotations, [])

    def test_farm_key_tag_is_attached_to_tool_followup_span(self):
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        fake_tool = mock.MagicMock(return_value={})
        with mock.patch.dict(ai.FUNCTIONS, {"get_current_telemetry": fake_tool}), \
                mock.patch.object(ai.urllib.request, "urlopen",
                                  _fake_urlopen(_tool_call_body("greenhouse_a"), _text_body())):
            result = ai.ask_ai("nhiet do the nao?")

        self.assertEqual(result.status, "ok")
        fake_tool.assert_called_once_with(farm_key="greenhouse_a")
        self.assertEqual(len(fake.spans), 2)
        self.assertEqual(len(fake.annotations), 2)
        self.assertEqual(fake.annotations[-1][1]["tags"]["farm_key"], "greenhouse_a")


class ApiKeyNotLeakedTests(_Base):
    """(c) Khong co khoa API nao xuat hien trong du lieu gui di, span, hoac log."""

    def test_key_only_in_transport_header_not_in_body_url_or_observability(self):
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        urlopen = _fake_urlopen(_text_body())
        with mock.patch.object(ai.urllib.request, "urlopen", urlopen):
            ai.ask_ai("tuoi bao nhieu?")

        req = urlopen.call_args_list[0].args[0]
        self.assertNotIn(FAKE_KEY, req.full_url)
        self.assertNotIn(FAKE_KEY, req.data.decode("utf-8"))
        self.assertEqual(req.get_header("X-goog-api-key"), FAKE_KEY)  # chi o header xac thuc
        observed = json.dumps([kw for _, kw in fake.annotations], default=str) + json.dumps(fake.spans, default=str)
        self.assertNotIn(FAKE_KEY, observed)
        self.assertNotIn(FAKE_KEY, self.stdout.getvalue())

    def test_key_echoed_in_provider_error_body_is_redacted_from_logs(self):
        fake = FakeLLMObs()
        self.enable_llmobs(fake)
        echoed = f"API key not valid: {FAKE_KEY}".encode("utf-8")
        http_err = urllib.error.HTTPError("https://example.invalid", 401, "Unauthorized", {}, io.BytesIO(echoed))
        with mock.patch.object(ai.urllib.request, "urlopen", side_effect=http_err):
            result = ai.ask_ai("tuoi bao nhieu?")

        self.assertEqual(result.reason, "http_401")
        self.assertNotIn(FAKE_KEY, self.stdout.getvalue())
        self.assertIn("[REDACTED]", self.stdout.getvalue())
        self.assertNotIn(FAKE_KEY, result)
        self.assertNotIn(FAKE_KEY, json.dumps(fake.spans, default=str))


if __name__ == "__main__":
    unittest.main()
