"""CHOP detector.

Identifies candles with structural signs of choppy, directionless price action:
inside bars or tiny body with no new structural extreme in either direction.

Emits CHOP (PARTIALLY_COVERED): contained_range is structurally detectable.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    CHOP_DETECTABLE_COMPONENTS,
    CHOP_MISSING_COMPONENTS,
    CHOP_INVALIDATING_COMPONENTS,
    CHOP_NO_TRADE_RISK,
    CHOP_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class ChopDetector(BaseDetector):
    """Detects choppy price action conditions.

    Two conditions that independently trigger CHOP:

    1. Inside bar: current range entirely within prior range.
       (is_inside_bar is True — requires at least one prior candle)

    2. Structural non-commitment: NOT a new high AND NOT a new low AND tiny body.
       (is_higher_high is False AND is_lower_low is False AND body_pct < chop_max_body_pct)
       Requires prior candle (is_higher_high and is_lower_low are not None).

    Either condition alone triggers CHOP.
    Emits CHOP at source_status=PARTIALLY_COVERED (contained_range is fully detectable).
    """

    @property
    def candidate_type(self) -> str:
        return "CHOP"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if not window:
            return None

        inside_bar = features.is_inside_bar is True

        structural_chop = (
            features.is_higher_high is not None
            and features.is_lower_low is not None
            and not features.is_higher_high
            and not features.is_lower_low
            and features.body_pct is not None
            and features.body_pct < cfg.chop_max_body_pct
        )

        if not inside_bar and not structural_chop:
            return None

        reasons: list[str] = []
        codes: list[str] = []

        if inside_bar:
            reasons.append("inside bar: range contained within prior candle")
            codes.append(ReasonCode.INSIDE_BAR)
        if structural_chop:
            reasons.append(
                f"no new high or low with tiny body "
                f"({features.body_pct:.1f}% < {cfg.chop_max_body_pct}%)"
            )
            codes.append(ReasonCode.STRUCTURAL_CHOP)

        chop_trigger = (
            "inside_bar" if inside_bar and not structural_chop
            else "structural" if structural_chop and not inside_bar
            else "both"
        )

        return self._make_event(
            features,
            source_status=CHOP_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=codes,
            supporting_features={
                "is_inside_bar": features.is_inside_bar,
                "is_higher_high": features.is_higher_high,
                "is_lower_low": features.is_lower_low,
                "body_pct": features.body_pct,
                "candle_range": features.candle_range,
                "consecutive_hh": features.consecutive_hh,
                "consecutive_ll": features.consecutive_ll,
                "chop_trigger": chop_trigger,
            },
            supporting_components=list(CHOP_DETECTABLE_COMPONENTS),
            required_missing_components=list(CHOP_MISSING_COMPONENTS),
            invalidating_components=list(CHOP_INVALIDATING_COMPONENTS),
            no_trade_risk=list(CHOP_NO_TRADE_RISK),
        )
