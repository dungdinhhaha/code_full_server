"""Deprecated legacy AP1 synthetic-metric test; intentionally performs no writes.

The active US1 monitor is based on MongoDB-backed application telemetry. Posting a
standalone metric would not exercise the real pipeline or prove recovery. Use the
cloud app's demo mode switch and the application recovery verifier instead.
"""


def main() -> int:
    print("This legacy test is disabled: it targeted the old AP1 monitor and would not validate the US1 MongoDB-backed incident flow.")
    print("Use the cloud app's Node 2 demo mode control, then verify the US1 monitor and recovery ledger.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())