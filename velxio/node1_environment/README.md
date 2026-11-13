# Velxio Node 1 Environment

Local snapshot of the public Velxio project `a652dc2a-b9f0-4923-8e82-4624509fc39f`.

- `sketch.ino` is the Node 1 firmware snapshot from the successful live run, using the modeled DHT22 on GPIO 4 and the Adafruit DHT library.
- `circuit.json` records the ESP32 board, modeled components, wiring, and installed libraries. The DHT22 data line remains on D4.
- DHT22 reads are validated before publishing. Invalid readings are omitted; no fallback sensor values are used.
- Soil temperature and EC remain explicitly synthetic demo values; the soil potentiometer remains the changing analog input.

The current sketch snapshot includes nonblocking Wi-Fi/MQTT reconnect diagnostics and a 512-byte MQTT buffer. The verified run read DHT22 values of 29.0 °C and 72.0% RH and published successfully every 10 seconds. EC2 read-back recorded the latest `greenhouse_j` telemetry with `source=velxio_synthetic`, `air_temp=29.0`, and `air_hum=72.0`.
