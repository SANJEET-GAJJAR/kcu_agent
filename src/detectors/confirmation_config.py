"""ConfirmationConfig — all thresholds for the Phase 4B confirmation engine.

No trading logic. No entry, stop, target, sizing, or trade management.
Grading thresholds describe structural quality of the setup pattern, not
profitability or trade viability.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfirmationConfig:
    """Thresholds used by the confirmation evaluators.

    All values describe structural properties of candle patterns.
    None of them imply entry conditions or trade decisions.
    """
    # FAILED_LTP_WATCH: body_pct of the candle AFTER the expansion that
    # triggers rejection (decisive directional break).
    # A large committed body following a FAILED_LTP_WATCH invalidates it.
    failed_ltp_decisive_body_pct: float = 60.0

    # Grading for FAILED_LTP_WATCH CONFIRMED_SETUP:
    # Based on body_pct of the expansion candle itself (from candidate.supporting_features).
    # Smaller body = more indecision = higher grade.
    failed_ltp_grade_a_body_pct: float = 10.0   # very indecisive expansion → A
    failed_ltp_grade_b_body_pct: float = 20.0   # moderately indecisive → B
    # body_pct >= grade_b but < detector max → C

    # Max candles to hold a pending candidate before force-rejecting.
    # In Phase 4B all deferred types resolve at N+1, so this is a safety valve.
    max_confirmation_wait: int = 3

    def __post_init__(self) -> None:
        if not (0.0 < self.failed_ltp_decisive_body_pct <= 100.0):
            raise ValueError(
                "failed_ltp_decisive_body_pct must be in (0, 100], "
                f"got {self.failed_ltp_decisive_body_pct}"
            )
        if not (0.0 < self.failed_ltp_grade_a_body_pct < self.failed_ltp_grade_b_body_pct):
            raise ValueError(
                "failed_ltp_grade_a_body_pct must be > 0 and < failed_ltp_grade_b_body_pct, "
                f"got A={self.failed_ltp_grade_a_body_pct}, B={self.failed_ltp_grade_b_body_pct}"
            )
        if self.max_confirmation_wait < 1:
            raise ValueError(
                f"max_confirmation_wait must be >= 1, got {self.max_confirmation_wait}"
            )
