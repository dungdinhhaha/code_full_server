"""
service/ai_service.py — AI Assistant Service using Gemini API
─────────────────────────────────────────────────────────────
Giao tiếp với Gemini API thông qua HTTP REST để xử lý hội thoại.
Hỗ trợ Function Calling (Whitelist Tools) để truy xuất dữ liệu từ DB.
"""
import os
import json
import urllib.request
import urllib.error
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
    "Tuyệt đối không có các công cụ để điều khiển thiết bị hay sửa đổi DB. Nếu người dùng ra lệnh điều khiển thiết bị (ví dụ: bật bơm, tắt đèn) hoặc sửa dữ liệu, "
    "hãy trả lời lịch sự rằng bạn không có quyền thực hiện các hành động điều khiển hoặc sửa đổi hệ thống."
)


@traced("gemini.request", resource="gemini.generateContent")
def _call_gemini_api(payload: dict) -> dict:
    """Gọi model Gemini Flash-Lite đã kiểm tra Function Calling thành công."""
    if not API_KEY or API_KEY == "chưa_có_điền_sau":
        raise ValueError("Thiếu GEMINI_API_KEY hoặc GOOGLE_API_KEY trong file .env!")
    return _call_gemini_model(payload, "gemini-3.5-flash-lite")


def _call_gemini_model(payload: dict, model: str) -> dict:
    """Gọi một model Gemini qua GenerateContent và ghi span riêng theo model."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
        method="POST"
    )

    with llm_observation(model, "Gemini GenerateContent") as llm_span:
        with trace_span("gemini.generate_content", resource=f"{model}.generateContent",
                        **{"gemini.model": model, "gen_ai.request.model": model}):
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
                    tags={"service": "smiot-smart-farm", "env": "demo"},
                )
            except Exception as exc:
                # Observability must not fail a farmer's AI request.
                print(f"[OBSERVABILITY] Could not annotate LLMObs usage: {type(exc).__name__}")
        return result


@traced("smiot.ai.ask", resource="ai.ask")
def ask_ai(user_message: str) -> str:
    """
    Hàm chính xử lý tin nhắn từ Telegram, quyết định gọi tool và trả về câu trả lời cuối cùng.
    """
    if not AI_ENABLED:
        return "🤖 Tính năng AI hiện đang tắt. Vui lòng bật AI_ENABLED=true trong file .env để sử dụng."

    if not API_KEY or API_KEY == "chưa_có_điền_sau":
        return "⚠️ Chưa cấu hình API Key của AI. Vui lòng thêm GEMINI_API_KEY hoặc GOOGLE_API_KEY vào file .env."

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
            return "Không có dữ liệu phù hợp để trả lời câu hỏi này."
            
        model_response_content = candidates[0].get("content", {})
        parts = model_response_content.get("parts", [])
        if not parts:
            return "Không có dữ liệu phù hợp để trả lời câu hỏi này."

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
                print(f"🧠 [AI] Gọi tool: {func_name} với đối số: {func_args}")
                # Thực thi hàm python local
                tool_func = FUNCTIONS[func_name]
                try:
                    with trace_span("smiot.ai.tool", resource=func_name, **{"ai.tool": func_name}):
                        tool_result = tool_func(**func_args)
                except Exception as e:
                    print(f"❌ [AI] Lỗi thực thi tool {func_name}: {e}")
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
                res_step2 = _call_gemini_api(payload_step2)
                candidates_step2 = res_step2.get("candidates", [])
                if candidates_step2:
                    parts_step2 = candidates_step2[0].get("content", {}).get("parts", [])
                    if parts_step2:
                        return parts_step2[0].get("text", "Không có dữ liệu phù hợp để trả lời câu hỏi này.")
            else:
                print(f"⚠️ [AI] Cảnh báo: AI cố gắng gọi tool không hợp lệ: {func_name}")
                return "Không có dữ liệu phù hợp để trả lời câu hỏi này."
        else:
            # Nếu AI tự trả lời trực tiếp mà không gọi tool
            return parts[0].get("text", "Không có dữ liệu phù hợp để trả lời câu hỏi này.")

    except urllib.error.HTTPError as he:
        err_msg = he.read().decode("utf-8")
        print(f"❌ [AI] HTTP Error calling Gemini: {he.code} - {err_msg}")
        if he.code in (429, 503):
            return "⚠️ Gemini đang quá tải tạm thời. Hãy thử lại sau ít phút."
        if he.code in (401, 403):
            return "⚠️ Gemini từ chối API key. Hãy kiểm tra key và quyền truy cập Gemini API."
        return "⚠️ Lỗi kết nối tới dịch vụ AI. Vui lòng kiểm tra lại cấu hình API Key."
    except Exception as e:
        print(f"❌ [AI] Lỗi xử lý AI: {e}")
        return "Không có dữ liệu phù hợp để trả lời câu hỏi này."

    return "Không có dữ liệu phù hợp để trả lời câu hỏi này."
