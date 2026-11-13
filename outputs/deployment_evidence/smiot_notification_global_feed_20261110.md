# Datadog workflow notifications in the SMIOT home feed

**Date:** 2026-11-10 (UTC)

## Change

- The home overview previously queried only notifications with a farm key among the farms visible to the user. Datadog workflow notices intentionally have no farm association, so the MongoDB records were saved but omitted from the 10-farm event feed.
- Added a separate MongoDB query for notifications with a missing or empty `farm_key`. These render as **Toàn hệ thống** and are not linked to a farm. Farm-scoped notices retain their existing farm labels and navigation.
- Demo-seed notices remain excluded.

## Verification

- Focused `unittest` for unscoped notice selection and attribution: passed (1 test; executed by the implementation agent before its session ended).
- The deployed module checksum matched the staged local module and remote `py_compile` passed before replacement.
- SSM single-file deployment command completed successfully at **2026-11-10T05:03:01Z** (response code 0). It replaced only `pages/farm_overview_component.py` and restarted only `smiot.service`.
- Live `/healthz` at **2026-11-10T05:10:59Z**: app `ok`, MongoDB `ok`, MQTT `ok`, newest sample age `12.2` seconds.
- Live Home at **2026-11-10T05:10:46Z** showed **2 open incidents · 30 notifications**. It displayed the successful W1 workflow notification and prior W1 smoke notification under **Toàn hệ thống**, with no farm misattribution.
- The bell and feed remain different views: the top bell is process-local state, while the 10-farm feed is queried from MongoDB. This change fixes the latter.

## Remaining Datadog limits

- W3 is published with its monitor trigger and `DryRun=false`, but remains **pending/unknown** after SSM submission. No W3 command was run in this change; a successful SSM command submission is not proof of command completion or app recovery.
- W6 still has no monitor because a fresh `smiot.detector.heartbeat` datapoint has not been verified in the Datadog metric query. A corrected direct API canary was accepted and registered in metric metadata, but its datapoint was not query-visible by **2026-11-10T04:54:28Z**.
- Do not claim the full 10-workflow set is Level 5 until W3 recovery verification and W6 live detector telemetry are closed. Several other monitors also remain without live datapoints.

