"""Pure feature extraction functions.

Each function takes (current_candle, window, ...) and returns one or more
feature values. No state, no side effects, no lookahead.

Rules:
  - current_candle: the candle being analysed.
  - window: tuple of past candles (oldest→newest). Never contains current.
  - All functions are deterministic: same inputs → same outputs.
  - No trading logic, no KCU-specific code, no pattern classification.
"""
from __future__ import annotations

from typing import Any

from src.collector.candle_record import CandleRecord


# ------------------------------------------------------------------
# Price action: single-candle
# ------------------------------------------------------------------

def candle_body(record: CandleRecord) -> float:
    """Absolute distance between open and close."""
    s = record.snapshot
    return abs(s.close - s.open)


def upper_wick(record: CandleRecord) -> float:
    """Distance from high to the top of the body."""
    s = record.snapshot
    return s.high - max(s.open, s.close)


def lower_wick(record: CandleRecord) -> float:
    """Distance from the bottom of the body to low."""
    s = record.snapshot
    return min(s.open, s.close) - s.low


def candle_range(record: CandleRecord) -> float:
    """High minus low."""
    s = record.snapshot
    return s.high - s.low


def body_pct(record: CandleRecord) -> float | None:
    """Candle body as a percentage of total range. None if range is zero (doji)."""
    rng = candle_range(record)
    if rng == 0.0:
        return None
    return (candle_body(record) / rng) * 100.0


# ------------------------------------------------------------------
# Price action: multi-candle (require window)
# ------------------------------------------------------------------

def atr(window: tuple[CandleRecord, ...], n: int) -> float | None:
    """Simple average of candle_range over the last n candles in the window.

    Returns None if the window has fewer than 1 candle.
    Uses all available candles if len(window) < n.
    """
    if not window:
        return None
    recent = window[-n:] if len(window) >= n else window
    return sum(candle_range(r) for r in recent) / len(recent)


def gap_from_prev(current: CandleRecord, window: tuple[CandleRecord, ...]) -> float | None:
    """Current open minus previous close. None for the first candle."""
    if not window:
        return None
    return current.snapshot.open - window[-1].snapshot.close


def distance_from_prev_close(current: CandleRecord, window: tuple[CandleRecord, ...]) -> float | None:
    """Current close minus previous close. None for the first candle."""
    if not window:
        return None
    return current.snapshot.close - window[-1].snapshot.close


# ------------------------------------------------------------------
# Structure flags
# ------------------------------------------------------------------

def is_higher_high(current: CandleRecord, window: tuple[CandleRecord, ...]) -> bool | None:
    """True if current high > previous high. None for first candle."""
    if not window:
        return None
    return current.snapshot.high > window[-1].snapshot.high


def is_lower_low(current: CandleRecord, window: tuple[CandleRecord, ...]) -> bool | None:
    """True if current low < previous low. None for first candle."""
    if not window:
        return None
    return current.snapshot.low < window[-1].snapshot.low


def is_inside_bar(current: CandleRecord, window: tuple[CandleRecord, ...]) -> bool | None:
    """True if current high < prev high AND current low > prev low. None for first candle."""
    if not window:
        return None
    prev = window[-1].snapshot
    cur = current.snapshot
    return cur.high < prev.high and cur.low > prev.low


def is_outside_bar(current: CandleRecord, window: tuple[CandleRecord, ...]) -> bool | None:
    """True if current high > prev high AND current low < prev low. None for first candle."""
    if not window:
        return None
    prev = window[-1].snapshot
    cur = current.snapshot
    return cur.high > prev.high and cur.low < prev.low


def consecutive_hh(current: CandleRecord, window: tuple[CandleRecord, ...]) -> int:
    """Streak of successive higher highs ending at current (not counting current itself).

    Returns how many consecutive past candles, counting back from most recent,
    each had a high strictly lower than its successor.

    Example: window highs [100, 102, 104], current high=106 → 3
             window highs [100, 105, 104], current high=106 → 1 (104 < 105 breaks it)
    """
    if not window:
        return 0
    count = 0
    prev_high = current.snapshot.high
    for rec in reversed(window):
        if rec.snapshot.high < prev_high:
            count += 1
            prev_high = rec.snapshot.high
        else:
            break
    return count


def consecutive_ll(current: CandleRecord, window: tuple[CandleRecord, ...]) -> int:
    """Streak of successive lower lows ending at current (not counting current itself)."""
    if not window:
        return 0
    count = 0
    prev_low = current.snapshot.low
    for rec in reversed(window):
        if rec.snapshot.low > prev_low:
            count += 1
            prev_low = rec.snapshot.low
        else:
            break
    return count


def consecutive_lh(current: CandleRecord, window: tuple[CandleRecord, ...]) -> int:
    """Streak of successive lower highs ending at current (not counting current itself)."""
    if not window:
        return 0
    count = 0
    prev_high = current.snapshot.high
    for rec in reversed(window):
        if rec.snapshot.high > prev_high:
            count += 1
            prev_high = rec.snapshot.high
        else:
            break
    return count


def consecutive_hl(current: CandleRecord, window: tuple[CandleRecord, ...]) -> int:
    """Streak of successive higher lows ending at current (not counting current itself)."""
    if not window:
        return 0
    count = 0
    prev_low = current.snapshot.low
    for rec in reversed(window):
        if rec.snapshot.low < prev_low:
            count += 1
            prev_low = rec.snapshot.low
        else:
            break
    return count


# ------------------------------------------------------------------
# Volume
# ------------------------------------------------------------------

def relative_volume(current: CandleRecord, window: tuple[CandleRecord, ...], n: int) -> float | None:
    """Current volume divided by average volume of the last n candles in window.

    Returns None if window is empty (no baseline).
    Uses all available window candles if len(window) < n.
    """
    if not window:
        return None
    recent = window[-n:] if len(window) >= n else window
    avg = sum(r.snapshot.volume for r in recent) / len(recent)
    if avg == 0:
        return None
    return current.snapshot.volume / avg


# ------------------------------------------------------------------
# Time / session
# ------------------------------------------------------------------

def classify_session(timestamp: int, market_open_ts: int, market_close_ts: int) -> str:
    """Return session label for a Unix timestamp.

    "premarket"   — before market open
    "regular"     — market open (inclusive) through market close (exclusive)
    "after_hours" — at or after market close
    """
    if timestamp < market_open_ts:
        return "premarket"
    if timestamp < market_close_ts:
        return "regular"
    return "after_hours"


def time_since_open_minutes(timestamp: int, market_open_ts: int) -> float:
    """Minutes elapsed since market open. Negative for premarket candles."""
    return (timestamp - market_open_ts) / 60.0


def distance_from_session_open(
    current: CandleRecord,
    session_open_price: float | None,
) -> float | None:
    """Current close minus the close of the first regular-session candle seen so far.

    None until the first regular-session candle has been processed.
    """
    if session_open_price is None:
        return None
    return current.snapshot.close - session_open_price
