"""Per-setup-type confirmation evaluators for Phase 4B.

Each evaluator is stateless: it takes a CandidateEvent and FeatureRecord(s),
applies deterministic KCU component checks, and returns a ConfirmationEvent.

Taxonomy:
  Immediate evaluators (same candle as the WATCH):
    LTPEvaluator         — always REJECTED; level_context + trend_context unverified
    RejectionEvaluator   — always REJECTED; level_context + directional_context unverified
    ReversalEvaluator    — always REJECTED; level_context unverified
    BounceEvaluator      — always REJECTED; level_context unverified

  Deferred evaluators (evaluated at candle N+1):
    FailedLTPWatchEvaluator  — CONFIRMED or REJECTED based on next-candle decisiveness
    ChopEvaluator            — CONFIRMED or REJECTED based on next-candle expansion

No trading logic. No entry, stop, target, sizing. No score.
"""
from __future__ import annotations

from src.detectors.candidate_event import CandidateEvent
from src.detectors.confirmation_config import ConfirmationConfig
from src.detectors.confirmation_event import (
    ConfirmationEvent,
    ConfirmationOutcome,
    ConfirmationReasonCode,
    SETUP_TYPE_MAP,
)
from src.detectors.kcu_candidate_contract import KCUSourceStatus
from src.features.feature_record import FeatureRecord


# ---------------------------------------------------------------------------
# Shared construction helpers
# ---------------------------------------------------------------------------

def _reject(
    candidate: CandidateEvent,
    eval_features: FeatureRecord,
    *,
    confirmed_components: list[str],
    missing_components: list[str],
    invalidating_components: list[str],
    reasons: list[str],
    reason_codes: list[str],
) -> ConfirmationEvent:
    return ConfirmationEvent(
        timestamp=candidate.timestamp,
        symbol=candidate.symbol,
        timeframe=candidate.timeframe,
        replay_date=candidate.replay_date,
        candle_index=candidate.candle_index,
        evaluated_at_candle_index=eval_features.candle_index,
        evaluated_at_timestamp=eval_features.timestamp,
        watch_type=candidate.candidate_type,
        setup_type=SETUP_TYPE_MAP.get(candidate.candidate_type, candidate.candidate_type),
        outcome=ConfirmationOutcome.REJECTED_SETUP,
        grade=None,
        source_status=candidate.source_status,
        confirmed_components=confirmed_components,
        missing_components=missing_components,
        invalidating_components=invalidating_components,
        reasons=reasons,
        reason_codes=reason_codes,
        candidate_candle_index=candidate.candle_index,
        candidate_timestamp=candidate.timestamp,
        candidate_reason_codes=list(candidate.reason_codes),
    )


def _confirm(
    candidate: CandidateEvent,
    eval_features: FeatureRecord,
    *,
    grade: str,
    confirmed_components: list[str],
    reasons: list[str],
    reason_codes: list[str],
) -> ConfirmationEvent:
    return ConfirmationEvent(
        timestamp=candidate.timestamp,
        symbol=candidate.symbol,
        timeframe=candidate.timeframe,
        replay_date=candidate.replay_date,
        candle_index=candidate.candle_index,
        evaluated_at_candle_index=eval_features.candle_index,
        evaluated_at_timestamp=eval_features.timestamp,
        watch_type=candidate.candidate_type,
        setup_type=SETUP_TYPE_MAP.get(candidate.candidate_type, candidate.candidate_type),
        outcome=ConfirmationOutcome.CONFIRMED_SETUP,
        grade=grade,
        source_status=KCUSourceStatus.CONFIRMED,
        confirmed_components=confirmed_components,
        missing_components=[],
        invalidating_components=[],
        reasons=reasons,
        reason_codes=reason_codes,
        candidate_candle_index=candidate.candle_index,
        candidate_timestamp=candidate.timestamp,
        candidate_reason_codes=list(candidate.reason_codes),
    )


# ---------------------------------------------------------------------------
# Immediate evaluators — resolved at the same candle as the WATCH
# ---------------------------------------------------------------------------

