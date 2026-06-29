"""ConfirmationEngine — Phase 4B setup confirmation engine.

Consumes WATCH candidates from Phase 4A DetectorEngine and evaluates each
against KCU confirmation requirements. Returns CONFIRMED_SETUP or
REJECTED_SETUP events. No trade management, no entry/stop/target.

Processing model — two tiers per candle:
  1. Deferred pending (added in prior step): evaluated with the current candle
     as the N+1 invalidation-check candle.
  2. New candidates (from current candle's DetectorEngine): immediately
     evaluated or added to pending for the next candle.

Immediate types (resolved at same candle as the WATCH):
  LTP_WATCH, REJECTION_WATCH, REVERSAL_WATCH, BOUNCE_WATCH → always REJECTED
  because level_context is not determinable from candle features in Phase 4B.

Deferred types (resolved at N+1):
  FAILED_LTP_WATCH → CONFIRMED or REJECTED based on next-candle decisiveness
  CHOP             → CONFIRMED or REJECTED based on next-candle expansion

No lookahead: pending items are only evaluated when the next candle arrives.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.detectors.candidate_event import CandidateEvent
from src.detectors.confirmation_config import ConfirmationConfig
from src.detectors.confirmation_event import ConfirmationEvent, ConfirmationOutcome
from src.detectors.setup_evaluators import (
    LTPEvaluator,
    RejectionEvaluator,
    ReversalEvaluator,
    BounceEvaluator,
    FailedLTPWatchEvaluator,
    ChopEvaluator,
)
from src.features.feature_record import FeatureRecord

log = logging.getLogger(__name__)


@dataclass
class _Pending:
    """Holds a deferred candidate and the features at which it was detected."""
    candidate: CandidateEvent
    origin_features: FeatureRecord


class ConfirmationEngine:
    """Evaluates WATCH candidates against KCU confirmation requirements.

    Usage — candle-by-candle:
        engine = ConfirmationEngine()
        for features in candles:
            watch_events = detector_engine.process(features)
            confirm_events = engine.step(watch_events, features)
        final = engine.flush(candles[-1])

    Usage — batch:
        events = ConfirmationEngine().run(feature_records, candidates_per_candle)

    Deterministic: same inputs → same outputs in the same order.
    State: only the list of pending deferred candidates.
    """

    _IMMEDIATE: dict = {
        "LTP_WATCH": LTPEvaluator(),
        "REJECTION_WATCH": RejectionEvaluator(),
        "REVERSAL_WATCH": ReversalEvaluator(),
        "BOUNCE_WATCH": BounceEvaluator(),
    }

    _DEFERRED: dict = {
        "FAILED_LTP_WATCH": FailedLTPWatchEvaluator(),
        "CHOP": ChopEvaluator(),
    }

    def __init__(self, config: ConfirmationConfig | None = None) -> None:
        self._config = config or ConfirmationConfig()
        self._pending: list[_Pending] = []

    def step(
        self,
        candidates: list[CandidateEvent],
        features: FeatureRecord,
    ) -> list[ConfirmationEvent]:
        """Process one candle — deferred pending first, then new candidates.

        Args:
            candidates: WATCH events from DetectorEngine for this candle.
            features:   The current FeatureRecord (same candle as candidates).

        Returns:
            All ConfirmationEvents emitted this step (immediate + deferred).
        """
        results: list[ConfirmationEvent] = []

        # --- Phase 1: evaluate any pending deferred candidates using this candle ---
        still_pending: list[_Pending] = []
        for p in self._pending:
            candles_elapsed = features.candle_index - p.origin_features.candle_index
            evaluator = self._DEFERRED.get(p.candidate.candidate_type)
            if evaluator is None or candles_elapsed < 1:
                still_pending.append(p)
                continue
            ev = evaluator.evaluate_deferred(p.candidate, features, self._config)
            results.append(ev)
        self._pending = still_pending

        # --- Phase 2: evaluate or enqueue new candidates ---
        for candidate in candidates:
            ct = candidate.candidate_type
            if ct in self._IMMEDIATE:
                ev = self._IMMEDIATE[ct].evaluate_immediate(
                    candidate, features, self._config
                )
                results.append(ev)
            elif ct in self._DEFERRED:
                self._pending.append(_Pending(candidate=candidate, origin_features=features))
            else:
                log.warning("ConfirmationEngine: unrecognised candidate_type %r — skipped", ct)

        log.debug(
            "candle %d: %d confirmation event(s) emitted, %d pending",
            features.candle_index,
            len(results),
            len(self._pending),
        )
        return results

    def flush(self, as_of_features: FeatureRecord) -> list[ConfirmationEvent]:
        """Force-reject all remaining pending candidates.

        Call after the last candle has been processed (end of session).
        Clears internal pending state.
        """
        results: list[ConfirmationEvent] = []
        for p in self._pending:
            evaluator = self._DEFERRED.get(p.candidate.candidate_type)
            if evaluator is None:
                continue
            results.append(evaluator.force_reject(p.candidate, as_of_features))
        self._pending.clear()
        return results

    def reset(self) -> None:
        """Clear pending state. Use between independent replay sessions."""
        self._pending.clear()

    @property
    def pending_count(self) -> int:
        """Number of candidates awaiting deferred evaluation."""
        return len(self._pending)

    def run(
        self,
        feature_records: list[FeatureRecord],
        candidates_per_candle: list[list[CandidateEvent]],
    ) -> list[ConfirmationEvent]:
        """Process a full sequence of candles and return all confirmation events.

        Args:
            feature_records:       Ordered FeatureRecords for the session.
            candidates_per_candle: Parallel list; index i = WATCH events from candle i.

        Returns:
            All ConfirmationEvents in chronological order (flush included).
        """
        if len(feature_records) != len(candidates_per_candle):
            raise ValueError(
                f"feature_records ({len(feature_records)}) and "
                f"candidates_per_candle ({len(candidates_per_candle)}) must have equal length"
            )

        all_events: list[ConfirmationEvent] = []
        for features, candidates in zip(feature_records, candidates_per_candle):
            all_events.extend(self.step(candidates, features))

        if feature_records:
            all_events.extend(self.flush(feature_records[-1]))

        confirmed = sum(
            1 for e in all_events if e.outcome == ConfirmationOutcome.CONFIRMED_SETUP
        )
        log.info(
            "ConfirmationEngine: %d candle(s), %d event(s) total "
            "(%d confirmed, %d rejected)",
            len(feature_records),
            len(all_events),
            confirmed,
            len(all_events) - confirmed,
        )
        return all_events
