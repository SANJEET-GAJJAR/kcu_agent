"""Unit tests for TradingViewClient. All MCP I/O is mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.collector.tv_client import TradingViewClient, TVClientError, _extract_text, _parse_result


def _make_content(data: dict):
    item = MagicMock()
    item.text = json.dumps(data)
    return [item]


def _make_error_content(msg: str):
    item = MagicMock()
    item.text = msg
    return [item]


class TestParseResult:
    def test_parses_json_text(self):
        content = _make_content({"success": True, "value": 42})
        result = _parse_result(content)
        assert result == {"success": True, "value": 42}

    def test_returns_raw_text_if_not_json(self):
        item = MagicMock()
        item.text = "plain string"
        result = _parse_result([item])
        assert result == "plain string"

    def test_returns_content_if_no_text(self):
        item = MagicMock(spec=[])  # no .text attribute
        result = _parse_result([item])
        assert result == [item]


class TestExtractText:
    def test_extracts_first_text(self):
        item = MagicMock()
        item.text = "hello"
        assert _extract_text([item]) == "hello"

    def test_falls_back_to_str(self):
        item = MagicMock(spec=[])
        result = _extract_text([item])
        assert isinstance(result, str)


class TestTradingViewClientCallTool:
    def _mock_session(self, return_data: dict, is_error: bool = False):
        session = AsyncMock()
        result = MagicMock()
        result.isError = is_error
        result.content = _make_content(return_data)
        session.call_tool = AsyncMock(return_value=result)
        session.initialize = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_call_tool_returns_parsed_result(self):
        client = TradingViewClient.__new__(TradingViewClient)
        client._max_retries = 3
        client._retry_delay = 0.0
        client._session = self._mock_session({"success": True, "symbol": "TSLA"})

        result = await client.call_tool("chart_get_state", {})
        assert result["symbol"] == "TSLA"

    @pytest.mark.asyncio
    async def test_call_tool_raises_when_not_connected(self):
        client = TradingViewClient.__new__(TradingViewClient)
        client._session = None
        with pytest.raises(TVClientError, match="not connected"):
            await client.call_tool("chart_get_state", {})

    @pytest.mark.asyncio
    async def test_call_tool_raises_on_mcp_error(self):
        client = TradingViewClient.__new__(TradingViewClient)
        client._max_retries = 1
        client._retry_delay = 0.0
        session = AsyncMock()
        result = MagicMock()
        result.isError = True
        result.content = _make_error_content("Tool not found")
        session.call_tool = AsyncMock(return_value=result)
        client._session = session

        with pytest.raises(TVClientError, match="returned error"):
            await client.call_tool("bad_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_retries_on_exception(self):
        client = TradingViewClient.__new__(TradingViewClient)
        client._max_retries = 3
        client._retry_delay = 0.0

        session = AsyncMock()
        good_result = MagicMock()
        good_result.isError = False
        good_result.content = _make_content({"success": True})

        # Fail twice, succeed on third
        session.call_tool = AsyncMock(
            side_effect=[RuntimeError("net error"), RuntimeError("net error"), good_result]
        )
        client._session = session

        result = await client.call_tool("some_tool", {})
        assert result["success"] is True
        assert session.call_tool.call_count == 3

    @pytest.mark.asyncio
    async def test_call_tool_raises_after_all_retries_fail(self):
        client = TradingViewClient.__new__(TradingViewClient)
        client._max_retries = 2
        client._retry_delay = 0.0

        session = AsyncMock()
        session.call_tool = AsyncMock(side_effect=RuntimeError("always fails"))
        client._session = session

        with pytest.raises(TVClientError, match="failed after 2 attempts"):
            await client.call_tool("some_tool", {})

    @pytest.mark.asyncio
    async def test_list_tools_returns_names(self):
        client = TradingViewClient.__new__(TradingViewClient)
        tool_a = MagicMock()
        tool_a.name = "chart_get_state"
        tool_b = MagicMock()
        tool_b.name = "replay_start"

        session = AsyncMock()
        tools_result = MagicMock()
        tools_result.tools = [tool_a, tool_b]
        session.list_tools = AsyncMock(return_value=tools_result)
        client._session = session

        names = await client.list_tools()
        assert "chart_get_state" in names
        assert "replay_start" in names
