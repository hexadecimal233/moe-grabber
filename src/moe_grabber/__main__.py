import sys
from datetime import datetime
from time import sleep

from moe_grabber.config import MoeConfig
from moe_grabber.claimer import MoeClaimer


def _wait_until(scheduled_time: str) -> None:
    """Sleep until the configured ISO 8601 datetime, then return
    immediately — no drift from init overhead.

    Sleeps until 500ms before target, then tight-spins for the last
    500ms for sub‑millisecond precision.
    """
    target = datetime.fromisoformat(scheduled_time)
    now = datetime.now(target.tzinfo)

    if target <= now:
        print(
            f"错误：定时启动时间 {scheduled_time} 已过当前时间 "
            f"({now.strftime('%Y-%m-%dT%H:%M:%S')})，请检查配置"
        )
        sys.exit(1)

    remaining = (target - now).total_seconds()

    # Sleep the bulk of the wait (all but the last 500ms)
    if remaining > 0.5:
        print(
            f"等待至 {target.strftime('%Y-%m-%d %H:%M:%S')} 开始抢号"
            f"（剩余 {remaining / 60:.1f} 分钟）..."
        )
        sleep(remaining - 0.5)

    # Tight spin‑loop for the last 500ms — <1ms precision
    while datetime.now(target.tzinfo) < target:
        pass


def main() -> None:
    print("本工具已启动")

    print("加载配置中...")
    config = MoeConfig.from_json()
    print(f"待抢 ID 列表: {', '.join(config.moe_numbers)}")
    print(f"定时启动: {config.scheduled_time}")

    # Init first — OCR engine, ProtonMail login, etc.
    # This guarantees zero drift: all heavyweight work is done
    # before the timer starts counting.
    print("初始化OCR和请求服务中...")
    claimer = MoeClaimer(config)

    # Now wait — only thin Python overhead remains between
    # _wait_until return and claimer.claim()
    _wait_until(config.scheduled_time)

    claimer.claim()


if __name__ == "__main__":
    main()
