"""BOUNCE_WATCH detector.

Identifies candles that stop making new extremes and show a directional wick
larger than the body — suggesting buyers or sellers are reacting at a level
without necessarily committing to a full reversal.

Emits BOUNCE_WATCH (PARTIALLY_COVERED): support_reaction and directional_wick
are detectable; level_context requires human review.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    BOUNCE_DETECTABLE_COMPONENTS,
    BOUNCE_MISSING_COMPONENTS,
    BOUNCE_INVALIDATING_COMPONENTS,
    BOUNCE_NO_TRADE_RISK,
    BOUNCE_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class BounceDetector(BaseDetector):
    """Detects price reactions at levels — lower low failure with bullish wick,
    or higher high failure with bearish wick.

    Bullish bounce candidate:
      is_lower_low is False AND lower_wick > upper_wick AND lower_wick > candle_body * ratio
      (buyers absorbed selling below; price pushed back up)

    Bearish bounce candidate:
      is_higher_high is False AND upper_wick > lower_wick AND upper_wick > candle_body * ratio
      (sellers absorbed buying above; price pushed back down)

    Distinct from REVERSAL_WATCH: bounce does not require a prior streak — just the
    immediate prior-candle comparison (is_lower_low / is_higher_high).

    Emits BOUNCE_WATCH at source_status=PARTIALLY_COVERED because support_reaction
    and directional_wick are detectable; only level_context remains unverifiable.
    """

    @property
    def candidate_type(self) -> str:
        return "BOUNCE_WATCH"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if not window:
            return None

        if features.is_lower_low is None or features.is_higher_high is None:
            return None

        ratio = cfg.bounce_wick_body_ratio
        u_wick = features.upper_wick
        l_wick = features.lower_wick
        body = features.candle_body

        bullish_bounce = (
            not features.is_lower_low
            and l_wick > u_wick
            and l_wick > body * ratio
        )
        bearish_bounce = (
            not features.is_higher_high
            and u_wick > l_wick
            and u_wick > body * ratio
        )

        if not bullish_bounce and not bearish_bounce:
            return None

        direction = "bullish" if bullish_bounce else "bearish"
        active_wick = l_wick if bullish_bounce else u_wick
        wick_label = "lower_wick" if bullish_bounce else "upper_wick"
        wick_code = ReasonCode.DIRECTIONAL_LOWER_WICK if bullish_bounce else ReasonCode.DIRECTIONAL_UPPER_WICK
        failed_code = ReasonCode.FAILED_LOWER_LOW if bullish_bounce else ReasonCode.FAILED_HIGHER_HIGH

        reasons = [
            f"{direction} bounce: {'lower low' if bullish_bounce else 'higher high'} failed",
            f"{wick_label} ({active_wick:.4f}) > body ({body:.4f}) * {ratio}",
            f"{wick_label} dominates range",
        ]

        return self._make_event(
            features,
            source_status=BOUNCE_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=[failed_code, wick_code],
            supporting_features={
                "direction": direction,
                "upper_wick": u_wick,
                "lower_wick": l_wick,
                "candle_body": body,
                "candle_range": features.candle_range,
                "is_higher_high": features.is_higher_high,
                "is_lower_low": features.is_lower_low,
                "body_pct": features.body_pct,
            },
            supporting_components=list(BOUNCE_DETECTABLE_COMPONENTS),
            required_missing_components=list(BOUNCE_MISSING_COMPONENTS),
            invalidating_components=list(BOUNCE_INVALIDATING_COMPONENTS),
            no_trade_risk=list(BOUNCE_NO_TRADE_RISK),
        )
