# HUONG DAN dan Velxio v2

Ba project Velxio (node1, node2, flow) giu nguyen mach cu; chi thay file `sketch.ino`. Moi thu muc co README.md liet ke chan noi va thu vien.

## Thu tu thuc hien (lam lan luot tung project)

1. Mo project Velxio, xoa toan bo noi dung sketch cu, dan noi dung file `sketch.ino` tuong ung:
   - node1 moi truong: `node1_environment\sketch.ino`
   - node2 bom ao: `node2_virtual_pump\sketch.ino`
   - node3 do luu luong: `node3_flow_monitor\sketch.ino`
2. Kiem tra thu vien: node1 can `DHT sensor library`, `PubSubClient`, `ArduinoJson`; node2 va flow can `PubSubClient`, `ArduinoJson`.
3. Bam Compile/Bien dich, doi bao thanh cong.
4. Bam Run. Mo Serial Monitor (115200) va xac nhan co dong `MQTT connected` (node1/node2) hoac `MQTT ready` (flow).
5. Doi dong dau tien: node1 va flow in mau do moi 10 s / 5 s; node2 chi in khi co lenh.

Broker `broker.hivemq.com:1883`, kenh `smiot-course-20261112-a91d4b`, farm_key `greenhouse_j` da dat san trong sketch; khong sua.

## Ma kich ban tac dong len mach nao

| Ma | Mach nhan SET_PROFILE | Hien tuong |
|---|---|---|
| S2 | node1 | do am dat 95, LED do |
| S3 | node1 | do am dat ket o 0%, LED do |
| C2 | node1 | at 39, ah 88 (VPD ngoai dai), LED do |
| C6 | node1 | sec 3.8 (EC nuoc thoat tang), LED do |
| A1 | node2 va flow | node2 SAFE HOLD; flow 12 L/phut |
| A2 | node2 | SAFE HOLD, dau ra = 0 |
| A3 | flow | flow 0.1 L/phut khi bom chay |
| A4 | node2 | khong gui ACK (Serial: ACK_SUPPRESSED) |
| C10 | flow | flow 12 L/phut, ap 0.2 bar |

Mach tu tro ve normal sau 120 s neu khong co lenh normal (`DRILL AUTO_REVERT`).

Bridge `scripts\velxio_mqtt_bridge.py` can dang chay voi cung kenh va farm_key thi lenh moi toi mach.
