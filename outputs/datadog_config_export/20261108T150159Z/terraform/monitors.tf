resource "datadog_monitor" "monitor_339687539" {
  name = "CPU usage is high for host {{host.name}}"
  type = "query alert"
  query = "avg(last_5m):100 - avg:system.cpu.idle{*} by {host} > 90"
  message = "## 🚨 What’s happening\n\nHigh CPU usage detected on host {{host.name}}.\n\nThis means the host is spending most of its time actively processing, with very little idle CPU capacity available. It typically signals that the system is under heavy load — either from intense workloads, misbehaving processes, or increased traffic.\n\n---\n\n## 📈 Impact\n\nIf CPU usage remains high over time, it can lead to:\n\n- Sluggish application and system performance\n- Delayed or stalled background jobs\n- Timeouts, degraded services, or crashes due to resource exhaustion\n\nThis may affect critical applications running on this host and lead to broader service degradation if not addressed promptly.\n\n---\n\n## Runbook\n\n### Initial Troubleshooting Steps\n\n1. **Identify the affected host** from the alert.\n2. Open [**Infrastructure > Host Details**](/infrastructure?tags=host%3A{{host.name}}) in Datadog.\n3. In the **Metrics** tab, examine:\n   - `system.cpu.user`, `system.cpu.system`, `system.cpu.idle`\n   - `process.cpu.total_pct`, `process.*` metrics\n4. Use [**Live Processes**](/process?query=host%3A{{host.name}}) to view real-time CPU usage.\n5. SSH into the host (if needed) and run:\n   ```bash\n   top -o %CPU\n   \n### Cause and Resolution\n\nCause | Resolution\n------|------\nRunaway processes | **Restart or stop** high-CPU processes if they’re stuck or misbehaving.\n------|------\nTraffic/load spike | Scale out or up the infrastructure\n------|------\nCode/deployment issue | Roll back recent changes or investigate further.\n------|------\nContainer/JVM misconfiguration | Tune resource limits and runtime settings\n        \n###  Related links\n\n* [Host Map](/infrastructure/map)\n* [Live Processes](/process?query=host%3A{{host.name}})\n* [System Dashboards](/dashboard/lists)\n* [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n* [Logs](/logs?query=host:{{host.name}})\n* [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n* [Metrics Explorer (system.cpu.idle)](/metric/explorer?exp_metric=system.cpu.idle&exp_scope=host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n### Who should be notified?\n\nAssign the appropriate notification handle for this alert (e.g., `@slack-infra`, `@pagerduty-core-systems`):  \n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 90
  }
}

