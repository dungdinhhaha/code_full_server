"""
service/ai_service.py — AI Assistant Service using Gemini API
─────────────────────────────────────────────────────────────
Giao tiếp với Gemini API thông qua HTTP REST để xử lý hội thoại.
Hỗ trợ Function Calling (Whitelist Tools) để truy xuất dữ liệu từ DB.
"""
import os
import re
import json
import socket
import time
import urllib.request
import urllib.error
import logging
from service.ai_tools import (
    get_current_telemetry,
    get_sensor_history,
    get_recent_system_warnings,
    get_active_irrigation_schedules,
    get_irrigation_history,
    get_system_mode,
    get_total_water_consumption,
    get_ai_agronomy_suggestion,
    get_future_schedules
)

# Load biến môi trường
from dotenv import load_dotenv
from service.observability import traced, trace_span, llm_observation
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
AI_ENABLED = os.environ.get("AI_ENABLED", "true").lower() == "true"
LOGGER = logging.getLogger(__name__)


def _redact(text) -> str:
    """Remove the configured Gemini API key from text before it is printed or sent anywhere."""
    out = str(text)
    if API_KEY:
        out = out.replace(API_KEY, "[REDACTED]")
    return out


def _observability_tags(args) -> dict:
    """Low-cardinality tags for Datadog search (farm_key only). Never free text, never secrets."""
    if not isinstance(args, dict):
        return {}
    tags = {}
    farm_key = args.get("farm_key")
    if isinstance(farm_key, str) and 0 < len(farm_key) <= 64 and re.fullmatch(r"[A-Za-z0-9_.-]+", farm_key):
        tags["farm_key"] = farm_key
    return tags

# Whitelist các hàm Python mà AI được phép gọi
FUNCTIONS = {
    "get_current_telemetry": get_current_telemetry,
    "get_sensor_history": get_sensor_history,
    "get_recent_system_warnings": get_recent_system_warnings,
    "get_active_irrigation_schedules": get_active_irrigation_schedules,
    "get_irrigation_history": get_irrigation_history,
    "get_system_mode": get_system_mode,
    "get_total_water_consumption": get_total_water_consumption,
    "get_ai_agronomy_suggestion": get_ai_agronomy_suggestion,
    "get_future_schedules": get_future_schedules
}

