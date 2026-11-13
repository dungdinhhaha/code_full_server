#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Safe, reversible Velxio installation. It never removes or replaces Wokwi.
# Run on EC2 only after the source has been uploaded to /opt/smiot.

APP_ROOT="${SMIOT_APP_ROOT:-/opt/smiot}"
ENV_FILE="/etc/smiot/velxio.env"
UNIT_FILE="/etc/systemd/system/velxio-bridge.service"
CHANNEL="${SMIOT_VELXIO_CHANNEL:-smiot-course-20261112-a91d4b}"
ENABLE="${SMIOT_VELXIO_ENABLE:-false}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "must run as root" >&2
  exit 2
fi
if [[ ! -f "${APP_ROOT}/scripts/velxio_mqtt_bridge.py" ]]; then
  echo "missing ${APP_ROOT}/scripts/velxio_mqtt_bridge.py" >&2
  exit 3
fi
if [[ ! "${CHANNEL}" =~ ^[A-Za-z0-9_-]{1,64}$ ]]; then
  echo "invalid Velxio channel" >&2
  exit 4
fi

install -d -m 0750 -o smiot -g smiot /etc/smiot
install -m 0644 -o root -g root "${APP_ROOT}/deploy/systemd/velxio-bridge.service" "${UNIT_FILE}"
cat > "${ENV_FILE}" <<ENV
# Synthetic Velxio demo only. Do not put credentials here.
SMIOT_VELXIO_CHANNEL=${CHANNEL}
VELXIO_CHANNEL=${CHANNEL}
VELXIO_FARM_KEY=greenhouse_j
SMIOT_VELXIO_SOURCE=velxio_synthetic
ENV
chown root:smiot "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

systemctl daemon-reload
systemctl disable --now velxio-bridge.service >/dev/null 2>&1 || true
if [[ "${ENABLE}" == "true" ]]; then
  systemctl enable --now velxio-bridge.service
  systemctl is-active --quiet velxio-bridge.service
  echo "VELXIO_BRIDGE_ENABLED channel=${CHANNEL} wokwi_untouched=true"
else
  systemctl disable velxio-bridge.service >/dev/null 2>&1 || true
  echo "VELXIO_BRIDGE_INSTALLED_DISABLED channel=${CHANNEL} wokwi_untouched=true"
fi

echo "SMIOT_HEALTH=$(curl -fsS --max-time 5 http://127.0.0.1:8080/healthz | tr '\n' ' ' | cut -c1-240 || true)"
echo "SMIOT_VELXIO_INSTALL_OK"
