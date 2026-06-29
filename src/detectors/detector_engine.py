"""DetectorEngine — aggregates all registered detectors and processes FeatureRecords.

Plugin architecture: any BaseDetector subclass can be registered at construction
or via register(). No modification of existing code required to add detectors.

No trading logic. No statistics. No learning.
"""
from __future__ import annotations

import logging
from collections import deque

from src.detectors.base_detector import BaseDetector, DetectorConfig
from src.detectors.candidate_event import CandidateEvent
from src.features.feature_record import FeatureRecord

log = logging.getLogger(__name__)


class DetectorEngine:
    """Routes each FeatureRecord through all registered detectors.

    Maintains a rolling window of recent FeatureRecords so detectors
    that require prior-candle context receive it without storing state.

    Plugin API:
        engine = DetectorEngine(detectors=[MyDetector()])
        engine.register(AnotherDetector())

    Usage:
        engine = DetectorEngine.default()
        events = engine.run(feature_records)
        # or candle-by-candle:
        events = engine.process(feature_record)
    """

    def __init__(
        self,
        detectors: list[BaseDetector],
        window_size: int = 10,
    ) -> None:
        if not detectors:
            raise ValueError("DetectorEngine requires at least one detector")
        self._detectors: list[BaseDetector] = list(detectors)
        self._window: deque[FeatureRecord] = deque(maxlen=window_size)
        self._window_size = window_size

    # ------------------------------------------------------------------
    # Plugin API
    # ------------------------------------------------------------------

    def register(self, detector: BaseDetector) -> None:
        """Add a detector to the engine. Takes effect on the next process() call."""
        self._detectors.append(detector)

    @property
    def detector_types(self) -> list[str]:
        """Ordered list of candidate types handled by registered detectors."""
        return [d.candidate_type for d in self._detectors]

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(self, features: FeatureRecord) -> list[CandidateEvent]:
        """Run all detectors on one FeatureRecord.

        Returns all CandidateEvents emitted (one per detector that fires).
        Window is updated AFTER detection so detectors never see the current
        candle in their window — no lookahead.
        """
        window = tuple(self._window)
        events: list[CandidateEvent] = []

        for detector in self._detectors:
            event = detector.detect(features, window)
            if event is not None:
                events.append(event)

        # Push current to window AFTER all detectors have processed it
        self._window.append(features)

        if events:
            log.debug(
                "candle %d: %d candidate(s): %s",
                features.candle_index,
                len(events),
                [e.candidate_type for e in events],
            )

        return events

    def run(self, feature_records: list[FeatureRecord]) -> list[CandidateEvent]:
        """Process a sequence of FeatureRecords in order.

        Returns all emitted events across all candles, in chronological order.
        """
        all_events: list[CandidateEvent] = []
        for fr in feature_records:
            all_events.extend(self.process(fr))

        log.info(
            "DetectorEngine: %d candles processed, %d candidate events emitted",
            len(feature_records),
            len(all_events),
        )
        return all_events

    def reset(self) -> None:
        """Clear the internal window. Use between independent replay sessions."""
        self._window.clear()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(cls, config: DetectorConfig | None = None) -> "DetectorEngine":
        """Pre-loaded with all six built-in detectors.

        Pass a DetectorConfig to tune thresholds across all detectors.
        """
        from src.detectors.ltp_detector import LTPDetector
        from src.detectors.rejection_detector import RejectionDetector
        from src.detectors.reversal_detector import ReversalDetector
        from src.detectors.bounce_detector import BounceDetector
        from src.detectors.failed_ltp_watch_detector import FailedLTPWatchDetector
        from src.detectors.chop_detector import ChopDetector

        cfg = config or DetectorConfig()
        return cls(
            detectors=[
                LTPDetector(cfg),
                RejectionDetector(cfg),
                ReversalDetector(cfg),
                BounceDetector(cfg),
                FailedLTPWatchDetector(cfg),
                ChopDetector(cfg),
            ],
            window_size=10,
        )