resource "datadog_monitor" "monitor_339687540" {
  name = "Disk latency is high for host {{host.name}} on device {{device.name}}"
  type = "query alert"
  query = "avg(last_5m):avg:system.io.await{*} by {device} > 500"
  message = "## 🚨 What’s happening\n\nHigh disk I/O wait time detected on host {{host.name}}.\n\nThis means one or more devices on the host are taking a long time to complete disk operations — averaging over 500ms in the last 5 minutes. High I/O wait time typically occurs when the system is frequently waiting for disk reads or writes to finish, often due to storage contention or inefficient disk usage by running processes.\n\n---\n\n## 📈 Impact\n\nIf I/O wait remains high, it can lead to:\n\n- Slower application and system performance, especially for disk-intensive services\n- Delayed job processing or database queries\n- Risk of timeouts or service degradation due to blocked I/O operations\n\nSustained disk latency can have cascading effects on dependent services and degrade user experience.\n\n---\n\n## Runbook\n\n### Initial Troubleshooting Steps\n\n## 🛠 How to fix (Runbook)\n\n### 🔍 Initial troubleshooting\n\n1. Identify the affected host and device from the alert.\n2. Open [**Infrastructure > Host Details**](/infrastructure) for {{host.name}}.\n3. In the **Metrics tab**, examine:\n   - `system.io.await` by device\n   - `system.disk.read_time`, `system.disk.write_time`, `system.disk.in_use`\n4. Use [**Live Processes**](/process) to find I/O-heavy processes.\n5. SSH into the host and run:\n   ```bash\n   iostat -xd 1 3\n   \n### Cause and Resolution\n\nCause | Resolution\n------|------\nDisk-heavy processes | Restart or optimize services with high I/O usage\n------|------\nBackup jobs, ETLs, logging | Schedule or throttle non-critical workloads\n------|------\nUnderlying disk performance | Check for slow or saturated disks, especially on network-attached volumes (e.g., EBS, NFS)\n------|------\nScale-out option | Move I/O-intensive tasks to separate or faster storage tiers\n        \n###  Related links\n\n* [Host Map](/infrastructure/map)\n* [Live Processes](/process?query=host%3A{{host.name}})\n* [System Dashboards](/dashboard/lists)\n* [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n* [Logs](/logs?query=device:{{device.name}})\n* [Metrics Explorer (system.io.await)](/metric/explorer?exp_metric=system.io.await&exp_scope=device:{{device.name}}&exp_agg=avg&exp_type=line)\n\n### Who should be notified?\n\nAssign the appropriate notification handle for this alert (e.g., `@slack-infra`, `@pagerduty-core-systems`):  \n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 500
  }
}

resource "datadog_monitor" "monitor_339687541" {
  name = "Disk usage is high for host {{host.name}} on device {{device.name}}"
  type = "query alert"
  query = "max(next_3d):forecast((1 - avg:system.disk.free{*} by {host,device} / avg:system.disk.total{*} by {host,device}) * 100, \"seasonal\", 1, interval=\"60m\", seasonality=\"weekly\") >= 99"
  message = "## 🚨 What’s happening\n\nLow disk capacity detected on host {{host.name}}.\n\nThis alert indicates that one or more filesystems are **over 90% full**, meaning they are at risk of running out of space for applications to write. If unaddressed, writes will fail and applications may crash. Investigate and free space by deleting or archiving data, or by expanding the volume.\n\n---\n\n## 📈 Impact\n\nWhen disks run out of space, it can result in:\n\n- Applications failing on writes (such as databases, services writing logs, or temp files)\n- Stuck or crashing jobs (logging, backups, compactions, builds)\n- Node instability (for example, kubelet/daemon issues or package updates failing)\n\nSpace exhaustion can quickly degrade services, especially on hosts that handle large volumes of data or critical workloads.\n\n---\n\n## 🛠 How to fix (Runbook)\n\n### 🔍 Initial troubleshooting\n\n1. Identify the affected host and device/mount point from the alert.\n2. Open [**Infrastructure → Host Details**](/infrastructure) for **{{host.name}}**.\n3. In the **Metrics** tab, review:\n   - `system.disk.in_use` (fraction of space used)\n   - `system.disk.total`, `system.disk.used`, `system.disk.free`\n4. SSH into the host to find large directories/files (Linux/macOS):\n   ```bash\n   # Top space consumers by directory (human-readable)\n   sudo du -xhd1 / | sort -h | tail -n 20\n\n   # Top 50 largest files (avoid virtual filesystems)\n   sudo find / -xdev -type f -printf '%s %p\n' 2>/dev/null | sort -nr | head -50\n\n   # Filesystem usage\n   df -h\n   ```\n\n   On systems with `ncdu`:\n\n   ```bash\n   sudo ncdu -x /\n   ```\n\n   For Docker-heavy hosts:\n\n   ```bash\n   docker system df\n   docker ps --filter status=exited --format '{{.ID}}\t{{.Names}}'\n   ```\n\n> ⚠️ Be cautious with deletions. Prefer archiving/moving off-host or rotating/truncating logs using the owning service.\n\n### 🧹 Common causes & resolutions\n\nCause | How to resolve safely\n------|------\nRunaway logs (app, systemd/journal) | Rotate/compress logs; fix log levels. For journald: `journalctl --disk-usage`, then set retention (`/etc/systemd/journald.conf`). For example, `SystemMaxUse=1G`, and `sudo systemctl restart systemd-journald`.\nLeftover build/artifact/temp files | Clean workspace caches and temp dirs (`/tmp`, build caches). Add periodic cleanup to CI or cron.\nOld backups/snapshots on the host | Move backups to object storage; prune old sets per retention policy; avoid storing backups on root volumes.\nContainer images/volumes piling up | Remove unused images/containers/volumes once verified: `docker image prune -a`, `docker container prune`, `docker volume ls` (review before removing).\nApplication data growth (DBs, queues) | Purge/archive old data; enable partitioning/TTL; move cold data to cheaper storage; consider resizing the volume.\nLarge core dumps or crash artifacts | Review & archive off-host; tune core dump settings to limit or disable where appropriate.\n\n\n### 🔗 Related links\n\n* [Host Map](/infrastructure/map)\n* [Live Processes](/process?query=host%3A{{host.name}})\n* [System Dashboards](/dashboard/lists)\n* [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n* [Logs](/logs?query=device:{{device.name}}+host:{{host.name}})\n* [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n* [Metrics Explorer (system.disk.free)](/metric/explorer?exp_metric=system.disk.free&exp_scope=device:{{device.name}},host:{{host.name}}&exp_agg=avg&exp_type=line)\n* [Metrics Explorer (system.disk.total)](/metric/explorer?exp_metric=system.disk.total&exp_scope=device:{{device.name}},host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n### 👥 Who should be notified?\n\nAssign the appropriate notification handle for this alert (for example, `@slack-infra`, `@pagerduty-core-systems`):  \n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 99
    criticalRecovery = 89
  }
}

