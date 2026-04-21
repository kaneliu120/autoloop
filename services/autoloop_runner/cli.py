"""autoloop-runner CLI: tick / loop (unattended)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from autoloop_runner.metrics import render_prometheus_text
from autoloop_runner.tick import run_tick

log = logging.getLogger("autoloop_runner")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AutoLoop L1 Runner — calls controller in slices per manual §5 + DECIDE/ACT/REFLECT"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tick = sub.add_parser("tick", help="Advance one step (based on checkpoint.last_completed_phase)")
    p_tick.add_argument("work_dir", help="Task work directory (contains autoloop-state.json)")
    p_tick.add_argument(
        "--no-strict",
        action="store_true",
        help="Do not inject AUTOLOOP_STRICT=1",
    )
    p_tick.add_argument(
        "--no-wait-lock",
        action="store_true",
        help="Exit immediately with 11 if the work_dir lock is unavailable instead of blocking",
    )

    p_loop = sub.add_parser("loop", help="Run ticks continuously until pause/failure/timeout")
    p_loop.add_argument("work_dir")
    p_loop.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        help="Maximum tick count; 0 means unlimited",
    )
    p_loop.add_argument(
        "--max-wall-seconds",
        type=float,
        default=0,
        help="Wall-clock limit in seconds; 0 means unlimited (same as RUNNER_MAX_WALL_SECONDS)",
    )
    p_loop.add_argument("--no-strict", action="store_true")

    p_metrics = sub.add_parser(
        "metrics",
        help="Print Prometheus text metrics (metadata.runner_metrics, etc.)",
    )
    p_metrics.add_argument("work_dir")

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="DEBUG logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    if args.cmd == "metrics":
        print(render_prometheus_text(os.path.abspath(args.work_dir)), end="")
        raise SystemExit(0)

    if args.cmd == "tick":
        rc = run_tick(
            args.work_dir,
            strict=not args.no_strict,
            lock_blocking=not args.no_wait_lock,
        )
        raise SystemExit(rc)

    if args.cmd == "loop":
        wall = args.max_wall_seconds or float(
            os.environ.get("RUNNER_MAX_WALL_SECONDS", "0") or 0
        )
        max_ticks = args.max_ticks or int(
            os.environ.get("RUNNER_MAX_TICKS", "0") or 0
        )
        start = time.monotonic()
        n = 0
        while True:
            if max_ticks and n >= max_ticks:
                log.info("max_ticks reached")
                raise SystemExit(0)
            if wall and (time.monotonic() - start) >= wall:
                log.info("max_wall_seconds reached")
                raise SystemExit(0)
            rc = run_tick(args.work_dir, strict=not args.no_strict)
            n += 1
            if rc == 10:
                log.info("paused (exit 10)")
                raise SystemExit(10)
            if rc == 11:
                log.warning("lock busy")
                raise SystemExit(11)
            if rc == 12:
                log.warning("budget / cost cap (exit 12)")
                raise SystemExit(12)
            if rc != 0:
                raise SystemExit(rc)

    raise SystemExit(2)


if __name__ == "__main__":
    main()
