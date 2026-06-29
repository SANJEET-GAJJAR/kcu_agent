"""FAILED_LTP_WATCH detector.

Identifies candles where a prior compression (LTP-like) was followed by an
expansion candle that failed to commit directionally — suggesting the setup
did not resolve cleanly and the watch window has likely expired.

Emits FAILED_LTP_WATCH (PARTIALLY_COVERED): both prior_compression and
expansion_failure are structurally detectable from candle features.

No entry logic. No level identification. No trade management.
"""
from __future__ import annotations

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import (
    FAILED_LTP_WATCH_DETECTABLE_COMPONENTS,
    FAILED_LTP_WATCH_MISSING_COMPONENTS,
    FAILED_LTP_WATCH_INVALIDATING_COMPONENTS,
    FAILED_LTP_WATCH_NO_TRADE_RISK,
    FAILED_LTP_WATCH_SOURCE_STATUS,
    ReasonCode,
)
from src.features.feature_record import FeatureRecord


class FailedLTPWatchDetector(BaseDetector):
    """Detects failed LTP setup conditions.

    Conditions (all must be met):
      1. window[-1] had ATR available.
      2. Prior candle was compressed: window[-1].candle_range < ATR * compression_ratio.
      3. Current candle expanded: features.candle_range >= ATR * expansion_ratio.
      4. Current candle body is indecisive: body_pct is None OR body_pct < max_body_pct.

    Self-contained: checks compression with its own threshold, not by querying
    whether LTPDetector fired on the prior candle.

    Emits FAILED_LTP_WATCH at source_status=PARTIALLY_COVERED because both
    structural components are detectable from candle features.
    """

    @property
    def candidate_type(self) -> str:
        return "FAILED_LTP_WATCH"

    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        cfg = self._config

        if not window:
            return None

        prior = window[-1]

        if prior.atr is None or features.atr is None:
            return None

        prior_compression_threshold = prior.atr * cfg.failed_ltp_compression_ratio
        if prior.candle_range >= prior_compression_threshold:
            return None

        current_expansion_threshold = features.atr * cfg.failed_ltp_expansion_ratio
        if features.candle_range < current_expansion_threshold:
            return None

        current_indecisive = (
            features.body_pct is None
            or features.body_pct < cfg.failed_ltp_max_body_pct
        )
        if not current_indecisive:
            return None

        reasons = [
            f"prior candle compressed (range {prior.candle_range:.4f} < "
            f"ATR*{cfg.failed_ltp_compression_ratio} = {prior_compression_threshold:.4f})",
            f"current expanded (range {features.candle_range:.4f} >= "
            f"ATR*{cfg.failed_ltp_expansion_ratio} = {current_expansion_threshold:.4f})",
            f"expansion indecisive (body_pct="
            f"{'None' if features.body_pct is None else f'{features.body_pct:.1f}%'}"
            f" < {cfg.failed_ltp_max_body_pct}%)",
        ]

        return self._make_event(
            features,
            source_status=FAILED_LTP_WATCH_SOURCE_STATUS,
            reasons=reasons,
            reason_codes=[ReasonCode.PRIOR_COMPRESSION, ReasonCode.INDECISIVE_EXPANSION],
            supporting_features={
                "prior_candle_index": prior.candle_index,
                "prior_candle_range": prior.candle_range,
                "prior_atr": prior.atr,
                "prior_compression_threshold": prior_compression_threshold,
                "current_candle_range": features.candle_range,
                "current_atr": features.atr,
                "current_expansion_threshold": current_expansion_threshold,
                "current_body_pct": features.body_pct,
            },
            supporting_components=list(FAILED_LTP_WATCH_DETECTABLE_COMPONENTS),
            required_missing_components=list(FAILED_LTP_WATCH_MISSING_COMPONENTS),
            invalidating_components=list(FAILED_LTP_WATCH_INVALIDATING_COMPONENTS),
            no_trade_risk=list(FAILED_LTP_WATCH_NO_TRADE_RISK),
        )
