"""autoloop-runner CLI：tick / loop（无人值守）。"""

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
        description="AutoLoop L1 Runner — 按手册 §5 切片调用 controller + DECIDE/ACT/REFLECT"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tick = sub.add_parser("tick", help="单步推进（按 checkpoint.last_completed_phase）")
    p_tick.add_argument("work_dir", help="任务工作目录（含 autoloop-state.json）")
    p_tick.add_argument(
        "--no-strict",
        action="store_true",
        help="不注入 AUTOLOOP_STRICT=1",
    )
    p_tick.add_argument(
        "--no-wait-lock",
        action="store_true",
        help="若无法获取 work_dir 锁立即退出(11)而非阻塞",
    )

    p_loop = sub.add_parser("loop", help="连续 tick 直至暂停/失败/超时")
    p_loop.add_argument("work_dir")
    p_loop.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        help="最大 tick 次数，0 表示不限制",
    )
    p_loop.add_argument(
        "--max-wall-seconds",
        type=float,
        default=0,
        help="墙钟上限秒，0 不限制（同 RUNNER_MAX_WALL_SECONDS）",
    )
    p_loop.add_argument("--no-strict", action="store_true")

    p_metrics = sub.add_parser(
        "metrics",
        help="打印 Prometheus 文本指标（metadata.runner_metrics 等）",
    )
    p_metrics.add_argument("work_dir")

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="DEBUG 日志"
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
