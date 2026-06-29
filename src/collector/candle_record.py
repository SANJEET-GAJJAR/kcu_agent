"""CandleRecord — one JSONL line per replay candle.

Extends CandleSnapshot with raw indicator values and collection metadata.
No trading logic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from .candle_schema import CandleSnapshot


@dataclass
class CandleRecord:
    """One complete record written per candle during day collection.

    Fields:
        snapshot        — validated OHLCV + symbol/timeframe/replay_date
        indicators      — flat key→value map from data_get_study_values (backward compat)
        raw_indicators  — unflattened studies list: [{"name": str, "values": {str: Any}}]
                          Preserves study attribution and all exposed fields/plots.
                          Empty list on candles collected before this field was added.
        meta            — collection bookkeeping (index, wall-clock timestamp)
    """
    snapshot: CandleSnapshot
    indicators: dict[str, Any] = field(default_factory=dict)
    raw_indicators: list[dict] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self.snapshot)
        d["indicators"] = self.indicators
        d["raw_indicators"] = self.raw_indicators
        d["meta"] = self.meta
        return d

    def to_jsonl_line(self) -> str:
        """Compact single-line JSON suitable for JSONL."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CandleRecord":
        snapshot = CandleSnapshot.from_dict(d)
        return cls(
            snapshot=snapshot,
            indicators=d.get("indicators", {}),
            raw_indicators=d.get("raw_indicators", []),
            meta=d.get("meta", {}),
        )

    @property
    def timestamp(self) -> int:
        return self.snapshot.timestamp


def build_record(
    snapshot: CandleSnapshot,
    indicators: dict[str, Any],
    candle_index: int,
    raw_indicators: list[dict] | None = None,
) -> CandleRecord:
    """Construct a CandleRecord with collection metadata."""
    meta = {
        "candle_index": candle_index,
        "collected_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    return CandleRecord(
        snapshot=snapshot,
        indicators=indicators,
        raw_indicators=raw_indicators or [],
        meta=meta,
    )
