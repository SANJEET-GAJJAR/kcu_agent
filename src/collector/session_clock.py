"""Market session boundary computation.

Converts a date string + session-end time string (ET) into a Unix timestamp.
Handles DST automatically via zoneinfo. No trading logic.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# Default session boundaries (US Eastern)
PREMARKET_OPEN_ET = "04:00"    # 4:00 AM ET — earliest premarket
MARKET_OPEN_ET = "09:30"       # 9:30 AM ET — regular session open
MARKET_CLOSE_ET = "16:00"      # 4:00 PM ET — regular session close
AFTERHOURS_CLOSE_ET = "20:00"  # 8:00 PM ET — after-hours end


def session_end_timestamp(date_str: str, end_time_et: str = MARKET_CLOSE_ET) -> int:
    """Return Unix timestamp (seconds) for end_time_et on date_str in US/Eastern.

    Handles DST automatically. For example:
        session_end_timestamp("2024-01-15", "16:00") → 1705356000
        (Jan 15 is EST = UTC-5, so 16:00 EST = 21:00 UTC)

    Args:
        date_str:    ISO date, e.g. "2024-01-15"
        end_time_et: Time string HH:MM in US Eastern, e.g. "16:00"

    Returns:
        Unix timestamp (int seconds)
    """
    dt = datetime.strptime(f"{date_str} {end_time_et}", "%Y-%m-%d %H:%M").replace(
        tzinfo=_ET
    )
    return int(dt.timestamp())


def is_past_session_end(timestamp: int, session_end_ts: int) -> bool:
    """True if timestamp is at or after session_end_ts."""
    return timestamp >= session_end_ts


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert timeframe string to interval in seconds.

    "1" → 60, "2" → 120, "5" → 300, "D" → 86400, etc.
    """
    if timeframe.upper() == "D":
        return 86400
    try:
        minutes = int(timeframe)
        return minutes * 60
    except ValueError:
        raise ValueError(f"Cannot convert timeframe {timeframe!r} to seconds")


def expected_candle_count(
    date_str: str,
    timeframe: str,
    start_time_et: str = PREMARKET_OPEN_ET,
    end_time_et: str = MARKET_CLOSE_ET,
) -> int:
    """Estimate the number of candles in a session.

    Used for progress reporting — not a hard constraint.
    """
    start_ts = session_end_timestamp(date_str, start_time_et)
    end_ts = session_end_timestamp(date_str, end_time_et)
    interval = timeframe_to_seconds(timeframe)
    return max(0, (end_ts - start_ts) // interval)
