"""Feature extraction configuration. No trading logic."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FeatureConfig:
    """Controls all configurable parameters of the feature extractor.

    Defaults are sensible for 2-minute US equity candles.
    All window sizes refer to the number of PAST candles (not including current).
    """
    # Rolling window sizes
    atr_window: int = 14        # candles used for ATR (average true range)
    rvol_window: int = 20       # candles used for relative volume baseline

    # Rolling window capacity — must be >= max(atr_window, rvol_window)
    max_window: int = 50

    # Session boundaries in US Eastern time (HH:MM strings)
    premarket_open_et: str = "04:00"
    market_open_et: str = "09:30"
    market_close_et: str = "16:00"

    def __post_init__(self) -> None:
        if self.max_window < max(self.atr_window, self.rvol_window):
            raise ValueError(
                f"max_window ({self.max_window}) must be >= "
                f"max(atr_window={self.atr_window}, rvol_window={self.rvol_window})"
            )
        if self.atr_window < 1:
            raise ValueError(f"atr_window must be >= 1, got {self.atr_window}")
        if self.rvol_window < 1:
            raise ValueError(f"rvol_window must be >= 1, got {self.rvol_window}")
