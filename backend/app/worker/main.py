"""ARQ worker entrypoint.

Run with: ``arq app.worker.main.WorkerSettings``
Database work is synchronous, so jobs are dispatched with asyncio.to_thread
to keep the worker event loop responsive.
"""

import asyncio
from urllib.parse import urlparse

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.tasks import (
    check_offline_devices,
    cleanup_expired_tokens,
    partition_maintenance,
    process_notifications,
    reconcile_discrepancies,
)


def _redis_settings() -> RedisSettings:
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
        password=parsed.password,
    )


async def _run(ctx, fn, *args):
    return await asyncio.to_thread(fn, *args)


async def offline_check(ctx):
    return await _run(ctx, check_offline_devices)


async def notifications(ctx):
    return await _run(ctx, process_notifications)


async def token_cleanup(ctx):
    return await _run(ctx, cleanup_expired_tokens)


async def partitions(ctx):
    return await _run(ctx, partition_maintenance)


async def discrepancies(ctx):
    return await _run(ctx, reconcile_discrepancies)


class WorkerSettings:
    functions = [offline_check, notifications, token_cleanup, partitions, discrepancies]
    cron_jobs = [
        cron(offline_check, minute={"0", "15", "30", "45"}),
        cron(notifications, minute=set(range(0, 60, 2))),
        cron(discrepancies, minute={"10", "40"}),
        cron(token_cleanup, hour=3, minute=0),
        cron(partitions, hour=2, minute=0),
    ]
    redis_settings = _redis_settings()
    max_jobs = 10
    job_timeout = 300
