"""Level Context Engine — Phase 4C.

Extracts and tracks price levels from FeatureRecords for use in setup
confirmation. Consumes FeatureRecord objects produced by FeatureExtractor.
No trading logic. No setup confirmation. No trade management.

Supported level types:
  PMH  — Pre-Market High (derived from premarket candles in window)
  PML  — Pre-Market Low
  PDH  — Prior Day High (from indicators dict; unknown if not provided)
  PDL  — Prior Day Low
  PDC  — Prior Day Close / Previous Close
  ORH  — Opening Range High (first opening_range_minutes of regular session)
  ORL  — Opening Range Low
  VWAP — Volume Weighted Average Price (from indicators dict)
  OPEN — Opening Price (first regular session candle's close)
  H{HH} — Hourly High for a completed ET hour
  H{HH}L — Hourly Low for a completed ET hour

Level source labels:
  "indicator" — value from FeatureRecord.indicators (TradingView passthrough)
  "derived"   — computed from past FeatureRecords in the window
  "unknown"   — insufficient history or not present in indicators

All "unknown" labels are explicit: never substitute False or 0.0.
No lookahead: current candle is never in the past window.
"""
from __future__ import annotations

import datetime
import json
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any
from zoneinfo import ZoneInfo

from src.features.feature_record import FeatureRecord

_ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class LevelSource:
    INDICATOR = "indicator"
    DERIVED = "derived"
    UNKNOWN = "unknown"
    ALL_VALUES: frozenset[str] = frozenset({"indicator", "derived", "unknown"})


# ---------------------------------------------------------------------------
# NamedLevel
# ---------------------------------------------------------------------------

@dataclass
class NamedLevel:
    """A named price level with provenance tracking.

    value=None means the level is unknown — do not treat as 0 or False.
    source must be one of LevelSource.ALL_VALUES.
    """
    name: str
    value: float | None
    source: str  # LevelSource constant

    def is_known(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "source": self.source}

    @classmethod
    def unknown(cls, name: str) -> "NamedLevel":
        return cls(name=name, value=None, source=LevelSource.UNKNOWN)

    @classmethod
    def derived(cls, name: str, value: float) -> "NamedLevel":
        return cls(name=name, value=value, source=LevelSource.DERIVED)

    @classmethod
    def from_indicator(cls, name: str, value: float) -> "NamedLevel":
        return cls(name=name, value=value, source=LevelSource.INDICATOR)

    @classmethod
    def from_dict(cls, d: dict) -> "NamedLevel":
        return cls(name=str(d["name"]), value=d.get("value"), source=str(d["source"]))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class LevelConfig:
    """Thresholds and parameters for level context extraction."""

    # Duration (minutes) that constitutes the Opening Range.
    opening_range_minutes: float = 30.0

    # Level is "touched" when price is within this % of the level value.
    touch_threshold_pct: float = 0.15

    # Levels within this % of each other (near current price) are "clustered".
    cluster_threshold_pct: float = 0.25

    # Candles to look back when computing level_hold.
    hold_lookback: int = 3

    # Max past FeatureRecords to retain in the internal window.
    max_past_candles: int = 100

    # Indicator dict keys to try for VWAP (first match wins).
    vwap_indicator_keys: tuple[str, ...] = ("VWAP", "Vwap", "vwap")

    # Indicator dict keys for prior-day levels (first match wins).
    pdh_indicator_keys: tuple[str, ...] = ("PDH", "Prior Day High", "PreviousDayHigh")
    pdl_indicator_keys: tuple[str, ...] = ("PDL", "Prior Day Low", "PreviousDayLow")
    pdc_indicator_keys: tuple[str, ...] = (
        "PDC", "Prior Day Close", "Previous Close", "PreviousClose",
    )

    def __post_init__(self) -> None:
        if self.opening_range_minutes <= 0:
            raise ValueError(f"opening_range_minutes must be > 0, got {self.opening_range_minutes}")
        if not (0 < self.touch_threshold_pct < 100):
            raise ValueError(f"touch_threshold_pct must be in (0,100), got {self.touch_threshold_pct}")
        if not (0 < self.cluster_threshold_pct < 100):
            raise ValueError(f"cluster_threshold_pct must be in (0,100), got {self.cluster_threshold_pct}")
        if self.hold_lookback < 1:
            raise ValueError(f"hold_lookback must be >= 1, got {self.hold_lookback}")
        if self.max_past_candles < 1:
            raise ValueError(f"max_past_candles must be >= 1, got {self.max_past_candles}")


