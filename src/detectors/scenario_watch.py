"""Scenario watch layer — deterministic pre-confirmation confluence logging."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.detectors.kcu_candidate_contract import KCUSourceStatus
from src.detectors.scenario_event import ScenarioConfidence, ScenarioEvent, ScenarioType
from src.features.feature_record import FeatureRecord
from src.features.level_context import LevelRecord, NamedLevel


@dataclass(frozen=True)
class ScenarioWatchConfig:
    """Thresholds for watch-only scenario generation."""

    zone_threshold_pct: float = 0.35
    atr_zone_multiplier: float = 0.25
    min_confluence_levels: int = 2
    min_trend_streak_for_ltp: int = 2
    emit_premarket_scenarios: bool = False

    def __post_init__(self) -> None:
        if self.zone_threshold_pct <= 0:
            raise ValueError("zone_threshold_pct must be > 0")
        if self.atr_zone_multiplier < 0:
            raise ValueError("atr_zone_multiplier must be >= 0")
        if self.min_confluence_levels < 1:
            raise ValueError("min_confluence_levels must be >= 1")
        if self.min_trend_streak_for_ltp < 1:
            raise ValueError("min_trend_streak_for_ltp must be >= 1")


@dataclass(frozen=True)
class ScenarioWatchArtifacts:
    scenario_events_path: Path


@dataclass
class ScenarioWatchResult:
    events: list[ScenarioEvent]
    artifacts: ScenarioWatchArtifacts | None = None


class ScenarioWatchEngine:
    """Creates watch-only scenario events from confluence + detector context."""

    def __init__(self, config: ScenarioWatchConfig | None = None) -> None:
        self._config = config or ScenarioWatchConfig()

    def step(
        self,
        features: FeatureRecord,
        level_record: LevelRecord,
        detector_labels: list[str],
        *,
        raw_indicator_values: list[dict[str, Any]] | None = None,
    ) -> list[ScenarioEvent]:
        if features.candle_index != level_record.candle_index:
            raise ValueError(
                "FeatureRecord and LevelRecord candle_index mismatch: "
                f"{features.candle_index} != {level_record.candle_index}"
            )
        if features.session == "premarket" and not self._config.emit_premarket_scenarios:
            return []

        near_levels = _nearby_levels(
            features,
            level_record,
            raw_indicator_values=raw_indicator_values,
            config=self._config,
        )
        approaching_levels = [name for name, _ in near_levels]
        min_distance = near_levels[0][1] if near_levels else None
        labels = tuple(sorted(set(detector_labels)))

        events: list[ScenarioEvent] = []

        if _should_emit_bounce(features, labels, len(approaching_levels), level_record, self._config):
            events.append(
                _build_event(
                    features,
                    labels,
                    ScenarioType.BOUNCE_WATCH,
                    approaching_levels,
                    min_distance,
                    required_confirmation=[
                        "support_holds_at_zone",
                        "directional_follow_through_after_reaction",
                    ],
                    invalidation_hint="Invalidate if price loses the confluence zone and closes through support.",
                )
            )

        if _should_emit_rejection(features, labels, len(approaching_levels), level_record, self._config):
            events.append(
                _build_event(
                    features,
                    labels,
                    ScenarioType.REJECTION_WATCH,
                    approaching_levels,
                    min_distance,
                    required_confirmation=[
                        "rejection_wick_holds_zone",
                        "failed_reclaim_of_rejected_extreme",
                    ],
                    invalidation_hint="Invalidate if price reclaims the zone and closes back through the rejected extreme.",
                )
            )

        if _should_emit_ltp_continuation(features, labels, len(approaching_levels), self._config):
            events.append(
                _build_event(
                    features,
                    labels,
                    ScenarioType.LTP_CONTINUATION_WATCH,
                    approaching_levels,
                    min_distance,
                    required_confirmation=[
                        "trend_holds_into_pullback_zone",
                        "patience_then_directional_break",
                    ],
                    invalidation_hint="Invalidate if the pullback breaks trend structure and loses the watched level.",
                )
            )

        return sorted(
            events,
            key=lambda e: (e.timestamp, e.candle_index, e.scenario_type),
        )

    def run(
        self,
        feature_records: list[FeatureRecord],
        level_records: list[LevelRecord],
        detector_labels_per_candle: list[list[str]],
        *,
        raw_indicators_per_candle: list[list[dict[str, Any]] | None] | None = None,
    ) -> list[ScenarioEvent]:
        if not (
            len(feature_records)
            == len(level_records)
            == len(detector_labels_per_candle)
        ):
            raise ValueError(
                "feature_records, level_records, and detector_labels_per_candle must "
                "have equal length"
            )
        if raw_indicators_per_candle is not None and len(raw_indicators_per_candle) != len(feature_records):
            raise ValueError(
                "raw_indicators_per_candle must have the same length as feature_records"
            )

        all_events: list[ScenarioEvent] = []
        for idx, (features, level_record, detector_labels) in enumerate(
            zip(feature_records, level_records, detector_labels_per_candle)
        ):
            raw = raw_indicators_per_candle[idx] if raw_indicators_per_candle is not None else None
            all_events.extend(
                self.step(
                    features,
                    level_record,
                    detector_labels,
                    raw_indicator_values=raw,
                )
            )
        return sorted(
            all_events,
            key=lambda e: (e.timestamp, e.candle_index, e.scenario_type),
        )

    def run_and_write(
        self,
        feature_records: list[FeatureRecord],
        level_records: list[LevelRecord],
        detector_labels_per_candle: list[list[str]],
        *,
        output_path: Path | str,
        raw_indicators_per_candle: list[list[dict[str, Any]] | None] | None = None,
    ) -> ScenarioWatchResult:
        events = self.run(
            feature_records,
            level_records,
            detector_labels_per_candle,
            raw_indicators_per_candle=raw_indicators_per_candle,
        )
        path = Path(output_path)
        _write_jsonl(path, events)
        return ScenarioWatchResult(
            events=events,
            artifacts=ScenarioWatchArtifacts(scenario_events_path=path),
        )


def _build_event(
    features: FeatureRecord,
    detector_labels: tuple[str, ...],
    scenario_type: str,
    approaching_levels: list[str],
    min_distance: float | None,
    *,
    required_confirmation: list[str],
    invalidation_hint: str,
) -> ScenarioEvent:
    event = ScenarioEvent(
        timestamp=features.timestamp,
        symbol=features.symbol,
        timeframe=features.timeframe,
        replay_date=features.replay_date,
        candle_index=features.candle_index,
        scenario_type=scenario_type,
        approaching_levels=approaching_levels,
        confluence_count=len(approaching_levels),
        distance_to_zone=min_distance,
        required_confirmation=required_confirmation,
        invalidation_hint=invalidation_hint,
        confidence=ScenarioConfidence.WATCH,
        source_status=KCUSourceStatus.HYPOTHESIS,
        detector_labels=list(detector_labels),
    )
    errors = event.validate()
    if errors:
        raise ValueError(f"invalid ScenarioEvent: {errors}")
    return event


def _should_emit_bounce(
    features: FeatureRecord,
    detector_labels: tuple[str, ...],
    confluence_count: int,
    level_record: LevelRecord,
    config: ScenarioWatchConfig,
) -> bool:
    if confluence_count < config.min_confluence_levels:
        return False
    if "BOUNCE_WATCH" in detector_labels:
        return True
    if features.session != "regular":
        return False
    return bool(
        _has_bounce_reaction(features, level_record)
        and (features.is_lower_low is False or features.is_higher_high is False)
    )


def _should_emit_rejection(
    features: FeatureRecord,
    detector_labels: tuple[str, ...],
    confluence_count: int,
    level_record: LevelRecord,
    config: ScenarioWatchConfig,
) -> bool:
    if confluence_count < config.min_confluence_levels:
        return False
    if "REJECTION_WATCH" in detector_labels or "FAILED_LTP_WATCH" in detector_labels:
        return True
    if features.session != "regular":
        return False
    return bool(
        _has_rejection_reaction(features, level_record)
    )


def _should_emit_ltp_continuation(
    features: FeatureRecord,
    detector_labels: tuple[str, ...],
    confluence_count: int,
    config: ScenarioWatchConfig,
) -> bool:
    if "LTP_WATCH" not in detector_labels:
        return False
    if confluence_count < 1:
        return False
    bullish = max(features.consecutive_hh, features.consecutive_hl) >= config.min_trend_streak_for_ltp
    bearish = max(features.consecutive_ll, features.consecutive_lh) >= config.min_trend_streak_for_ltp
    return bullish or bearish


def _has_bounce_reaction(
    features: FeatureRecord,
    level_record: LevelRecord,
) -> bool:
    reaction_context = bool(
        level_record.level_touch
        or level_record.level_hold
        or level_record.level_reclaim
    )
    wick_reaction = bool(
        features.lower_wick >= features.candle_body * 0.5
        and features.lower_wick > features.upper_wick
    )
    return reaction_context and wick_reaction


def _has_rejection_reaction(
    features: FeatureRecord,
    level_record: LevelRecord,
) -> bool:
    if level_record.level_reject:
        return True
    reclaim_reaction = bool(level_record.level_reclaim and features.upper_wick >= features.candle_body * 0.5)
    wick_reaction = bool(
        level_record.level_hold
        and features.upper_wick >= features.candle_body * 0.5
        and features.upper_wick > features.lower_wick
    )
    return reclaim_reaction or wick_reaction


def _nearby_levels(
    features: FeatureRecord,
    level_record: LevelRecord,
    *,
    raw_indicator_values: list[dict[str, Any]] | None,
    config: ScenarioWatchConfig,
) -> list[tuple[str, float]]:
    threshold = max(
        abs(features.close) * (config.zone_threshold_pct / 100.0),
        (features.atr or 0.0) * config.atr_zone_multiplier,
    )

    level_values: dict[str, float] = {}
    for level in _levels_from_level_record(level_record):
        if level.value is None:
            continue
        level_values.setdefault(level.name, level.value)
    for name, value in _levels_from_indicators(features, raw_indicator_values):
        level_values.setdefault(name, value)

    nearby: list[tuple[str, float]] = []
    for name, value in level_values.items():
        distance = round(abs(features.close - value), 6)
        if distance <= threshold:
            nearby.append((name, distance))

    return sorted(nearby, key=lambda item: (item[1], item[0]))


def _levels_from_level_record(level_record: LevelRecord) -> list[NamedLevel]:
    return [
        level_record.pmh,
        level_record.pml,
        level_record.pdh,
        level_record.pdl,
        level_record.pdc,
        level_record.orh,
        level_record.orl,
        level_record.vwap,
        *level_record.hourly_levels,
    ]


def _levels_from_indicators(
    features: FeatureRecord,
    raw_indicator_values: list[dict[str, Any]] | None,
) -> list[tuple[str, float]]:
    levels: dict[str, float] = {}

    for study in raw_indicator_values or []:
        for name, value in _extract_indicator_levels_from_study(study):
            levels.setdefault(name, value)

    if levels:
        return sorted(levels.items())

    for key, value in features.indicators.items():
        normalized = _normalize_indicator_name(key)
        if normalized is None:
            continue
        parsed = _coerce_float(value)
        if parsed is None:
            continue
        levels.setdefault(normalized, parsed)

    return sorted(levels.items())


def _extract_indicator_levels_from_study(study: dict[str, Any]) -> list[tuple[str, float]]:
    values = study.get("values", {})
    if not isinstance(values, dict):
        return []
    levels: list[tuple[str, float]] = []
    for key, raw_value in values.items():
        normalized = _normalize_indicator_name(str(key))
        if normalized is None:
            continue
        parsed = _coerce_float(raw_value)
        if parsed is None:
            continue
        levels.append((normalized, parsed))
    return levels


def _normalize_indicator_name(name: str) -> str | None:
    label = name.split(".")[-1].strip()
    if not label or label.lower() == "volume":
        return None
    if label == "Opening Price":
        return None
    aliases = {
        "OR High": "ORH",
        "OR Low": "ORL",
        "PM High": "PMH",
        "PM Low": "PML",
        "Prior Day High": "PDH",
        "Prior Day Low": "PDL",
        "Prior Day Close": "PDC",
        "Previous Close": "PDC",
    }
    return aliases.get(label, label)


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _write_jsonl(path: Path, events: list[ScenarioEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(event.to_jsonl_line() + "\n")


def load_scenario_events(path: Path | str) -> list[ScenarioEvent]:
    target = Path(path)
    events: list[ScenarioEvent] = []
    with target.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            row = json.loads(line)
            event = ScenarioEvent.from_dict(row)
            errors = event.validate()
            if errors:
                raise ValueError(
                    f"{target}:{lineno}: invalid ScenarioEvent: {errors}"
                )
            events.append(event)
    return events
