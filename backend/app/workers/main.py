"""
Worker 主程式 - APScheduler 管理所有排程任務
"""
import asyncio
import logging
import signal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.workers.email_sync import sync_all_accounts
from app.workers.digest import send_digest_for_all_users

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    scheduler = AsyncIOScheduler()

    # 每 2 分鐘同步一次信件
    scheduler.add_job(
        sync_all_accounts,
        trigger=IntervalTrigger(minutes=2),
        id="email_sync",
        name="Email Sync",
        max_instances=1,
        misfire_grace_time=30,
    )

    # 每小時整點檢查是否有 Digest 要發送
    scheduler.add_job(
        send_digest_for_all_users,
        trigger=CronTrigger(minute=0),
        id="digest_sender",
        name="Digest Sender",
        max_instances=1,
    )

    scheduler.start()
    logger.info("✅ Worker 啟動，排程任務已設定")
    logger.info("  - Email 同步: 每 2 分鐘")
    logger.info("  - Digest 發送: 每小時整點檢查")

    # 優雅關閉
    stop_event = asyncio.Event()

    def handle_signal():
        logger.info("收到關閉訊號，停止 Worker...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    await stop_event.wait()
    scheduler.shutdown()
    logger.info("Worker 已停止")


if __name__ == "__main__":
    asyncio.run(main())
