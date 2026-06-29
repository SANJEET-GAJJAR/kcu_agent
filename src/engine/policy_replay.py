"""Dual-timeframe policy replay engine for KCU backtesting.

Merges candles from a 2m collection (before the policy boundary) and a 5m
collection (from the boundary onward) into a single forward-only cursor,
respecting the KCU timeframe policy:
  - Before 10:00 ET: 2m candles (open range + premarket)
  - 10:00 ET onward: 5m candles (main session)

The split point is derived from the policy configuration — not hardcoded.
No lookahead bias: backward navigation and peek operations are blocked.

No trading logic. No analysis. No interpretation.
"""
from __future__ import annotations

import bisect
import logging
from pathlib import Path

from src.collector.candle_record import CandleRecord
from src.collector.chart_preflight import require_valid_collection
from src.collector.jsonl_store import JsonlStore, JsonlStoreError
from src.collector.session_clock import session_end_timestamp
from src.collector.timeframe_policy import (
    TimeframePolicyConfig,
    collection_path,
    load_timeframe_policy,
    require_protocol_ready,
)
from src.engine.backtest_replay import LookaheadGuardError
from src.engine.replay_engine import (
    EndOfReplay,
    ReplayState,
    TimestampNotFound,
    _parse_timestamp,
)

log = logging.getLogger(__name__)


class PolicyReplayError(Exception):
    """Raised when the policy replay cannot be constructed."""