# Khai báo cấu trúc tool cho Gemini
TOOL_DECLARATIONS = [
    {
        "name": "get_current_telemetry",
        "description": "Lấy dữ liệu cảm biến mới nhất hiện tại của một trang trại (Node cảm biến, chất lượng nước, lưu lượng). Trả về dict rỗng nếu không có dữ liệu.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {
                    "type": "STRING",
                    "description": "Mã định danh của trang trại, ví dụ: 'greenhouse_a'"
                }
            },
            "required": ["farm_key"]
        }
    },
    {
        "name": "get_sensor_history",
        "description": "Truy xuất lịch sử cảm biến theo loại cảm biến và khoảng thời gian. start_date và end_date định dạng YYYY-MM-DD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {
                    "type": "STRING",
                    "description": "Mã định danh của trang trại, ví dụ: 'greenhouse_a'"
                },
                "sensor_type": {
                    "type": "STRING",
                    "description": "Loại cảm biến: 'node', 'water', hoặc 'flow'"
                },
                "start_date": {
                    "type": "STRING",
                    "description": "Ngày bắt đầu, định dạng 'YYYY-MM-DD'"
                },
                "end_date": {
                    "type": "STRING",
                    "description": "Ngày kết thúc, định dạng 'YYYY-MM-DD'"
                }
            },
            "required": ["farm_key", "sensor_type", "start_date", "end_date"]
        }
    },
    {
        "name": "get_recent_system_warnings",
        "description": "Lấy danh sách các thông báo cảnh báo (warning) hoặc lỗi (error) hệ thống gần đây nhất.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "limit": {
                    "type": "INTEGER",
                    "description": "Số lượng thông báo tối đa cần lấy (mặc định 10)"
                }
            }
        }
    },
    {
        "name": "get_active_irrigation_schedules",
        "description": "Lấy danh sách các lịch tưới nước tự động đang hoạt động (trạng thái 'pending' hoặc 'running') của trang trại.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {
                    "type": "STRING",
                    "description": "Mã định danh của trang trại, ví dụ: 'greenhouse_a'"
                }
            },
            "required": ["farm_key"]
        }
    },
    {
        "name": "get_irrigation_history",
        "description": "Truy xuất lịch sử tưới tự động trong một ngày cụ thể (đã xong hoặc lỗi). Dùng để trả lời câu hỏi hôm nay/hôm qua tưới mấy cữ, mỗi cữ bao nhiêu lít.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {"type": "STRING", "description": "Mã trang trại, ví dụ: 'greenhouse_a'"},
                "target_date": {"type": "STRING", "description": "Ngày cần xem, định dạng 'YYYY-MM-DD'"}
            },
            "required": ["farm_key", "target_date"]
        }
    },
    {
        "name": "get_system_mode",
        "description": "Kiểm tra trạng thái vận hành của hệ thống nhà màng đang ở chế độ Auto (tự động) hay Manual (thủ công).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {"type": "STRING", "description": "Mã trang trại, ví dụ: 'greenhouse_a'"}
            },
            "required": ["farm_key"]
        }
    },
    {
        "name": "get_total_water_consumption",
        "description": "Tính tổng lượng nước ĐÃ TIÊU THỤ THỰC TẾ của trang trại (gồm cả bơm tự động lẫn bơm tay) dựa vào đồng hồ lưu lượng tổng.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {"type": "STRING", "description": "Mã trang trại, ví dụ: 'greenhouse_a'"},
                "target_date": {"type": "STRING", "description": "Ngày cần xem, định dạng 'YYYY-MM-DD'"}
            },
            "required": ["farm_key", "target_date"]
        }
    },
    {
        "name": "get_ai_agronomy_suggestion",
        "description": "Lấy khuyến cáo lượng nước tưới từ hệ thống chuyên gia AI nội bộ dựa trên độ ẩm đất hiện tại.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {"type": "STRING", "description": "Mã trang trại, ví dụ: 'greenhouse_a'"}
            },
            "required": ["farm_key"]
        }
    },
    {
        "name": "get_future_schedules",
        "description": "Xem danh sách các lịch tưới ĐÃ ĐƯỢC CÀI ĐẶT cho tương lai (ngày mai, tuần sau...) nhưng chưa chạy.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "farm_key": {"type": "STRING", "description": "Mã trang trại, ví dụ: 'greenhouse_a'"}
            },
            "required": ["farm_key"]
        }
    }
]

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý AI giám sát hệ thống Smart Farm SMIOT. Bạn chỉ được phép đọc thông tin thông qua các công cụ được cung cấp.\n"
    "Tuyệt đối không được bịa đặt (hallucinate) bất kỳ số liệu nào. Nếu không tìm thấy thông tin phù hợp, hoặc dữ liệu trả về từ tool rỗng, "
    "bạn BẮT BUỘC phải trả lời nguyên văn câu: 'Không có dữ liệu phù hợp để trả lời câu hỏi này.'\n"
    "Phân biệt rõ: Lịch sử tưới (irrigation history) chỉ đếm lượng nước bơm bằng chế độ Tự Động. Để tính TỔNG lượng nước dùng thực tế (gồm cả bơm tay), hãy gọi hàm tiêu thụ nước tổng (total water consumption).\n"
    "Nếu dữ liệu trả về từ công cụ có chứa trường 'status' là 'OFFLINE', bạn BẮT BUỘC phải thông báo cho người dùng biết "
    "rằng thiết bị hiện đang mất kết nối và không có dữ liệu thực tế, đồng thời báo thời điểm cuối cùng nhận được tín hiệu (dựa vào trường 'last_seen').\n"
    "Nếu 'status' là 'STALE' thì dữ liệu đã cũ (mẫu mới nhất quá ngưỡng tươi nhưng chưa tới ngưỡng mất kết nối): hãy nói rõ dữ liệu có thể đã cũ và báo 'last_seen'. "
    "Nếu 'status' là 'UNKNOWN' thì chưa có dữ liệu để kết luận, đừng nói thiết bị online.\n"
    "Tuyệt đối không có các công cụ để điều khiển thiết bị hay sửa đổi DB. Nếu người dùng ra lệnh điều khiển thiết bị (ví dụ: bật bơm, tắt đèn) hoặc sửa dữ liệu, "
    "hãy trả lời lịch sự rằng bạn không có quyền thực hiện các hành động điều khiển hoặc sửa đổi hệ thống."
)


