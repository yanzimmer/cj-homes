import logging
import os
import signal
import time

from notification_service import run_due_bark_notifications


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("notification_worker")
POLL_SECONDS = max(30, int(os.getenv("NOTIFICATION_POLL_SECONDS", "300")))
running = True


def _stop_worker(signum, frame):
    global running
    running = False


def main():
    signal.signal(signal.SIGTERM, _stop_worker)
    signal.signal(signal.SIGINT, _stop_worker)
    logger.info("Bark 自动通知进程已启动，检查间隔 %s 秒", POLL_SECONDS)
    while running:
        try:
            result = run_due_bark_notifications()
            if result.get("status") == "completed" and (result.get("sent") or result.get("failed")):
                logger.info("Bark 自动通知完成: %s", result)
        except Exception:
            logger.exception("Bark 自动通知检查失败")
        for _ in range(POLL_SECONDS):
            if not running:
                break
            time.sleep(1)
    logger.info("Bark 自动通知进程已停止")


if __name__ == "__main__":
    main()
