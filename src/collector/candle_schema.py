"""Candle data schema and validation. No trading logic."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class CandleSnapshot:
    """A single OHLCV candle at a specific replay position.

    All fields are required. Validation is strict so corrupt data is caught
    at the boundary rather than propagating into analysis.
    """
    timestamp: int      # Unix seconds (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str      # e.g. "2", "5"
    replay_date: str    # ISO date the replay session was started on (YYYY-MM-DD)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.timestamp, int) or self.timestamp <= 0:
            raise ValueError(f"timestamp must be a positive int, got {self.timestamp!r}")
        for field in ("open", "high", "low", "close"):
            v = getattr(self, field)
            if not isinstance(v, (int, float)) or v != v:  # NaN check
                raise ValueError(f"{field} must be a finite number, got {v!r}")
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) < low ({self.low})")
        if self.volume < 0:
            raise ValueError(f"volume must be >= 0, got {self.volume}")
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")
        if not self.replay_date:
            raise ValueError("replay_date must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandleSnapshot":
        return cls(
            timestamp=int(d["timestamp"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d["volume"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
        )


def export_snapshot(snapshot: CandleSnapshot, path: Path) -> Path:
    """Write a validated candle snapshot to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.to_json())
    return path
