"""Unit tests for session_clock."""
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.collector.session_clock import (
    session_end_timestamp,
    is_past_session_end,
    timeframe_to_seconds,
    expected_candle_count,
    MARKET_CLOSE_ET,
    PREMARKET_OPEN_ET,
)

_ET = ZoneInfo("America/New_York")


class TestSessionEndTimestamp:
    def test_est_date_correct_utc(self):
        # Jan 15 2024 is EST (UTC-5). 16:00 EST = 21:00 UTC
        ts = session_end_timestamp("2024-01-15", "16:00")
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt_utc.hour == 21
        assert dt_utc.minute == 0

    def test_edt_date_correct_utc(self):
        # Jun 23 2026 is EDT (UTC-4). 16:00 EDT = 20:00 UTC
        ts = session_end_timestamp("2026-06-23", "16:00")
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert dt_utc.hour == 20
        assert dt_utc.minute == 0

    def test_returns_int(self):
        ts = session_end_timestamp("2024-01-15")
        assert isinstance(ts, int)

    def test_premarket_open_earlier_than_close(self):
        open_ts = session_end_timestamp("2024-01-15", PREMARKET_OPEN_ET)
        close_ts = session_end_timestamp("2024-01-15", MARKET_CLOSE_ET)
        assert open_ts < close_ts

    def test_custom_end_time(self):
        ts_4pm = session_end_timestamp("2024-01-15", "16:00")
        ts_930am = session_end_timestamp("2024-01-15", "09:30")
        assert ts_4pm > ts_930am


class TestIsPastSessionEnd:
    def test_timestamp_before_end_is_false(self):
        end_ts = session_end_timestamp("2024-01-15", "16:00")
        assert is_past_session_end(end_ts - 1, end_ts) is False

    def test_timestamp_at_end_is_true(self):
        end_ts = session_end_timestamp("2024-01-15", "16:00")
        assert is_past_session_end(end_ts, end_ts) is True

    def test_timestamp_after_end_is_true(self):
        end_ts = session_end_timestamp("2024-01-15", "16:00")
        assert is_past_session_end(end_ts + 3600, end_ts) is True


class TestTimeframeToSeconds:
    def test_1_minute(self):
        assert timeframe_to_seconds("1") == 60

    def test_2_minute(self):
        assert timeframe_to_seconds("2") == 120

    def test_5_minute(self):
        assert timeframe_to_seconds("5") == 300

    def test_daily(self):
        assert timeframe_to_seconds("D") == 86400

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            timeframe_to_seconds("X")


class TestExpectedCandleCount:
    def test_2m_full_regular_session(self):
        # 9:30 AM to 4:00 PM = 6.5 hours = 390 minutes → 195 candles at 2m
        count = expected_candle_count("2024-01-15", "2", start_time_et="09:30", end_time_et="16:00")
        assert count == 195

    def test_5m_full_regular_session(self):
        # 6.5 hours = 390 minutes → 78 candles at 5m
        count = expected_candle_count("2024-01-15", "5", start_time_et="09:30", end_time_et="16:00")
        assert count == 78

    def test_returns_non_negative(self):
        count = expected_candle_count("2024-01-15", "2")
        assert count >= 0
