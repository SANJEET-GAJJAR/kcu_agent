"""BaseDetector ABC and DetectorConfig.

All detectors inherit BaseDetector. All thresholds live in DetectorConfig.
No trading logic, no learning, no statistics.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.detectors.candidate_event import CandidateEvent
from src.features.feature_record import FeatureRecord


@dataclass
class DetectorConfig:
    """Configurable thresholds used by all built-in detectors.

    All ratios are expressed as multipliers of ATR or as fractions of candle range.
    Changing these values changes sensitivity but never changes detector logic.
    """
    # LTP: compression thresholds
    ltp_compression_ratio: float = 0.5     # range < ATR * ratio → compressed
    ltp_max_body_pct: float = 40.0         # body < this % of range (or None = doji)

    # Rejection: wick thresholds
    rej_wick_body_ratio: float = 2.0       # wick must be > body * ratio
    rej_wick_range_pct: float = 0.40       # wick must be >= range * pct

    # Reversal: minimum prior trend streak
    rev_min_streak: int = 2

    # Bounce: wick-to-body ratio
    bounce_wick_body_ratio: float = 1.0    # directional wick > body

    # Failed LTP Watch
    failed_ltp_compression_ratio: float = 0.5   # prior range < ATR * ratio
    failed_ltp_expansion_ratio: float = 0.7     # current range >= ATR * ratio
    failed_ltp_max_body_pct: float = 30.0       # indecision on the expansion

    # Chop
    chop_max_body_pct: float = 25.0        # tiny body for structural chop

    def __post_init__(self) -> None:
        if self.ltp_compression_ratio <= 0:
            raise ValueError("ltp_compression_ratio must be > 0")
        if not (0.0 < self.ltp_max_body_pct <= 100.0):
            raise ValueError("ltp_max_body_pct must be in (0, 100]")
        if self.rej_wick_body_ratio <= 0:
            raise ValueError("rej_wick_body_ratio must be > 0")
        if not (0.0 < self.rej_wick_range_pct < 1.0):
            raise ValueError("rej_wick_range_pct must be in (0, 1)")
        if self.rev_min_streak < 1:
            raise ValueError("rev_min_streak must be >= 1")
        if self.bounce_wick_body_ratio <= 0:
            raise ValueError("bounce_wick_body_ratio must be > 0")
        if self.failed_ltp_expansion_ratio <= self.failed_ltp_compression_ratio:
            raise ValueError(
                "failed_ltp_expansion_ratio must be > failed_ltp_compression_ratio"
            )
        if not (0.0 < self.chop_max_body_pct <= 100.0):
            raise ValueError("chop_max_body_pct must be in (0, 100]")


class BaseDetector(ABC):
    """Abstract base for all setup candidate detectors.

    Subclasses implement detect() to identify one specific candidate type.
    The method is pure: given current features + past window → event or None.
    No state is stored between candles. No future candles are accessed.

    Plugin API: subclass BaseDetector and register with DetectorEngine.register().
    """

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self._config = config or DetectorConfig()

    @property
    @abstractmethod
    def candidate_type(self) -> str:
        """The WATCH_CANDIDATE_TYPES key this detector emits."""

    @abstractmethod
    def detect(
        self,
        features: FeatureRecord,
        window: tuple[FeatureRecord, ...],
    ) -> CandidateEvent | None:
        """Evaluate one candle.

        Args:
            features: The current candle's extracted features.
            window: Past candles only (oldest at [0], most recent at [-1]).
                    Never contains the current candle. May be empty.

        Returns:
            A CandidateEvent if conditions are met, else None.
        """

    def _make_event(
        self,
        features: FeatureRecord,
        *,
        source_status: str,
        reasons: list[str],
        reason_codes: list[str],
        supporting_features: dict,
        supporting_components: list[str],
        required_missing_components: list[str],
        invalidating_components: list[str],
        no_trade_risk: list[str],
    ) -> CandidateEvent:
        return CandidateEvent(
            timestamp=features.timestamp,
            symbol=features.symbol,
            timeframe=features.timeframe,
            replay_date=features.replay_date,
            candle_index=features.candle_index,
            candidate_type=self.candidate_type,
            source_status=source_status,
            reasons=reasons,
            reason_codes=reason_codes,
            supporting_features=supporting_features,
            supporting_components=supporting_components,
            required_missing_components=required_missing_components,
            invalidating_components=invalidating_components,
            no_trade_risk=no_trade_risk,
        )
