#!/usr/bin/env python3
"""
Orchestrator Daemon — 纯 Python 守护进程，替代 cron job

设计原则：
  - 本地轮询，零 LLM 消耗
  - 30 秒检查一次待执行任务
  - 不空烧 token：没任务就 sleep
  - 支持优雅退出

用法：
  python3 orchestrator_daemon.py
  # 或通过 systemd 管理
"""

import os
import sys
import time
import signal
import logging

# 确保 Django 环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_platform.settings")

import django
django.setup()

from agents.orchestrator import poll_and_execute
from agents.pitfall_memory import get_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OrchDaemon] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

POLL_INTERVAL = 30  # 秒
running = True


def handle_signal(signum, frame):
    global running
    log.info(f"收到信号 {signum}，正在退出...")
    running = False


def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    log.info("Orchestrator Daemon 启动")
    log.info(f"轮询间隔: {POLL_INTERVAL}s")
    stats = get_stats()
    log.info(f"坑位记忆: {stats['total_entries']} 条, 累计命中 {stats['total_hits']} 次")

    total_executed = 0
    idle_rounds = 0

    while running:
        try:
            count, error = poll_and_execute()

            if error:
                log.error(f"轮询出错: {error}")
            elif count > 0:
                total_executed += count
                log.info(f"执行了 {count} 个任务 (累计 {total_executed})")
                idle_rounds = 0
            else:
                idle_rounds += 1
                if idle_rounds % 20 == 0:  # 每 10 分钟
                    log.debug(f"空闲中... ({idle_rounds} 轮)")

        except Exception as e:
            log.error(f"轮询异常: {e}")

        # sleep，但响应退出信号
        for _ in range(POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    log.info(f"Orchestrator Daemon 退出。共执行 {total_executed} 个任务。")


if __name__ == "__main__":
    main()
