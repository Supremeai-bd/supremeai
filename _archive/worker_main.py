"""core/worker_main.py — Background Worker entrypoint for Render (free tier).

বাংলা মন্তব্য: এই মডিউলটি Render worker service-এর startCommand হিসেবে চলে।
আগে render.yaml-এ `python -c "..."` দিয়ে inline asyncio চালানোর চেষ্টা করা হয়েছিল,
যা ভাঙা সিনট্যাক্স ছিল (async def-কে -c-এর মাঝে বসানো + asyncio.run-এর ভিতরে
asyncio.run)। তাই worker আসলে কখনো সঠিকভাবে স্টার্ট হতো না। এখন সঠিক মডিউল
এন্ট্রি পয়েন্ট দেওয়া হলো। Worker HTTP serve করে না, শুধু maintenance/sentinel
background loop চালায়।
"""

from __future__ import annotations

import asyncio
import os

# বাংলা মন্তব্য: কনটেইনার অডিট ও সাইলেন্ট ক্যাচার আগে ইনিশিয়ালাইজ করা হচ্ছে
from core.intelligent_silent_catcher import setup_silent_catcher

setup_silent_catcher()

from loguru import logger

from core.agent_supervisor import agent_supervisor
from core.config import settings
from core.logging_config import setup_logging
from core.maintenance_pipeline import maintenance_pipeline
from core.sentinel_agent import sentinel


async def _main() -> None:
    logger.info("🌐 Background Worker bootstrap starting...")
    maintenance_pipeline.start_monitoring()
    await agent_supervisor.start_agent(
        "sentinel",
        lambda: sentinel.run_periodic_loop(),
        health_check_interval=60,
        max_restarts=10,
        restart_delay=1.0,
    )
    await agent_supervisor.start_monitor(check_interval=30)
    # বাংলা মন্তব্য: worker চিরকাল বাঁচিয়ে রাখার জন্য idle করবে না — supervisor loop-এর
    # মাধ্যমেই সব background task পরিচালিত হয়। এখানে শুধু run-এর মাধ্যমে বাঁধা থাকবে।
    await agent_supervisor._shutdown_event.wait()


def main() -> None:
    setup_logging()
    if settings.env not in {"test"}:
        from core.container_auditor import audit_container_resources

        audit_container_resources()
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down.")
    finally:
        logger.info("Background Worker stopped.")


if __name__ == "__main__":
    # বাংলা মন্তব্য: SERVICE_ROLE=user নিশ্চিত করা হচ্ছে যাতে worker ইউজার DB pool ব্যবহার করে
    os.environ.setdefault("SERVICE_ROLE", "user")
    main()