# ---------------------------------------------------------------------------
# LevelRecord
# ---------------------------------------------------------------------------

@dataclass
class LevelRecord:
    """Per-candle level context.

    All NamedLevel fields carry a .source tag ("indicator"/"derived"/"unknown").
    Binary fields (level_touch, level_reclaim, etc.) are None when insufficient
    information is available — never False as a proxy for unknown.

    No trade management fields. No trade simulation. No position sizing.
    """

    # --- Identity ---
    timestamp: int
    symbol: str
    timeframe: str
    replay_date: str
    candle_index: int

    # --- Named price levels ---
    pmh: NamedLevel
    pml: NamedLevel
    pdh: NamedLevel
    pdl: NamedLevel
    pdc: NamedLevel
    orh: NamedLevel
    orl: NamedLevel
    vwap: NamedLevel
    opening_price: NamedLevel
    hourly_levels: list[NamedLevel] = field(default_factory=list)

    # --- Proximity analysis ---
    nearest_level_above: NamedLevel | None = None
    nearest_level_below: NamedLevel | None = None
    distance_to_nearest_level: float | None = None

    # --- Binary analysis (None = cannot be determined) ---
    level_touch: bool | None = None
    level_reclaim: bool | None = None
    level_reject: bool | None = None
    level_hold: bool | None = None
    in_middle_of_range: bool | None = None

    # --- Clustering ---
    clustered_levels: list[str] = field(default_factory=list)

    # --- Distance helpers ---
    distance_to_open: float | None = None
    distance_to_vwap: float | None = None

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.timestamp <= 0:
            errors.append(f"timestamp must be > 0, got {self.timestamp}")
        if not self.symbol:
            errors.append("symbol must not be empty")
        if not self.timeframe:
            errors.append("timeframe must not be empty")
        if not self.replay_date:
            errors.append("replay_date must not be empty")
        if self.candle_index < 0:
            errors.append(f"candle_index must be >= 0, got {self.candle_index}")

        for lvl_field_name in ("pmh", "pml", "pdh", "pdl", "pdc", "orh", "orl", "vwap", "opening_price"):
            lvl: NamedLevel = getattr(self, lvl_field_name)
            if lvl.source not in LevelSource.ALL_VALUES:
                errors.append(
                    f"{lvl_field_name}.source must be one of {LevelSource.ALL_VALUES}, "
                    f"got {lvl.source!r}"
                )
            if lvl.value is not None and not isinstance(lvl.value, float):
                errors.append(f"{lvl_field_name}.value must be float or None")

        for lvl in self.hourly_levels:
            if lvl.source not in LevelSource.ALL_VALUES:
                errors.append(f"hourly level {lvl.name!r} has invalid source {lvl.source!r}")

        if self.distance_to_nearest_level is not None and self.distance_to_nearest_level < 0:
            errors.append(
                f"distance_to_nearest_level must be >= 0, got {self.distance_to_nearest_level}"
            )

        return errors

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        def lvl(x: NamedLevel | None) -> dict | None:
            return x.to_dict() if x is not None else None

        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "replay_date": self.replay_date,
            "candle_index": self.candle_index,
            "pmh": self.pmh.to_dict(),
            "pml": self.pml.to_dict(),
            "pdh": self.pdh.to_dict(),
            "pdl": self.pdl.to_dict(),
            "pdc": self.pdc.to_dict(),
            "orh": self.orh.to_dict(),
            "orl": self.orl.to_dict(),
            "vwap": self.vwap.to_dict(),
            "opening_price": self.opening_price.to_dict(),
            "hourly_levels": [l.to_dict() for l in self.hourly_levels],
            "nearest_level_above": lvl(self.nearest_level_above),
            "nearest_level_below": lvl(self.nearest_level_below),
            "distance_to_nearest_level": self.distance_to_nearest_level,
            "level_touch": self.level_touch,
            "level_reclaim": self.level_reclaim,
            "level_reject": self.level_reject,
            "level_hold": self.level_hold,
            "in_middle_of_range": self.in_middle_of_range,
            "clustered_levels": list(self.clustered_levels),
            "distance_to_open": self.distance_to_open,
            "distance_to_vwap": self.distance_to_vwap,
        }

    def to_jsonl_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LevelRecord":
        def lvl(x: dict | None) -> NamedLevel | None:
            return NamedLevel.from_dict(x) if x is not None else None

        def lvl_req(x: dict) -> NamedLevel:
            return NamedLevel.from_dict(x)

        return cls(
            timestamp=int(d["timestamp"]),
            symbol=str(d["symbol"]),
            timeframe=str(d["timeframe"]),
            replay_date=str(d["replay_date"]),
            candle_index=int(d["candle_index"]),
            pmh=lvl_req(d["pmh"]),
            pml=lvl_req(d["pml"]),
            pdh=lvl_req(d["pdh"]),
            pdl=lvl_req(d["pdl"]),
            pdc=lvl_req(d["pdc"]),
            orh=lvl_req(d["orh"]),
            orl=lvl_req(d["orl"]),
            vwap=lvl_req(d["vwap"]),
            opening_price=lvl_req(d["opening_price"]),
            hourly_levels=[lvl_req(l) for l in d.get("hourly_levels", [])],
            nearest_level_above=lvl(d.get("nearest_level_above")),
            nearest_level_below=lvl(d.get("nearest_level_below")),
            distance_to_nearest_level=d.get("distance_to_nearest_level"),
            level_touch=d.get("level_touch"),
            level_reclaim=d.get("level_reclaim"),
            level_reject=d.get("level_reject"),
            level_hold=d.get("level_hold"),
            in_middle_of_range=d.get("in_middle_of_range"),
            clustered_levels=list(d.get("clustered_levels", [])),
            distance_to_open=d.get("distance_to_open"),
            distance_to_vwap=d.get("distance_to_vwap"),
        )


