# RULES — Non-negotiable project rules

1. Preserve pre-existing user edits; inspect `git status` before editing or deployment. Do not reset, checkout, clean, or rewrite unrelated files.
2. Never read, print, commit, or paste secrets from `.env`, EC2 env files, credentials, API keys, connection strings, tokens, ARNs, or account identifiers. Reference secret variable names only.
3. Simulated means simulated. No claim of physical sensor, pump, valve, yield gain, cost savings, or field agronomy validation without direct evidence.
4. No cloud-triggered action substitutes for local PLC/interlock safety. No pump/valve/fan hardware command in development or demo.
5. Never use arbitrary shell/API/MQTT inputs from an external scenario request. Allowlist farm/scenario/device; use the separately provisioned admin-controlled bearer token and enforce rate, concurrency, idempotency, and bounded runtime.
6. Restart the smallest justified service. Never reboot EC2 or restart MongoDB/MQTT as a generic repair. W4 must prove refusal with no command invocation.
7. Recovery status is evidence-driven: command accepted ≠ ACK; process active ≠ data restored; HTTP 200 alone ≠ pipeline healthy. Unknown checks stay `unverified`.
8. App “recovered” notification is sent only after the verifier succeeds. On verifier failure, report `unverified` and preserve the open incident.
9. One incident/run/command identity must correlate metric-adjacent logs/traces, Mongo evidence, workflow, and app message. Do not join a lot or farm without a real relationship in data.
10. Metrics use bounded dimensions. Put IDs in log/span/Mongo fields, not unbounded metric tags.
11. Before writing Datadog configuration, verify US1 org and target resource. Never write through an API/MCP connector that resolves to a different organization.
12. Bits automatic-investigation toggle is configuration only; it is not proof of a completed investigation. Do not deliberately alert production-like monitors without an explicitly safe drill window.
13. For W6, do not claim detector isolation while heartbeat thread shares the app process. Monitor metric producer, tags, query, enabled flag, and EC2 deployment must all match.
14. Do not call any case Level 5 until the same incident has evidence for detection, multi-source investigation, guarded action/refusal, correlated ACK/readback, fresh recovery proof, and final notification.
15. Label generated or seeded telemetry as synthetic in source/evidence. Never splice unrelated drills into one story.
16. Keep docs truthful: mark `local code`, `deployed`, `metric observed`, `workflow run`, and `end-to-end proof` separately.