resource "datadog_monitor" "monitor_339687542" {
  name = "System load is high for host {{host.name}}"
  type = "query alert"
  query = "avg(last_5m):avg:system.load.norm.1{*} by {host} > 1"
  message = "## 🚨 What’s happening\n\nHigh 1-minute load average detected on host {{host.name}}.\n\nThis alert means the system has more processes waiting to run than it can efficiently handle. A high load average often indicates that the host is under significant resource pressure — typically due to CPU saturation, blocked I/O, or memory contention. While some load is normal, consistently high load (especially relative to the number of CPU cores) can signal an unhealthy or overloaded system.\n\n---\n\n## 📈 Impact\n\nIf load remains high, the host may experience:\n\n- Slower system and application performance\n- Backlogged scheduled jobs or delayed processing\n- Increased risk of timeouts, dropped requests, or service degradation\n\nIn environments with strict performance requirements, high load can quickly lead to cascading failures or degraded user experience.\n\n---\n\n## 🛠 How to fix (Runbook)\n\n### 🔍 Initial troubleshooting\n\n1. Identify the affected host from the alert.\n2. Open [**Infrastructure > Host Details**](/infrastructure) for {{host.name}}.\n3. In the **Metrics tab**, examine:\n   - `system.load.1`\n   - `system.cpu.user`, `system.cpu.system`, `system.io.await`, `system.mem.pct_usable`\n4. Use [**Live Processes**](/process) to find CPU- or I/O-heavy processes.\n5. SSH into the host and run:\n   ```bash\n   uptime\n   top -o %CPU\n   \n### Cause and Resolution\n\nCause | Resolution\n------|------\nCPU-bound processes: | Restart or optimize heavy applications\n------|------\nBlocked I/O or memory pressure | Investigate disk or memory bottlenecks\n------|------\nConcurrent workload spikes | Throttle or redistribute jobs across hosts\n------|------\nConfiguration changes | Roll back recent updates or autoscaling settings if related\n\n        \n###  Related links\n\n* [Host Map](/infrastructure/map)\n* [Live Processes](/process?query=host%3A{{host.name}})\n* [System Dashboards](/dashboard/lists)\n* [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n* [Logs](/logs?query=host:{{host.name}})\n* [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n* [Metrics Explorer (system.load.norm.1)](/metric/explorer?exp_metric=system.load.norm.1&exp_scope=host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n### Who should be notified?\n\nAssign the appropriate notification handle for this alert (e.g., `@slack-infra`, `@pagerduty-core-systems`):  \n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 1
  }
}