class LTPEvaluator:
    """LTP_WATCH → always REJECTED_SETUP in Phase 4B.

    Requires level_context (price at/near a prior key level) and trend_context
    (identifiable directional bias). Neither is determinable from candle features
    alone. A level database is required (future phase).

    patience_candle is confirmed by the WATCH itself but insufficient alone.
    """

    def evaluate_immediate(
        self,
        candidate: CandidateEvent,
        features: FeatureRecord,
        _config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=list(candidate.required_missing_components),
            invalidating_components=[],
            reasons=[
                "level_context cannot be verified from candle features in Phase 4B "
                "(requires level database — future phase)",
                "trend_context cannot be verified from candle features in Phase 4B "
                "(requires higher-timeframe context — future phase)",
                "patience_candle confirmed but insufficient without level and trend context",
            ],
            reason_codes=[
                ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED,
                ConfirmationReasonCode.TREND_CONTEXT_UNVERIFIED,
            ],
        )


class RejectionEvaluator:
    """REJECTION_WATCH → always REJECTED_SETUP in Phase 4B.

    Requires level_context and directional_context. Neither is determinable
    from candle features. rejection_wick is confirmed by the WATCH.
    """

    def evaluate_immediate(
        self,
        candidate: CandidateEvent,
        features: FeatureRecord,
        _config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=list(candidate.required_missing_components),
            invalidating_components=[],
            reasons=[
                "level_context cannot be verified from candle features in Phase 4B "
                "(requires level database — future phase)",
                "directional_context cannot be verified from candle features in Phase 4B "
                "(requires trend context — future phase)",
                "rejection_wick confirmed but insufficient without level and directional context",
            ],
            reason_codes=[
                ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED,
                ConfirmationReasonCode.DIRECTIONAL_CONTEXT_UNVERIFIED,
            ],
        )


class ReversalEvaluator:
    """REVERSAL_WATCH → always REJECTED_SETUP in Phase 4B.

    trend_exhaustion and change_of_character are confirmed by the WATCH.
    level_context (reversal at a prior key level) is not verifiable from
    candle features. Confirmation candle check is skipped because without
    level_context the setup cannot be confirmed regardless.
    """

    def evaluate_immediate(
        self,
        candidate: CandidateEvent,
        features: FeatureRecord,
        _config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=list(candidate.required_missing_components),
            invalidating_components=[],
            reasons=[
                "level_context cannot be verified from candle features in Phase 4B "
                "(requires level database — future phase)",
                "trend_exhaustion and change_of_character confirmed by WATCH; "
                "confirmation_candle check deferred until level_context is available",
            ],
            reason_codes=[
                ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED,
            ],
        )


class BounceEvaluator:
    """BOUNCE_WATCH → always REJECTED_SETUP in Phase 4B.

    support_reaction and directional_wick are confirmed by the WATCH.
    level_context (bounce at a prior key level) is not verifiable from
    candle features. Reaction confirmation check is skipped accordingly.
    """

    def evaluate_immediate(
        self,
        candidate: CandidateEvent,
        features: FeatureRecord,
        _config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=list(candidate.required_missing_components),
            invalidating_components=[],
            reasons=[
                "level_context cannot be verified from candle features in Phase 4B "
                "(requires level database — future phase)",
                "support_reaction and directional_wick confirmed by WATCH; "
                "reaction_confirmation check deferred until level_context is available",
            ],
            reason_codes=[
                ConfirmationReasonCode.LEVEL_CONTEXT_UNVERIFIED,
            ],
        )


# ---------------------------------------------------------------------------
# Deferred evaluators — resolved at candle N+1 (one candle after the WATCH)
# ---------------------------------------------------------------------------

