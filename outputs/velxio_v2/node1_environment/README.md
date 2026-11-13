# Node 1 - Moi truong (device_id `velxio-node1`, node_id `node1`)

## Chan noi (ESP32 DevKit)

| Linh kien | Chan ESP32 |
|---|---|
| DHT22 VCC / SDA / GND | 3V3 / D4 (GPIO4) / GND |
| Bien tro dat (soil) VCC / SIG / GND | 3V3 / D34 / GND |
| LED do CLIMATE ALERT (qua dien tro 220) | D23 |
| Buzzer | D22 (noi GND) |

## Thu vien can cai

`DHT sensor library` (Adafruit), `PubSubClient`, `ArduinoJson` (ban 7, dung `JsonDocument`).
Neu Velxio khong tim thay `DHT.h`, thu `DHT sensor library for ESPx`.
$common
- Telemetry (gui): `smiot/velxio/smiot-course-20261112-a91d4b/sensor/node1`, chu ky 10 s.

## Dong Serial mong doi

- `Node 1 started; waiting for sensor and MQTT.`
- `MQTT connected; profile commands active`
- Moi 10 s: mot dong JSON (`farm_key`, `at`, `ah`, `st`, `sh`, `sec`, `alert`, `profile`, `scenario_code`...) roi `MQTT publish OK`
- Khi nhan SET_PROFILE fault: `DRILL ALERT profile=fault scenario_code=... scenario_run_id=...`, `DRILL OUTPUT LED23=HIGH BUZZER22=beep700Hz ...`, `PROFILE ACK ...`
- Khoi phuc: `DRILL RESTORED ...`; tu dong sau 120 s: `DRILL AUTO_REVERT ...`
- Loi cam bien: `DHT22 read failed; sample omitted ...`

## Ma kich ban dap ung

| Ma | Tac dong tren mach |
|---|---|
| S1 (soil_flatline) | sh = 8 (dat kho), LED do bat |
| S2 (soil_spike) | sh = 95 |
| S3 (soil_out_of_range) | sh = 0 (do am dat ket o 0%) |
| C2 | at 39, ah 88, sec 3.8 (VPD ngoai dai), LED do bat |
| C6 | at 39, ah 88, sec 3.8 (EC nuoc thoat tang), LED do bat |

Bridge chi gui SET_PROFILE toi node1 cho S2, S3, C2, C6 (va ma cu W8/vpd_ec_risk, khong co trong catalog). Ma khac: profile `fault` mac dinh at 38, ah 82, sh 12.