resource "datadog_monitor" "monitor_339687543" {
  name = "Network traffic (received) is high on host {{host.name}}"
  type = "query alert"
  query = "avg(last_15m):avg:system.net.bytes_rcvd{*} by {host} / (1024 * 1024 * 1024) > 0.08"
  message = "## 🚨 What's happening\n\nHigh **incoming network traffic** detected on host {{host.name}}.\n\nThis means the host is receiving a sustained high volume of data — with the 15-minute average of `system.net.bytes_rcvd` exceeding **80 MB/min**. This typically indicates heavy data ingestion, large transfers, or inefficient service communication patterns.\n\n***\n\n## 📈 Impact\n\nIf network traffic remains elevated, it can lead to:\n\n-   **Bandwidth saturation**, packet loss, or throttling\n-   **Latency or degraded performance** in network-bound services\n-   **Slow log shipping**, delayed data pipelines, or failed syncs\n-   **Contended resources** in multi-tenant environments (e.g., containers)\n\nThis may impact the host's ability to serve real-time workloads or maintain timely communication with external systems, APIs, or databases.\n\n***\n\n## 🛠️ Runbook\n\n### Initial Troubleshooting Steps\n\n1.  **Identify the affected host** from the alert.\n\n2.  Open [**Infrastructure > Host Details**](/infrastructure) in Datadog.\n\n3.  In the **Metrics** tab, examine:\n\n    -   `system.net.bytes_rcvd`, `system.net.bytes_sent`\n    -   Interface metrics (`system.net.iface.*`)\n\n4.  Check application logs for unexpected ingest behavior.\n\n5.  Use tools like `iftop`, `nload`, or `netstat` to inspect top inbound connections.\n\n6.  (If needed) SSH into the host and run:\n\n    ```\n    bash\n    CopyEdit\n    sudo iftop -i <interface>\n    ```\n\n***\n\n### Cause and Resolution\n\n| Cause                                           | Resolution                                                  |\n| ----------------------------------------------- | ----------------------------------------------------------- |\n| Large file transfers (e.g., backups, ingestion) | Schedule during off-peak hours or limit transfer rate       |\n| Misconfigured agents or services                | Review configs and reduce polling or payload size           |\n| Unexpected traffic spike or DDoS                | Block IPs, apply rate limits, or enable network protections |\n| Log/metric flooding from other systems          | Throttle integrations or export rates                       |\n\n***\n\n### 🔗 Related links\n\n-   [Host Map](/infrastructure/map)\n-   [Live Processes](/process)\n-   [System Dashboards](/dashboard/lists)\n-   [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n-   [Logs](/logs?query=host:{{host.name}})\n-   [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n-   [Metrics Explorer (system.net.bytes_rcvd)](/metric/explorer?exp_metric=system.net.bytes_rcvd&exp_scope=host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n***\n\n### 📣 Who should be notified?\n\nPlease assign the appropriate notification handle for this alert (e.g., `@slack-networking`, `@pagerduty-platform-oncall`):\\\n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.08
  }
}

