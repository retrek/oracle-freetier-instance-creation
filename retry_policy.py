"""Pace capacity polling without immediately returning to a throttled rate."""

import math
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def retry_delay(error, interval):
    interval = max(60, interval)
    if error.get("status") == 429 or error.get("code") == "TooManyRequests":
        interval = max(interval, min(900, interval * 2))
    delay = random.uniform(interval, interval * 1.25)
    retry_after = error.get("retry_after")
    if retry_after:
        try:
            server_delay = float(retry_after)
        except (TypeError, ValueError):
            try:
                server_delay = (parsedate_to_datetime(retry_after) -
                                datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                server_delay = 0
        if math.isfinite(server_delay):
            delay = max(delay, server_delay)
    return interval, delay
