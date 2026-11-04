#!/usr/bin/env bash
# Datadog Private Action Runner entry point.
# Remediate only a stopped SMIOT web service. Never restart the host, MongoDB,
# Mosquitto, the Datadog Agent, or an app process that is already running.
set -Eeuo pipefail
umask 077

service='smiot.service'
health_url='http://127.0.0.1:8080/login'
runtime_dir='/run/smiot-recovery'
lock_file="$runtime_dir/lock"
cooldown_file="$runtime_dir/last_action_epoch"
cooldown_seconds=300
telemetry_max_age_ms=180000
recovery_log='/opt/smiot/logs/recovery/guarded_recovery.jsonl'

emit() {
  local action="$1" result="$2" reason="$3" run_id="$4"
  local timestamp
  timestamp="$(date -u +%FT%TZ)"
  local line
  line="$(printf '{"event":"smiot.guarded_recovery","run_id":"%s","action":"%s","result":"%s","reason":"%s","service":"%s","timestamp":"%s"}' \
    "$run_id" "$action" "$result" "$reason" "$service" "$timestamp")"
  printf '%s\n' "$line"
  if [[ -d "$(dirname "$recovery_log")" && -w "$(dirname "$recovery_log")" ]]; then
    printf '%s\n' "$line" >> "$recovery_log" 2>/dev/null || true
  fi
  logger -t smiot-recovery -- "event=smiot.guarded_recovery run_id=$run_id action=$action result=$result reason=$reason service=$service timestamp=$timestamp" 2>/dev/null || true
}

http_healthy() {
  curl -fsS --connect-timeout 2 --max-time 4 -o /dev/null "$health_url"
}

unit_state() {
  systemctl is-active "$1" 2>/dev/null || true
}

mongo_latest_timestamp_ms() {
  # The runner user must not be able to read the app's secret environment file.
  # This root-owned helper performs one read-only query and returns only its timestamp.
  sudo -n /usr/local/sbin/smiot-recovery-mongo-readback
}

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"

# No action if a preceding systemd restart policy or operator already restored it.
if http_healthy; then
  emit none verified_healthy already_healthy "$run_id"
  exit 0
fi

# Let systemd's Restart=on-failure policy settle before deciding anything.
sleep 5
if http_healthy; then
  emit none verified_healthy systemd_recovered_before_action "$run_id"
  exit 0
fi

app_state="$(unit_state "$service")"
if [[ "$app_state" == active ]]; then
  # An active process with a failed endpoint is ambiguous (event loop, route,
  # config, or downstream issue). Restarting would erase evidence and may not fix it.
  mongo_state="$(unit_state mongod.service)"
  mqtt_state="$(unit_state mosquitto.service)"
  disk_used="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
  emit none refused_app_process_active_healthcheck_failed "app=active,mongodb=$mongo_state,mqtt=$mqtt_state,root_disk_percent=$disk_used" "$run_id"
  exit 2
fi

if [[ "$app_state" != inactive && "$app_state" != failed ]]; then
  emit none refused_unexpected_app_unit_state "app=$app_state" "$run_id"
  exit 2
fi

# The sole permitted action is a guarded start of a stopped app service.
disk_used="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
if [[ ! "$disk_used" =~ ^[0-9]+$ ]] || (( disk_used >= 85 )); then
  emit none refused_host_disk_pressure "root_disk_percent=${disk_used:-unknown},limit=85" "$run_id"
  exit 2
fi

mongo_state="$(unit_state mongod.service)"
mqtt_state="$(unit_state mosquitto.service)"
if [[ "$mongo_state" != active ]]; then
  emit none refused_mongodb_not_active "mongodb=$mongo_state" "$run_id"
  exit 2
fi
if [[ "$mqtt_state" != active ]]; then
  emit none refused_mqtt_not_active "mqtt=$mqtt_state" "$run_id"
  exit 2
fi

if ! baseline_ms="$(mongo_latest_timestamp_ms 2>/dev/null)" || [[ ! "$baseline_ms" =~ ^[0-9]+$ ]]; then
  emit none refused_mongodb_readback_failed mongo_ping_or_telemetry_read_failed "$run_id"
  exit 2
fi

exec 9>"$lock_file"
if ! flock -n 9; then
  emit none skipped another_recovery_is_running "$run_id"
  exit 0
fi

now_s="$(date +%s)"
if [[ -f "$cooldown_file" ]]; then
  last_s="$(cat "$cooldown_file" 2>/dev/null || printf '0')"
  if [[ "$last_s" =~ ^[0-9]+$ ]] && (( now_s - last_s < cooldown_seconds )); then
    emit none skipped start_cooldown_active "$run_id"
    exit 0
  fi
fi

printf '%s\n' "$now_s" > "$cooldown_file"
if ! sudo -n /usr/bin/systemctl start "$service"; then
  emit start failed systemd_start_command_failed "$run_id"
  exit 3
fi

app_ready=false
for _ in $(seq 1 30); do
  if [[ "$(unit_state "$service")" == active ]] && http_healthy; then
    app_ready=true
    break
  fi
  sleep 2
done
if [[ "$app_ready" != true ]]; then
  emit start failed app_or_http_healthcheck_failed "$run_id"
  exit 4
fi

# Verify the end-to-end persistence path, not just the systemd process.
for _ in $(seq 1 18); do
  current_ms="$(mongo_latest_timestamp_ms 2>/dev/null || printf '0')"
  if [[ "$current_ms" =~ ^[0-9]+$ ]] && (( current_ms > baseline_ms )); then
    now_ms="$(date +%s%3N)"
    age_ms=$(( now_ms - current_ms ))
    if (( age_ms >= 0 && age_ms <= telemetry_max_age_ms )); then
      emit start verified app_http_and_fresh_mongodb_telemetry "$run_id"
      exit 0
    fi
  fi
  sleep 5
done

emit start unverified no_new_fresh_mongodb_telemetry_within_90_seconds "$run_id"
exit 5
