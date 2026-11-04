"""Continuously emit an explicitly synthetic, accelerated GDD demo series.

This is isolated from live telemetry and must not be presented as a real crop
or harvest forecast. It keeps the demo forecast monitor fed after the initial
recent-history seed ages out of Datadog's default timestamp acceptance window.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METRIC = "smiot.demo.crop.gdd_cumulative"
TAGS_BASE = [
    "farm:greenhouse_a",
    "cohort:synthetic_accelerated_demo",
    "source:synthetic",
]


def submit(api_key: str, api_host: str, values: dict[int, float]) -> None:
    now = int(time.time())
    series = [
        {
            "metric": METRIC,
            "type": 3,
            "points": [{"timestamp": now, "value": value}],
            "tags": TAGS_BASE + [f"node:{node_id}"],
        }
        for node_id, value in sorted(values.items())
    ]
    request = urllib.request.Request(
        f"https://{api_host}/api/v2/series",
        data=json.dumps({"series": series}).encode("utf-8"),
        method="POST",
        headers={
            "DD-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in (200, 202):
            raise RuntimeError(f"Datadog metric intake returned HTTP {response.status}")


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=60, help="Seconds between synthetic points (minimum 30).")
    parser.add_argument("--node1-start", type=float, default=458.0)
    parser.add_argument("--node2-start", type=float, default=505.0)
    parser.add_argument("--node1-step", type=float, default=2.0)
    parser.add_argument("--node2-step", type=float, default=2.5)
    args = parser.parse_args()
    if args.interval < 30:
        parser.error("--interval must be at least 30 seconds")

    api_key = os.getenv("DD_API_KEY")
    if not api_key:
        parser.error("DD_API_KEY is missing from the project .env")
    site = os.getenv("DD_SITE", "datadoghq.com").strip()
    api_host = site if site.startswith("api.") else f"api.{site}"
    values = {1: args.node1_start, 2: args.node2_start}
    steps = {1: args.node1_step, 2: args.node2_step}

    print(
        f"Synthetic accelerated GDD demo only; metric={METRIC}; "
        f"cohort=synthetic_accelerated_demo; interval={args.interval}s.",
        flush=True,
    )
    try:
        while True:
            for node_id in values:
                values[node_id] += steps[node_id]
            try:
                submit(api_key, api_host, values)
                stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                print(
                    f"[{stamp}] accepted; node1={values[1]:.2f}; node2={values[2]:.2f}; source=synthetic",
                    flush=True,
                )
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError) as exc:
                print(f"Datadog synthetic demo submit failed: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped synthetic accelerated GDD demo publisher.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