@traced("gemini.request", resource="gemini.generateContent")
def _call_gemini_api(payload: dict, obs_tags: dict | None = None) -> dict:
    """Gọi model Gemini Flash-Lite đã kiểm tra Function Calling thành công."""
    if not API_KEY or API_KEY == "chưa_có_điền_sau":
        raise ValueError("Thiếu GEMINI_API_KEY hoặc GOOGLE_API_KEY trong file .env!")
    return _call_gemini_model(payload, "gemini-3.5-flash-lite", obs_tags=obs_tags)


def _call_gemini_model(payload: dict, model: str, obs_tags: dict | None = None) -> dict:
    """Gọi một model Gemini qua GenerateContent và ghi span riêng theo model."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    data = json.dumps(payload).encode("utf-8")
    obs_tags = dict(obs_tags or {})

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
        method="POST"
    )

    with llm_observation(model, "Gemini GenerateContent") as llm_span:
        with trace_span("gemini.generate_content", resource=f"{model}.generateContent",
                        **{"gemini.model": model, "gen_ai.request.model": model, **obs_tags}):
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        if llm_span is not None:
            try:
                from ddtrace.llmobs import LLMObs

                usage = result.get("usageMetadata") or {}
                metrics = {}
                for source_key, target_key in (
                    ("promptTokenCount", "input_tokens"),
                    ("candidatesTokenCount", "output_tokens"),
                    ("totalTokenCount", "total_tokens"),
                ):
                    value = usage.get(source_key)
                    if isinstance(value, (int, float)) and value >= 0:
                        metrics[target_key] = value
                parts = ((result.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                LLMObs.annotate(
                    span=llm_span,
                    input_data={"content_redacted": True, "prompt_character_count": sum(
                        len(str(part.get("text", ""))) for item in payload.get("contents", [])
                        for part in item.get("parts", []) if isinstance(part, dict)
                    )},
                    output_data={
                        "content_redacted": True,
                        "response_character_count": sum(len(str(part.get("text", ""))) for part in parts),
                        "tool_call": any("functionCall" in part for part in parts),
                        "finish_reason": ((result.get("candidates") or [{}])[0].get("finishReason")),
                    },
                    metadata={"model_name": model, "provider": "google", "usage_reported": bool(metrics)},
                    metrics=metrics or None,
                    tags={"service": "smiot-smart-farm", "env": "demo", **obs_tags},
                )
            except Exception as exc:
                # Observability must not fail a farmer's AI request.
                print(f"[OBSERVABILITY] Could not annotate LLMObs usage: {type(exc).__name__}")
        return result


NO_DATA_TEXT = "Không có dữ liệu phù hợp để trả lời câu hỏi này."
AI_MODEL = "gemini-3.5-flash-lite"
AI_STATUSES = ("ok", "no_water", "no_data", "provider_error")


class AIResult(str):
    """Structured AI result that is still a str (the answer text) for old callers.

    Fields: status ok|no_water|no_data|provider_error, amount_ml (float|None),
    reason, model, latency_ms, action ("HOLD" when the provider failed or returned no usable data).
    """

    def __new__(cls, text: str, status: str = "ok", amount_ml: float | None = None, reason: str = "",
                model: str | None = None, latency_ms: float | None = None):
        obj = super().__new__(cls, text)
        obj.status = status
        obj.amount_ml = amount_ml
        obj.reason = reason
        obj.model = model
        obj.latency_ms = latency_ms
        return obj

    @property
    def action(self) -> str:
        if self.status in {"provider_error", "no_data"}:
            return "HOLD"
        return "NO_WATER" if self.status == "no_water" else "NONE"

    def as_dict(self) -> dict:
        return {"status": self.status, "amount_ml": self.amount_ml, "reason": self.reason,
                "model": self.model, "latency_ms": self.latency_ms, "action": self.action,
                "text": str(self)}


def parse_amount_ml(text) -> tuple[float | None, str | None]:
    """(amount_ml, error). amount 0 is valid. (None, None) = not a structured recommendation."""
    if not isinstance(text, str):
        return None, None
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except (TypeError, ValueError):
        return None, None
    if not isinstance(value, dict) or "amount_ml" not in value:
        return None, None
    amount = value.get("amount_ml")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        return None, "invalid_amount_ml"
    return float(amount), None


def classify_ai_text(text: str, model: str | None = None) -> AIResult:
    """Map model output text to an AIResult. 0 ml is no_water, never an error."""
    if text is None or not str(text).strip() or str(text).strip() == NO_DATA_TEXT:
        return AIResult(NO_DATA_TEXT, "no_data", None, "no_data_from_model_or_tools", model)
    amount, err = parse_amount_ml(text)
    if err:
        return AIResult(NO_DATA_TEXT, "no_data", None, err, model)
    if amount is None:
        return AIResult(text, "ok", None, "free_text_answer", model)
    if amount == 0:
        return AIResult(text, "no_water", 0.0, "recommendation_no_irrigation", model)
    return AIResult(text, "ok", amount, "recommendation", model)


def provider_error_result(reason: str, text: str, model: str | None = AI_MODEL) -> AIResult:
    # Record evidence at the existing provider-failure/HOLD decision point.
    # Keep tags fixed-cardinality; reason/model text can vary and is not a tag.
    try:
        from service.datadog_metrics import emit_count
        emit_count("smiot.ai.provider_failure", ["status:provider_error", "action:hold"])
    except Exception:
        pass  # Observability must not change the fail-safe response.
    return AIResult(text, "provider_error", None, reason, model)


def classify_ai_payload(payload: dict) -> dict:
    """Interpret a farm/ai MQTT payload for the UI. Never turns missing/error into 0 ml.

    Returns {status, amount_ml, reason, hold}. any status other than ok/no_water with an amount -> hold=True and no irrigation
    (HOLD is display + publisher rule; the app does not enforce pump commands).
    """
    raw_status = payload.get("ai_status")
    amount = payload.get("amount_ml")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
        amount = None
    if raw_status in ("provider_error", "error"):
        return {"status": "provider_error", "amount_ml": None,
                "reason": str(payload.get("reason") or "ai_provider_error")[:240], "hold": True}
    # Anything other than a clean ok/no_water with a usable amount is HOLD (never irrigate):
    # no_data, timeout, failed, unknown ai_status, or a missing amount.
    if raw_status not in (None, "ok", "no_water", "no_data"):
        return {"status": "provider_error", "amount_ml": None,
                "reason": str(payload.get("reason") or f"ai_status_{raw_status}")[:240], "hold": True}
    if raw_status == "no_data" or amount is None:
        return {"status": "no_data", "amount_ml": None,
                "reason": str(payload.get("reason") or "no_amount_in_payload")[:240], "hold": True}
    if amount == 0:
        return {"status": "no_water", "amount_ml": 0.0,
                "reason": str(payload.get("reason") or "recommendation_no_irrigation")[:240], "hold": False}
    return {"status": "ok", "amount_ml": float(amount),
            "reason": str(payload.get("reason") or "recommendation")[:240], "hold": False}


def ask_ai(user_message: str) -> AIResult:
    """Backward compatible: behaves like the old str answer, plus .status/.amount_ml/.reason/.model/.latency_ms."""
    started = time.monotonic()
    result = _ask_ai_impl(user_message)
    result.latency_ms = round((time.monotonic() - started) * 1000, 1)
    if result.model is None and result.status != "provider_error":
        result.model = AI_MODEL
    try:
        from service.datadog_metrics import emit_count, emit_health_gauge
        status = result.status if result.status in {"ok", "no_water", "no_data", "provider_error"} else "other"
        emit_health_gauge("smiot.ai.ask_latency_ms", result.latency_ms, [f"status:{status}"])
        action = result.action if result.action in {"HOLD", "NO_WATER", "NONE"} else "NONE"
        bounded_tags = [f"status:{status}", f"action:{action}"]
        emit_count("smiot.ai.decision_result", bounded_tags)
        if action == "HOLD":
            emit_count("smiot.ai.safe_fallback", bounded_tags)
        elif status in {"ok", "no_water"}:
            emit_count("smiot.ai.provider_success", bounded_tags)
    except Exception:
        # Observability must not change the application response.
        pass
    return result


def ask_ai_structured(user_message: str) -> dict:
    """Same call as ask_ai but returns the plain dict {status, amount_ml, reason, model, latency_ms, ...}."""
    return ask_ai(user_message).as_dict()


@traced("smiot.ai.ask", resource="ai.ask")
def _ask_ai_impl(user_message: str) -> AIResult:
    """
    Hàm chính xử lý tin nhắn từ Telegram, quyết định gọi tool và trả về câu trả lời cuối cùng.
    """
    if not AI_ENABLED:
        return provider_error_result("ai_disabled", "🤖 Tính năng AI hiện đang tắt. Vui lòng bật AI_ENABLED=true trong file .env để sử dụng.", None)

    if not API_KEY or API_KEY == "chưa_có_điền_sau":
        return provider_error_result("missing_api_key", "⚠️ Chưa cấu hình API Key của AI. Vui lòng thêm GEMINI_API_KEY hoặc GOOGLE_API_KEY vào file .env.", None)

    try:
        # Lấy thời gian hiện tại của hệ thống để làm ngữ cảnh cho AI
        from datetime import datetime
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dynamic_system_instruction = (
            SYSTEM_INSTRUCTION + 
            f"\n\n[CONTEXT] Thời gian hiện tại của hệ thống (local time): {current_time_str}.\n"
            "Hãy luôn dùng thông tin thời gian này để xác định chính xác ngày hôm nay, hôm qua, ngày mai, v.v., "
            "khi cần điền các tham số ngày (ví dụ: target_date, start_date, end_date) cho các công cụ."
        )

        # Chuẩn bị payload ban đầu gửi cho Gemini
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}]
                }
            ],
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
            "systemInstruction": {"parts": [{"text": dynamic_system_instruction}]},
            "generationConfig": {
                "temperature": 0.2
            }
        }

        # Gọi Gemini lần 1
        res = _call_gemini_api(payload)
        
        # Kiểm tra xem Model có yêu cầu gọi Function không
        candidates = res.get("candidates", [])
        if not candidates:
            return AIResult(NO_DATA_TEXT, "no_data", None, "no_candidates", AI_MODEL)

        model_response_content = candidates[0].get("content", {})
        parts = model_response_content.get("parts", [])
        if not parts:
            return AIResult(NO_DATA_TEXT, "no_data", None, "empty_parts", AI_MODEL)

        # Kiểm tra yêu cầu gọi Function Call
        function_call = next(
            (part.get("functionCall") for part in parts if part.get("functionCall")),
            None,
        )
        
        if function_call:
            func_name = function_call.get("name")
            func_args = function_call.get("args", {})
            
            # Kiểm tra xem function có nằm trong whitelist không
            if func_name in FUNCTIONS:
                LOGGER.info("[AI] tool=%s args=%s", func_name, func_args)
                # Thực thi hàm python local
                tool_func = FUNCTIONS[func_name]
                try:
                    with trace_span("smiot.ai.tool", resource=func_name,
                                    **{"ai.tool": func_name, **_observability_tags(func_args)}):
                        tool_result = tool_func(**func_args)
                except Exception as e:
                    LOGGER.warning("[AI] tool execution failed tool=%s error=%s", func_name, _redact(e))
                    tool_result = {}
                
                # Nếu tool trả về rỗng (dict rỗng hoặc list rỗng), ta trả về chuỗi thông báo rỗng cho AI để nó xử lý
                # Nếu kết quả thực sự rỗng, AI sẽ kích hoạt system instruction để trả lời câu mẫu
                
                # Xây dựng payload lần 2 bao gồm lịch sử trò chuyện và kết quả của tool
                function_response = {
                    "name": func_name,
                    "response": {"result": tool_result}
                }
                if function_call.get("id"):
                    function_response["id"] = function_call["id"]

                payload_step2 = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": user_message}]
                        },
                        # Preserve the complete response including Gemini 3 thought signatures.
                        model_response_content,
                        {
                            # Gemini GenerateContent accepts only user/model roles;
                            # function results are sent as a user turn.
                            "role": "user",
                            "parts": [
                                {
                                    "functionResponse": function_response
                                }
                            ]
                        }
                    ],
                    "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
                    "systemInstruction": {"parts": [{"text": dynamic_system_instruction}]},
                    "generationConfig": {
                        "temperature": 0.2
                    }
                }
                
                # Gọi Gemini lần 2
                res_step2 = _call_gemini_api(payload_step2, obs_tags=_observability_tags(func_args))
                candidates_step2 = res_step2.get("candidates", [])
                if candidates_step2:
                    parts_step2 = candidates_step2[0].get("content", {}).get("parts", [])
                    if parts_step2:
                        return classify_ai_text(parts_step2[0].get("text", ""), AI_MODEL)
            else:
                LOGGER.warning("[AI] invalid tool requested: %s", func_name)
                return AIResult(NO_DATA_TEXT, "no_data", None, "invalid_tool_requested", AI_MODEL)
        else:
            # Nếu AI tự trả lời trực tiếp mà không gọi tool
            return classify_ai_text(parts[0].get("text", ""), AI_MODEL)

    except urllib.error.HTTPError as he:
        err_msg = _redact(he.read().decode("utf-8", errors="replace"))
        print(f"[AI] Gemini HTTP error code={he.code} error={err_msg}")
        LOGGER.error("[AI] Gemini HTTP error code=%s error=%s", he.code, err_msg)
        if he.code in (429, 503):
            return provider_error_result(f"http_{he.code}", "⚠️ Gemini đang quá tải tạm thời. Hãy thử lại sau ít phút. (AI lỗi - HOLD, không tưới)")
        if he.code in (401, 403):
            return provider_error_result(f"http_{he.code}", "⚠️ Gemini từ chối API key. Hãy kiểm tra key và quyền truy cập Gemini API. (AI lỗi - HOLD, không tưới)")
        return provider_error_result(f"http_{he.code}", "⚠️ Lỗi kết nối tới dịch vụ AI. Vui lòng kiểm tra lại cấu hình API Key. (AI lỗi - HOLD, không tưới)")
    except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
        LOGGER.error("[AI] Gemini timeout/network error=%s", type(e).__name__)
        return provider_error_result("timeout_or_network", "⚠️ Không kết nối được dịch vụ AI (timeout/mạng). (AI lỗi - HOLD, không tưới)")
    except Exception as e:
        LOGGER.exception("[AI] processing error: %s", _redact(e))
        return provider_error_result(f"exception_{type(e).__name__}", "⚠️ Lỗi xử lý AI. (AI lỗi - HOLD, không tưới)")

    return AIResult(NO_DATA_TEXT, "no_data", None, "no_response_text", AI_MODEL)