class FailedLTPWatchEvaluator:
    """FAILED_LTP_WATCH confirmation: evaluated at candle N+1.

    All required components (prior_compression, expansion_failure) are
    structurally detectable — no missing components.

    Invalidation check at N+1: if the next candle shows a decisive
    directional break (large committed body + new structural extreme),
    the setup is invalidated → REJECTED_SETUP.

    If no decisive break at N+1 → CONFIRMED_SETUP with grade based on
    how indecisive the expansion candle's body was.
    """

    def evaluate_deferred(
        self,
        candidate: CandidateEvent,
        next_features: FeatureRecord,
        config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        body_pct = next_features.body_pct
        decisive_break = (
            body_pct is not None
            and body_pct >= config.failed_ltp_decisive_body_pct
            and (
                next_features.is_higher_high is True
                or next_features.is_lower_low is True
            )
        )

        if decisive_break:
            direction = (
                "higher_high" if next_features.is_higher_high is True else "lower_low"
            )
            return _reject(
                candidate,
                next_features,
                confirmed_components=list(candidate.supporting_components),
                missing_components=[],
                invalidating_components=["decisive_directional_break"],
                reasons=[
                    f"next candle ({direction}) shows decisive directional break: "
                    f"body_pct={body_pct:.1f}% >= {config.failed_ltp_decisive_body_pct}%"
                ],
                reason_codes=[ConfirmationReasonCode.DECISIVE_DIRECTIONAL_BREAK],
            )

        grade = self._grade(candidate, config)
        exp_body = candidate.supporting_features.get("current_body_pct")
        body_desc = (
            f"expansion body_pct={exp_body:.1f}%"
            if exp_body is not None
            else "expansion body indecisive (doji)"
        )
        return _confirm(
            candidate,
            next_features,
            grade=grade,
            confirmed_components=list(candidate.supporting_components),
            reasons=[
                "prior_compression confirmed",
                "expansion_failure confirmed",
                f"no decisive directional break at N+1 ({body_desc}, grade={grade})",
            ],
            reason_codes=[
                ConfirmationReasonCode.NO_INVALIDATING_COMPONENT,
                ConfirmationReasonCode.ALL_COMPONENTS_VERIFIED,
            ],
        )

    def force_reject(
        self,
        candidate: CandidateEvent,
        as_of_features: FeatureRecord,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            as_of_features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=[],
            invalidating_components=[],
            reasons=["confirmation window expired — no subsequent candle available"],
            reason_codes=[ConfirmationReasonCode.CONFIRMATION_WINDOW_EXPIRED],
        )

    def _grade(self, candidate: CandidateEvent, config: ConfirmationConfig) -> str:
        body_pct = candidate.supporting_features.get("current_body_pct")
        if body_pct is None:
            return "A"  # doji body = maximally indecisive
        if body_pct < config.failed_ltp_grade_a_body_pct:
            return "A"
        if body_pct < config.failed_ltp_grade_b_body_pct:
            return "B"
        return "C"


class ChopEvaluator:
    """CHOP confirmation: evaluated at candle N+1.

    All required components (contained_range) are structurally detectable —
    no missing components.

    Invalidation check at N+1: if the next candle makes a new higher high
    or lower low (directional range expansion), the chop is invalidated
    → REJECTED_SETUP.

    If no directional expansion at N+1 → CONFIRMED_SETUP.
    Grade is based on the strength of containment in the original CHOP candle.
    """

    def evaluate_deferred(
        self,
        candidate: CandidateEvent,
        next_features: FeatureRecord,
        _config: ConfirmationConfig,
    ) -> ConfirmationEvent:
        directional_expansion = (
            next_features.is_higher_high is True
            or next_features.is_lower_low is True
        )

        if directional_expansion:
            direction = (
                "higher_high" if next_features.is_higher_high is True else "lower_low"
            )
            return _reject(
                candidate,
                next_features,
                confirmed_components=list(candidate.supporting_components),
                missing_components=[],
                invalidating_components=["directional_range_expansion"],
                reasons=[f"next candle broke out directionally ({direction})"],
                reason_codes=[ConfirmationReasonCode.DIRECTIONAL_RANGE_EXPANSION],
            )

        grade = self._grade(candidate)
        trigger = candidate.supporting_features.get("chop_trigger", "unknown")
        return _confirm(
            candidate,
            next_features,
            grade=grade,
            confirmed_components=list(candidate.supporting_components),
            reasons=[
                f"chop trigger confirmed: {trigger}",
                "no directional expansion at N+1",
            ],
            reason_codes=[
                ConfirmationReasonCode.NO_INVALIDATING_COMPONENT,
                ConfirmationReasonCode.ALL_COMPONENTS_VERIFIED,
            ],
        )

    def force_reject(
        self,
        candidate: CandidateEvent,
        as_of_features: FeatureRecord,
    ) -> ConfirmationEvent:
        return _reject(
            candidate,
            as_of_features,
            confirmed_components=list(candidate.supporting_components),
            missing_components=[],
            invalidating_components=[],
            reasons=["confirmation window expired — no subsequent candle available"],
            reason_codes=[ConfirmationReasonCode.CONFIRMATION_WINDOW_EXPIRED],
        )

    def _grade(self, candidate: CandidateEvent) -> str:
        trigger = candidate.supporting_features.get("chop_trigger", "")
        if trigger in ("inside_bar", "both"):
            return "A"
        return "B"