# ---------------------------------------------------------------------------
# LevelExtractor
# ---------------------------------------------------------------------------

class LevelExtractor:
    """Extracts level context for each FeatureRecord.

    Stateful: maintains a rolling window of past FeatureRecords and latches
    the opening price when the first regular session candle is seen.

    Usage — candle by candle:
        extractor = LevelExtractor()
        for feature_record in feature_records:
            level_record = extractor.step(feature_record)

    Usage — batch:
        level_records = LevelExtractor().run(feature_records)

    No lookahead: the current candle is never in the past window when
    computing levels. Window is pushed AFTER extraction.

    PMH/PML include the current candle when it is premarket (closing
    premarket high/low is known at each premarket candle).

    ORH/ORL are only available once we are past the opening range period.
    PDH/PDL/PDC require TradingView indicator values — unknown otherwise.
    """

    def __init__(self, config: LevelConfig | None = None) -> None:
        self._config = config or LevelConfig()
        self._past: deque[FeatureRecord] = deque(maxlen=self._config.max_past_candles)
        self._opening_price: float | None = None

    def step(self, features: FeatureRecord) -> LevelRecord:
        """Extract level context for one FeatureRecord.

        Advances internal state: latches opening price, pushes to window.
        Call in chronological order.
        """
        past = tuple(self._past)  # snapshot: past candles only (no current)

        # Latch opening price on the first regular session candle.
        # Done before compute so this candle's own level context includes its open.
        if self._opening_price is None and features.session == "regular":
            self._opening_price = features.close

        record = self._compute(features, past)

        # Push current to window AFTER extraction — never before.
        self._past.append(features)

        return record

    def run(self, feature_records: list[FeatureRecord]) -> list[LevelRecord]:
        """Process a full sequence of FeatureRecords.

        Returns one LevelRecord per input, in the same order.
        """
        return [self.step(f) for f in feature_records]

    def reset(self) -> None:
        """Clear internal state. Use between independent replay sessions."""
        self._past.clear()
        self._opening_price = None

    @property
    def past_count(self) -> int:
        return len(self._past)

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def _compute(
        self,
        features: FeatureRecord,
        past: tuple[FeatureRecord, ...],
    ) -> LevelRecord:
        close = features.close
        cfg = self._config

        # --- Derive individual levels ---
        vwap = self._derive_vwap(features)
        opening_price = self._derive_opening_price()
        pmh, pml = self._derive_premarket_levels(features, past)
        pdh, pdl, pdc = self._derive_prior_day_levels(features)
        orh, orl = self._derive_opening_range_levels(features, past)
        hourly = self._derive_hourly_levels(features, past)

        # --- Collect all known levels into a single list ---
        all_levels: list[NamedLevel] = [
            vwap, opening_price, pmh, pml, pdh, pdl, pdc, orh, orl,
        ] + hourly
        known = [lvl for lvl in all_levels if lvl.is_known()]

        # --- Proximity analysis ---
        nearest_above, nearest_below = _find_nearest(close, known)
        dist_nearest = _distance_to_nearest(close, nearest_above, nearest_below)

        # --- Binary analysis ---
        prev_close: float | None = past[-1].close if past else None

        level_touch = _compute_touch(close, known, cfg.touch_threshold_pct)
        level_reclaim = _compute_reclaim(close, prev_close, known)
        level_reject = _compute_reject(close, prev_close, known)
        level_hold = _compute_hold(close, past, known, cfg.hold_lookback)
        in_middle = _compute_in_middle(close, known, cfg.touch_threshold_pct)

        # --- Clustering ---
        clustered = _compute_clustered(close, known, cfg.cluster_threshold_pct)

        # --- Distance helpers ---
        dist_to_open = (
            round(close - opening_price.value, 6)
            if opening_price.is_known() else None
        )
        dist_to_vwap = (
            round(close - vwap.value, 6)  # type: ignore[arg-type]
            if vwap.is_known() else None
        )

        return LevelRecord(
            timestamp=features.timestamp,
            symbol=features.symbol,
            timeframe=features.timeframe,
            replay_date=features.replay_date,
            candle_index=features.candle_index,
            pmh=pmh,
            pml=pml,
            pdh=pdh,
            pdl=pdl,
            pdc=pdc,
            orh=orh,
            orl=orl,
            vwap=vwap,
            opening_price=opening_price,
            hourly_levels=hourly,
            nearest_level_above=nearest_above,
            nearest_level_below=nearest_below,
            distance_to_nearest_level=dist_nearest,
            level_touch=level_touch,
            level_reclaim=level_reclaim,
            level_reject=level_reject,
            level_hold=level_hold,
            in_middle_of_range=in_middle,
            clustered_levels=clustered,
            distance_to_open=dist_to_open,
            distance_to_vwap=dist_to_vwap,
        )

    # ------------------------------------------------------------------
    # Individual level derivation
    # ------------------------------------------------------------------

    def _derive_vwap(self, features: FeatureRecord) -> NamedLevel:
        for key in self._config.vwap_indicator_keys:
            val = features.indicators.get(key)
            if val is not None:
                try:
                    return NamedLevel.from_indicator("VWAP", float(val))
                except (TypeError, ValueError):
                    continue
        return NamedLevel.unknown("VWAP")

    def _derive_opening_price(self) -> NamedLevel:
        if self._opening_price is not None:
            return NamedLevel.derived("OPEN", self._opening_price)
        return NamedLevel.unknown("OPEN")

    def _derive_prior_day_levels(
        self, features: FeatureRecord
    ) -> tuple[NamedLevel, NamedLevel, NamedLevel]:
        """PDH, PDL, PDC — from indicators dict only.

        Prior-day data is not available in a single-day rolling window.
        If TradingView provides PDH/PDL/PDC as indicator values, they appear
        in features.indicators. Otherwise: UNKNOWN.
        """
        indicators = features.indicators

        def _try_keys(keys: tuple[str, ...], name: str) -> NamedLevel:
            for key in keys:
                val = indicators.get(key)
                if val is not None:
                    try:
                        return NamedLevel.from_indicator(name, float(val))
                    except (TypeError, ValueError):
                        continue
            return NamedLevel.unknown(name)

        pdh = _try_keys(self._config.pdh_indicator_keys, "PDH")
        pdl = _try_keys(self._config.pdl_indicator_keys, "PDL")
        pdc = _try_keys(self._config.pdc_indicator_keys, "PDC")
        return pdh, pdl, pdc

    def _derive_premarket_levels(
        self,
        features: FeatureRecord,
        past: tuple[FeatureRecord, ...],
    ) -> tuple[NamedLevel, NamedLevel]:
        """PMH, PML — from all premarket candles seen so far.

        Includes the current candle when it is premarket, since premarket
        highs/lows are known as each candle closes.
        """
        candidates = [
            f for f in past
            if f.session == "premarket" and f.replay_date == features.replay_date
        ]
        if features.session == "premarket":
            candidates.append(features)  # current premarket candle is fully known

        if not candidates:
            return NamedLevel.unknown("PMH"), NamedLevel.unknown("PML")

        pmh_val = max(f.high for f in candidates)
        pml_val = min(f.low for f in candidates)
        return (
            NamedLevel.derived("PMH", pmh_val),
            NamedLevel.derived("PML", pml_val),
        )

    def _derive_opening_range_levels(
        self,
        features: FeatureRecord,
        past: tuple[FeatureRecord, ...],
    ) -> tuple[NamedLevel, NamedLevel]:
        """ORH, ORL — from the first opening_range_minutes of the regular session.

        Only available once we are past the opening range period.
        Uses PAST candles only (current candle is never included).
        """
        or_minutes = self._config.opening_range_minutes

        # Not yet past the opening range — OR is still forming.
        if features.time_since_open_minutes < or_minutes:
            return NamedLevel.unknown("ORH"), NamedLevel.unknown("ORL")

        # Scan past candles from the same replay date within the opening range.
        or_candles = [
            f for f in past
            if (
                f.replay_date == features.replay_date
                and 0 <= f.time_since_open_minutes < or_minutes
            )
        ]

        if not or_candles:
            return NamedLevel.unknown("ORH"), NamedLevel.unknown("ORL")

        orh_val = max(f.high for f in or_candles)
        orl_val = min(f.low for f in or_candles)
        return (
            NamedLevel.derived("ORH", orh_val),
            NamedLevel.derived("ORL", orl_val),
        )

    def _derive_hourly_levels(
        self,
        features: FeatureRecord,
        past: tuple[FeatureRecord, ...],
    ) -> list[NamedLevel]:
        """Hourly high/low levels for completed ET hours.

        For each ET hour that has fully elapsed (all 2-minute candles in the
        hour have been processed), compute the high/low range.

        A completed hour is one where the hour boundary has passed relative to
        the current candle's timestamp.
        """
        current_et_hour = _et_hour(features.timestamp)

        # Group past candles from the same replay date by their ET hour.
        hour_groups: dict[int, list[FeatureRecord]] = {}
        for f in past:
            if f.replay_date != features.replay_date:
                continue
            h = _et_hour(f.timestamp)
            hour_groups.setdefault(h, []).append(f)

        levels: list[NamedLevel] = []
        for hour, candles in sorted(hour_groups.items()):
            # Only include levels for hours fully elapsed before the current hour.
            if hour >= current_et_hour:
                continue
            h_high = max(f.high for f in candles)
            h_low = min(f.low for f in candles)
            hour_str = f"{hour:02d}"
            levels.append(NamedLevel.derived(f"H{hour_str}_HIGH", h_high))
            levels.append(NamedLevel.derived(f"H{hour_str}_LOW", h_low))

        return levels


