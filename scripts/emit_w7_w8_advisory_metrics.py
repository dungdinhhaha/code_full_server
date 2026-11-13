"""Bounded DogStatsD demo signal for W7/W8 advisory-only workflows.

This deliberately emits review signals and evidence only. It never calls an
actuator, changes an irrigation schedule, or changes crop data in MongoDB.
"""
from __future__ import annotations

import argparse
import socket
import time


def send(sock: socket.socket, host: str, port: int, metric: str, value: float, tags: list[str]) -> None:
    packet = f"{metric}:{value}|g|#{','.join(tags)}".encode("utf-8")
    sock.sendto(packet, (host, port))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("w7", "w8", "normal"), required=True)
    parser.add_argument("--farm", default="greenhouse_j")
    parser.add_argument("--node", type=int, default=1)
    parser.add_argument("--seconds", type=int, default=140)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8125)
    args = parser.parse_args()
    tags = [f"farm:{args.farm}", f"node:{args.node}", "source:smiot_synthetic_drill"]
    deadline = time.monotonic() + max(10, args.seconds)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while time.monotonic() < deadline:
            # Fresh evidence remains present in both branches so the workflow
            # can distinguish a review signal from missing telemetry.
            for metric, value in [
                ("smiot.telemetry.sample_age_seconds", 30),
                ("smiot.crop.envelope.approved", 1),
                ("smiot.crop.stage_context.valid", 1),
                ("smiot.telemetry.soil_humidity", 24),
                ("smiot.telemetry.soil_ec", 2.4),
                ("smiot.crop.vpd_kpa", 1.15),
                ("smiot.crop.soil_moisture.review_required", int(args.mode == "w7")),
                ("smiot.crop.vpd_ec.review_required", int(args.mode == "w8")),
            ]:
                send(sock, args.host, args.port, metric, value, tags)
            time.sleep(max(1.0, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
