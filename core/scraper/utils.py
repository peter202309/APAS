import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def human_sleep(min_seconds: float = 2.0, max_seconds: float = 5.0):
    """
    Sleeps for a random duration between min_seconds and max_seconds
    to mimic human interaction speed and avoid detection.
    """
    sleep_time = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Thinking for {sleep_time:.2f}s...")
    await asyncio.sleep(sleep_time)