resource "datadog_monitor" "monitor_339687545" {
  name = "Network traffic (sent) is high on host {{host.name}}"
  type = "query alert"
  query = "avg(last_15m):avg:system.net.bytes_sent{*} by {host} / (1024 * 1024 * 1024) > 0.08"
  message = "## 🚨 What's happening\n\nHigh outgoing network traffic detected on host {{host.name}}.\n\nThis means the host is sending a sustained high volume of data — with the 15-minute average of `system.net.bytes_sent` exceeding **80 MB/min**. This typically points to large data exports, logging spikes, backup activity, or misconfigured services.\n\n***\n\n## 📈 Impact\n\nIf network traffic remains elevated, it can lead to:\n\n-   **Bandwidth saturation**, resulting in packet loss or throttling\n-   **Degraded performance** for outbound services like APIs, exporters, or clients\n-   **Delays in data processing**, backups, or inter-service communication\n-   **Resource contention** on shared hosts or virtualized environments\n\nThis may prevent the host from reliably transmitting time-sensitive or critical data, potentially impacting service-level objectives.\n\n***\n\n## Runbook\n\n### Initial Troubleshooting Steps\n\n1.  **Identify the affected host** from the alert.\n\n2.  Open [**Infrastructure > Host Details**](/infrastructure) in Datadog.\n\n3.  In the **Metrics** tab, examine:\n\n    -   `system.net.bytes_sent`, `system.net.bytes_rcvd`\n    -   Interface metrics (`system.net.iface.*`)\n\n4.  Check application logs or exporters for spikes in outbound traffic.\n\n5.  Use tools like `iftop`, `nload`, or `netstat` to inspect top outbound connections.\n\n6.  (If needed) SSH into the host and run:\n\n    ```\n    bash\n    CopyEdit\n    sudo iftop -i <interface>\n    ```\n\n### Cause and Resolution\n\n| Cause                                            | Resolution                                      |\n| ------------------------------------------------ | ----------------------------------------------- |\n| Large data exports (e.g., backups, log shipping) | Schedule exports off-peak or throttle bandwidth |\n| Misconfigured services flooding traffic          | Review configs and reduce payloads or frequency |\n| Traffic spike from application behavior          | Add caching or batching; review architecture    |\n| Third-party abuse or unintended syncs            | Audit external endpoints and restrict access    |\n\n***\n\n### Related links\n\n-   [Host Map](/infrastructure/map)\n-   [Live Processes](/process)\n-   [System Dashboards](/dashboard/lists)\n-   [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n-   [Logs](/logs?query=host:{{host.name}})\n-   [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n-   [Metrics Explorer (system.net.bytes_sent)](/metric/explorer?exp_metric=system.net.bytes_sent&exp_scope=host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n***\n\n### Who should be notified?\n\nPlease assign the appropriate notification handle for this alert (e.g., `@slack-networking`, `@pagerduty-platform-oncall`):\\\n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.08
  }
}

