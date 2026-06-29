"""FeatureRecord — one feature record per replay candle.

Contains all extracted features plus raw indicator passthrough.
No trading logic. No KCU-specific fields.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FeatureRecord:
    """All features extracted from one candle at replay position candle_index.

    Nullable fields (float | None, bool | None) are None when insufficient
    history is available (e.g. first candle has no previous for gap calculation).

    Fields are grouped by category for readability but stored flat for JSON export.
    """
    # --- Identity ---
    timestamp: int
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int

    # --- Raw OHLCV (copied from candle for self-contained records) ---
    open: float
    high: float
    low: float
    close: float
    volume: float

    # --- Price action: single-candle ---
    candle_body: float          # abs(close - open)
    upper_wick: float           # high - max(open, close)
    lower_wick: float           # min(open, close) - low
    body_pct: float | None      # candle_body / range * 100; None if range == 0
    candle_range: float         # high - low

    # --- Price action: multi-candle ---
    atr: float | None                     # rolling average of candle_range
    gap_from_prev: float | None           # open - prev_close; None for first candle
    distance_from_prev_close: float | None  # close - prev_close; None for first candle

    # --- Structure ---
    is_higher_high: bool | None   # high > prev high
    is_lower_low: bool | None     # low < prev low
    is_inside_bar: bool | None    # high < prev_high AND low > prev_low
    is_outside_bar: bool | None   # high > prev_high AND low < prev_low
    consecutive_hh: int           # streak of successive higher highs ending at current
    consecutive_ll: int           # streak of successive lower lows ending at current
    consecutive_lh: int           # streak of successive lower highs ending at current
    consecutive_hl: int           # streak of successive higher lows ending at current

    # --- Volume ---
    relative_volume: float | None   # volume / avg_volume(rvol_window); None if no history

    # --- Time / session ---
    session: str                        # "premarket" | "regular" | "after_hours"
    time_since_open_minutes: float      # minutes since 09:30 ET; negative = premarket
    distance_from_session_open: float | None  # close - first regular session close

    # --- Indicator passthrough (raw, no interpretation) ---
    indicators: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_jsonl_line(self) -> str:
        """Compact single-line JSON for JSONL output."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FeatureRecord":
        return cls(
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
            candle_body=float(d["candle_body"]),
            upper_wick=float(d["upper_wick"]),
            lower_wick=float(d["lower_wick"]),
            body_pct=float(d["body_pct"]) if d["body_pct"] is not None else None,
            candle_range=float(d["candle_range"]),
            atr=float(d["atr"]) if d["atr"] is not None else None,
            gap_from_prev=float(d["gap_from_prev"]) if d["gap_from_prev"] is not None else None,
            distance_from_prev_close=float(d["distance_from_prev_close"]) if d["distance_from_prev_close"] is not None else None,
            is_higher_high=d["is_higher_high"],
            is_lower_low=d["is_lower_low"],
            is_inside_bar=d["is_inside_bar"],
            is_outside_bar=d["is_outside_bar"],
            consecutive_hh=int(d["consecutive_hh"]),
            consecutive_ll=int(d["consecutive_ll"]),
            consecutive_lh=int(d["consecutive_lh"]),
            consecutive_hl=int(d["consecutive_hl"]),
            relative_volume=float(d["relative_volume"]) if d["relative_volume"] is not None else None,
            session=str(d["session"]),
            time_since_open_minutes=float(d["time_since_open_minutes"]),
            distance_from_session_open=float(d["distance_from_session_open"]) if d["distance_from_session_open"] is not None else None,
            indicators=dict(d.get("indicators", {})),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors. Empty list = valid."""
        errors: list[str] = []

        if self.timestamp <= 0:
            errors.append(f"timestamp must be > 0, got {self.timestamp}")
        if not self.symbol:
            errors.append("symbol must not be empty")
        if not self.timeframe:
            errors.append("timeframe must not be empty")
        if not self.replay_date:
            errors.append("replay_date must not be empty")
        if self.candle_index < 0:
            errors.append(f"candle_index must be >= 0, got {self.candle_index}")
        if self.high < self.low:
            errors.append(f"high ({self.high}) < low ({self.low})")
        if self.candle_body < 0:
            errors.append(f"candle_body must be >= 0, got {self.candle_body}")
        if self.upper_wick < 0:
            errors.append(f"upper_wick must be >= 0, got {self.upper_wick}")
        if self.lower_wick < 0:
            errors.append(f"lower_wick must be >= 0, got {self.lower_wick}")
        if self.candle_range < 0:
            errors.append(f"candle_range must be >= 0, got {self.candle_range}")
        if self.session not in ("premarket", "regular", "after_hours"):
            errors.append(f"session must be premarket/regular/after_hours, got {self.session!r}")
        if self.consecutive_hh < 0:
            errors.append(f"consecutive_hh must be >= 0")
        if self.consecutive_ll < 0:
            errors.append(f"consecutive_ll must be >= 0")
        if self.consecutive_lh < 0:
            errors.append(f"consecutive_lh must be >= 0")
        if self.consecutive_hl < 0:
            errors.append(f"consecutive_hl must be >= 0")

        return errors
