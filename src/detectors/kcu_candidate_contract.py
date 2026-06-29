"""KCU Candidate Contract — required component definitions per setup type.

This module defines what structural components each KCU setup type requires
to be considered valid, which ones Phase 4A can detect from candle features,
which ones are missing (require future phases or human review), and what
conditions would invalidate the watch.

SOURCE AUTHORITY: This file is the single source of truth for component names.
All detectors must import component lists from here — never hardcode strings.

No trading logic. No entries, stops, or targets. No learning.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Source status vocabulary
# ---------------------------------------------------------------------------

class KCUSourceStatus:
    """Enumeration of candidate confidence levels.

    HYPOTHESIS:         More than one required KCU component is unverified.
                        The signal is structural only — not sufficient for a watch.
    PARTIALLY_COVERED:  One required component is unverified.
                        The setup structure is present; human review adds the rest.
    CONFIRMED:          All required components are verified.
                        Phase 4A NEVER emits CONFIRMED — reserved for future phases.
    """
    HYPOTHESIS = "HYPOTHESIS"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    CONFIRMED = "CONFIRMED"

    ALL_VALUES: frozenset[str] = frozenset({HYPOTHESIS, PARTIALLY_COVERED, CONFIRMED})
    WATCH_VALUES: frozenset[str] = frozenset({HYPOTHESIS, PARTIALLY_COVERED})


# ---------------------------------------------------------------------------
# Valid candidate type labels (all Phase 4A types are WATCH)
# ---------------------------------------------------------------------------

WATCH_CANDIDATE_TYPES: frozenset[str] = frozenset({
    "LTP_WATCH",
    "REJECTION_WATCH",
    "REVERSAL_WATCH",
    "BOUNCE_WATCH",
    "FAILED_LTP_WATCH",
    "CHOP",
})

# These labels may never be emitted by Phase 4A detectors.
FORBIDDEN_CANDIDATE_TYPES: frozenset[str] = frozenset({
    "VALID_LTP",
    "VALID_REJECTION",
    "VALID_REVERSAL",
    "VALID_BOUNCE",
    "LTP",           # old unqualified label
    "REJECTION",     # old unqualified label
    "REVERSAL",      # old unqualified label
    "BOUNCE",        # old unqualified label
})


# ---------------------------------------------------------------------------
# Reason code vocabulary (machine-readable, stable identifiers)
# ---------------------------------------------------------------------------

class ReasonCode:
    # Price action
    COMPRESSED_RANGE = "COMPRESSED_RANGE"
    SMALL_BODY = "SMALL_BODY"
    DOJI_BODY = "DOJI_BODY"
    UPPER_REJECTION_WICK = "UPPER_REJECTION_WICK"
    LOWER_REJECTION_WICK = "LOWER_REJECTION_WICK"
    BOTH_REJECTION_WICKS = "BOTH_REJECTION_WICKS"
    BEARISH_BODY = "BEARISH_BODY"
    BULLISH_BODY = "BULLISH_BODY"
    DIRECTIONAL_LOWER_WICK = "DIRECTIONAL_LOWER_WICK"
    DIRECTIONAL_UPPER_WICK = "DIRECTIONAL_UPPER_WICK"
    # Structure
    FAILED_HIGHER_HIGH = "FAILED_HIGHER_HIGH"
    FAILED_LOWER_LOW = "FAILED_LOWER_LOW"
    TREND_STREAK_BROKEN = "TREND_STREAK_BROKEN"
    INSIDE_BAR = "INSIDE_BAR"
    STRUCTURAL_CHOP = "STRUCTURAL_CHOP"
    PRIOR_COMPRESSION = "PRIOR_COMPRESSION"
    INDECISIVE_EXPANSION = "INDECISIVE_EXPANSION"


# ---------------------------------------------------------------------------
# LTP_WATCH contract
# ---------------------------------------------------------------------------

LTP_ALL_COMPONENTS = (
    "level_context",    # price is at or near a prior key level
    "trend_context",    # broader directional bias is identifiable
    "patience_candle",  # compressed/contained candle suggesting waiting
)

# Detectable from candle features alone in Phase 4A
LTP_DETECTABLE_COMPONENTS = (
    "patience_candle",  # → compressed range + small/doji body
)

# Require human review or future phase
LTP_MISSING_COMPONENTS = (
    "level_context",    # requires level database (future phase)
    "trend_context",    # requires higher-timeframe context (future phase)
)

LTP_INVALIDATING_COMPONENTS = (
    "range_expansion_below_compression",   # price broke down through compression zone
    "failed_to_hold_compression",          # body closed outside compression high/low
)

LTP_NO_TRADE_RISK = (
    "level_context_unverified",   # no prior level confirmed at this price
    "trend_context_unverified",   # no directional bias confirmed
)

LTP_SOURCE_STATUS = KCUSourceStatus.HYPOTHESIS   # two components unverifiable


# ---------------------------------------------------------------------------
# REJECTION_WATCH contract
# ---------------------------------------------------------------------------

REJECTION_ALL_COMPONENTS = (
    "rejection_wick",       # long wick relative to body and range
    "level_context",        # wick occurred at a prior key level
    "directional_context",  # rejection is against an identifiable prior trend
)

REJECTION_DETECTABLE_COMPONENTS = (
    "rejection_wick",       # → upper/lower wick vs body and range ratio
)

REJECTION_MISSING_COMPONENTS = (
    "level_context",        # requires level database
    "directional_context",  # requires trend context
)

REJECTION_INVALIDATING_COMPONENTS = (
    "price_reclaims_rejection_extreme",  # close back through the rejected extreme
    "follow_through_absent_next_candle",  # next candle fails to confirm direction
)

REJECTION_NO_TRADE_RISK = (
    "level_context_unverified",
    "directional_context_unverified",
    "no_follow_through_confirmed",
)

REJECTION_SOURCE_STATUS = KCUSourceStatus.HYPOTHESIS   # two components unverifiable


# ---------------------------------------------------------------------------
# REVERSAL_WATCH contract
# ---------------------------------------------------------------------------

REVERSAL_ALL_COMPONENTS = (
    "trend_exhaustion",     # prior run of higher highs or lower lows
    "change_of_character",  # first candle that breaks the trend (committed body)
    "level_context",        # reversal occurs at a prior key level
)

REVERSAL_DETECTABLE_COMPONENTS = (
    "trend_exhaustion",     # → consecutive_hh / consecutive_ll streak
    "change_of_character",  # → failed new extreme + committed directional body
)

REVERSAL_MISSING_COMPONENTS = (
    "level_context",        # requires level database
)

REVERSAL_INVALIDATING_COMPONENTS = (
    "new_higher_high_after_reversal",   # bearish reversal invalidated
    "new_lower_low_after_reversal",     # bullish reversal invalidated
)

REVERSAL_NO_TRADE_RISK = (
    "level_context_unverified",
    "no_confirmation_candle",
)

REVERSAL_SOURCE_STATUS = KCUSourceStatus.PARTIALLY_COVERED   # one component unverifiable


# ---------------------------------------------------------------------------
# BOUNCE_WATCH contract
# ---------------------------------------------------------------------------

BOUNCE_ALL_COMPONENTS = (
    "support_reaction",    # prior extreme failed (no new HH or LL)
    "directional_wick",    # wick in the bounce direction dominates body
    "level_context",       # bounce occurs at a prior key level
)

BOUNCE_DETECTABLE_COMPONENTS = (
    "support_reaction",    # → is_lower_low / is_higher_high is False
    "directional_wick",    # → lower/upper wick > body ratio
)

BOUNCE_MISSING_COMPONENTS = (
    "level_context",       # requires level database
)

BOUNCE_INVALIDATING_COMPONENTS = (
    "new_lower_low_after_bullish_bounce",   # bounce failed
    "new_higher_high_after_bearish_bounce",  # bounce failed
)

BOUNCE_NO_TRADE_RISK = (
    "level_context_unverified",
    "no_follow_through_confirmed",
)

BOUNCE_SOURCE_STATUS = KCUSourceStatus.PARTIALLY_COVERED   # one component unverifiable


# ---------------------------------------------------------------------------
# FAILED_LTP_WATCH contract
# ---------------------------------------------------------------------------

FAILED_LTP_WATCH_ALL_COMPONENTS = (
    "prior_compression",    # prior candle was compressed (in watch)
    "expansion_failure",    # current candle expanded without committing
)

FAILED_LTP_WATCH_DETECTABLE_COMPONENTS = (
    "prior_compression",    # → prior candle_range < ATR * ratio
    "expansion_failure",    # → current range expanded, body indecisive
)

FAILED_LTP_WATCH_MISSING_COMPONENTS: tuple[str, ...] = ()   # fully structural

FAILED_LTP_WATCH_INVALIDATING_COMPONENTS = (
    "decisive_directional_break",   # current candle commits to a direction cleanly
)

FAILED_LTP_WATCH_NO_TRADE_RISK = (
    "setup_expired_without_entry",  # the watch window has closed
    "level_likely_no_longer_active",
)

FAILED_LTP_WATCH_SOURCE_STATUS = KCUSourceStatus.PARTIALLY_COVERED


# ---------------------------------------------------------------------------
# CHOP contract
# ---------------------------------------------------------------------------

CHOP_ALL_COMPONENTS = (
    "contained_range",   # range is inside or structurally non-committed
)

CHOP_DETECTABLE_COMPONENTS = (
    "contained_range",   # → inside bar OR tiny body with no new extreme
)

CHOP_MISSING_COMPONENTS: tuple[str, ...] = ()

CHOP_INVALIDATING_COMPONENTS = (
    "directional_range_expansion",  # breaks out of chop with committed body
)

CHOP_NO_TRADE_RISK = (
    "no_directional_bias",
    "range_unexpanded",
)

CHOP_SOURCE_STATUS = KCUSourceStatus.PARTIALLY_COVERED


# ---------------------------------------------------------------------------
# Unified lookup (for engine / audit use)
# ---------------------------------------------------------------------------

CONTRACT: dict[str, dict] = {
    "LTP_WATCH": {
        "all_components": LTP_ALL_COMPONENTS,
        "detectable": LTP_DETECTABLE_COMPONENTS,
        "missing": LTP_MISSING_COMPONENTS,
        "invalidating": LTP_INVALIDATING_COMPONENTS,
        "no_trade_risk": LTP_NO_TRADE_RISK,
        "source_status": LTP_SOURCE_STATUS,
    },
    "REJECTION_WATCH": {
        "all_components": REJECTION_ALL_COMPONENTS,
        "detectable": REJECTION_DETECTABLE_COMPONENTS,
        "missing": REJECTION_MISSING_COMPONENTS,
        "invalidating": REJECTION_INVALIDATING_COMPONENTS,
        "no_trade_risk": REJECTION_NO_TRADE_RISK,
        "source_status": REJECTION_SOURCE_STATUS,
    },
    "REVERSAL_WATCH": {
        "all_components": REVERSAL_ALL_COMPONENTS,
        "detectable": REVERSAL_DETECTABLE_COMPONENTS,
        "missing": REVERSAL_MISSING_COMPONENTS,
        "invalidating": REVERSAL_INVALIDATING_COMPONENTS,
        "no_trade_risk": REVERSAL_NO_TRADE_RISK,
        "source_status": REVERSAL_SOURCE_STATUS,
    },
    "BOUNCE_WATCH": {
        "all_components": BOUNCE_ALL_COMPONENTS,
        "detectable": BOUNCE_DETECTABLE_COMPONENTS,
        "missing": BOUNCE_MISSING_COMPONENTS,
        "invalidating": BOUNCE_INVALIDATING_COMPONENTS,
        "no_trade_risk": BOUNCE_NO_TRADE_RISK,
        "source_status": BOUNCE_SOURCE_STATUS,
    },
    "FAILED_LTP_WATCH": {
        "all_components": FAILED_LTP_WATCH_ALL_COMPONENTS,
        "detectable": FAILED_LTP_WATCH_DETECTABLE_COMPONENTS,
        "missing": FAILED_LTP_WATCH_MISSING_COMPONENTS,
        "invalidating": FAILED_LTP_WATCH_INVALIDATING_COMPONENTS,
        "no_trade_risk": FAILED_LTP_WATCH_NO_TRADE_RISK,
        "source_status": FAILED_LTP_WATCH_SOURCE_STATUS,
    },
    "CHOP": {
        "all_components": CHOP_ALL_COMPONENTS,
        "detectable": CHOP_DETECTABLE_COMPONENTS,
        "missing": CHOP_MISSING_COMPONENTS,
        "invalidating": CHOP_INVALIDATING_COMPONENTS,
        "no_trade_risk": CHOP_NO_TRADE_RISK,
        "source_status": CHOP_SOURCE_STATUS,
    },
}
