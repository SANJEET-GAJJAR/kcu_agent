"""Deterministic offline replay engine.

Replays a previously collected JSONL trading day one candle at a time.
Zero dependency on TradingView MCP or any network resource.

Rules enforced:
  - Candles are loaded once, sorted by timestamp, and stored immutably.
  - The cursor is the only mutable state.
  - current() never exposes a candle beyond the cursor.
  - No future candles are accessible by any public method.
  - Generic: no ticker-specific or KCU-specific logic.
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.collector.candle_record import CandleRecord
from src.collector.jsonl_store import JsonlStore, JsonlStoreError

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------

class ReplayEngineError(Exception):
    """Base error for ReplayEngine misuse."""


class BeginningOfReplay(ReplayEngineError):
    """Raised when previous() is called at the first candle."""


class EndOfReplay(ReplayEngineError):
    """Raised when next() is called at the last candle."""


class TimestampNotFound(ReplayEngineError):
    """Raised when goto() cannot find an exact match."""


# ------------------------------------------------------------------
# Replay state snapshot
# ------------------------------------------------------------------

@dataclass(frozen=True)
class ReplayState:
    """Immutable snapshot of replay cursor position.

    Can be serialised and used to restore position across sessions.
    """
    source_path: str
    cursor: int
    total_candles: int
    current_timestamp: int
    symbol: str
    timeframe: str
    replay_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "cursor": self.cursor,
            "total_candles": self.total_candles,
            "current_timestamp": self.current_timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
        }


# ------------------------------------------------------------------
# Replay engine
# ------------------------------------------------------------------

class ReplayEngine:
    """Offline, deterministic candle-by-candle replay from a JSONL file.

    Usage:
        replay = ReplayEngine("outputs/candles/TICKER_2024-01-15_2m.jsonl")
        while not replay.finished():
            candle = replay.current()
            replay.next()

    No lookahead: next() moves the cursor but current() at any position
    only returns the candle AT the cursor, never ahead of it.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._candles: tuple[CandleRecord, ...] = ()
        self._timestamps: tuple[int, ...] = ()   # parallel index for O(log n) goto
        self._cursor: int = 0
        self._iter_done: bool = False
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load and validate JSONL, sort by timestamp, freeze into a tuple."""
        if not self._path.exists():
            raise ReplayEngineError(f"JSONL file not found: {self._path}")

        store = JsonlStore(self._path)
        try:
            records = store.read_all()
        except JsonlStoreError as exc:
            raise ReplayEngineError(f"Failed to load {self._path}: {exc}") from exc

        if not records:
            raise ReplayEngineError(f"JSONL file is empty: {self._path}")

        # Sort by timestamp — the source of truth for chronological order
        sorted_records = sorted(records, key=lambda r: r.timestamp)

        # Deduplicate timestamps: keep first occurrence
        seen: set[int] = set()
        deduped: list[CandleRecord] = []
        for r in sorted_records:
            if r.timestamp not in seen:
                deduped.append(r)
                seen.add(r.timestamp)

        self._candles = tuple(deduped)
        self._timestamps = tuple(r.timestamp for r in self._candles)
        self._cursor = 0

        log.info(
            "Loaded %d candles from %s (symbol=%s timeframe=%s date=%s)",
            len(self._candles),
            self._path.name,
            self._candles[0].snapshot.symbol,
            self._candles[0].snapshot.timeframe,
            self._candles[0].snapshot.replay_date,
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def current(self) -> CandleRecord:
        """Return the candle at the current cursor position."""
        return self._candles[self._cursor]

    def next(self) -> CandleRecord:
        """Advance cursor one candle forward and return the new current candle.

        Raises EndOfReplay if already at the last candle.
        """
        if self._cursor >= len(self._candles) - 1:
            raise EndOfReplay(
                f"Already at last candle (index {self._cursor}, "
                f"ts={self._candles[self._cursor].timestamp})"
            )
        self._cursor += 1
        return self._candles[self._cursor]

    def previous(self) -> CandleRecord:
        """Move cursor one candle backward and return the new current candle.

        Raises BeginningOfReplay if already at the first candle.
        """
        if self._cursor == 0:
            raise BeginningOfReplay(
                f"Already at first candle (ts={self._candles[0].timestamp})"
            )
        self._cursor -= 1
        return self._candles[self._cursor]

    def goto(self, timestamp: int | str) -> CandleRecord:
        """Move cursor to the candle matching timestamp.

        timestamp may be:
          - int: Unix seconds
          - str: ISO 8601 (e.g. "2024-01-15T09:30:00-05:00" or "2024-01-15T14:30:00Z")

        Raises TimestampNotFound if no candle matches exactly.
        No lookahead: goto() can move to any candle, including earlier ones.
        The caller is responsible for not using goto() to peek at future candles.
        """
        ts_int = _parse_timestamp(timestamp)

        idx = bisect.bisect_left(self._timestamps, ts_int)
        if idx >= len(self._timestamps) or self._timestamps[idx] != ts_int:
            raise TimestampNotFound(
                f"No candle with timestamp {ts_int} "
                f"(from {timestamp!r}) in {self._path.name}"
            )

        self._cursor = idx
        return self._candles[self._cursor]

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    def finished(self) -> bool:
        """True when the cursor is at the last candle."""
        return self._cursor >= len(self._candles) - 1

    def at_beginning(self) -> bool:
        """True when the cursor is at the first candle."""
        return self._cursor == 0

    def reset(self) -> None:
        """Reset cursor to the first candle."""
        self._cursor = 0

    def peek_next(self) -> CandleRecord | None:
        """Return the next candle without advancing. None if at the end.

        NOTE: this is provided for engine-internal use only (e.g. end-of-day
        detection). Callers must not use this to read future candle prices
        and influence decisions — that would be lookahead bias.
        """
        if self._cursor >= len(self._candles) - 1:
            return None
        return self._candles[self._cursor + 1]

    def state(self) -> ReplayState:
        """Return a frozen snapshot of current replay position."""
        c = self.current()
        return ReplayState(
            source_path=str(self._path),
            cursor=self._cursor,
            total_candles=len(self._candles),
            current_timestamp=c.timestamp,
            symbol=c.snapshot.symbol,
            timeframe=c.snapshot.timeframe,
            replay_date=c.snapshot.replay_date,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def total_candles(self) -> int:
        return len(self._candles)

    @property
    def source_path(self) -> Path:
        return self._path

    @property
    def symbol(self) -> str:
        return self._candles[0].snapshot.symbol

    @property
    def timeframe(self) -> str:
        return self._candles[0].snapshot.timeframe

    @property
    def replay_date(self) -> str:
        return self._candles[0].snapshot.replay_date

    # ------------------------------------------------------------------
    # Iteration support
    # ------------------------------------------------------------------

    def __iter__(self) -> "ReplayEngine":
        """Iterate from current position to end. Does NOT reset cursor.

        Yields every candle from current position including the last.
        """
        self._iter_done = False
        return self

    def __next__(self) -> CandleRecord:
        if self._iter_done:
            raise StopIteration
        candle = self.current()
        if self.finished():
            self._iter_done = True   # yield last candle this call; stop next call
        else:
            self.next()
        return candle

    def __len__(self) -> int:
        return len(self._candles)

    def __repr__(self) -> str:
        return (
            f"ReplayEngine({self._path.name!r}, "
            f"cursor={self._cursor}/{len(self._candles) - 1}, "
            f"finished={self.finished()})"
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_timestamp(timestamp: int | str) -> int:
    """Convert a timestamp to Unix seconds int."""
    if isinstance(timestamp, int):
        return timestamp
    if isinstance(timestamp, float):
        return int(timestamp)
    if isinstance(timestamp, str):
        # Try ISO 8601 first
        try:
            dt = datetime.fromisoformat(timestamp)
            # If naive, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            pass
        # Try plain integer string
        try:
            return int(timestamp)
        except ValueError:
            pass
        raise TimestampNotFound(
            f"Cannot parse timestamp {timestamp!r}. "
            "Use Unix seconds (int) or ISO 8601 string."
        )
    raise TimestampNotFound(f"Unsupported timestamp type: {type(timestamp)}")
