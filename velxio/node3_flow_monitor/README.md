# Velxio Node 3 — Flow monitor

ESP32 + flow pulse button + green FLOW OK LED + red FLOW ALERT LED + buzzer. The circuit runs firmware in Velxio and publishes synthetic water-flow telemetry over MQTT to the SMIOT bridge.

- Normal profile: pulse input produces measured flow; pump state follows command feedback.
- Fault profile: an incident-scoped `SET_PROFILE` command selects a water-flow fault dataset. Scenario A1/A2/A3 changes flow and pressure readings and lights the alert LED. This simulates telemetry; it does not claim a physical pipe fault.
- Recovery profile: a correlated command selects `normal`; the app needs a verified ACK and a fresh normal sample before calling it recovered.

Dependencies: `PubSubClient`, `ArduinoJson`.
