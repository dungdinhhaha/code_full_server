# Nhánh guard của workflow phục hồi (BẢN NHÁP, chưa tạo trên Datadog)

Mục đích: workflow chỉ được làm hành động nhỏ nhất, và phải TỪ CHỐI khi dữ liệu cho thấy app đang ghi mẫu.
Phần đã có trong `scripts/aws/smiot-recover-guarded.sh` được đánh dấu `[có sẵn]`; phần chưa có trong script được đánh dấu `[đề xuất]`
(cần chủ sở hữu script bổ sung; file này không sửa script).

```yaml
workflow: smiot-guarded-recovery            # tên nháp
trigger:
  - monitor 340356283 (systemd.unit.active smiot.service)       # có sẵn
  - monitor Ca 3 bổ sung smiot.external.app_up < 1              # nháp, xem monitor_ca3_external_app_down.json
rate_limit: 1 / 60s                                              # có sẵn trên workflow EC2
guard:
  # Thứ tự đánh giá. Điều kiện đầu tiên khớp quyết định kết quả.
  - id: G0_already_healthy                  # [có sẵn]
    if: "HTTP healthy"
    then: {action: none, result: verified_healthy, reason: already_healthy}
  - id: G1_systemd_grace                    # [có sẵn]
    if: "HTTP healthy sau 5 s chờ Restart=on-failure"
    then: {action: none, result: verified_healthy, reason: systemd_recovered_before_action}
  - id: G2_fresh_sample_refuse              # [đề xuất]
    if: "tuổi mẫu mới nhất trong MongoDB < SAMPLE_FRESH_MAX_SECONDS"
    params: {SAMPLE_FRESH_MAX_SECONDS: 90}   # cùng mức SMIOT_TELEMETRY_STALE_SECONDS; chốt lại bằng dữ liệu thực
    then: {action: none, result: refused, reason: fresh_samples_still_arriving_do_not_restart}
    note: "Ca 1: app/ingest đang sống, lỗi nằm ở trạng thái hiển thị. TỪ CHỐI restart."
  - id: G3_app_active_refuse                # [có sẵn]
    if: "smiot.service active nhưng HTTP lỗi"
    then: {action: none, result: refused_app_process_active_healthcheck_failed, exit: 2}
  - id: G4_unexpected_state_refuse          # [có sẵn]
    if: "unit không phải inactive/failed"
    then: {action: none, result: refused_unexpected_app_unit_state}
  - id: G5_dependencies                     # [có sẵn]
    require: [disk < 85%, mongod active, mosquitto active, MongoDB readback OK]
    else: {action: none, result: refused_<lý do>}
  - id: G6_lock_and_cooldown                # [có sẵn]
    require: [flock thành công, "now - last_action >= 300 s"]
    else: {action: none, result: skipped_<lý do>}
  - id: G7_start_only                       # [có sẵn]
    action: "systemctl start smiot.service"  # KHÔNG restart, KHÔNG đụng mongod/mosquitto/agent/EC2
verify:                                     # [có sẵn]
  require_all:
    - systemd active
    - HTTP 200
    - "mẫu MongoDB MỚI hơn baseline và tuổi <= 180 s"
  else: {result: unverified, exit: 5}
evidence_log: /opt/smiot/logs/recovery/guarded_recovery.jsonl   # source smiot-recovery
never: [restart EC2, restart mongod, restart mosquitto, restart datadog-agent, restart app đang chạy]
```

## Nguyên tắc diễn giải
- `result=verified` chỉ khi có mẫu MongoDB mới sau lúc start. Lệnh `systemctl start` thành công chưa phải phục hồi.
- Mọi từ chối ghi một dòng JSONL; dùng làm bằng chứng "không restart nhầm" (số restart nhầm = số dòng `action=start` mà trước đó mẫu còn mới = 0).
- Bits chưa xác nhận phục hồi: ghi `bits_confirmed: false` trong hồ sơ cho đến khi có investigation kết luận.
- Ghi nhớ cooldown 300 s: nếu drill lặp lại trong 5 phút, kết quả `skipped_start_cooldown_active` là hành vi đúng, không phải lỗi.
