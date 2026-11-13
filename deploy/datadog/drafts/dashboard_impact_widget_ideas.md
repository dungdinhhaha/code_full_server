# Ý tưởng widget cho dashboard "Impact" (BẢN NHÁP, chưa tạo trên Datadog)

Quy ước: **Có** = query chạy được với metric/log đang tồn tại; **Cần metric mới** = chưa có nguồn dữ liệu, ghi rõ metric cần phát.
Không đặt con số mục tiêu hay tuyên bố SLO; widget chỉ hiển thị số đo thật của các lần chạy đã ghi hồ sơ.

| # | Widget | Loại | Query / nguồn | Trạng thái |
|---|---|---|---|---|
| 1 | Tuổi mẫu mới nhất (trong app) | timeseries | `max:smiot.telemetry.sample_age_seconds{$farm} by {node}` | Có |
| 2 | Tuổi mẫu mới nhất (probe ngoài) | timeseries | `max:smiot.external.sample_age_seconds{service:smiot-smart-farm} by {farm}` | Có sau khi cài `smiot-external-probe.timer` |
| 3 | App up theo probe ngoài | query_value / check | `min:smiot.external.app_up{service:smiot-smart-farm,env:demo}` | Có sau khi cài probe |
| 4 | Thời gian phát hiện (MTTD) mỗi ca | table | Alert time (monitor event) trừ thời điểm bắt đầu sự cố; đọc từ hồ sơ `*_EVIDENCE.md` | Cần metric mới: `smiot.incident.detect_seconds{case}` (gauge, phát khi ghi hồ sơ) hoặc nhập tay từ hồ sơ |
| 5 | Thời gian vào trạng thái an toàn (HOLD / start đã verify) | table | `action_ledger` (HOLD acknowledged) hoặc log guard `action:start result:verified` trừ Alert time | Cần metric mới: `smiot.incident.safe_state_seconds{case}`; log guard `source:smiot-recovery` có sẵn timestamp |
| 6 | Số lần guard chạy start | query_value (logs) | Logs: `service:smiot-smart-farm source:smiot-recovery event:smiot.guarded_recovery @action:start` count | Có |
| 7 | Số lần guard TỪ CHỐI restart | query_value (logs) | `... @action:none @result:refused*` count | Có |
| 8 | Số lần restart nhầm = 0 | query_value | Định nghĩa: số `action:start` mà ngay trước đó tuổi mẫu Mongo < ngưỡng. Hiện log không ghi tuổi mẫu | Cần log field mới: `sample_age_seconds_before` trong bản ghi guard (nhánh G2 đề xuất). Hiển thị "0" chỉ khi trường này tồn tại và đã đối chiếu |
| 9 | Giờ dữ liệu không đáng tin | query_value | Tổng thời gian `smiot.telemetry.fresh == 0` hoặc `sensor_flatline == 1`: `sum:smiot.telemetry.sensor_flatline{$farm}.as_count()` x chu kỳ 30 s (xấp xỉ) | Một phần có (flatline, fresh); chuẩn hoá cần metric mới `smiot.telemetry.untrusted{node,reason}` |
| 10 | Mismatch UI vs MongoDB (Ca 1) | timeseries | `max:smiot.telemetry.status_mismatch{*} by {farm,node}` | Cần metric mới `smiot.telemetry.status_mismatch` (app phát khi trạng thái hiển thị = OFFLINE mà mẫu Mongo còn mới) |
| 11 | Timeline workflow thực thi | list/events | Events của workflow EC2 và Node 2 (execution, kết quả script) | Có (ghi chú: chỉ ghi kết quả script; chưa có log stop riêng) |
| 12 | Dependency | query_value | `min:smiot.dependency.mongo.up{*}`, `min:smiot.dependency.mqtt.up{*}` | Có (đã có trên dashboard nkc-685-vw8) |

## Lưu ý khi dựng thật
- Tag env hiện không nhất quán: metric telemetry `env:production`, dependency/monitor `env:demo` (theo baseline A1). Query widget nên lọc theo `service`/`project` hoặc thống nhất env trước.
- Không đưa `incident_id` hoặc `message_id` vào tag metric (cardinality). Dùng log/trace facet `@incident.id`.
- Widget 4, 5, 8, 10 cần thay đổi app/ghi hồ sơ; nếu chưa có, hiển thị "chưa đo" thay vì số ước tính.