# ---------------------------------------------------------------------------
# Pure analysis helpers (no state, no lookahead)
# ---------------------------------------------------------------------------

def _find_nearest(
    close: float,
    known_levels: list[NamedLevel],
) -> tuple[NamedLevel | None, NamedLevel | None]:
    """Return (nearest above close, nearest below close).

    Excludes levels equal to close (at exactly the price, not above/below).
    """
    above = [lvl for lvl in known_levels if lvl.value is not None and lvl.value > close]
    below = [lvl for lvl in known_levels if lvl.value is not None and lvl.value < close]

    nearest_above = min(above, key=lambda l: l.value - close) if above else None  # type: ignore[arg-type]
    nearest_below = max(below, key=lambda l: l.value) if below else None

    return nearest_above, nearest_below


def _distance_to_nearest(
    close: float,
    nearest_above: NamedLevel | None,
    nearest_below: NamedLevel | None,
) -> float | None:
    """Absolute distance to the nearest level (either above or below)."""
    dist_above = abs(nearest_above.value - close) if nearest_above else None  # type: ignore[operator]
    dist_below = abs(closest_below.value - close) if (closest_below := nearest_below) else None

    if dist_above is None and dist_below is None:
        return None
    if dist_above is None:
        return round(dist_below, 6)  # type: ignore[arg-type]
    if dist_below is None:
        return round(dist_above, 6)
    return round(min(dist_above, dist_below), 6)


