"""Unit tests for CandleRecord."""
import json
import pytest
from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record


def _snap(**kw):
    base = dict(timestamp=1700000000, open=195.0, high=196.5, low=194.0,
                close=196.0, volume=100000.0, symbol="TSLA", timeframe="2",
                replay_date="2024-01-15")
    base.update(kw)
    return CandleSnapshot(**base)


class TestCandleRecord:
    def test_to_dict_includes_all_fields(self):
        rec = CandleRecord(snapshot=_snap(), indicators={"RSI": 55.0}, meta={"candle_index": 0})
        d = rec.to_dict()
        assert d["symbol"] == "TSLA"
        assert d["indicators"] == {"RSI": 55.0}
        assert d["meta"]["candle_index"] == 0

    def test_to_jsonl_line_is_compact(self):
        rec = CandleRecord(snapshot=_snap(), indicators={}, meta={})
        line = rec.to_jsonl_line()
        assert "\n" not in line
        parsed = json.loads(line)
        assert parsed["symbol"] == "TSLA"

    def test_roundtrip_from_dict(self):
        rec = CandleRecord(
            snapshot=_snap(),
            indicators={"VWAP": 195.5},
            meta={"candle_index": 3},
        )
        restored = CandleRecord.from_dict(rec.to_dict())
        assert restored.timestamp == rec.timestamp
        assert restored.indicators == {"VWAP": 195.5}
        assert restored.meta["candle_index"] == 3

    def test_timestamp_property(self):
        snap = _snap(timestamp=1700000120)
        rec = CandleRecord(snapshot=snap)
        assert rec.timestamp == 1700000120


class TestBuildRecord:
    def test_build_record_sets_meta(self):
        rec = build_record(_snap(), {"RSI": 42.0}, candle_index=7)
        assert rec.meta["candle_index"] == 7
        assert "collected_at" in rec.meta
        assert rec.indicators == {"RSI": 42.0}

    def test_build_record_empty_indicators(self):
        rec = build_record(_snap(), {}, candle_index=0)
        assert rec.indicators == {}
