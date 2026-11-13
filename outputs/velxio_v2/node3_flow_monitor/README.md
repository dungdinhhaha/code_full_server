# Node 3 - Do luu luong (device_id `velxio-flow-monitor-01`, node_id `flow`)

## Chan noi (ESP32 DevKit)

| Linh kien | Chan ESP32 |
|---|---|
| Nut FLOW PULSE (xung luu luong) | D27 va GND |
| LED xanh FLOW OK (qua 220) | D23 |
| LED do FLOW ALERT (qua 220) | D22 |
| Buzzer | D21 (noi GND) |

## Thu vien can cai

`PubSubClient`, `ArduinoJson` (ban 7, dung `JsonDocument`). Khong can DHT.
$common
- Telemetry (gui): `smiot/velxio/smiot-course-20261112-a91d4b/sensor/flow`, chu ky 5 s.

## Dong Serial mong doi

- `Flow meter online; pulse button and synthetic fault profiles are enabled.`
- `MQTT ready`
- Moi 5 s: `sample #N profile=normal flow=... pressure=... fault=none`
- Canh bao: `virtual_plc_safety_trip device=velxio-flow-monitor-01 state=ALARM|CLEAR cause=... alarm_led=1|0`
- SET_PROFILE: `DRILL ALERT profile=fault scenario_code=...`, `PROFILE ACK <id> -> fault applied=1 ...`
- Khoi phuc: `DRILL RESTORED ...`; tu dong sau 120 s: `DRILL AUTO_REVERT ...`

## Ma kich ban dap ung

| Ma | Tac dong tren mach |
|---|---|
| A1 (water_overrun) | flow 12 L/phut, ap 0.2 bar, fault=high_flow_leak |
| C10 (pipe_leak) | flow 12 L/phut, ap 0.2 bar, fault=pipe_leak |
| A3 (low_flow) | flow 0.1 L/phut khi bom duoc lenh chay, fault=low_flow |

Bridge chi gui SET_PROFILE toi flow cho A1, A3, C10. Voi A2 mach flow khong nhan lenh.