class PolicyReplay:
    """Forward-only dual-timeframe replay cursor.

    Stitches 2m candles (before the policy boundary) with 5m candles
    (from the boundary onward) into a single immutable candle sequence.
    The boundary is derived from the policy configuration (10:00 ET by default).

    Permitted:
        current(), next(), goto() forward-only, finished(), at_beginning(), state()

    Blocked (raise LookaheadGuardError):
        previous(), reset(), peek_next()

    Production usage:
        replay = PolicyReplay.from_protocol(ticker, date, Path("outputs/candles"))

    Test usage (no preflight enforcement):
        replay = PolicyReplay.from_paths(path_2m, path_5m, "2024-01-15")
    """

    def __init__(self, candles: tuple[CandleRecord, ...], source_desc: str, date: str) -> None:
        if not candles:
            raise PolicyReplayError("PolicyReplay requires at least one candle")
        self._candles = candles
        self._timestamps = tuple(c.timestamp for c in candles)
        self._cursor = 0
        self._source_desc = source_desc
        self._date = date
        self._iter_done = False

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_paths(
        cls,
        path_2m: str | Path,
        path_5m: str | Path,
        date: str,
        policy: TimeframePolicyConfig | None = None,
    ) -> "PolicyReplay":
        """Load both files without preflight validation.

        For unit tests and synthetic fixtures only.
        Use from_validated_paths() or from_protocol() for all production runs.
        """
        path_2m = Path(path_2m)
        path_5m = Path(path_5m)
        if policy is None:
            policy = load_timeframe_policy()
        return cls._build(path_2m, path_5m, date, policy)

    @classmethod
    def from_validated_paths(
        cls,
        path_2m: str | Path,
        path_5m: str | Path,
        date: str,
        policy: TimeframePolicyConfig | None = None,
    ) -> "PolicyReplay":
        """Load both files with preflight validation.

        Raises StaleCollectionError if either file is missing a valid preflight
        companion. Use this method for production backtest runs when you have
        explicit paths but are not using the default output directory layout.
        """
        path_2m = Path(path_2m)
        path_5m = Path(path_5m)
        require_valid_collection(path_2m)
        require_valid_collection(path_5m)
        if policy is None:
            policy = load_timeframe_policy()
        return cls._build(path_2m, path_5m, date, policy)

    @classmethod
    def from_protocol(
        cls,
        ticker: str,
        date: str,
        output_dir: str | Path,
        policy: TimeframePolicyConfig | None = None,
    ) -> "PolicyReplay":
        """Production factory: enforce protocol readiness then build replay.

        Calls require_protocol_ready() which verifies both the 2m and 5m
        collection files exist with valid preflight companions.
        Raises ProtocolReadinessError if any required collection is missing or
        has failed preflight.
        """
        output_dir = Path(output_dir)
        if policy is None:
            policy = load_timeframe_policy()
        require_protocol_ready(ticker, date, output_dir, "full_protocol", policy)
        path_2m = collection_path(ticker, date, "2", output_dir)
        path_5m = collection_path(ticker, date, "5", output_dir)
        return cls._build(path_2m, path_5m, date, policy)

    @classmethod
    def _build(
        cls,
        path_2m: Path,
        path_5m: Path,
        date: str,
        policy: TimeframePolicyConfig,
    ) -> "PolicyReplay":
        """Load, split at boundary, deduplicate, and return PolicyReplay."""
        boundary_ts = _policy_boundary_ts(date, policy)

        candles_2m = _load_records(path_2m)
        candles_5m = _load_records(path_5m)

        pre_boundary = [c for c in candles_2m if c.timestamp < boundary_ts]
        post_boundary = [c for c in candles_5m if c.timestamp >= boundary_ts]

        if not pre_boundary and not post_boundary:
            raise PolicyReplayError(
                f"No candles found on either side of the policy boundary "
                f"(boundary_ts={boundary_ts}, date={date})"
            )

        # Sort and deduplicate — 2m wins if both files have the same timestamp
        merged = sorted(pre_boundary + post_boundary, key=lambda c: c.timestamp)
        seen: set[int] = set()
        deduped: list[CandleRecord] = []
        for c in merged:
            if c.timestamp not in seen:
                deduped.append(c)
                seen.add(c.timestamp)

        # Re-index candle_index in meta to be contiguous 0-based over the merged
        # sequence.  The original files each have their own 0-based indices that
        # overlap (2m: 0..N, 5m: 0..M).  FeatureExtractor assigns its own
        # sequential index starting at 0, and OutcomeSimulator reads
        # meta["candle_index"] to advance the cursor — both must use the same
        # numbering.  Mutating the dict is safe: _load_records returns freshly
        # deserialized CandleRecord objects that are not shared with anything.
        for idx, c in enumerate(deduped):
            c.meta["candle_index"] = idx

        source_desc = f"{path_2m.name}+{path_5m.name}"
        log.info(
            "PolicyReplay: %d candles merged (%d pre-boundary 2m, %d post-boundary 5m) "
            "date=%s boundary_ts=%d",
            len(deduped), len(pre_boundary), len(post_boundary), date, boundary_ts,
        )
        return cls(tuple(deduped), source_desc, date)

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
                f"Already at last candle (index={self._cursor}, "
                f"ts={self._candles[self._cursor].timestamp})"
            )
        self._cursor += 1
        return self._candles[self._cursor]

    def goto(self, timestamp: int | str) -> CandleRecord:
        """Jump to a candle by timestamp. Only forward jumps are permitted.

        Raises LookaheadGuardError if the target timestamp is before the
        current candle's timestamp.
        Raises TimestampNotFound if no candle matches.
        """
        ts_int = _parse_timestamp(timestamp)
        current_ts = self.current().timestamp
        if ts_int < current_ts:
            raise LookaheadGuardError(
                f"PolicyReplay.goto() only permits forward jumps. "
                f"Target ts={ts_int} is before current ts={current_ts}."
            )
        idx = bisect.bisect_left(self._timestamps, ts_int)
        if idx >= len(self._timestamps) or self._timestamps[idx] != ts_int:
            raise TimestampNotFound(
                f"No candle with timestamp {ts_int} in merged policy sequence"
            )
        self._cursor = idx
        return self._candles[self._cursor]

    # ------------------------------------------------------------------
    # Blocked: backward / peek operations
    # ------------------------------------------------------------------

    def previous(self) -> None:
        raise LookaheadGuardError(
            "PolicyReplay.previous() is not permitted. "
            "Backward navigation is lookahead bias in backtest mode."
        )

    def reset(self) -> None:
        raise LookaheadGuardError(
            "PolicyReplay.reset() is not permitted. "
            "Create a new PolicyReplay instance to restart."
        )

    def peek_next(self) -> None:
        raise LookaheadGuardError(
            "PolicyReplay.peek_next() is not permitted. "
            "Reading ahead is lookahead bias."
        )

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------

    def finished(self) -> bool:
        """True when the cursor is at the last candle."""
        return self._cursor >= len(self._candles) - 1

    def at_beginning(self) -> bool:
        """True when the cursor is at the first candle."""
        return self._cursor == 0

    def state(self) -> ReplayState:
        """Return a frozen snapshot of current replay position."""
        c = self.current()
        return ReplayState(
            source_path=self._source_desc,
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
    def date(self) -> str:
        return self._date

    # BacktestReplay-compatible properties — required by FeatureExtractor

    @property
    def replay_date(self) -> str:
        """Date string for this replay session (e.g. '2026-06-22')."""
        return self._date

    @property
    def symbol(self) -> str:
        """Symbol from the first candle in the merged sequence."""
        return self._candles[0].snapshot.symbol

    @property
    def timeframe(self) -> str:
        """'policy' — signals dual-timeframe mode to callers."""
        return "policy"

    # ------------------------------------------------------------------
    # Iteration (forward-only; yields all candles including last)
    # ------------------------------------------------------------------

    def __iter__(self) -> "PolicyReplay":
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
        return len(self._candles)

    def __repr__(self) -> str:
        return (
            f"PolicyReplay({self._source_desc!r}, "
            f"cursor={self._cursor}/{len(self._candles) - 1}, "
            f"finished={self.finished()})"
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _policy_boundary_ts(date: str, policy: TimeframePolicyConfig) -> int:
    """Compute the unix timestamp where 2m ends and 5m begins.

    Finds the earliest start time of any 5m window in the policy.
    Raises PolicyReplayError if no 5m window is defined.
    """
    five_m_starts = [w.start for w in policy.windows if w.timeframe == "5"]
    if not five_m_starts:
        raise PolicyReplayError(
            "Timeframe policy has no 5m window defined. "
            "PolicyReplay requires both a 2m and a 5m window."
        )
    earliest_5m_start = min(five_m_starts)
    return session_end_timestamp(date, earliest_5m_start)


def _load_records(path: Path) -> list[CandleRecord]:
    """Load and sort CandleRecords from a JSONL file."""
    if not path.exists():
        raise PolicyReplayError(f"Collection file not found: {path}")
    try:
        store = JsonlStore(path)
        records = store.read_all()
    except JsonlStoreError as exc:
        raise PolicyReplayError(f"Failed to load {path}: {exc}") from exc
    if not records:
        raise PolicyReplayError(f"Collection file is empty: {path}")
    return sorted(records, key=lambda r: r.timestamp)
