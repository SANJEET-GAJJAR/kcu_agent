"""Unit tests for CandleSnapshot schema and export."""
import json
import pytest
from pathlib import Path

from src.collector.candle_schema import CandleSnapshot, export_snapshot


def _valid_kwargs(**overrides):
    base = dict(
        timestamp=1700000000,
        open=195.0,
        high=196.5,
        low=194.0,
        close=196.0,
        volume=100000.0,
        symbol="TSLA",
        timeframe="2",
        replay_date="2024-01-15",
    )
    base.update(overrides)
    return base


class TestCandleSnapshotValidation:
    def test_valid_candle_creates_ok(self):
        snap = CandleSnapshot(**_valid_kwargs())
        assert snap.symbol == "TSLA"
        assert snap.close == 196.0

    def test_invalid_timestamp_raises(self):
        with pytest.raises(ValueError, match="timestamp"):
            CandleSnapshot(**_valid_kwargs(timestamp=-1))

    def test_zero_timestamp_raises(self):
        with pytest.raises(ValueError, match="timestamp"):
            CandleSnapshot(**_valid_kwargs(timestamp=0))

    def test_high_less_than_low_raises(self):
        with pytest.raises(ValueError, match="high"):
            CandleSnapshot(**_valid_kwargs(high=193.0, low=194.0))

    def test_negative_volume_raises(self):
        with pytest.raises(ValueError, match="volume"):
            CandleSnapshot(**_valid_kwargs(volume=-1.0))

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol"):
            CandleSnapshot(**_valid_kwargs(symbol=""))

    def test_empty_timeframe_raises(self):
        with pytest.raises(ValueError, match="timeframe"):
            CandleSnapshot(**_valid_kwargs(timeframe=""))

    def test_empty_replay_date_raises(self):
        with pytest.raises(ValueError, match="replay_date"):
            CandleSnapshot(**_valid_kwargs(replay_date=""))

    def test_high_equals_low_is_valid(self):
        # Doji candle — high == low is valid
        snap = CandleSnapshot(**_valid_kwargs(high=195.0, low=195.0, open=195.0, close=195.0))
        assert snap.high == snap.low

    def test_zero_volume_is_valid(self):
        snap = CandleSnapshot(**_valid_kwargs(volume=0.0))
        assert snap.volume == 0.0


class TestCandleSnapshotSerialization:
    def test_to_dict_has_all_fields(self):
        snap = CandleSnapshot(**_valid_kwargs())
        d = snap.to_dict()
        for key in ("timestamp", "open", "high", "low", "close", "volume", "symbol", "timeframe", "replay_date"):
            assert key in d

    def test_to_json_is_valid_json(self):
        snap = CandleSnapshot(**_valid_kwargs())
        raw = snap.to_json()
        parsed = json.loads(raw)
        assert parsed["symbol"] == "TSLA"

    def test_roundtrip_from_dict(self):
        snap = CandleSnapshot(**_valid_kwargs())
        restored = CandleSnapshot.from_dict(snap.to_dict())
        assert restored.timestamp == snap.timestamp
        assert restored.close == snap.close

    def test_from_dict_validates(self):
        d = _valid_kwargs(high=190.0, low=195.0)  # invalid: high < low
        with pytest.raises(ValueError):
            CandleSnapshot.from_dict(d)


class TestExportSnapshot:
    def test_export_writes_file(self, tmp_path):
        snap = CandleSnapshot(**_valid_kwargs())
        out = export_snapshot(snap, tmp_path / "snap.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["symbol"] == "TSLA"

    def test_export_creates_parent_dirs(self, tmp_path):
        snap = CandleSnapshot(**_valid_kwargs())
        out = export_snapshot(snap, tmp_path / "a" / "b" / "snap.json")
        assert out.exists()

    def test_export_returns_path(self, tmp_path):
        snap = CandleSnapshot(**_valid_kwargs())
        out = export_snapshot(snap, tmp_path / "x.json")
        assert isinstance(out, Path)
