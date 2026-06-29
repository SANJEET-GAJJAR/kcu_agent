"""Forward-only replay guard for backtesting.

BacktestReplay wraps a ReplayEngine and enforces strict forward-only movement.
Any attempt to move backward, peek ahead, or reset raises LookaheadGuardError.

This is the interface that Phase 3 (feature extraction) and all downstream
phases must use. It makes accidental lookahead a hard error rather than a
silent correctness bug.

ReplayEngine remains unchanged — it is still available for non-backtest use
cases (e.g. Phase 7 human review, which legitimately needs previous()).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .replay_engine import (
    ReplayEngine,
    ReplayState,
    TimestampNotFound,
    _parse_timestamp,
)
from src.collector.candle_record import CandleRecord
from src.collector.chart_preflight import (
    StaleCollectionError,
    require_valid_collection,
)


class LookaheadGuardError(Exception):
    """Raised when a backward or peek operation is attempted in backtest mode."""


class BacktestReplay:
    """Forward-only replay wrapper.

    Permitted operations:
        current()   — return candle at cursor
        next()      — advance one candle (raises EndOfReplay at end)
        goto(ts)    — jump to timestamp >= current timestamp only
        finished()  — True at last candle
        at_beginning() — True at first candle
        state()     — frozen ReplayState snapshot
        Properties: cursor, total_candles, symbol, timeframe, replay_date, source_path

    Blocked operations (raise LookaheadGuardError):
        previous()  — backward navigation
        reset()     — rewinding to start
        peek_next() — direct lookahead

    Usage:
        engine = ReplayEngine("outputs/candles/TICKER_2024-01-15_2m.jsonl")
        replay = BacktestReplay(engine)
        while not replay.finished():
            candle = replay.current()
            # ... process candle ...
            replay.next()
    """

    def __init__(self, engine: ReplayEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Permitted: forward navigation
    # ------------------------------------------------------------------

    def current(self) -> CandleRecord:
        """Return the candle at the current cursor position."""
        return self._engine.current()

    def next(self) -> CandleRecord:
        """Advance cursor one candle forward. Raises EndOfReplay at the last candle."""
        return self._engine.next()

    def goto(self, timestamp: int | str) -> CandleRecord:
        """Jump to a candle by timestamp. Only forward jumps are permitted.

        Raises LookaheadGuardError if the target timestamp is before the
        current candle's timestamp.
        Raises TimestampNotFound if no candle matches.
        """
        ts_int = _parse_timestamp(timestamp)
        current_ts = self._engine.current().timestamp

        if ts_int < current_ts:
            raise LookaheadGuardError(
                f"BacktestReplay.goto() only permits forward jumps. "
                f"Target ts={ts_int} is before current ts={current_ts}. "
                "Use ReplayEngine directly if backward navigation is required."
            )

        return self._engine.goto(ts_int)

    # ------------------------------------------------------------------
    # Permitted: state inspection
    # ------------------------------------------------------------------

    def finished(self) -> bool:
        """True when the cursor is at the last candle."""
        return self._engine.finished()

    def at_beginning(self) -> bool:
        """True when the cursor is at the first candle."""
        return self._engine.at_beginning()

    def state(self) -> ReplayState:
        """Return a frozen snapshot of current replay position."""
        return self._engine.state()

    # ------------------------------------------------------------------
    # Blocked: backward / peek operations
    # ------------------------------------------------------------------

    def previous(self) -> None:
        raise LookaheadGuardError(
            "BacktestReplay.previous() is not permitted. "
            "Backward navigation during backtesting risks double-processing candles. "
            "Use ReplayEngine directly if review navigation is required."
        )

    def reset(self) -> None:
        raise LookaheadGuardError(
            "BacktestReplay.reset() is not permitted. "
            "Resetting during backtesting would re-expose already-processed candles. "
            "Create a new BacktestReplay instance to restart."
        )

    def peek_next(self) -> None:
        raise LookaheadGuardError(
            "BacktestReplay.peek_next() is not permitted. "
            "Reading the next candle before advancing is lookahead bias."
        )

    # ------------------------------------------------------------------
    # Properties (delegated, read-only)
    # ------------------------------------------------------------------

    @property
    def cursor(self) -> int:
        return self._engine.cursor

    @property
    def total_candles(self) -> int:
        return self._engine.total_candles

    @property
    def symbol(self) -> str:
        return self._engine.symbol

    @property
    def timeframe(self) -> str:
        return self._engine.timeframe

    @property
    def replay_date(self) -> str:
        return self._engine.replay_date

    @property
    def source_path(self) -> Path:
        return self._engine.source_path

    # ------------------------------------------------------------------
    # Iteration (forward only — yields all candles including last)
    # ------------------------------------------------------------------

    def __iter__(self) -> "BacktestReplay":
        self._iter_done = False
        return self

    def __next__(self) -> CandleRecord:
        if self._iter_done:
            raise StopIteration
        candle = self.current()
        if self.finished():
            self._iter_done = True
        else:
            self.next()
        return candle

    def __len__(self) -> int:
        return self._engine.total_candles

    def __repr__(self) -> str:
        return (
            f"BacktestReplay({self._engine.source_path.name!r}, "
            f"cursor={self.cursor}/{self.total_candles - 1}, "
            f"finished={self.finished()})"
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, path: str | Path) -> "BacktestReplay":
        """Convenience constructor: load JSONL and wrap in BacktestReplay."""
        return cls(ReplayEngine(path))

    @classmethod
    def from_validated_path(cls, path: str | Path) -> "BacktestReplay":
        """Load JSONL and enforce preflight validation before replay.

        Identical to from_path() but calls require_valid_collection() first.
        Raises StaleCollectionError if the collection has no valid preflight
        companion file — it was gathered without the mandatory chart preflight
        check and cannot be trusted for backtesting.

        Use this method for all production backtest runs.
        Use from_path() only for unit tests with synthetic JSONL fixtures.

        Args:
            path: Path to the JSONL collection file.

        Raises:
            StaleCollectionError: If the collection is stale or missing preflight.
        """
        path = Path(path)
        require_valid_collection(path)
        return cls(ReplayEngine(path))
