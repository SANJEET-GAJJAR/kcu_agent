"""REJECTION_WATCH detector.

Identifies candles with long wicks relative to body and range,
suggesting price attempted a directional move and failed.

Emits REJECTION_WATCH (HYPOTHESIS): only the rejection_wick component is
detectable from candle features. level_context and directional_context
require human review or future phases.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    REJECTION_DETECTABLE_COMPONENTS,
    REJECTION_MISSING_COMPONENTS,
    REJECTION_INVALIDATING_COMPONENTS,
    REJECTION_NO_TRADE_RISK,
    REJECTION_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class RejectionDetector(BaseDetector):
    """Detects rejection wicks — long wick relative to body and range.

    Two signal variants:
      UPPER rejection: upper_wick > body * ratio AND upper_wick >= range * pct
        → price pushed up and failed
      LOWER rejection: lower_wick > body * ratio AND lower_wick >= range * pct
        → price pushed down and failed

    Either variant triggers a REJECTION_WATCH.
    supporting_features includes "rejection_direction": "upper" | "lower" | "both".

    Emits REJECTION_WATCH at source_status=HYPOTHESIS because level_context
    and directional_context cannot be determined from candle features alone.
    """

    @property
    def candidate_type(self) -> str:
        return "REJECTION_WATCH"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if features.candle_range == 0.0:
            return None

        body = features.candle_body
        rng = features.candle_range
        u_wick = features.upper_wick
        l_wick = features.lower_wick

        upper_rej = (
            u_wick > body * cfg.rej_wick_body_ratio
            and u_wick >= rng * cfg.rej_wick_range_pct
        )
        lower_rej = (
            l_wick > body * cfg.rej_wick_body_ratio
            and l_wick >= rng * cfg.rej_wick_range_pct
        )

        if not upper_rej and not lower_rej:
            return None

        if upper_rej and lower_rej:
            direction = "both"
        elif upper_rej:
            direction = "upper"
        else:
            direction = "lower"

        reasons: list[str] = []
        codes: list[str] = []

        if upper_rej:
            reasons.append(
                f"upper wick ({u_wick:.4f}) > body*{cfg.rej_wick_body_ratio} "
                f"({body * cfg.rej_wick_body_ratio:.4f})"
                f" and >= range*{cfg.rej_wick_range_pct} ({rng * cfg.rej_wick_range_pct:.4f})"
            )
            codes.append(ReasonCode.UPPER_REJECTION_WICK)
        if lower_rej:
            reasons.append(
                f"lower wick ({l_wick:.4f}) > body*{cfg.rej_wick_body_ratio} "
                f"({body * cfg.rej_wick_body_ratio:.4f})"
                f" and >= range*{cfg.rej_wick_range_pct} ({rng * cfg.rej_wick_range_pct:.4f})"
            )
            codes.append(ReasonCode.LOWER_REJECTION_WICK)
        if upper_rej and lower_rej:
            codes = [ReasonCode.BOTH_REJECTION_WICKS]

        return self._make_event(
            features,
            source_status=REJECTION_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=codes,
            supporting_features={
                "upper_wick": u_wick,
                "lower_wick": l_wick,
                "candle_body": body,
                "candle_range": rng,
                "body_pct": features.body_pct,
                "rejection_direction": direction,
            },
            supporting_components=list(REJECTION_DETECTABLE_COMPONENTS),
            required_missing_components=list(REJECTION_MISSING_COMPONENTS),
            invalidating_components=list(REJECTION_INVALIDATING_COMPONENTS),
            no_trade_risk=list(REJECTION_NO_TRADE_RISK),
        )
