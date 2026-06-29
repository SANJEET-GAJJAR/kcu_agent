"""Focused wiring tests for scenario artifacts in the dry-run flow."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_milestone1_dry_run import (
    _build_detector_labels_per_candle,
    _update_day_runner_summary_with_scenarios,
    _write_scenario_artifacts,
)
from src.collector.candle_record import CandleRecord
from src.collector.candle_schema import CandleSnapshot
from src.detectors.candidate_event import CandidateEvent
from src.detectors.kcu_candidate_contract import KCUSourceStatus
from src.features.feature_record import FeatureRecord


def _feature(
    *,
    candle_index: int,
    timestamp: int,
    close: float,
    high: float,
    low: float,
    time_since_open_minutes: float,
    indicators: dict | None = None,
) -> FeatureRecord:
    return FeatureRecord(
        timestamp=timestamp,
        symbol="TSLA",
        timeframe="5",
        replay_date="2026-06-22",
        candle_index=candle_index,
        open=close - 0.4,
        high=high,
        low=low,
        close=close,
        volume=10000.0,
        candle_body=0.4,
        upper_wick=high - close,
        lower_wick=close - low,
        body_pct=20.0,
        candle_range=high - low,
        atr=4.0,
        gap_from_prev=None,
        distance_from_prev_close=None,
        is_higher_high=False,
        is_lower_low=False,
        is_inside_bar=False,
        is_outside_bar=False,
        consecutive_hh=0,
        consecutive_ll=0,
        consecutive_lh=0,
        consecutive_hl=0,
        relative_volume=None,
        session="regular",
        time_since_open_minutes=time_since_open_minutes,
        distance_from_session_open=0.0,
        indicators=indicators or {},
    )


def _record(
    *,
    candle_index: int,
    timestamp: int,
    close: float,
    high: float,
    low: float,
    raw_indicators: list[dict] | None = None,
) -> CandleRecord:
    snap = CandleSnapshot(
        timestamp=timestamp,
        open=close - 0.4,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        symbol="TSLA",
        timeframe="5",
        replay_date="2026-06-22",
    )
    return CandleRecord(
        snapshot=snap,
        indicators={},
        raw_indicators=raw_indicators or [],
        meta={"candle_index": candle_index},
    )


def _candidate(
    *,
    candle_index: int,
    timestamp: int,
    candidate_type: str,
) -> CandidateEvent:
    return CandidateEvent(
        timestamp=timestamp,
        symbol="TSLA",
        timeframe="5",
        replay_date="2026-06-22",
        candle_index=candle_index,
        candidate_type=candidate_type,
        source_status=KCUSourceStatus.HYPOTHESIS,
        reasons=["watch"],
        reason_codes=["x"],
        supporting_features={},
        supporting_components=[],
        required_missing_components=["level_context"],
        invalidating_components=[],
        no_trade_risk=["watch only"],
    )


def test_build_detector_labels_per_candle_is_deterministic():
    features = [
        _feature(candle_index=0, timestamp=1, close=100.0, high=101.0, low=99.0, time_since_open_minutes=0.0),
        _feature(candle_index=1, timestamp=2, close=101.0, high=102.0, low=100.0, time_since_open_minutes=5.0),
    ]
    candidates = [
        _candidate(candle_index=1, timestamp=2, candidate_type="REJECTION_WATCH"),
        _candidate(candle_index=1, timestamp=2, candidate_type="FAILED_LTP_WATCH"),
        _candidate(candle_index=1, timestamp=2, candidate_type="REJECTION_WATCH"),
    ]

    labels = _build_detector_labels_per_candle(features, candidates)

    assert labels == [[], ["FAILED_LTP_WATCH", "REJECTION_WATCH"]]


def test_write_scenario_artifacts_writes_jsonl_and_updates_summary(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "day_runner_summary.json"
    summary_path.write_text(json.dumps({"run_id": "run-1"}) + "\n", encoding="utf-8")

    features = [
        _feature(
            candle_index=0,
            timestamp=1782133200,
            close=320.0,
            high=321.0,
            low=319.0,
            time_since_open_minutes=0.0,
            indicators={"PDH": 322.1, "VWAP": 321.9},
        ),
        _feature(
            candle_index=1,
            timestamp=1782136200,
            close=322.0,
            high=324.4,
            low=321.8,
            time_since_open_minutes=20.0,
            indicators={"PDH": 322.1, "VWAP": 321.9},
        ),
    ]
    replay_records = [
        _record(candle_index=0, timestamp=1782133200, close=320.0, high=321.0, low=319.0),
        _record(
            candle_index=1,
            timestamp=1782136200,
            close=322.0,
            high=324.4,
            low=321.8,
            raw_indicators=[{
                "name": "KCU",
                "values": {
                    "OR High": "321.95",
                    "200 SMA 1h": "322.20",
                    "VWAP": "321.90",
                    "PDH": "322.10",
                },
            }],
        ),
    ]
    candidates = [
        _candidate(candle_index=1, timestamp=1782136200, candidate_type="REJECTION_WATCH"),
    ]

    result = _write_scenario_artifacts(
        feature_records=features,
        replay_records=replay_records,
        candidate_events=candidates,
        run_dir=run_dir,
    )

    assert result.artifacts is not None
    assert result.artifacts.scenario_events_path == run_dir / "scenario_events.jsonl"
    rows = [
        json.loads(line)
        for line in result.artifacts.scenario_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["scenario_type"] == "REJECTION_WATCH"
    assert "ORH" in rows[0]["approaching_levels"]
    assert "PDH" in rows[0]["approaching_levels"]
    assert "200 SMA 1h" in rows[0]["approaching_levels"]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["scenario_count"] == 1
    assert summary["scenario_events_path"].endswith("scenario_events.jsonl")


def test_update_day_runner_summary_with_scenarios_can_create_summary(tmp_path):
    summary_path = tmp_path / "day_runner_summary.json"

    _update_day_runner_summary_with_scenarios(
        summary_path,
        scenario_count=0,
        scenario_events_path=Path("scenario_events.jsonl"),
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["scenario_count"] == 0
    assert summary["scenario_events_path"] == "scenario_events.jsonl"


def test_write_scenario_artifacts_excludes_premarket_by_default(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "day_runner_summary.json"
    summary_path.write_text(json.dumps({"run_id": "run-1"}) + "\n", encoding="utf-8")

    features = [
        _feature(
            candle_index=0,
            timestamp=1782129600,
            close=300.0,
            high=301.0,
            low=298.0,
            time_since_open_minutes=-30.0,
            indicators={"PDH": 300.05},
        ),
        _feature(
            candle_index=1,
            timestamp=1782136200,
            close=322.0,
            high=324.4,
            low=321.8,
            time_since_open_minutes=20.0,
            indicators={"PDH": 322.1, "VWAP": 321.9},
        ),
    ]
    features[0].session = "premarket"

    replay_records = [
        _record(
            candle_index=0,
            timestamp=1782129600,
            close=300.0,
            high=301.0,
            low=298.0,
            raw_indicators=[{
                "name": "KCU",
                "values": {"200 SMA 1h": "299.95", "PDH": "300.05"},
            }],
        ),
        _record(
            candle_index=1,
            timestamp=1782136200,
            close=322.0,
            high=324.4,
            low=321.8,
            raw_indicators=[{
                "name": "KCU",
                "values": {
                    "OR High": "321.95",
                    "200 SMA 1h": "322.20",
                    "VWAP": "321.90",
                    "PDH": "322.10",
                },
            }],
        ),
    ]
    candidates = [
        _candidate(candle_index=0, timestamp=1782129600, candidate_type="BOUNCE_WATCH"),
        _candidate(candle_index=1, timestamp=1782136200, candidate_type="REJECTION_WATCH"),
    ]

    result = _write_scenario_artifacts(
        feature_records=features,
        replay_records=replay_records,
        candidate_events=candidates,
        run_dir=run_dir,
    )

    rows = [
        json.loads(line)
        for line in result.artifacts.scenario_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == 1782136200

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["scenario_count"] == 1
