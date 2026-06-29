"""PlanBuilder — constructs TradePlan from CONFIRMED_SETUP events.

Phase 5A: plan construction only.
No outcome simulation. No win/loss. No position sizing. No statistics.

Tradability rules (KCU semantics):
  - A CONFIRMED_SETUP is NOT the same as a TRADABLE setup.
  - CHOP: structural no-trade / avoid condition. Never tradable. Hard-coded.
  - FAILED_LTP: watch/warning only by default. Disabled until explicitly
    added to PlanConfig.tradable_setup_types.
  - LTP, REJECTION, REVERSAL, BOUNCE: not yet confirmable (level_context
    unverified in Phase 4B). Will be enabled when level context is wired in.

Usage:
    builder = PlanBuilder()
    plan = builder.build(confirmation_event, eval_feature_record)
    if plan.is_valid():
        # plan.entry_trigger, plan.stop, plan.target_1_5r are populated
    else:
        # plan.rejection_reason explains why

    # To explicitly enable FAILED_LTP (when KCU rules permit):
    cfg = PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"}))
    builder = PlanBuilder(cfg)

All inputs must be from past-closed candles. The eval_features argument
must be the FeatureRecord at the candle where confirmation was assessed
(ConfirmationEvent.evaluated_at_candle_index). No future candles are used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.detectors.confirmation_event import ConfirmationEvent, ConfirmationOutcome
from src.features.feature_record import FeatureRecord
from src.simulator.trade_plan import TradePlan, TradePlanDirection, PlanStatus


# ---------------------------------------------------------------------------
# Setup type registry
# ---------------------------------------------------------------------------

KNOWN_SETUP_TYPES: frozenset[str] = frozenset({
    "LTP",          # confirmable once level_context is wired into Phase 4B
    "REJECTION",    # confirmable once level_context is wired into Phase 4B
    "REVERSAL",     # confirmable once level_context is wired into Phase 4B
    "BOUNCE",       # confirmable once level_context is wired into Phase 4B
    "FAILED_LTP",   # watch/warning only — disabled by default, can be enabled via config
    "CHOP",         # structural no-trade condition — never tradable
})

NON_TRADABLE_SETUP_TYPES: frozenset[str] = frozenset({
    "CHOP",  # KCU rule: CHOP is an avoid condition, not a trade setup
             # Hard-coded: config.tradable_setup_types cannot override this
})

_INVALIDATION_TEXT: dict[str, str] = {
    "CHOP": "Invalidated if price returns inside the pre-breakout range.",
    "FAILED_LTP": "Invalidated if price commits decisively in the opposite direction.",
    "LTP": "Invalidated if price closes below the compression zone (long) or above (short).",
    "REJECTION": "Invalidated if price reclaims the rejected extreme.",
    "REVERSAL": "Invalidated if price makes a new extreme in the prior direction.",
    "BOUNCE": "Invalidated if price makes a new low (bullish) or new high (bearish).",
}

_DEFAULT_INVALIDATION = "Invalidation condition unknown — unsupported setup type."


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PlanConfig:
    """Configuration for TradePlan construction.

    target_r:             R-multiple used for the target price (1.5 = 1.5R).
    min_rr_threshold:     Plans with reward_risk < this value are rejected.
    min_risk_dollars:     Minimum stop distance. Plans with risk < this are rejected.
    tradable_setup_types: Setup types explicitly allowed to produce VALID TradePlans.

    Default is an empty set — no setup types are tradable until explicitly enabled.
    This enforces the KCU rule that confirmed ≠ tradable.

    Example (enable FAILED_LTP):
        PlanConfig(tradable_setup_types=frozenset({"FAILED_LTP"}))

    Note: NON_TRADABLE_SETUP_TYPES (e.g. CHOP) are structurally excluded and
    cannot be overridden by adding them to tradable_setup_types.
    """
    target_r: float = 1.5
    min_rr_threshold: float = 1.5
    min_risk_dollars: float = 0.01
    allow_premarket_trades: bool = False
    tradable_setup_types: frozenset[str] = field(
        default_factory=lambda: frozenset()
    )

    def __post_init__(self) -> None:
        if self.target_r <= 0:
            raise ValueError(f"target_r must be > 0, got {self.target_r}")
        if self.min_rr_threshold <= 0:
            raise ValueError(f"min_rr_threshold must be > 0, got {self.min_rr_threshold}")
        if self.min_risk_dollars < 0:
            raise ValueError(f"min_risk_dollars must be >= 0, got {self.min_risk_dollars}")


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class PlanBuilder:
    """Constructs a TradePlan from a ConfirmationEvent + eval candle features.

    The builder is stateless: each call to build() is independent.
    The eval_features must correspond to event.evaluated_at_candle_index.
    No state is accumulated between calls.

    Gate order (first failing gate determines rejection status):
      1. outcome == CONFIRMED_SETUP           else REJECTED_NOT_CONFIRMED
      2. event/features alignment check       else REJECTED_EVENT_FEATURE_MISMATCH
      3. setup_type in KNOWN_SETUP_TYPES      else REJECTED_UNSUPPORTED_TYPE
      4. setup_type not in NON_TRADABLE       else REJECTED_NOT_TRADABLE (CHOP)
      5. setup_type in tradable_setup_types   else REJECTED_NOT_TRADABLE
      6. tradable session gate passes         else REJECTED_NOT_TRADABLE
      7. direction determinable               else REJECTED_MISSING_FIELDS
      8. risk >= min_risk_dollars             else REJECTED_MISSING_FIELDS
      9. reward_risk >= min_rr_threshold      else REJECTED_RR_BELOW_MINIMUM
      → VALID
    """

    def __init__(self, config: PlanConfig | None = None) -> None:
        self._config = config or PlanConfig()

    def build(
        self,
        event: ConfirmationEvent,
        eval_features: FeatureRecord,
    ) -> TradePlan:
        """Build a TradePlan from a ConfirmationEvent.

        Args:
            event:         A ConfirmationEvent from Phase 4B.
                           Only CONFIRMED_SETUP events with tradable setup types
                           can produce VALID plans.
            eval_features: FeatureRecord at the eval candle
                           (event.evaluated_at_candle_index).
                           Must be a past-closed candle — no future data.

        Returns:
            TradePlan with plan_status=VALID or a REJECTED_* status.
            Never raises — all failures are captured in plan_status.
        """
        # Use candidate_candle_index (setup detection point) + setup_type so that
        # multiple setups detected at the same candle produce distinct plan IDs.
        # evaluated_at_candle_index is NOT used here because N setups can all be
        # evaluated at the same candle, causing collisions.
        plan_id = (
            f"{event.symbol}_{event.replay_date}_"
            f"{event.candidate_candle_index:05d}_{event.setup_type}"
        )

        # --- Gate 1: must be a confirmed setup ---
        if event.outcome != ConfirmationOutcome.CONFIRMED_SETUP:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_NOT_CONFIRMED,
                reason=(
                    f"outcome is {event.outcome!r}; "
                    "only CONFIRMED_SETUP events can produce a TradePlan"
                ),
            )

        # --- Gate 2: event/features must refer to the same eval candle ---
        alignment_errors = _alignment_errors(event, eval_features)
        if alignment_errors:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_EVENT_FEATURE_MISMATCH,
                reason="; ".join(alignment_errors),
            )

        # --- Gate 3: must be a known setup type ---
        if event.setup_type not in KNOWN_SETUP_TYPES:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_UNSUPPORTED_TYPE,
                reason=(
                    f"setup_type {event.setup_type!r} is not a recognised KCU setup type "
                    f"(known: {sorted(KNOWN_SETUP_TYPES)})"
                ),
            )

        # --- Gate 4: structural non-tradable types (CHOP — hard KCU rule) ---
        if event.setup_type in NON_TRADABLE_SETUP_TYPES:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_NOT_TRADABLE,
                reason=(
                    f"setup_type {event.setup_type!r} is a structural no-trade condition "
                    "in KCU rules and cannot produce a TradePlan"
                ),
            )

        # --- Gate 5: setup type must be explicitly enabled in config ---
        if event.setup_type not in self._config.tradable_setup_types:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_NOT_TRADABLE,
                reason=(
                    f"setup_type {event.setup_type!r} is not enabled in "
                    "PlanConfig.tradable_setup_types; add it explicitly to enable trading"
                ),
            )

        # --- Gate 6: session policy (premarket = context only by default) ---
        if eval_features.session == "premarket" and not self._config.allow_premarket_trades:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_NOT_TRADABLE,
                reason=(
                    "premarket/context-only candle cannot produce a TradePlan by default; "
                    "set PlanConfig.allow_premarket_trades=True to override session policy"
                ),
            )

        # --- Gate 7: direction inference ---
        direction = _infer_direction(eval_features)
        if direction == TradePlanDirection.UNKNOWN:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_MISSING_FIELDS,
                reason=(
                    "direction is unknown — eval candle has no body commitment "
                    "(close == open or ambiguous); cannot determine trade direction"
                ),
            )

        # --- Gate 8: entry, stop, risk ---
        entry = eval_features.close
        stop = eval_features.low if direction == TradePlanDirection.LONG else eval_features.high
        risk = abs(entry - stop)

        if risk < self._config.min_risk_dollars:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_MISSING_FIELDS,
                reason=(
                    f"risk {risk:.5f} is below minimum {self._config.min_risk_dollars:.5f}; "
                    "entry is too close to stop to form a valid plan"
                ),
            )

        # --- Target and reward/risk ---
        if direction == TradePlanDirection.LONG:
            target = entry + self._config.target_r * risk
        else:
            target = entry - self._config.target_r * risk

        reward_risk = self._config.target_r  # by construction: always target_r

        # --- Gate 9: R:R gate ---
        if reward_risk < self._config.min_rr_threshold:
            return _build_rejected(
                plan_id=plan_id, event=event, eval_features=eval_features,
                status=PlanStatus.REJECTED_RR_BELOW_MINIMUM,
                reason=(
                    f"reward_risk {reward_risk:.2f} is below "
                    f"min_rr_threshold {self._config.min_rr_threshold:.2f}"
                ),
            )

        invalidation = _INVALIDATION_TEXT.get(event.setup_type, _DEFAULT_INVALIDATION)

        return TradePlan(
            plan_id=plan_id,
            timestamp=eval_features.timestamp,
            symbol=event.symbol,
            timeframe=event.timeframe,
            replay_date=event.replay_date,
            candle_index=eval_features.candle_index,
            setup_type=event.setup_type,
            watch_type=event.watch_type,
            grade=event.grade,
            source_candle_index=event.candidate_candle_index,
            direction=direction,
            entry_trigger=entry,
            stop=stop,
            risk=risk,
            target_1_5r=target,
            reward_risk=reward_risk,
            invalidation=invalidation,
            plan_status=PlanStatus.VALID,
            rejection_reason=None,
        )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _infer_direction(features: FeatureRecord) -> str:
    """Infer trade direction from eval candle body.

    close > open → long (bullish body)
    close < open → short (bearish body)
    close == open → unknown (doji)
    """
    if features.close > features.open:
        return TradePlanDirection.LONG
    if features.close < features.open:
        return TradePlanDirection.SHORT
    return TradePlanDirection.UNKNOWN


def _alignment_errors(
    event: ConfirmationEvent,
    eval_features: FeatureRecord,
) -> list[str]:
    """Return deterministic mismatch messages for event/features alignment."""
    errors: list[str] = []

    if eval_features.candle_index != event.evaluated_at_candle_index:
        errors.append(
            "eval_features.candle_index "
            f"{eval_features.candle_index} does not match "
            f"event.evaluated_at_candle_index {event.evaluated_at_candle_index}"
        )

    if eval_features.symbol != event.symbol:
        errors.append(
            "eval_features.symbol "
            f"{eval_features.symbol!r} does not match event.symbol {event.symbol!r}"
        )

    if eval_features.timeframe != event.timeframe:
        errors.append(
            "eval_features.timeframe "
            f"{eval_features.timeframe!r} does not match event.timeframe {event.timeframe!r}"
        )

    if eval_features.replay_date != event.replay_date:
        errors.append(
            "eval_features.replay_date "
            f"{eval_features.replay_date!r} does not match event.replay_date {event.replay_date!r}"
        )

    return errors


def _build_rejected(
    *,
    plan_id: str,
    event: ConfirmationEvent,
    eval_features: FeatureRecord,
    status: str,
    reason: str,
) -> TradePlan:
    """Construct a rejected TradePlan with all price fields set to None."""
    return TradePlan(
        plan_id=plan_id,
        timestamp=eval_features.timestamp,
        symbol=event.symbol,
        timeframe=event.timeframe,
        replay_date=event.replay_date,
        candle_index=eval_features.candle_index,
        setup_type=event.setup_type,
        watch_type=event.watch_type,
        grade=event.grade,
        source_candle_index=event.candidate_candle_index,
        direction=TradePlanDirection.UNKNOWN,
        entry_trigger=None,
        stop=None,
        risk=None,
        target_1_5r=None,
        reward_risk=None,
        invalidation=_INVALIDATION_TEXT.get(event.setup_type, _DEFAULT_INVALIDATION),
        plan_status=status,
        rejection_reason=reason,
    )
