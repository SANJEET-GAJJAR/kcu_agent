"""LTP_WATCH detector.

Identifies candles showing compression — small range relative to ATR,
small body — suggesting price is pausing or coiling near a potential level.

Emits LTP_WATCH (HYPOTHESIS): only the patience_candle component is
detectable from candle features. level_context and trend_context require
human review or future phases.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    KCUSourceStatus,
    LTP_DETECTABLE_COMPONENTS,
    LTP_MISSING_COMPONENTS,
    LTP_INVALIDATING_COMPONENTS,
    LTP_NO_TRADE_RISK,
    LTP_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class LTPDetector(BaseDetector):
    """Detects candles with compressed range and small body (patience_candle component).

    Conditions (all must be met):
      1. ATR is available (requires at least one prior candle).
      2. candle_range < ATR * ltp_compression_ratio.
      3. body_pct is None (doji) OR body_pct < ltp_max_body_pct.

    Emits LTP_WATCH at source_status=HYPOTHESIS because level_context and
    trend_context cannot be determined from candle features alone.
    """

    @property
    def candidate_type(self) -> str:
        return "LTP_WATCH"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if features.atr is None:
            return None

        compression_threshold = features.atr * cfg.ltp_compression_ratio

        if features.candle_range >= compression_threshold:
            return None

        is_small_body = (
            features.body_pct is None
            or features.body_pct < cfg.ltp_max_body_pct
        )
        if not is_small_body:
            return None

        reasons = [
            f"compressed range ({features.candle_range:.4f} < "
            f"ATR*{cfg.ltp_compression_ratio} = {compression_threshold:.4f})",
        ]
        codes = [ReasonCode.COMPRESSED_RANGE]

        if features.body_pct is None:
            reasons.append("doji body")
            codes.append(ReasonCode.DOJI_BODY)
        else:
            reasons.append(f"small body ({features.body_pct:.1f}% < {cfg.ltp_max_body_pct}%)")
            codes.append(ReasonCode.SMALL_BODY)

        return self._make_event(
            features,
            source_status=LTP_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=codes,
            supporting_features={
                "candle_range": features.candle_range,
                "atr": features.atr,
                "compression_threshold": compression_threshold,
                "body_pct": features.body_pct,
                "session": features.session,
            },
            supporting_components=list(LTP_DETECTABLE_COMPONENTS),
            required_missing_components=list(LTP_MISSING_COMPONENTS),
            invalidating_components=list(LTP_INVALIDATING_COMPONENTS),
            no_trade_risk=list(LTP_NO_TRADE_RISK),
        )
