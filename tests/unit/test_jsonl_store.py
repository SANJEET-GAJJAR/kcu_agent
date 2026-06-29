"""Unit tests for JsonlStore and validate_jsonl."""
import json
import pytest
from pathlib import Path

from src.collector.candle_schema import CandleSnapshot
from src.collector.candle_record import CandleRecord, build_record
from src.collector.jsonl_store import JsonlStore, JsonlStoreError, validate_jsonl


def _snap(ts: int, **kw):
    base = dict(timestamp=ts, open=195.0, high=196.5, low=194.0,
                close=196.0, volume=100000.0, symbol="TSLA", timeframe="2",
                replay_date="2024-01-15")
    base.update(kw)
    return CandleSnapshot(**base)


def _rec(ts: int, idx: int = 0) -> CandleRecord:
    return build_record(_snap(ts), {}, idx)


class TestJsonlStoreWrite:
    def test_append_writes_line(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["timestamp"] == 1000

    def test_multiple_appends(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))
            store.append(_rec(1120, 1))
            store.append(_rec(1240, 2))
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_duplicate_timestamp_skipped(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            written = store.append(_rec(1000, 0))
            skipped = store.append(_rec(1000, 1))
        assert written is True
        assert skipped is False
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1

    def test_append_without_open_raises(self, tmp_path):
        store = JsonlStore(tmp_path / "x.jsonl")
        with pytest.raises(JsonlStoreError, match="not open"):
            store.append(_rec(1000))

    def test_record_count_increments(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            assert store.record_count == 0
            store.append(_rec(1000, 0))
            assert store.record_count == 1
            store.append(_rec(1120, 1))
            assert store.record_count == 2


class TestJsonlStoreResume:
    def test_existing_timestamps_loaded_on_open(self, tmp_path):
        path = tmp_path / "test.jsonl"
        # Write first session
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))
            store.append(_rec(1120, 1))

        # Second session: open should detect existing records
        with JsonlStore(path) as store:
            assert 1000 in store.seen_timestamps
            assert 1120 in store.seen_timestamps
            assert store.record_count == 2

    def test_resume_skips_existing_appends_new(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))

        with JsonlStore(path) as store:
            # 1000 already exists — skip
            skipped = store.append(_rec(1000, 0))
            # 1120 is new — write
            written = store.append(_rec(1120, 1))

        assert skipped is False
        assert written is True
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_read_all_returns_records(self, tmp_path):
        path = tmp_path / "test.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))
            store.append(_rec(1120, 1))

        store = JsonlStore(path)
        records = store.read_all()
        assert len(records) == 2
        assert records[0].timestamp == 1000
        assert records[1].timestamp == 1120

    def test_load_seen_timestamps_on_empty_file(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        store = JsonlStore(path)
        assert store.load_seen_timestamps() == set()

    def test_load_seen_timestamps_on_nonexistent_file(self, tmp_path):
        store = JsonlStore(tmp_path / "nonexistent.jsonl")
        assert store.load_seen_timestamps() == set()


class TestJsonlStoreCorruption:
    def test_corrupt_line_raises_on_read(self, tmp_path):
        path = tmp_path / "corrupt.jsonl"
        path.write_text('{"timestamp": 1000, "open": 195.0}\nnot json\n')
        store = JsonlStore(path)
        with pytest.raises(JsonlStoreError, match="invalid record"):
            store.read_all()

    def test_missing_required_field_raises(self, tmp_path):
        path = tmp_path / "bad.jsonl"
        path.write_text('{"timestamp": 1000}\n')  # missing open, high, etc.
        store = JsonlStore(path)
        with pytest.raises(JsonlStoreError):
            store.read_all()


class TestValidateJsonl:
    def test_valid_file_passes(self, tmp_path):
        path = tmp_path / "ok.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1000, 0))
            store.append(_rec(1120, 1))
            store.append(_rec(1240, 2))
        vr = validate_jsonl(path)
        assert vr.valid is True
        assert vr.record_count == 3
        assert vr.errors == []

    def test_nonexistent_file_fails(self, tmp_path):
        vr = validate_jsonl(tmp_path / "nope.jsonl")
        assert vr.valid is False

    def test_duplicate_timestamps_detected(self, tmp_path):
        path = tmp_path / "dup.jsonl"
        # Manually write duplicate
        rec = _rec(1000, 0)
        line = rec.to_jsonl_line()
        path.write_text(line + "\n" + line + "\n")
        vr = validate_jsonl(path)
        assert vr.valid is False
        assert any("Duplicate" in e for e in vr.errors)

    def test_non_chronological_order_detected(self, tmp_path):
        path = tmp_path / "nonchron.jsonl"
        with JsonlStore(path) as store:
            store.append(_rec(1120, 0))
        # Manually append out-of-order record
        rec = _rec(1000, 1)
        with path.open("a") as f:
            f.write(rec.to_jsonl_line() + "\n")
        vr = validate_jsonl(path)
        assert vr.valid is False
        assert any("chronological" in e.lower() for e in vr.errors)
