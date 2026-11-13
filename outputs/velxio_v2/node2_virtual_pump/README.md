# Node 2 - Bom ao (device_id `velxio-virtual-pump-01`, node_id `node2`)

## Chan noi (ESP32 DevKit, moi LED qua dien tro 220 ve GND)

| Dau ra | Chan ESP32 |
|---|---|
| PUMP bit0 .. bit6 (LED xanh) | D23, D22, D21, D19, D18, D17, D16 |
| SAFE HOLD (LED do) | D25 |
| Buzzer | D26 (noi GND) |

## Thu vien can cai

`PubSubClient`, `ArduinoJson` (ban 7, dung `JsonDocument`). Khong can DHT.
$common

## Dong Serial mong doi

- `Virtual pump controller starting; all outputs are LEDs, no physical pump.`
- `MQTT connected; actuator command subscription active.`
- Lenh output: `ACK <command_id>; virtual pumps on=N/7, safe_hold=0|1`
- Doi trang thai an toan: `virtual_plc_safety_trip device=velxio-virtual-pump-01 state=HOLD|CLEAR cause=... hold_led=.. pumps_on=..`
- SET_PROFILE: `DRILL ALERT profile=fault scenario_code=...`, `PROFILE ACK <id> -> fault applied=1 sent=1 ...; pumps remain OFF`
- A4: `ACK_SUPPRESSED command_id=... scenario_code=A4 ...` (khong gui ACK, khong beep)
- Khoi phuc: `DRILL RESTORED ...`; tu dong sau 120 s: `DRILL AUTO_REVERT ...`

## Ma kich ban dap ung

| Ma | Tac dong tren mach |
|---|---|
| A1 (water_overrun) | Node 2 vao fault: SAFE HOLD, 7 LED tat (flow cung nhan lenh) |
| A2 (pump_pressure_zero) | SAFE HOLD bat, tat ca dau ra = 0, 2 tieng beep thap |
| A4 (command_no_ack) | Van ap dung lenh nhung KHONG gui ACK va khong beep, khong bat HOLD |

Bridge chi gui SET_PROFILE toi node2 cho A1, A2, A4.
