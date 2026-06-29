"""Execution contract primitives for Phase 5B.

Defines deterministic, implementation-ready outcome semantics without building
the full simulator yet.

Canonical rules:
  - Outcome scanning starts at plan.candle_index + 1.
  - The eval candle can never determine trade outcome.
  - Rejected plans are skipped.
  - Gaps are resolved before intrabar touches.
  - If both stop and target are touched in the same candle, outcome is
    AMBIGUOUS_BOTH_TOUCHED with realized_r=None.
  - End-of-replay/session without resolution is deterministic and unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.simulator.trade_plan import TradePlan, TradePlanDirection


class ExecutionOutcome:
    """Canonical execution outcomes for one hypothetical plan."""
    TARGET_BEFORE_STOP = "TARGET_BEFORE_STOP"
    STOP_BEFORE_TARGET = "STOP_BEFORE_TARGET"
    AMBIGUOUS_BOTH_TOUCHED = "AMBIGUOUS_BOTH_TOUCHED"
    GAP_BEYOND_TARGET = "GAP_BEYOND_TARGET"
    GAP_BEYOND_STOP = "GAP_BEYOND_STOP"
    UNRESOLVED_END_OF_REPLAY = "UNRESOLVED_END_OF_REPLAY"
    SKIPPED_REJECTED_PLAN = "SKIPPED_REJECTED_PLAN"
    ALL_VALUES: frozenset[str] = frozenset({
        "TARGET_BEFORE_STOP",
        "STOP_BEFORE_TARGET",
        "AMBIGUOUS_BOTH_TOUCHED",
        "GAP_BEYOND_TARGET",
        "GAP_BEYOND_STOP",
        "UNRESOLVED_END_OF_REPLAY",
        "SKIPPED_REJECTED_PLAN",
    })


@dataclass(frozen=True)
class ExecutionDecision:
    """Deterministic decision emitted by the execution contract."""
    outcome: str
    realized_r: float | None
    counts_as_win: bool
    counts_as_loss: bool
    reason: str


@dataclass(frozen=True)
class CandleExecutionView:
    """Minimal candle data required for deterministic contract resolution."""
    candle_index: int
    open: float
    high: float
    low: float


def outcome_scan_start_candle_index(plan: TradePlan) -> int:
    """Return the first candle index allowed to determine outcome."""
    return plan.candle_index + 1


def can_scan_outcome_on_candle(plan: TradePlan, candle_index: int) -> bool:
    """True only for candles after the eval candle."""
    return candle_index >= outcome_scan_start_candle_index(plan)


def resolve_candle_outcome(
    plan: TradePlan,
    candle: CandleExecutionView,
) -> ExecutionDecision | None:
    """Resolve one candle against the canonical contract.

    Returns:
        ExecutionDecision when the candle deterministically resolves the plan.
        None when the candle is eligible but does not resolve the plan yet, or
        when the candle is before the allowed scan start.
    """
    if not plan.is_valid():
        return skip_rejected_plan(plan)

    if not can_scan_outcome_on_candle(plan, candle.candle_index):
        return None

    assert plan.entry_trigger is not None
    assert plan.stop is not None
    assert plan.target_1_5r is not None
    assert plan.reward_risk is not None

    if plan.direction == TradePlanDirection.LONG:
        if candle.open >= plan.target_1_5r:
            return ExecutionDecision(
                outcome=ExecutionOutcome.GAP_BEYOND_TARGET,
                realized_r=plan.reward_risk,
                counts_as_win=True,
                counts_as_loss=False,
                reason=(
                    f"long plan gapped beyond target at candle open "
                    f"({candle.open} >= {plan.target_1_5r})"
                ),
            )
        if candle.open <= plan.stop:
            return ExecutionDecision(
                outcome=ExecutionOutcome.GAP_BEYOND_STOP,
                realized_r=-1.0,
                counts_as_win=False,
                counts_as_loss=True,
                reason=(
                    f"long plan gapped beyond stop at candle open "
                    f"({candle.open} <= {plan.stop})"
                ),
            )
        touched_target = candle.high >= plan.target_1_5r
        touched_stop = candle.low <= plan.stop
    else:
        if candle.open <= plan.target_1_5r:
            return ExecutionDecision(
                outcome=ExecutionOutcome.GAP_BEYOND_TARGET,
                realized_r=plan.reward_risk,
                counts_as_win=True,
                counts_as_loss=False,
                reason=(
                    f"short plan gapped beyond target at candle open "
                    f"({candle.open} <= {plan.target_1_5r})"
                ),
            )
        if candle.open >= plan.stop:
            return ExecutionDecision(
                outcome=ExecutionOutcome.GAP_BEYOND_STOP,
                realized_r=-1.0,
                counts_as_win=False,
                counts_as_loss=True,
                reason=(
                    f"short plan gapped beyond stop at candle open "
                    f"({candle.open} >= {plan.stop})"
                ),
            )
        touched_target = candle.low <= plan.target_1_5r
        touched_stop = candle.high >= plan.stop

    if touched_target and touched_stop:
        return ExecutionDecision(
            outcome=ExecutionOutcome.AMBIGUOUS_BOTH_TOUCHED,
            realized_r=None,
            counts_as_win=False,
            counts_as_loss=False,
            reason="both stop and target were touched in the same candle",
        )

    if touched_target:
        return ExecutionDecision(
            outcome=ExecutionOutcome.TARGET_BEFORE_STOP,
            realized_r=plan.reward_risk,
            counts_as_win=True,
            counts_as_loss=False,
            reason="target was touched and stop was not touched in this candle",
        )

    if touched_stop:
        return ExecutionDecision(
            outcome=ExecutionOutcome.STOP_BEFORE_TARGET,
            realized_r=-1.0,
            counts_as_win=False,
            counts_as_loss=True,
            reason="stop was touched and target was not touched in this candle",
        )

    return None


def unresolved_at_end_of_replay(plan: TradePlan) -> ExecutionDecision:
    """Deterministic terminal outcome when replay/session ends unresolved."""
    return ExecutionDecision(
        outcome=ExecutionOutcome.UNRESOLVED_END_OF_REPLAY,
        realized_r=None,
        counts_as_win=False,
        counts_as_loss=False,
        reason="replay/session ended before stop or target was resolved",
    )


def skip_rejected_plan(plan: TradePlan) -> ExecutionDecision:
    """Deterministic terminal outcome for rejected/non-tradable plans."""
    return ExecutionDecision(
        outcome=ExecutionOutcome.SKIPPED_REJECTED_PLAN,
        realized_r=None,
        counts_as_win=False,
        counts_as_loss=False,
        reason=f"plan_status={plan.plan_status} is not executable",
    )
