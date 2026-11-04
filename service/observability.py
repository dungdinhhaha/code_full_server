"""Optional Datadog APM tracing and trace-correlated JSON logs for SMIOT."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

from dotenv import load_dotenv
from service.logger import get_logger

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logger = get_logger("OBSERVABILITY")
_initialized = False
_tracer = None
_llmobs = None


def initialize_tracing() -> bool:
    """Initialize ddtrace before application frameworks are imported."""
    global _initialized, _tracer, _llmobs
    if _initialized:
        return _tracer is not None
    _initialized = True

    if os.getenv("DATADOG_APM_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return False

    os.environ.setdefault("DD_SERVICE", "smiot-smart-farm")
    os.environ.setdefault("DD_ENV", "demo")
    os.environ.setdefault("DD_VERSION", "1.0.0")
    os.environ.setdefault("DD_TRACE_AGENT_URL", "http://127.0.0.1:8126")
    os.environ.setdefault("DD_LOGS_INJECTION", "true")
    if os.getenv("DATADOG_LLMOBS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        os.environ.setdefault("DD_LLMOBS_ENABLED", "1")
        os.environ.setdefault("DD_LLMOBS_ML_APP", "smiot-smart-farm")

    try:
        import ddtrace

        ddtrace.patch_all()
        _tracer = ddtrace.tracer
        if os.getenv("DATADOG_LLMOBS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
            try:
                from ddtrace.llmobs import LLMObs

                LLMObs.enable(
                    ml_app=os.getenv("DD_LLMOBS_ML_APP", "smiot-smart-farm"),
                    integrations_enabled=False,
                    agentless_enabled=False,
                    site=os.getenv("DD_SITE"),
                    service=os.getenv("DD_SERVICE"),
                    env=os.getenv("DD_ENV"),
                )
                _llmobs = LLMObs
                logger.info("Datadog LLM Observability enabled for ml_app=smiot-smart-farm (inputs/outputs redacted)")
            except Exception as exc:
                logger.warning("Datadog LLM Observability could not start: %s", type(exc).__name__)
        logger.info("Datadog APM tracing initialized for service=smiot-smart-farm env=demo")
        return True
    except ImportError:
        logger.warning("DATADOG_APM_ENABLED=true but ddtrace is not installed; tracing is disabled")
        return False


@contextmanager
def llm_observation(model_name: str, operation: str = "generateContent"):
    """Yield an LLMObs span if configured; callers must annotate token counts.

    Raw user prompts, farm readings, and model responses are deliberately not
    attached to spans. Callers can safely attach redacted summaries and usage.
    """
    if _llmobs is None:
        yield None
        return
    with _llmobs.llm(model_name=model_name, name=operation, model_provider="google") as span:
        yield span


@contextmanager
def trace_span(operation: str, resource: str | None = None, child_of: Any = None, **tags: Any) -> Iterator[Any]:
    """Create a Datadog span when enabled; otherwise behave as a no-op."""
    if not _tracer:
        yield None
        return

    if child_of is not None:
        # ddtrace 4.x accepts child_of on start_span(), not trace().
        span = _tracer.start_span(
            operation,
            resource=resource or operation,
            child_of=child_of,
            activate=True,
        )
    else:
        span = _tracer.trace(operation, resource=resource or operation)
    for key, value in tags.items():
        if value is not None:
            span.set_tag(key, value)
    started = time.perf_counter()
    try:
        yield span
    except Exception as exc:
        span.set_exc_info(type(exc), exc, exc.__traceback__)
        raise
    finally:
        trace_id = str(span.trace_id) if span.trace_id else None
        span_id = str(span.span_id) if span.span_id else None
        span.finish()
        logger.info(json.dumps({
            "event": "smiot_trace_span",
            "operation": operation,
            "resource": resource or operation,
            "trace_id": trace_id,
            "span_id": span_id,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": bool(span.error),
        }, ensure_ascii=False, separators=(",", ":")))


def traced(operation: str, resource: str | None = None) -> Callable:
    """Decorator for existing synchronous application boundaries."""
    def decorate(func: Callable) -> Callable:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with trace_span(operation, resource or func.__name__):
                return func(*args, **kwargs)
        return wrapped
    return decorate


def inject_mqtt_trace_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach Datadog propagation headers to a JSON MQTT payload, if active."""
    if not _tracer:
        return payload
    active_span = _tracer.current_span()
    if not active_span:
        return payload
    try:
        from ddtrace.propagation.http import HTTPPropagator

        carrier: dict[str, str] = {}
        HTTPPropagator.inject(active_span.context, carrier)
        if carrier:
            payload["_dd_trace_context"] = carrier
    except Exception:
        logger.exception("Could not inject Datadog context into MQTT payload")
    return payload


def traced_mqtt_callback(operation: str) -> Callable:
    """Trace an MQTT callback as a child of the publisher when context is present."""
    def decorate(func: Callable) -> Callable:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            parent = None
            topic = None
            farm_key = "greenhouse_a"
            incident_id = None
            message_id = None
            try:
                msg = args[2]
                topic = msg.topic
                payload = json.loads(msg.payload.decode("utf-8"))
                farm_key = payload.get("farm_key", farm_key)
                incident_id = payload.get("incident_id")
                message_id = payload.get("message_id") or payload.get("sample_sequence")
                carrier = payload.get("_dd_trace_context") or {}
                if _tracer and carrier:
                    from ddtrace.propagation.http import HTTPPropagator

                    parent = HTTPPropagator.extract(carrier)
            except Exception:
                pass

            with trace_span(operation, resource=topic or operation, child_of=parent,
                            **{"mqtt.topic": topic, "farm.key": farm_key,
                               "incident.id": incident_id, "smiot.message_id": message_id}):
                if incident_id:
                    try:
                        from service.incident_lifecycle import add_incident_trace_evidence
                        span = _tracer.current_span() if _tracer else None
                        add_incident_trace_evidence(str(incident_id), trace_id=str(span.trace_id) if span else None,
                                                    message_id=str(message_id) if message_id else None)
                    except Exception:
                        logger.exception("Could not attach MQTT trace evidence to incident")
                return func(*args, **kwargs)
        return wrapped
    return decorate
