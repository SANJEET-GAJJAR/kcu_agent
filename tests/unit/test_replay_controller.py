"""Unit tests for ReplayController. TradingViewClient is fully mocked."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.collector.replay_controller import ReplayController, ReplayControllerError
from src.collector.tv_client import TVClientError
from src.collector.candle_schema import CandleSnapshot


def _make_client(**tool_responses):
    """Return a mock TradingViewClient where call_tool returns from tool_responses dict."""
    client = AsyncMock()

    async def _call_tool(name, args=None):
        if name not in tool_responses:
            raise TVClientError(f"Unexpected tool call: {name}")
        resp = tool_responses[name]
        if isinstance(resp, Exception):
            raise resp
        return resp

    client.call_tool = AsyncMock(side_effect=_call_tool)
    return client


def _ohlcv_response(ts=1700000000, o=195.0, h=196.5, l=194.0, c=196.0, v=100000.0):
    return {
        "success": True,
        "bar_count": 1,
        "bars": [{"time": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}],
    }


class TestLoadTicker:
    @pytest.mark.asyncio
    async def test_load_ticker_sets_symbol(self):
        client = _make_client(**{"chart_set_symbol": {"success": True}})
        ctrl = ReplayController(client)
        result = await ctrl.load_ticker("TSLA")
        assert result["symbol"] == "TSLA"
        assert ctrl.symbol == "TSLA"

    @pytest.mark.asyncio
    async def test_load_ticker_normalises_to_uppercase(self):
        client = _make_client(**{"chart_set_symbol": {"success": True}})
        ctrl = ReplayController(client)
        await ctrl.load_ticker("tsla")
        assert ctrl.symbol == "TSLA"

    @pytest.mark.asyncio
    async def test_load_ticker_empty_string_raises(self):
        client = _make_client()
        ctrl = ReplayController(client)
        with pytest.raises(ReplayControllerError):
            await ctrl.load_ticker("")

    @pytest.mark.asyncio
    async def test_load_ticker_tv_failure_raises(self):
        client = _make_client(**{"chart_set_symbol": {"success": False, "error": "symbol not found"}})
        ctrl = ReplayController(client)
        with pytest.raises(TVClientError, match="symbol not found"):
            await ctrl.load_ticker("INVALID")


class TestSetTimeframe:
    @pytest.mark.asyncio
    async def test_set_valid_timeframe(self):
        client = _make_client(**{"chart_set_timeframe": {"success": True}})
        ctrl = ReplayController(client)
        result = await ctrl.set_timeframe("2")
        assert result["timeframe"] == "2"
        assert ctrl.timeframe == "2"

    @pytest.mark.asyncio
    async def test_set_invalid_timeframe_raises(self):
        client = _make_client()
        ctrl = ReplayController(client)
        with pytest.raises(ReplayControllerError, match="Unsupported timeframe"):
            await ctrl.set_timeframe("7")

    @pytest.mark.asyncio
    async def test_all_supported_timeframes_accepted(self):
        for tf in ("1", "2", "3", "5", "10", "15", "30", "60", "D"):
            client = _make_client(**{"chart_set_timeframe": {"success": True}})
            ctrl = ReplayController(client)
            result = await ctrl.set_timeframe(tf)
            assert result["timeframe"] == tf


class TestLoadTradingDay:
    def _setup_ctrl(self):
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True, "replay_started": True, "current_date": 1700000000},
        })
        ctrl = ReplayController(client)
        return ctrl, client

    @pytest.mark.asyncio
    async def test_load_trading_day_sets_state(self):
        ctrl, _ = self._setup_ctrl()
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        result = await ctrl.load_trading_day("2024-01-15")
        assert result["success"] is True
        assert ctrl.replay_date == "2024-01-15"
        assert ctrl.is_replay_active is True

    @pytest.mark.asyncio
    async def test_load_trading_day_invalid_date_raises(self):
        ctrl, _ = self._setup_ctrl()
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        with pytest.raises(ReplayControllerError, match="YYYY-MM-DD"):
            await ctrl.load_trading_day("01-15-2024")

    @pytest.mark.asyncio
    async def test_load_trading_day_without_ticker_raises(self):
        ctrl, _ = self._setup_ctrl()
        await ctrl.set_timeframe("2")
        with pytest.raises(ReplayControllerError, match="load_ticker"):
            await ctrl.load_trading_day("2024-01-15")

    @pytest.mark.asyncio
    async def test_load_trading_day_without_timeframe_raises(self):
        ctrl, _ = self._setup_ctrl()
        await ctrl.load_ticker("TSLA")
        with pytest.raises(ReplayControllerError, match="set_timeframe"):
            await ctrl.load_trading_day("2024-01-15")


class TestAdvanceOneCandle:
    @pytest.mark.asyncio
    async def test_advance_one_candle(self):
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "replay_step": {"success": True, "current_date": 1700000060},
        })
        ctrl = ReplayController(client)
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")
        result = await ctrl.advance_one_candle()
        assert result["success"] is True
        assert result["current_date"] == 1700000060

    @pytest.mark.asyncio
    async def test_advance_without_active_replay_raises(self):
        client = _make_client()
        ctrl = ReplayController(client)
        with pytest.raises(ReplayControllerError, match="Replay is not active"):
            await ctrl.advance_one_candle()


class TestReadCurrentCandle:
    def _active_ctrl(self):
        # current_date=1700000100 falls within the 2m bar [1700000000, 1700000120)
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "replay_status": {"success": True, "current_date": 1700000100},
            "data_get_ohlcv": _ohlcv_response(),
        })
        ctrl = ReplayController(client)
        return ctrl

    @pytest.mark.asyncio
    async def test_read_current_candle_returns_snapshot(self):
        ctrl = self._active_ctrl()
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")

        snap = await ctrl.read_current_candle()
        assert isinstance(snap, CandleSnapshot)
        assert snap.symbol == "TSLA"
        assert snap.timeframe == "2"
        assert snap.replay_date == "2024-01-15"
        assert snap.close == 196.0
        assert snap.high >= snap.low

    @pytest.mark.asyncio
    async def test_read_candle_without_replay_raises(self):
        client = _make_client()
        ctrl = ReplayController(client)
        with pytest.raises(ReplayControllerError, match="Replay is not active"):
            await ctrl.read_current_candle()

    @pytest.mark.asyncio
    async def test_read_candle_empty_bars_raises(self):
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "replay_status": {"success": True, "current_date": 1700000100},
            "data_get_ohlcv": {"success": True, "bars": []},
        })
        ctrl = ReplayController(client)
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")

        with pytest.raises(ReplayControllerError, match="No bars"):
            await ctrl.read_current_candle()


class TestReadIndicatorValues:
    @pytest.mark.asyncio
    async def test_read_indicators_returns_raw_values(self):
        study_data = {
            "success": True,
            "studies": [{"name": "RSI", "values": {"RSI": 55.2}}],
        }
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "data_get_study_values": study_data,
        })
        ctrl = ReplayController(client)
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")

        result = await ctrl.read_indicator_values()
        assert result["success"] is True
        assert "studies" in result

    @pytest.mark.asyncio
    async def test_read_indicators_without_replay_raises(self):
        client = _make_client()
        ctrl = ReplayController(client)
        with pytest.raises(ReplayControllerError, match="Replay is not active"):
            await ctrl.read_indicator_values()


class TestExportCandleSnapshot:
    @pytest.mark.asyncio
    async def test_export_writes_json(self, tmp_path):
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "replay_status": {"success": True, "current_date": 1700000100},
            "data_get_ohlcv": _ohlcv_response(),
        })
        ctrl = ReplayController(client)
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")

        out = await ctrl.export_candle_snapshot(tmp_path / "candle.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["symbol"] == "TSLA"
        assert data["high"] >= data["low"]

    @pytest.mark.asyncio
    async def test_export_returns_path(self, tmp_path):
        client = _make_client(**{
            "chart_set_symbol": {"success": True},
            "chart_set_timeframe": {"success": True},
            "chart_scroll_to_date": {"success": True},
            "replay_start": {"success": True},
            "replay_status": {"success": True, "current_date": 1700000100},
            "data_get_ohlcv": _ohlcv_response(),
        })
        ctrl = ReplayController(client)
        await ctrl.load_ticker("TSLA")
        await ctrl.set_timeframe("2")
        await ctrl.load_trading_day("2024-01-15")

        out = await ctrl.export_candle_snapshot(tmp_path / "snap.json")
        assert isinstance(out, Path)


class TestNoTradingLogic:
    """Ensure the controller contains no trading-domain concepts."""

    def test_replay_controller_has_no_trading_methods(self):
        forbidden = [
            "buy", "sell", "entry", "exit", "long", "short",
            "profit", "loss", "stop_loss", "take_profit",
            "ltp", "rejection", "reversal", "bounce",
            "pattern", "setup", "signal", "trigger",
        ]
        import inspect
        from src.collector import replay_controller as mod
        source = inspect.getsource(mod)
        for term in forbidden:
            assert term not in source, (
                f"Trading logic term {term!r} found in replay_controller.py"
            )
