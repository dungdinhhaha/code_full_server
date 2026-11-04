import logging
from logging.handlers import RotatingFileHandler
import os
import json
from datetime import datetime, timezone

# Đảm bảo thư mục logs tồn tại
os.makedirs("logs", exist_ok=True)

# Định dạng chuẩn cho log hệ thống
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 1. System Handler (Log mọi thứ từ INFO trở lên)
file_handler = RotatingFileHandler(
    'logs/system.log', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# 2. Error Handler (Chỉ log WARNING, ERROR, CRITICAL)
class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.WARNING

error_handler = RotatingFileHandler(
    'logs/error.log', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.WARNING)
error_handler.addFilter(ErrorFilter())

# Ghi log ra console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

def get_logger(name: str):
    """
    Khởi tạo và cấu hình logger với tên chỉ định (ví dụ: 'SCHEDULE', 'MQTT', 'SYSTEM').
    """
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(error_handler)
        logger.addHandler(console_handler)
        logger.propagate = False
    return logger

# 3. Access Logger riêng cho web
access_formatter = logging.Formatter(
    '[%(asctime)s] [ACCESS] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
access_handler = RotatingFileHandler(
    'logs/access.log', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8'
)
access_handler.setFormatter(access_formatter)
access_handler.setLevel(logging.INFO)

def get_access_logger():
    """
    Logger chuyên biệt cho Access web (HTTP Requests)
    """
    logger = logging.getLogger("ACCESS")
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        logger.addHandler(access_handler)
        # Tùy chọn: có thể không in access log ra console nếu sợ rác
        # logger.addHandler(console_handler) 
        logger.propagate = False
    return logger


def log_incident_event(
    *,
    incident_id: str | None,
    farm_key: str,
    node_id: int,
    kind: str,
    **fields,
) -> None:
    """Write an incident event as a JSON log with queryable Datadog attributes.

    Keep this stream separate from the human-readable application logs so the
    Datadog Agent's JSON parser can index correlation dimensions as attributes.
    """
    logger = logging.getLogger("smiot.incident.json")
    if not logger.handlers:
        os.makedirs("logs", exist_ok=True)
        handler = RotatingFileHandler(
            "logs/incident_events.jsonl",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.propagate = False

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "service": os.getenv("DD_SERVICE", "smiot-smart-farm"),
        "env": os.getenv("DD_ENV", "demo"),
        "event": "smiot_incident_event",
        "kind": str(kind),
        "incident": {"id": str(incident_id)} if incident_id else None,
        "farm": {"key": str(farm_key)},
        "node": {"id": int(node_id)},
        **fields,
    }
    logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str))
