#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${EUID}" -ne 0 ]]; then echo "must run as root" >&2; exit 2; fi
systemctl disable --now velxio-bridge.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/velxio-bridge.service /etc/smiot/velxio.env
systemctl daemon-reload
echo "SMIOT_VELXIO_ROLLBACK_OK wokwi_untouched=true smiot_untouched=true"
