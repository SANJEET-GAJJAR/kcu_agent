"""Unit tests for day_collector. ReplayController and TradingViewClient are mocked."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.day_collector import (
    CollectionResult,
    IndicatorQualityError,
    _extract_raw_studies,
    _normalise_timeframe,
    _output_path,
    _flatten_indicators,
    _is_already_complete,
    build_indicator_quality_report,
)
from src.collector.jsonl_store import JsonlStore, validate_jsonl


# ------------------------------------------------------------------
# Helper builders
# ------------------------------------------------------------------

def _snap(ts: int, symbol: str = "TSLA", tf: str = "2") -> CandleSnapshot:
    return CandleSnapshot(
        timestamp=ts, open=195.0, high=196.5, low=194.0, close=196.0,
        volume=100000.0, symbol=symbol, timeframe=tf, replay_date="2024-01-15",
    )


def _day_of_candles(date: str, tf_minutes: int, start_ts: int, n: int) -> list[CandleSnapshot]:
    interval = tf_minutes * 60
    return [
        CandleSnapshot(
            timestamp=start_ts + i * interval,
            open=195.0, high=196.5, low=194.0, close=196.0,
            volume=float(1000 * (i + 1)),
            symbol="TSLA", timeframe=str(tf_minutes), replay_date=date,
        )
        for i in range(n)
    ]


# ------------------------------------------------------------------
# Unit tests: pure helpers (no async)
# ------------------------------------------------------------------

class TestNormaliseTimeframe:
    def test_2m_alias(self):
        assert _normalise_timeframe("2m") == "2"

    def test_plain_2(self):
        assert _normalise_timeframe("2") == "2"

    def test_1h_alias(self):
        assert _normalise_timeframe("1h") == "60"

    def test_uppercase_preserved_if_unknown(self):
        # Unknown alias passes through unchanged
        assert _normalise_timeframe("D") == "D"


class TestOutputPath:
    def test_filename_format(self, tmp_path):
        p = _output_path("TSLA", "2024-01-15", "2", tmp_path)
        assert p.name == "TSLA_2024-01-15_2m.jsonl"
        assert p.parent == tmp_path

    def test_generic_ticker(self, tmp_path):
        p = _output_path("AAPL", "2024-06-01", "5", tmp_path)
        assert "AAPL" in p.name
        assert "5m" in p.name


class TestFlattenIndicators:
    def test_flattens_study_values(self):
        raw = {
            "success": True,
            "studies": [
                {"name": "RSI", "values": {"RSI": 55.2}},
                {"name": "VWAP", "values": {"VWAP": 195.5}},
            ],
        }
        flat = _flatten_indicators(raw)
        assert flat.get("RSI") == 55.2
        assert flat.get("VWAP") == 195.5
        assert "success" not in flat

    def test_prefixes_when_key_differs_from_name(self):
        raw = {
            "success": True,
            "studies": [
                {"name": "MACD", "values": {"Signal": 0.5, "Histogram": 0.1}},
            ],
        }
        flat = _flatten_indicators(raw)
        assert "MACD.Signal" in flat
        assert "MACD.Histogram" in flat

    def test_empty_studies_list(self):
        flat = _flatten_indicators({"success": True, "studies": []})
        assert flat == {}

    def test_non_dict_returns_empty(self):
        assert _flatten_indicators("bad") == {}

    def test_unexpected_structure_excludes_success(self):
        raw = {"success": True, "data": [1, 2, 3]}
        flat = _flatten_indicators(raw)
        assert "success" not in flat
        assert "data" in flat


class TestIsAlreadyComplete:
    def test_missing_file_is_not_complete(self, tmp_path):
        assert _is_already_complete(tmp_path / "x.jsonl", 9999999999) is False

    def test_empty_file_is_not_complete(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.touch()
        assert _is_already_complete(path, 9999999999) is False

    def test_file_with_record_past_session_end_is_complete(self, tmp_path):
        from src.collector.candle_record import build_record
        path = tmp_path / "done.jsonl"
        session_end = 1705356000  # 2024-01-15 16:00 ET
        snap = _snap(session_end + 60)  # past end
        with JsonlStore(path) as store:
            store.append(build_record(snap, {}, 0))
        assert _is_already_complete(path, session_end) is True

    def test_file_with_record_before_session_end_is_not_complete(self, tmp_path):
        from src.collector.candle_record import build_record
        path = tmp_path / "partial.jsonl"
        session_end = 1705356000
        snap = _snap(session_end - 3600)  # before end
        with JsonlStore(path) as store:
            store.append(build_record(snap, {}, 0))
        assert _is_already_complete(path, session_end) is False


# ------------------------------------------------------------------
# Integration-style test: run the collection loop with mocked controller
# ------------------------------------------------------------------

class TestCollectionLoopIntegration:
    """Test _run_collection_loop with a mock ReplayController."""

    def _build_mock_ctrl(self, candles: list[CandleSnapshot], indicators_resp: dict):
        ctrl = MagicMock()
        # read_current_candle cycles through the candle list
        ctrl.read_current_candle = AsyncMock(side_effect=list(candles))
        ctrl.read_indicator_values = AsyncMock(return_value={
            "success": True,
            "studies": [{"name": "RSI", "values": {"RSI": 55.0}}],
        })
        ctrl.advance_one_candle = AsyncMock(return_value={"success": True, "current_date": None})
        ctrl.stop_replay = AsyncMock()
        return ctrl

    @pytest.mark.asyncio
    async def test_full_day_writes_all_candles(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        # 3 candles: two before session end, one at session end
        candles = [
            _snap(session_end_ts - 240),   # 4 min before close
            _snap(session_end_ts - 120),   # 2 min before close
            _snap(session_end_ts),         # at close — write then stop
        ]
        ctrl = self._build_mock_ctrl(candles, {})
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"

        result = await _run_collection_loop(
            ctrl=ctrl,
            output_path=path,
            session_end_ts=session_end_ts,
            ticker="TSLA",
            date=date,
            timeframe="2",
            include_indicators=True,
            est_count=3,
        )

        assert result.candles_written == 3
        assert result.stop_reason == "session_end"
        assert path.exists()

        vr = validate_jsonl(path)
        assert vr.valid is True
        assert vr.record_count == 3

    @pytest.mark.asyncio
    async def test_stuck_detection_stops_loop(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop

        session_end_ts = 9999999999
        # Same timestamp repeated — simulate stuck replay.
        # Must be after midnight UTC of date="2024-01-15" (= 1705276800)
        # so the pre-replay date filter does not silently skip these bars.
        stuck_ts = 1705300000  # 2024-01-15 ~06:26 UTC
        candles = [_snap(stuck_ts)] * 10  # always same ts
        ctrl = self._build_mock_ctrl(candles, {})
        path = tmp_path / "stuck.jsonl"

        result = await _run_collection_loop(
            ctrl=ctrl,
            output_path=path,
            session_end_ts=session_end_ts,
            ticker="TSLA",
            date="2024-01-15",
            timeframe="2",
            include_indicators=False,
            est_count=100,
        )

        assert result.stop_reason == "end_of_data"
        # Only the first unique candle was written
        assert result.candles_written == 1

    @pytest.mark.asyncio
    async def test_resume_skips_seen_timestamps(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop
        from src.collector.candle_record import build_record
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")

        ts0 = session_end_ts - 240
        ts1 = session_end_ts - 120
        ts2 = session_end_ts

        path = tmp_path / "partial.jsonl"
        # Pre-write first two candles (simulating interrupted session)
        with JsonlStore(path) as store:
            store.append(build_record(_snap(ts0), {}, 0))
            store.append(build_record(_snap(ts1), {}, 1))

        # Replay starts from the beginning — presents all 3 candles
        candles = [_snap(ts0), _snap(ts1), _snap(ts2)]
        ctrl = self._build_mock_ctrl(candles, {})

        result = await _run_collection_loop(
            ctrl=ctrl,
            output_path=path,
            session_end_ts=session_end_ts,
            ticker="TSLA",
            date=date,
            timeframe="2",
            include_indicators=False,
            est_count=3,
        )

        assert result.candles_skipped == 2   # ts0 and ts1 already existed
        assert result.candles_written == 1   # only ts2 is new
        assert result.stop_reason == "session_end"

        vr = validate_jsonl(path)
        assert vr.valid is True
        assert vr.record_count == 3

    @pytest.mark.asyncio
    async def test_chronological_order_enforced(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        candles = [
            _snap(session_end_ts - 240),
            _snap(session_end_ts - 120),
            _snap(session_end_ts),
        ]
        ctrl = self._build_mock_ctrl(candles, {})
        path = tmp_path / "chron.jsonl"

        await _run_collection_loop(
            ctrl=ctrl, output_path=path, session_end_ts=session_end_ts,
            ticker="TSLA", date=date, timeframe="2",
            include_indicators=False, est_count=3,
        )

        records = JsonlStore(path).read_all()
        timestamps = [r.timestamp for r in records]
        assert timestamps == sorted(timestamps), "Candles not in chronological order"

    @pytest.mark.asyncio
    async def test_no_duplicate_timestamps_in_output(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        ts = session_end_ts - 120
        # Duplicate candles provided (e.g. replay glitch)
        candles = [_snap(ts), _snap(ts), _snap(session_end_ts)]
        ctrl = self._build_mock_ctrl(candles, {})
        path = tmp_path / "nodup.jsonl"

        await _run_collection_loop(
            ctrl=ctrl, output_path=path, session_end_ts=session_end_ts,
            ticker="TSLA", date=date, timeframe="2",
            include_indicators=False, est_count=2,
        )

        records = JsonlStore(path).read_all()
        timestamps = [r.timestamp for r in records]
        assert len(timestamps) == len(set(timestamps)), "Duplicate timestamps in output"

    @pytest.mark.asyncio
    async def test_indicators_included_in_output(self, tmp_path):
        from src.collector.day_collector import _run_collection_loop
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        candles = [_snap(session_end_ts)]
        ctrl = self._build_mock_ctrl(candles, {})
        path = tmp_path / "indicators.jsonl"

        await _run_collection_loop(
            ctrl=ctrl, output_path=path, session_end_ts=session_end_ts,
            ticker="TSLA", date=date, timeframe="2",
            include_indicators=True, est_count=1,
        )

        records = JsonlStore(path).read_all()
        assert len(records) == 1
        assert "RSI" in records[0].indicators

    @pytest.mark.asyncio
    async def test_idempotent_second_run(self, tmp_path):
        """Running collection twice on a completed day produces identical output."""
        from src.collector.day_collector import _run_collection_loop
        from src.collector.session_clock import session_end_timestamp

        date = "2024-01-15"
        session_end_ts = session_end_timestamp(date, "16:00")
        candles_first = [
            _snap(session_end_ts - 120),
            _snap(session_end_ts),
        ]
        path = tmp_path / "idem.jsonl"

        # First run
        ctrl1 = self._build_mock_ctrl(candles_first, {})
        await _run_collection_loop(
            ctrl=ctrl1, output_path=path, session_end_ts=session_end_ts,
            ticker="TSLA", date=date, timeframe="2",
            include_indicators=False, est_count=2,
        )
        content_after_first = path.read_text()

        # Second run (same candles)
        candles_second = [
            _snap(session_end_ts - 120),
            _snap(session_end_ts),
        ]
        ctrl2 = self._build_mock_ctrl(candles_second, {})
        r2 = await _run_collection_loop(
            ctrl=ctrl2, output_path=path, session_end_ts=session_end_ts,
            ticker="TSLA", date=date, timeframe="2",
            include_indicators=False, est_count=2,
        )

        # Second run writes nothing new
        assert r2.candles_written == 0
        assert r2.candles_skipped == 2

        # File content is identical (only the first run's meta timestamps could differ)
        records_after_second = JsonlStore(path).read_all()
        assert len(records_after_second) == 2


class TestNoBizLogic:
    """Ensure day_collector contains no trading-domain concepts."""

    def test_no_trading_terms_in_day_collector(self):
        import inspect
        from src.collector import day_collector as mod
        source = inspect.getsource(mod)
        forbidden = [
            "buy", "sell", "entry", "exit",
            "stop_loss", "take_profit", "ltp",
            "rejection", "reversal", "bounce",
        ]
        for term in forbidden:
            assert term not in source, (
                f"Trading term {term!r} found in day_collector.py"
            )


# ------------------------------------------------------------------
# Helpers shared by indicator quality tests
# ------------------------------------------------------------------

_KCU_RAW = [{"name": "KCU LTP Indicator v1.4.1", "values": {
    "PM High": "397.33", "PM Low": "392.50",
}}]
_VOLUME_RAW = [{"name": "Volume", "values": {"Volume": "96.45 K"}}]
_KCU_AND_VOLUME = _KCU_RAW + _VOLUME_RAW


def _write_records(path: Path, records: list[CandleRecord]) -> None:
    with JsonlStore(path) as store:
        for r in records:
            store.append(r)


def _make_record(ts: int, raw_indicators: list[dict], volume: float = 10000.0) -> CandleRecord:
    snap = CandleSnapshot(
        timestamp=ts, open=195.0, high=197.0, low=193.0, close=196.0,
        volume=volume, symbol="TSLA", timeframe="2", replay_date="2024-01-15",
    )
    return build_record(snap, indicators={}, candle_index=0, raw_indicators=raw_indicators)


# ------------------------------------------------------------------
# Task 7 — Four required tests
# ------------------------------------------------------------------

class TestMissingIndicatorValuesFailsCollection:
    """missing indicator_values fails full-protocol collection (quality gate)."""

    def test_empty_raw_indicators_fails_quality_report(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        # One candle with raw_indicators=[] (no studies captured)
        _write_records(path, [_make_record(1705276800, raw_indicators=[])])

        with pytest.raises(IndicatorQualityError, match="empty raw_indicators"):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)

    def test_report_file_written_even_on_failure(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_records(path, [_make_record(1705276800, raw_indicators=[])])

        with pytest.raises(IndicatorQualityError):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=True)

        report_path = tmp_path / "TSLA_2024-01-15_2m_indicator_quality.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text())
        assert report["quality_passed"] is False

    def test_partial_missing_fails(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        ts = 1705276800
        # First candle has indicators, second does not
        _write_records(path, [
            _make_record(ts, raw_indicators=_KCU_AND_VOLUME),
            _make_record(ts + 120, raw_indicators=[]),
        ])

        with pytest.raises(IndicatorQualityError):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)


class TestEmptyKCUPayloadMarksInvalid:
    """empty KCU indicator payload fails or marks collection invalid."""

    def test_no_kcu_study_at_all_fails(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        # Only Volume study — KCU absent; use 9:30 AM EST (session-open) timestamp
        # so the KCU check is not skipped (pre-market bars are excluded from the check).
        _write_records(path, [_make_record(1705329000, raw_indicators=_VOLUME_RAW)])

        with pytest.raises(IndicatorQualityError, match="missing a KCU study"):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)

    def test_kcu_study_with_empty_values_fails(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        # KCU study present but no values; use session-open timestamp
        empty_kcu = [{"name": "KCU LTP Indicator v1.4.1", "values": {}}]
        _write_records(path, [_make_record(1705329000, raw_indicators=empty_kcu)])

        with pytest.raises(IndicatorQualityError, match="empty values"):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)

    def test_report_marks_kcu_absent(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_records(path, [_make_record(1705329000, raw_indicators=_VOLUME_RAW)])

        with pytest.raises(IndicatorQualityError):
            build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=True)

        report = json.loads((tmp_path / "TSLA_2024-01-15_2m_indicator_quality.json").read_text())
        assert report["required_checks"]["kcu_study_present"] is False


class TestUnknownOptionalPlotsAllowed:
    """unknown optional plots are allowed — quality check does not fail on extra studies."""

    def test_extra_unknown_studies_pass(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        extra = _KCU_AND_VOLUME + [
            {"name": "My Custom Indicator v9", "values": {"FooBar": "123"}},
            {"name": "AnotherOne", "values": {"X": "abc", "Y": "def"}},
        ]
        _write_records(path, [_make_record(1705276800, raw_indicators=extra)])
        # Must NOT raise
        report = build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)
        assert report["quality_passed"] is True

    def test_optional_ema_absence_does_not_fail(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        # KCU + Volume only — no EMA/SMA/VWAP studies
        _write_records(path, [_make_record(1705276800, raw_indicators=_KCU_AND_VOLUME)])
        report = build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)
        assert report["quality_passed"] is True
        # Optional presence counts are zero — that's fine
        assert report["optional_checks"]["EMA"]["bars_present"] == 0

    def test_optional_studies_counted_when_present(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        with_ema = _KCU_AND_VOLUME + [{"name": "8 EMA", "values": {"EMA": "196.50"}}]
        _write_records(path, [_make_record(1705276800, raw_indicators=with_ema)])
        report = build_indicator_quality_report(path, "TSLA", "2024-01-15", "2", write=False)
        assert report["quality_passed"] is True
        assert report["optional_checks"]["EMA"]["bars_present"] == 1


class TestRawIndicatorPayloadPreserved:
    """raw indicator payload is preserved without interpretation."""

    def test_raw_indicators_written_to_jsonl(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        _write_records(path, [_make_record(1705276800, raw_indicators=_KCU_AND_VOLUME)])
        records = JsonlStore(path).read_all()
        assert records[0].raw_indicators == _KCU_AND_VOLUME

    def test_string_values_not_coerced_to_float(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        kcu_with_strings = [{"name": "KCU LTP Indicator", "values": {
            "PM High": "397.33",    # must stay as string
            "Volume": "1.87 K",  # must stay as string with narrow space
        }}]
        _write_records(path, [_make_record(1705276800, raw_indicators=kcu_with_strings)])
        records = JsonlStore(path).read_all()
        values = records[0].raw_indicators[0]["values"]
        assert values["PM High"] == "397.33"           # str, not float
        assert values["Volume"] == "1.87 K"       # str with narrow space preserved

    def test_extract_raw_studies_preserves_structure(self):
        raw_response = {
            "success": True,
            "study_count": 2,
            "studies": [
                {"name": "KCU LTP Indicator", "values": {"PM High": "397.33", "PM Low": "392.50"}},
                {"name": "8 EMA", "values": {"EMA": "196.50"}},
            ],
        }
        studies = _extract_raw_studies(raw_response)
        assert len(studies) == 2
        assert studies[0]["name"] == "KCU LTP Indicator"
        assert studies[0]["values"]["PM High"] == "397.33"
        assert studies[1]["name"] == "8 EMA"

    def test_round_trip_via_jsonl(self, tmp_path):
        path = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        raw = [
            {"name": "KCU Indicator", "values": {"A": "1", "B": "2"}},
            {"name": "Volume", "values": {"Volume": "5.00 K"}},
        ]
        _write_records(path, [_make_record(1705276800, raw_indicators=raw)])

        # Re-read from disk and confirm round-trip fidelity
        line = path.read_text().strip()
        d = json.loads(line)
        assert d["raw_indicators"] == raw
        record = CandleRecord.from_dict(d)
        assert record.raw_indicators == raw
