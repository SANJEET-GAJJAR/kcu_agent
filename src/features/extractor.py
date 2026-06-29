"""Feature extractor — drives BacktestReplay and produces one FeatureRecord per candle.

Imports BacktestReplay exclusively. ReplayEngine is never imported here.
No trading logic. No KCU-specific code.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.collector.candle_record import CandleRecord
from src.collector.session_clock import session_end_timestamp
from src.engine.backtest_replay import BacktestReplay
from src.engine.policy_replay import PolicyReplay
from src.features import candle_features as cf
from src.features.feature_config import FeatureConfig
from src.features.feature_record import FeatureRecord
from src.features.rolling_window import RollingWindow

log = logging.getLogger(__name__)


class FeatureExtractor:
    """Extract features from a BacktestReplay one candle at a time.

    Usage:
        replay = BacktestReplay.from_path("outputs/candles/TICKER_2024-01-15_2m.jsonl")
        extractor = FeatureExtractor(replay)
        records = extractor.run()           # process all candles
        # or step-by-step:
        record = extractor.step()           # extract for current candle and advance
    """

    def __init__(
        self,
        replay: BacktestReplay | PolicyReplay,
        config: FeatureConfig | None = None,
    ) -> None:
        # Enforce replay-safe cursor — reject raw ReplayEngine instances
        if not isinstance(replay, (BacktestReplay, PolicyReplay)):
            raise TypeError(
                f"FeatureExtractor requires a BacktestReplay or PolicyReplay instance, "
                f"got {type(replay).__name__}. "
                "Wrap your ReplayEngine with BacktestReplay first, or use PolicyReplay "
                "for dual-timeframe sessions."
            )
        self._replay = replay
        self._config = config or FeatureConfig()
        self._window = RollingWindow(self._config.max_window)
        self._candle_index: int = 0
        self._session_open_price: float | None = None

        # Compute session boundary timestamps once per replay_date
        self._market_open_ts: int = session_end_timestamp(
            replay.replay_date, self._config.market_open_et
        )
        self._market_close_ts: int = session_end_timestamp(
            replay.replay_date, self._config.market_close_et
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> list[FeatureRecord]:
        """Process all remaining candles. Returns one FeatureRecord per candle."""
        records: list[FeatureRecord] = []
        while True:
            records.append(self._extract_current())
            if self._replay.finished():
                break
            self._replay.next()
        log.info(
            "Feature extraction complete: %d records for %s %s @ %s",
            len(records), self._replay.symbol,
            self._replay.replay_date, self._replay.timeframe,
        )
        return records

    def step(self) -> FeatureRecord:
        """Extract features for the current candle and advance the replay.

        Returns the FeatureRecord for the candle that was current before advancing.
        Raises EndOfReplay if called when already at the last candle.
        """
        record = self._extract_current()
        if not self._replay.finished():
            self._replay.next()
        return record

    @property
    def candle_index(self) -> int:
        return self._candle_index

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extract_current(self) -> FeatureRecord:
        """Extract all features for the candle currently at the replay cursor.

        Does NOT advance the cursor or push to window — caller manages that.
        """
        current = self._replay.current()
        window = self._window.snapshot()   # past candles only
        config = self._config
        ts = current.snapshot.timestamp

        # --- Price action: single-candle ---
        body = cf.candle_body(current)
        u_wick = cf.upper_wick(current)
        l_wick = cf.lower_wick(current)
        rng = cf.candle_range(current)
        b_pct = cf.body_pct(current)

        # --- Price action: multi-candle ---
        atr_val = cf.atr(window, config.atr_window)
        gap = cf.gap_from_prev(current, window)
        dist_prev_close = cf.distance_from_prev_close(current, window)

        # --- Structure ---
        hh = cf.is_higher_high(current, window)
        ll = cf.is_lower_low(current, window)
        inside = cf.is_inside_bar(current, window)
        outside = cf.is_outside_bar(current, window)
        c_hh = cf.consecutive_hh(current, window)
        c_ll = cf.consecutive_ll(current, window)
        c_lh = cf.consecutive_lh(current, window)
        c_hl = cf.consecutive_hl(current, window)

        # --- Volume ---
        rvol = cf.relative_volume(current, window, config.rvol_window)

        # --- Time / session ---
        session = cf.classify_session(ts, self._market_open_ts, self._market_close_ts)
        t_since_open = cf.time_since_open_minutes(ts, self._market_open_ts)

        # Track session open price: first regular-session candle's close
        if self._session_open_price is None and session == "regular":
            self._session_open_price = current.snapshot.close

        dist_open = cf.distance_from_session_open(current, self._session_open_price)

        # --- Indicators passthrough ---
        indicators: dict[str, Any] = dict(current.indicators)

        record = FeatureRecord(
            timestamp=ts,
            symbol=current.snapshot.symbol,
            timeframe=current.snapshot.timeframe,
            replay_date=current.snapshot.replay_date,
            candle_index=self._candle_index,
            open=current.snapshot.open,
            high=current.snapshot.high,
            low=current.snapshot.low,
            close=current.snapshot.close,
            volume=current.snapshot.volume,
            candle_body=body,
            upper_wick=u_wick,
            lower_wick=l_wick,
            body_pct=b_pct,
            candle_range=rng,
            atr=atr_val,
            gap_from_prev=gap,
            distance_from_prev_close=dist_prev_close,
            is_higher_high=hh,
            is_lower_low=ll,
            is_inside_bar=inside,
            is_outside_bar=outside,
            consecutive_hh=c_hh,
            consecutive_ll=c_ll,
            consecutive_lh=c_lh,
            consecutive_hl=c_hl,
            relative_volume=rvol,
            session=session,
            time_since_open_minutes=t_since_open,
            distance_from_session_open=dist_open,
            indicators=indicators,
        )

        # Push current to window AFTER extraction — never before
        self._window.push(current)
        self._candle_index += 1

        return record