def _is_near(close: float, level_value: float, threshold_pct: float) -> bool:
    """True when close is within threshold_pct percent of level_value."""
    if level_value == 0:
        return False
    diff_pct = abs(close - level_value) / abs(level_value) * 100.0
    return diff_pct <= threshold_pct


def _compute_touch(
    close: float,
    known: list[NamedLevel],
    threshold_pct: float,
) -> bool | None:
    """True if close is within threshold_pct of ANY known level.

    None if there are no known levels.
    """
    if not known:
        return None
    return any(_is_near(close, lvl.value, threshold_pct) for lvl in known if lvl.value is not None)  # type: ignore[arg-type]


def _compute_reclaim(
    close: float,
    prev_close: float | None,
    known: list[NamedLevel],
) -> bool | None:
    """True if close crossed ABOVE a known level from below since the prior candle.

    Returns None when prev_close is not available or no levels exist.
    """
    if prev_close is None or not known:
        return None
    for lvl in known:
        if lvl.value is None:
            continue
        if prev_close < lvl.value <= close:
            return True
    return False


def _compute_reject(
    close: float,
    prev_close: float | None,
    known: list[NamedLevel],
) -> bool | None:
    """True if close crossed BELOW a known level from above since the prior candle.

    Returns None when prev_close is not available or no levels exist.
    """
    if prev_close is None or not known:
        return None
    for lvl in known:
        if lvl.value is None:
            continue
        if prev_close > lvl.value >= close:
            return True
    return False


