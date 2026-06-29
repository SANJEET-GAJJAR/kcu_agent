"""REVERSAL_WATCH detector.

Identifies candles that show a change-of-character after a clear trend:
a bearish body failing to make a new high after a run of higher highs,
or a bullish body failing to make a new low after a run of lower lows.

Emits REVERSAL_WATCH (PARTIALLY_COVERED): trend_exhaustion and
change_of_character are detectable; level_context requires human review.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    REVERSAL_DETECTABLE_COMPONENTS,
    REVERSAL_MISSING_COMPONENTS,
    REVERSAL_INVALIDATING_COMPONENTS,
    REVERSAL_NO_TRADE_RISK,
    REVERSAL_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class ReversalDetector(BaseDetector):
    """Detects change-of-character candles after a prior trend streak.

    Bearish reversal candidate:
      consecutive_hh >= rev_min_streak AND is_higher_high is False AND close < open

    Bullish reversal candidate:
      consecutive_ll >= rev_min_streak AND is_lower_low is False AND close > open

    Emits REVERSAL_WATCH at source_status=PARTIALLY_COVERED because two of three
    required components (trend_exhaustion + change_of_character) are detectable;
    only level_context remains unverifiable.
    """

    @property
    def candidate_type(self) -> str:
        return "REVERSAL_WATCH"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if not window:
            return None

        if features.is_higher_high is None or features.is_lower_low is None:
            return None

        bearish = (
            features.consecutive_hh >= cfg.rev_min_streak
            and not features.is_higher_high
            and features.close < features.open
        )
        bullish = (
            features.consecutive_ll >= cfg.rev_min_streak
            and not features.is_lower_low
            and features.close > features.open
        )

        if not bearish and not bullish:
            return None

        if bearish:
            direction = "bearish"
            streak_desc = f"consecutive_hh={features.consecutive_hh}"
            codes = [ReasonCode.TREND_STREAK_BROKEN, ReasonCode.FAILED_HIGHER_HIGH, ReasonCode.BEARISH_BODY]
        else:
            direction = "bullish"
            streak_desc = f"consecutive_ll={features.consecutive_ll}"
            codes = [ReasonCode.TREND_STREAK_BROKEN, ReasonCode.FAILED_LOWER_LOW, ReasonCode.BULLISH_BODY]

        reasons = [
            f"{direction} change-of-character after {streak_desc} (min={cfg.rev_min_streak})",
            f"{'failed to make new high' if bearish else 'failed to make new low'}",
            f"{'bearish' if bearish else 'bullish'} body (close {'<' if bearish else '>'} open)",
        ]

        return self._make_event(
            features,
            source_status=REVERSAL_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=codes,
            supporting_features={
                "direction": direction,
                "consecutive_hh": features.consecutive_hh,
                "consecutive_ll": features.consecutive_ll,
                "is_higher_high": features.is_higher_high,
                "is_lower_low": features.is_lower_low,
                "open": features.open,
                "close": features.close,
                "candle_body": features.candle_body,
                "body_pct": features.body_pct,
            },
            supporting_components=list(REVERSAL_DETECTABLE_COMPONENTS),
            required_missing_components=list(REVERSAL_MISSING_COMPONENTS),
            invalidating_components=list(REVERSAL_INVALIDATING_COMPONENTS),
            no_trade_risk=list(REVERSAL_NO_TRADE_RISK),
        )