resource "datadog_monitor" "monitor_339687546" {
  name = "Memory space is low for host {{host.name}}"
  type = "query alert"
  query = "avg(last_5m):avg:system.mem.pct_usable{*} by {host} < 0.1"
  message = "## 🚨 What's happening\n\nLow available memory detected on host {{host.name}}.\n\nThis means the host has less than **10% usable memory** on average over the last 5 minutes, based on the `system.mem.pct_usable` metric. This typically indicates that applications or services are consuming most of the RAM, leaving little room for new processes or memory-intensive operations.\n\n***\n\n## 📈 Impact\n\nIf memory remains low, it can lead to:\n\n-   **Slower application performance** due to increased paging or swapping\n-   **Crashes or restarts** of services that can’t allocate enough memory\n-   **System instability** or degraded responsiveness under load\n-   **Failure of background jobs** or scheduled tasks\n\nThis may impact key services running on the host and disrupt user-facing or backend operations.\n\n***\n\n## Runbook\n\n### Initial Troubleshooting Steps\n\n1.  **Identify the affected host** from the alert.\n\n2.  Open [**Infrastructure > Host Details**](/infrastructure) in Datadog.\n\n3.  In the **Metrics** tab, examine:\n\n    -   `system.mem.pct_usable`, `system.mem.total`, `system.mem.used`\n    -   `process.mem.rss`, `process.mem.real`, or specific memory-hungry processes\n\n4.  Use [**Live Processes**](/process) to check which processes are using the most memory.\n\n5.  SSH into the host and run:\n\n    ```\n    bash\n    CopyEdit\n    top -o %MEM\n    ```\n\n***\n\n### Cause and Resolution\n\n| Cause                                      | Resolution                                                |\n| ------------------------------------------ | --------------------------------------------------------- |\n| Memory leaks or runaway processes          | Restart or stop problematic processes                     |\n| Memory-intensive workloads                 | Scale up memory capacity or move workloads to other nodes |\n| Background jobs or batch tasks overlapping | Stagger or reschedule heavy memory consumers              |\n| Misconfigured applications or JVMs         | Tune memory settings (e.g., heap size, buffers)           |\n\n***\n\n### Related links\n\n-   [Host Map](/infrastructure/map)\n-   [Live Processes](/process)\n-   [System Dashboards](/dashboard/lists)\n-   [Monitor Documentation](https://docs.datadoghq.com/monitors/)\n-   [Logs](/logs?query=host:{{host.name}})\n-   [Infrastructure](/infrastructure/hosts?scope=host:{{host.name}})\n-   [Metrics Explorer (system.mem.pct_usable)](/metric/explorer?exp_metric=system.mem.pct_usable&exp_scope=host:{{host.name}}&exp_agg=avg&exp_type=line)\n\n***\n\n### Who should be notified?\n\nPlease assign the appropriate notification handle for this alert (e.g., `@slack-infra`, `@pagerduty-core-systems`):\\\n`@your-team-handle`"
  tags = ["integration:host","monitor_pack:host"]
  priority = null
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.1
  }
}

resource "datadog_monitor" "monitor_339977691" {
  name = "SMIOT | greenhouse_a Node 2 soil humidity flatline (synthetic demo)"
  type = "query alert"
  query = "max(last_2m):max:smiot.telemetry.sensor_flatline{farm:greenhouse_a,node:2,source:smiot_demo_stream} > 0"
  message = "{{#is_alert}}\r\nMongo-backed detector observed 10 fresh Node 2 soil-humidity readings with range <= 0.01 over the recent window. This indicates the greenhouse_a telemetry stream is flatlined; it does not prove a physical probe failure. Inspect sample freshness, MQTT bridge, and Mongo persistence before action. The attached workflow can only place the virtual output in SAFE HOLD; it cannot command physical pumps or PLCs.\r\n[Open correlated Node 2 logs](https://app.datadoghq.com/logs?query=service%3Asmiot-smart-farm%20%40farm.key%3Agreenhouse_a%20%40node.id%3A2%20%40source%3Asmiot_demo_stream)\r\n@workflow-smiot-node-2-safe-mode-hold-and-verify\r\n{{/is_alert}}\r\n{{#is_recovery}}\r\nThe Mongo-backed flatline signal returned to 0. The application recovery verifier checks monitor state, fresh varying Node 2 MongoDB samples, the acknowledged HOLD record, and virtual PLC acknowledgement. It sends CLEAR only when every check passes; simulated pump outputs must remain OFF. This proves telemetry recovery, not physical sensor repair.\r\n[Open correlated Node 2 logs](https://app.datadoghq.com/logs?query=service%3Asmiot-smart-farm%20%40farm.key%3Agreenhouse_a%20%40node.id%3A2%20%40source%3Asmiot_demo_stream)\r\n{{/is_recovery}}"
  tags = ["project:smiot","farm:greenhouse_a","node:2","source:smiot_demo_stream","scenario:flatline"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0
  }
}

