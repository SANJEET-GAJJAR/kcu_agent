"""Fixed-size rolling window of past CandleRecords.

Only past candles are stored. The current candle is never inside the window.
Push is append-only: oldest drops off when capacity is reached.
No trading logic.
"""
from __future__ import annotations

from collections import deque

from src.collector.candle_record import CandleRecord


class RollingWindow:
    """Append-only fixed-capacity window of CandleRecords.

    Ordering: index 0 is oldest, index -1 is most recent (immediately before current).

    Usage pattern in the extractor:
        window = RollingWindow(max_size=50)
        for each candle:
            features = extract(current_candle, window.snapshot())
            window.push(current_candle)   # push AFTER extraction
    """

    def __init__(self, max_size: int) -> None:
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._max_size = max_size
        self._data: deque[CandleRecord] = deque(maxlen=max_size)

    def push(self, record: CandleRecord) -> None:
        """Append record. Oldest is dropped when at capacity."""
        self._data.append(record)

    def snapshot(self) -> tuple[CandleRecord, ...]:
        """Return an immutable ordered view of the window (oldest→newest).

        Safe to pass to pure feature functions without risk of mutation.
        """
        return tuple(self._data)

    def __len__(self) -> int:
        return len(self._data)

    @property
    def max_size(self) -> int:
        return self._max_size

    def is_empty(self) -> bool:
        return len(self._data) == 0

    def last(self) -> CandleRecord | None:
        """Most recent record in the window (immediately before current). None if empty."""
        return self._data[-1] if self._data else None
