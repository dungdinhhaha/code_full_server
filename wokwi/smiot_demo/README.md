# Wokwi SMIOT demo

Starter project for ESP32 + DHT22 + potentiometer soil input + a Node 2 fault switch + virtual status LEDs.

## What it demonstrates

- The potentiometer supplies changing synthetic soil humidity; DHT22 supplies virtual air temperature and humidity.
- Slide switch left holds Node 2 soil humidity at 2.4%; slide switch right resumes changing readings.
- The ESP32 automatically publishes one daily photo-capture event every 15 seconds (one accelerated simulated day). The lot progresses through sowing, seedling, vegetative, flowering/fruiting, and harvest—one stage per simulated day, then stays at harvest while daily events continue.
- The blue LED flashes at each scheduled event, which is published to the `.../traceability` MQTT topic. The event contains lot ID, farm key, simulated day, stage, and synthetic image asset/panel reference. Wokwi does not take a real image and the bridge does not send image bytes; it forwards metadata that points to the generated JPEG already stored by the app.
- The generated image asset is `static/device_images/smiot_melon_growth_contact_sheet.jpg`; it is one five-panel illustrative image, not five separately captured image files.
- ESP32 publishes both nodes to a unique demo topic on the public HiveMQ MQTT broker.
- The local SMIOT bridge forwards those readings to `farm/sensor`; the existing app stores them in MongoDB and emits the same Datadog metrics used by the dashboard/monitor. It relays stage metadata to `farm/traceability/event`; the app stores one idempotent MongoDB event per simulated lot/day and the `/traceability` page displays the selected lot's stage timeline using the corresponding panel of the stored JPEG.
- The bridge watches successful executions of the Node 2 Datadog monitor workflow and sends a retained `HOLD` command to Wokwi. When the monitor returns to OK, it sends `CLEAR`.
- Red LED = safe hold; green LED = virtual output available. Both are simulation indicators. No physical pump, PLC, or inverter is attached.

## Create the Wokwi project

1. Start a new ESP32 project at [Wokwi](https://wokwi.com/projects/new/esp32).
2. Replace `sketch.ino` and `diagram.json` with the files in this folder; add `libraries.txt`.
3. Start the simulation. The initial slide switch position is fault-injected (left), so Node 2 emits 2.4% every 10 seconds.

The channel in the sketch is `greenhouse-a-7f38c2d1`. Keep it identical to `WOKWI_CHANNEL` in the local `.env` if you override the default. This is a public, unauthenticated demo broker, so publish synthetic values only and do not put secrets in the sketch.

## Run locally

### Run with Wokwi CLI (no browser extension required)

The Wokwi CLI and ESP32 firmware build are already set up on the development PC. To run the cloud simulation:

1. Create a Wokwi CI token in the [Wokwi CI dashboard](https://wokwi.com/dashboard/ci). Do not put it in chat or commit it to a file.
2. In PowerShell, run. To read a `WOKWI_CLI_TOKEN=...` assignment from a local file, add `-TokenFile` with that file's path; the token value is never printed:

   ```powershell
   cd 'D:\IOT Trung\code_full_server'
   .\wokwi\smiot_demo\run-wokwi.ps1 -TokenFile 'C:\path\to\wokwi-token.env'
   ```

3. If you omit `-TokenFile`, paste the token at the hidden prompt. The script runs the ESP32 simulation and clears the token from the process environment when it exits.
4. To stop the simulation, press `Ctrl+C`.

The CLI uses Wokwi's cloud simulation service, so an internet connection and an active Wokwi CI token are required. The simulation can run without the SMIOT app/bridge, but telemetry will reach the app only when the app, local MQTT broker, and bridge described below are running.

1. Ensure the SMIOT app and local Mosquitto broker are already running, and the app is subscribed to `farm/sensor`.
2. Add these non-secret settings to the project `.env` if needed:

   ```dotenv
   WOKWI_CHANNEL=greenhouse-a-7f38c2d1
   WOKWI_MQTT_HOST=broker.hivemq.com
   WOKWI_MQTT_PORT=1883
   MQTT_HOST=127.0.0.1
   MQTT_PORT=1883
   ```

3. Run the local bridge in a separate PowerShell window:

   ```powershell
   cd 'D:\IOT Trung\code_full_server'
   py -3.12 -X utf8 scripts\wokwi_datadog_bridge.py
   ```

   The bridge reads `DD_API_KEY`, `DD_APP_KEY`, and `DD_SITE` from the project `.env`. It does not print key values.
4. Start the Wokwi simulation. Wait for the monitor to evaluate the five-minute flatline. A successful Datadog workflow run turns the red SAFE HOLD LED on and green virtual output off.
5. Move the Node 2 fault switch right. After the monitor recovers to OK, red turns off and green turns on.

The public broker has no authentication or delivery guarantee. This project is for a synthetic demo only. For a private or physical deployment, replace it with an authenticated TLS broker and require an explicit human safety interlock before any real actuator command.

### Demo the traceability page without Wokwi

If Wokwi CLI cannot connect, keep the SMIOT app and local MQTT broker running and publish a complete five-stage synthetic lot through the app's MQTT handler:

```powershell
cd 'D:\IOT Trung\code_full_server'
py -3.12 -X utf8 scripts\demo_traceability.py
```

By default, the script publishes 150 events (15 simulated days for each of 10 lots) to `farm/traceability/event`, waits for the app to persist them, and verifies the event IDs in MongoDB. Then open the authenticated app at `/traceability` and choose any `melon-lot-local-demo-*` lot. Use `--lots 5 --days 7` for a smaller set. Re-running updates the same lot/day records instead of creating duplicates. All timestamps and images remain explicitly synthetic.