resource "datadog_monitor" "monitor_339977703" {
  name = "SMIOT | greenhouse_a telemetry stale"
  type = "query alert"
  query = "max(last_5m):max:smiot.telemetry.sample_age_seconds{farm:greenhouse_a,source:smiot_demo_stream} by {node} > 120"
  message = "Telemetry sample age exceeds 120 seconds. Check Wokwi source, MQTT broker, bridge, app persistence, and MongoDB in that order. Keep pumps in safe HOLD when sensor data is stale."
  tags = ["project:smiot","farm:greenhouse_a","source:smiot_demo_stream","scenario:stale-data"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 120
  }
}

resource "datadog_monitor" "monitor_339978300" {
  name = "Watchdog Anomaly: {{event.title}} for {{service}}"
  type = "event-v2 alert"
  query = "events(\"source:watchdog (story_category:apm)\").rollup(\"count\").by(\"story_key\").last(\"30m\") > 0"
  message = "{{event.title}} detected on {{event.tags.service}}\n {{event.text}}"
  tags = ["$service","$env","product:apm","monitor_pack:apm"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0
  }
}

resource "datadog_monitor" "monitor_339985452" {
  name = "[operation:fastapi.request] High Error Rate on {{service.name}}"
  type = "query alert"
  query = "min(last_15m):sum:trace.fastapi.request.errors{span.kind IN (server,consumer)}by{env,service}.as_rate() / sum:trace.fastapi.request.hits{span.kind IN (server,consumer)}by{env,service}.as_rate() > 0.1"
  message = "Service {{service.name}} has a high error rate on operation fastapi.request for env {{env.name}}.\n\n### About this monitor\n**This monitor has been automatically generated by Datadog.**"
  tags = ["monitor_pack:apm"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.1
  }
}

resource "datadog_monitor" "monitor_339990226" {
  name = "SMIOT | MongoDB dependency unhealthy"
  type = "query alert"
  query = "min(last_5m):min:smiot.dependency.mongo.up{*} < 1"
  message = "{{#is_alert}}MongoDB dependency check is unhealthy. Inspect the correlated app logs and pymongo spans. Do not restart or delete data automatically.{{/is_alert}}\n\n{{#is_no_data}}No Mongo health signal. Check app and watchdog before attributing failure to MongoDB.{{/is_no_data}}\n\n{{#is_recovery}}MongoDB health signal recovered. Verify a new telemetry document and its timestamp in the Time Series collection.{{/is_recovery}}"
  tags = ["service:smiot-smart-farm","env:demo","component:mongodb","source:app_healthcheck","managed_by:codex"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 1
  }
}

resource "datadog_monitor" "monitor_339990232" {
  name = "SMIOT | MQTT dependency unhealthy"
  type = "query alert"
  query = "min(last_5m):min:smiot.dependency.mqtt.up{*} < 1"
  message = "{{#is_alert}}MQTT dependency check is unhealthy. Check broker connectivity, MQTT handler logs, then verify whether the telemetry source itself is online. Do not restart a physical pump.{{/is_alert}}\n\n{{#is_no_data}}No MQTT health signal. Check app and watchdog heartbeat.{{/is_no_data}}\n\n{{#is_recovery}}MQTT health recovered. Confirm a new MQTT message was persisted in MongoDB before closing.{{/is_recovery}}"
  tags = ["service:smiot-smart-farm","env:demo","component:mqtt","source:app_healthcheck","managed_by:codex"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 1
  }
}

resource "datadog_monitor" "monitor_339992811" {
  name = "[operation:websocket.close] High Error Rate on {{service.name}}"
  type = "query alert"
  query = "min(last_15m):sum:trace.websocket.close.errors{span.kind IN (server,consumer)}by{env,service}.as_rate() / sum:trace.websocket.close.hits{span.kind IN (server,consumer)}by{env,service}.as_rate() > 0.1"
  message = "Service {{service.name}} has a high error rate on operation websocket.close for env {{env.name}}.\n\n### About this monitor\n**This monitor has been automatically generated by Datadog.**"
  tags = ["monitor_pack:apm"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.1
  }
}

