"""Classify failed schedule_logs using SQLite records, schedules, notifications, and code rules.

Reads the database read-only and writes a row-level CSV plus a summary Markdown
report under reports/. Classifications distinguish direct evidence from likely
auto-fail records and unresolved rows; they do not assert physical pump failure.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
NOTICE_ID = re.compile(r"Lịch tưới\s+#(\d+)")

CATEGORY_INFO = {
    "missed_schedule_notification": (
        "Confirmed by a matching schedule error notification",
        "High",
    ),
    "silent_missed_schedule_likely": (
        "Schedule ID, expected start, and target match; failed more than 2 hours after due; consistent with silent auto-fail path",
        "Likely, code-consistent",
    ),
    "missed_schedule_candidate_unconfirmed": (
        "Schedule ID, expected start, and target match; failed 10 minutes to 2 hours after due, but no matching notification found",
        "Possible, not confirmed",
    ),
    "schedule_timestamp_anomaly_unverified": (
        "Schedule ID, expected start, and target match, but end timestamp is before due or within 10 minutes of due",
        "Unverified anomaly",
    ),
    "failed_without_end_timestamp": (
        "Failed row has no end timestamp; startup code marks prior running logs failed without filling end_at, but this row's prior state is unavailable",
        "Unverified; startup-recovery candidate",
    ),
    "unverified_schedule_or_notification_mismatch": (
        "No exact schedule metadata match and no schedule error notification matched this schedule ID",
        "Unverified",
    ),
}


def parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=str(ROOT / "farm_data.db"), help="SQLite database to inspect (read-only).")
    args = parser.parse_args()

    db_path = Path(args.sqlite).resolve()
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        raw_notices = connection.execute(
            "SELECT message FROM notifications WHERE category = 'schedule' AND severity = 'error'"
        ).fetchall()
        noticed_ids = {
            int(match.group(1))
            for row in raw_notices
            if (match := NOTICE_ID.search(row["message"] or ""))
        }
        rows = connection.execute(
            """
            SELECT sl.id, sl.schedule_id, sl.farm_key, sl.start_at, sl.end_at,
                   sl.target_water, sl.actual_water, sl.status,
                   s.schedule_date, s.start_time, s.water_amount, s.status AS schedule_status
            FROM schedule_logs AS sl
            LEFT JOIN schedules AS s ON s.id = sl.schedule_id
            WHERE lower(sl.status) = 'failed'
            ORDER BY sl.id
            """
        ).fetchall()
        end_counts = Counter(row["end_at"] for row in rows if row["end_at"] is not None)
    finally:
        connection.close()

    classified: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    schedule_match_count = 0
    for row in rows:
        schedule_id = row["schedule_id"]
        has_notice = bool(schedule_id is not None and int(schedule_id) in noticed_ids)
        expected_start = None
        schedule_match = False
        delay_minutes: float | None = None

        if schedule_id is not None and row["schedule_date"] and row["start_time"]:
            expected_start = f"{row['schedule_date']} {row['start_time']}"
            start_at = str(row["start_at"] or "")
            amount_match = row["target_water"] == row["water_amount"]
            schedule_match = start_at[:16] == expected_start[:16] and amount_match
            if schedule_match:
                schedule_match_count += 1
                due = parse_time(expected_start)
                ended = parse_time(row["end_at"])
                if due and ended:
                    delay_minutes = round((ended - due).total_seconds() / 60, 2)

        if has_notice:
            category = "missed_schedule_notification"
        elif row["end_at"] is None:
            category = "failed_without_end_timestamp"
        elif schedule_match and delay_minutes is not None and delay_minutes > 120:
            category = "silent_missed_schedule_likely"
        elif schedule_match and delay_minutes is not None and delay_minutes > 10:
            category = "missed_schedule_candidate_unconfirmed"
        elif schedule_match:
            category = "schedule_timestamp_anomaly_unverified"
        else:
            category = "unverified_schedule_or_notification_mismatch"

        evidence, confidence = CATEGORY_INFO[category]
        counts[category] += 1
        classified.append(
            {
                "log_id": row["id"],
                "schedule_id": row["schedule_id"],
                "farm_key": row["farm_key"],
                "start_at": row["start_at"],
                "end_at": row["end_at"],
                "target_water": row["target_water"],
                "actual_water": row["actual_water"],
                "schedule_status_now": row["schedule_status"],
                "schedule_expected_start": expected_start,
                "matches_schedule_start_and_target": schedule_match,
                "minutes_after_expected_start": delay_minutes,
                "end_at_group_size": end_counts.get(row["end_at"], 0) if row["end_at"] else 0,
                "matching_schedule_error_notification": has_notice,
                "classification": category,
                "confidence": confidence,
                "evidence": evidence,
            }
        )

    REPORT_DIR.mkdir(exist_ok=True)
    csv_path = REPORT_DIR / "schedule_logs_failed_classification.csv"
    md_path = REPORT_DIR / "schedule_logs_failed_analysis.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(classified[0].keys()) if classified else [])
        writer.writeheader()
        writer.writerows(classified)

    labels = {
        "missed_schedule_notification": "Có notification xác nhận lịch bị bỏ lỡ do hệ thống offline",
        "silent_missed_schedule_likely": "Khả năng cao app tự đánh failed im lặng (>2 giờ trễ; khớp lịch và lượng nước)",
        "missed_schedule_candidate_unconfirmed": "Khớp lịch, trễ 10 phút–2 giờ nhưng không tìm thấy notification tương ứng",
        "schedule_timestamp_anomaly_unverified": "Timestamp bất thường (trước giờ lịch hoặc trong 10 phút đầu)",
        "failed_without_end_timestamp": "Thiếu end_at; có thể là log running cũ bị đổi trạng thái khi khởi động",
        "unverified_schedule_or_notification_mismatch": "Không khớp lịch hiện tại và không có notification đối chiếu",
    }
    notification_count = len(noticed_ids)
    lines = [
        "# Phân loại `schedule_logs` có trạng thái `failed`",
        "",
        f"- SQLite nguồn: `{db_path.name}` (mở chỉ đọc).",
        f"- Tổng số dòng được phân loại: **{len(classified)}**.",
        f"- Có {notification_count} mã lịch riêng biệt trong notification `schedule/error`; mã được nối với log khi `schedule_id` trùng.",
        f"- Có **{schedule_match_count}** log khớp đồng thời `schedule_date + start_time` và `water_amount` của bảng `schedules` hiện tại.",
        "- Bằng chứng `notification` xác nhận lịch bị bỏ lỡ/offline; nó **không chứng minh bơm vật lý đã chạy hay hỏng**.",
        "- `auto_fail_missed_schedules()` đặt failed cho lịch pending quá 10 phút; nếu trễ hơn 2 giờ thì code không gửi notification. Vì vậy nhóm im lặng được ghi là *likely*, không gọi là sự cố thiết bị đã xác minh.",
        "- `init_db()` đổi các log còn `running` thành `failed` nhưng không điền `end_at`; các dòng thiếu thời gian kết thúc không thể xác định chắc trạng thái trước lần khởi động.",
        "- Không tính `failure rate`; tập dữ liệu không đủ chứng minh mọi dòng `failed` là một lỗi phần cứng độc lập.",
        "",
        "| Phân loại | Số dòng | Mức kết luận |",
        "|---|---:|---|",
    ]
    for key, label in labels.items():
        lines.append(f"| {label} | {counts[key]} | {CATEGORY_INFO[key][1]} |")
    lines += [
        "",
        "## Cách đọc file CSV",
        "",
        "Mỗi `log_id` có một dòng riêng. Các cột `matches_schedule_start_and_target`, `minutes_after_expected_start`, `end_at_group_size` và `matching_schedule_error_notification` cho biết vì sao dòng được xếp vào nhóm đó. File không sửa SQLite.",
        "",
        "## Cách diễn giải an toàn",
        "",
        "Chỉ báo cáo số notification về lịch bị bỏ lỡ/offline như số sự kiện được ghi log; không đổi tên chúng thành số lần bơm hỏng. Không gộp 272 log `failed` thành tổng số sự cố, và không dùng tỷ lệ phần trăm failure nếu chưa có thêm log thiết bị/feedback để xác minh.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"failed_rows={len(classified)}")
    print("categories=" + ", ".join(f"{key}:{counts[key]}" for key in labels))
    print(f"csv={csv_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