def _compute_hold(
    close: float,
    past: tuple[FeatureRecord, ...],
    known: list[NamedLevel],
    lookback: int,
) -> bool | None:
    """True if close and the last lookback past closes are all consistently
    on the same side of at least one known level.

    Returns None when there are fewer than lookback past candles or no levels.
    """
    if len(past) < lookback or not known:
        return None

    recent_closes = [f.close for f in past[-lookback:]]

    for lvl in known:
        if lvl.value is None:
            continue
        lv = lvl.value
        # All above
        if all(c > lv for c in recent_closes) and close > lv:
            return True
        # All below
        if all(c < lv for c in recent_closes) and close < lv:
            return True

    return False


def _compute_in_middle(
    close: float,
    known: list[NamedLevel],
    threshold_pct: float,
) -> bool | None:
    """True if close is NOT within threshold_pct of ANY known level.

    Returns None if there are no known levels (cannot determine).
    """
    if not known:
        return None
    touching = any(
        _is_near(close, lvl.value, threshold_pct)
        for lvl in known
        if lvl.value is not None
    )
    return not touching


def _compute_clustered(
    close: float,
    known: list[NamedLevel],
    cluster_threshold_pct: float,
) -> list[str]:
    """Return names of known levels that are clustered near current price.

    A level is "near current price" when it is within cluster_threshold_pct
    of the close price.
    """
    clustered: list[str] = []
    for lvl in known:
        if lvl.value is None:
            continue
        if _is_near(close, lvl.value, cluster_threshold_pct):
            clustered.append(lvl.name)
    return clustered


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _et_hour(timestamp: int) -> int:
    """Return the US/Eastern hour (0-23) for a Unix timestamp."""
    dt = datetime.datetime.fromtimestamp(timestamp, tz=_ET)
    return dt.hour