resource "datadog_monitor" "monitor_339992812" {
  name = "[operation:websocket.receive] High Error Rate on {{service.name}}"
  type = "query alert"
  query = "min(last_15m):sum:trace.websocket.receive.errors{span.kind IN (server,consumer)}by{env,service}.as_rate() / sum:trace.websocket.receive.hits{span.kind IN (server,consumer)}by{env,service}.as_rate() > 0.1"
  message = "Service {{service.name}} has a high error rate on operation websocket.receive for env {{env.name}}.\n\n### About this monitor\n**This monitor has been automatically generated by Datadog.**"
  tags = ["monitor_pack:apm"]
  priority = null
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0.1
  }
}

resource "datadog_monitor" "monitor_340356283" {
  name = "SMIOT | EC2 app service inactive"
  type = "query alert"
  query = "avg(last_5m):avg:systemd.unit.active{host:i-00bf2d3591d3ee0a2,unit:smiot.service} <= 0"
  message = "{{#is_alert}}\r\nEC2 server incident: smiot.service is inactive on i-00bf2d3591d3ee0a2. New farm data and the melon harvest estimate may stop updating.\r\nCheck EC2 and Datadog Agent health, then inspect SMIOT logs/APM and MongoDB/MQTT dependencies. Do not restart MongoDB or operate pumps.\r\nRecovery action is restricted to smiot.service, guarded by a local health check, cooldown and HTTP verification.\r\n@workflow-Dũng-Nov-04-2026-1601\r\n{{/is_alert}}\r\n{{#is_recovery}}\r\nsmiot.service is active again. Confirm app health, a successful trace and a newer telemetry record persisted in MongoDB before closing the incident.\r\n{{/is_recovery}}"
  tags = ["project:smiot","env:demo","service:smiot-smart-farm"]
  priority = 2
  include_tags = false
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0
  }
}

resource "datadog_monitor" "monitor_341409441" {
  name = "[SMIOT][Ca 1] UI bao OFFLINE nhung mau van vao MongoDB (status mismatch)"
  type = "query alert"
  query = "max(last_5m):max:smiot.telemetry.status_mismatch{*} by {farm,node} > 0"
  message = "@workflow-smiot-ca1-refuse-restart  Ca 1 - bao offline sai. Metric smiot.telemetry.status_mismatch > 0 nghia la trang thai node hien thi/tinh trong app la OFFLINE trong khi MongoDB van nhan mau moi (mau moi hon nguong stale).\n\nKHONG RESTART smiot.service khi mau MongoDB con moi: app dang song va dang ghi du lieu, restart se mat bang chung va co the lam mat phien. Workflow guard phai TU CHOI restart trong truong hop nay.\n\nDieu tra:\n1. So sanh smiot.telemetry.sample_age_seconds (nguon MongoDB) voi trang thai node tren UI cung farm/node: {{farm.name}} / {{node.name}}.\n2. Neu smiot.external.sample_age_seconds < nguong stale: du lieu dang vao -> loi nam o logic hien thi/cache trang thai, khong phai o luong du lieu.\n3. Ghi lai: thoi diem Alert, ma ca, farm/node, khoang thoi gian lech, so mau da vao trong khoang do (Aggregation Pipeline).\n\nKhong dung monitor nay de ket luan thiet bi vat ly hong. Du lieu la tong hop (synthetic).\n\n{{#is_alert}}Mismatch dang xay ra. Nguoi truc: xac minh mau Mongo moi, KHONG restart.{{/is_alert}}\n{{#is_recovery}}Trang thai UI da khop lai voi MongoDB. Ghi thoi diem Recovered vao ho so ca.{{/is_recovery}}"
  tags = ["service:smiot-smart-farm","env:demo","project:smiot","scenario:false-offline"]
  priority = 3
  include_tags = true
  notify_no_data = false
  new_host_delay = 300
  monitor_thresholds {
    critical = 0
  }
}
