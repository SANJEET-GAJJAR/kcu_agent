"""Unit tests for workspace_preflight.py.

Tests the seven required behaviors:
1. Live workspace blocks collection.
2. Unknown workspace blocks by default.
3. Unknown workspace allowed only with explicit override.
4. Backtesting workspace passes.
5. Workspace preflight runs before ticker/timeframe/replay changes.
6. Metadata is written.
7. Override with non-backtesting non-live workspace.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.collector.workspace_preflight import (
    WorkspaceConfig,
    WorkspacePreflight,
    WorkspacePreflightError,
    WorkspacePreflightResult,
    load_workspace_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(
    *,
    live: str = "Live Trading",
    backtest: str = "KCU Backtesting",
    allow_unknown: bool = False,
    protected_live: bool = True,
) -> WorkspaceConfig:
    return WorkspaceConfig(
        live_workspace_name=live,
        backtest_workspace_name=backtest,
        required_workspace="backtesting",
        protected_live_workspace=protected_live,
        allow_unknown_workspace_for_collection=allow_unknown,
    )


def _mock_client(layout_name: str | None, success: bool = True) -> AsyncMock:
    client = AsyncMock()
    client.call_tool.return_value = {
        "success": success,
        "layout_name": layout_name,
        "detected": layout_name is not None,
        "detection_source": "dom_header_button" if layout_name else None,
    }
    return client


# ---------------------------------------------------------------------------
# 1. Live workspace blocks collection
# ---------------------------------------------------------------------------

class TestLiveWorkspaceBlocked:

    @pytest.mark.asyncio
    async def test_exact_live_name_raises(self):
        config = _make_config(live="Live Trading")
        client = _mock_client("Live Trading")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError, match="protected live trading workspace"):
            await pf.run(client)

    @pytest.mark.asyncio
    async def test_live_name_case_insensitive(self):
        config = _make_config(live="Live Trading")
        client = _mock_client("live trading")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError):
            await pf.run(client)

    @pytest.mark.asyncio
    async def test_live_name_substring_match(self):
        """If detected name contains the live workspace name, it is blocked."""
        config = _make_config(live="Live Trading")
        client = _mock_client("My Live Trading Layout")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError):
            await pf.run(client)

    @pytest.mark.asyncio
    async def test_live_blocked_even_with_allow_unknown_override(self):
        """allow_unknown_workspace_for_collection=True does NOT allow live workspace."""
        config = _make_config(live="Live Trading", allow_unknown=True)
        client = _mock_client("Live Trading")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError, match="protected live trading workspace"):
            await pf.run(client)


# ---------------------------------------------------------------------------
# 2. Unknown workspace blocked by default
# ---------------------------------------------------------------------------

class TestUnknownWorkspaceBlockedByDefault:

    @pytest.mark.asyncio
    async def test_none_layout_name_blocked(self):
        config = _make_config(allow_unknown=False)
        client = _mock_client(None)
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError, match="could not be detected"):
            await pf.run(client)

    @pytest.mark.asyncio
    async def test_tool_call_failure_blocked(self):
        """If layout_get_current raises an exception, treat as unknown → block."""
        config = _make_config(allow_unknown=False)
        client = AsyncMock()
        client.call_tool.side_effect = Exception("CDP connection lost")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError, match="could not be detected"):
            await pf.run(client)

    @pytest.mark.asyncio
    async def test_unrecognised_layout_blocked(self):
        """A layout that is neither live nor backtest is treated as unknown (blocked by default)."""
        config = _make_config(allow_unknown=False)
        client = _mock_client("Some Other Layout")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError):
            await pf.run(client)


# ---------------------------------------------------------------------------
# 3. Unknown workspace allowed only with explicit override
# ---------------------------------------------------------------------------

class TestUnknownWorkspaceWithOverride:

    @pytest.mark.asyncio
    async def test_none_layout_passes_with_override(self):
        config = _make_config(allow_unknown=True)
        client = _mock_client(None)
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.passed is True
        assert result.workspace_verified is False
        assert result.workspace_warning is not None
        assert "override" in result.workspace_warning.lower()

    @pytest.mark.asyncio
    async def test_unrecognised_layout_passes_with_override(self):
        config = _make_config(allow_unknown=True)
        client = _mock_client("Mystery Layout")
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.passed is True
        assert result.workspace_verified is False
        assert result.workspace_name == "Mystery Layout"
        assert result.workspace_warning is not None

    @pytest.mark.asyncio
    async def test_override_still_blocks_live_workspace(self):
        """Even with override, live workspace is always blocked."""
        config = _make_config(live="Live Trading", allow_unknown=True)
        client = _mock_client("Live Trading")
        pf = WorkspacePreflight(config)
        with pytest.raises(WorkspacePreflightError):
            await pf.run(client)


# ---------------------------------------------------------------------------
# 4. Backtesting workspace passes
# ---------------------------------------------------------------------------

class TestBacktestWorkspacePasses:

    @pytest.mark.asyncio
    async def test_exact_backtest_name_passes(self):
        config = _make_config(backtest="KCU Backtesting")
        client = _mock_client("KCU Backtesting")
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.passed is True
        assert result.workspace_verified is True
        assert result.workspace_name == "KCU Backtesting"
        assert result.workspace_warning is None

    @pytest.mark.asyncio
    async def test_backtest_name_case_insensitive(self):
        config = _make_config(backtest="KCU Backtesting")
        client = _mock_client("kcu backtesting")
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.passed is True
        assert result.workspace_verified is True

    @pytest.mark.asyncio
    async def test_backtest_name_substring_match(self):
        config = _make_config(backtest="KCU Backtesting")
        client = _mock_client("My KCU Backtesting Layout")
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.passed is True
        assert result.workspace_verified is True

    @pytest.mark.asyncio
    async def test_backtest_passes_live_protected_is_true(self):
        config = _make_config(backtest="KCU Backtesting")
        client = _mock_client("KCU Backtesting")
        pf = WorkspacePreflight(config)
        result = await pf.run(client)
        assert result.live_workspace_protected is True


# ---------------------------------------------------------------------------
# 5. Workspace preflight runs before ticker/timeframe/replay changes
# ---------------------------------------------------------------------------

class TestWorkspacePreflightRunsFirst:
    """Verify workspace preflight is called before ctrl.load_ticker().

    This is an integration-level unit test that patches the relevant callables
    and verifies call order.
    """

    @pytest.mark.asyncio
    async def test_workspace_checked_before_load_ticker(self):
        """collect_day() with live workspace must fail before load_ticker is called."""
        from unittest.mock import patch, AsyncMock, MagicMock

        workspace_config = _make_config(live="Live Trading", backtest="KCU Backtesting")

        # Mock TradingViewClient to return live workspace
        mock_client = _mock_client("Live Trading")

        # Track whether load_ticker was called
        load_ticker_called = []

        async def fake_load_ticker(ticker):
            load_ticker_called.append(ticker)

        with patch("src.collector.day_collector.TradingViewClient") as MockTV:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            MockTV.return_value = ctx

            mock_ctrl = AsyncMock()
            mock_ctrl.load_ticker = fake_load_ticker
            mock_ctrl.set_timeframe = AsyncMock()
            mock_ctrl.load_trading_day = AsyncMock()
            mock_ctrl.stop_replay = AsyncMock()

            with patch("src.collector.day_collector.ReplayController", return_value=mock_ctrl):
                with patch("src.collector.day_collector.ChartPreflight"):
                    from src.collector.day_collector import collect_day
                    with pytest.raises(WorkspacePreflightError):
                        await collect_day(
                            ticker="TSLA",
                            date="2024-01-15",
                            timeframe="2",
                            workspace_config=workspace_config,
                            dry_run=True,
                        )

        assert load_ticker_called == [], (
            "load_ticker should NOT have been called when workspace preflight fails"
        )


# ---------------------------------------------------------------------------
# 6. Metadata is written into collection result
# ---------------------------------------------------------------------------

class TestWorkspaceMetadataWritten:

    @pytest.mark.asyncio
    async def test_to_metadata_fields_present(self):
        config = _make_config(backtest="KCU Backtesting")
        result = WorkspacePreflightResult(
            workspace_name="KCU Backtesting",
            workspace_verified=True,
            live_workspace_protected=True,
            workspace_warning=None,
            passed=True,
        )
        meta = result.to_metadata()
        assert meta["workspace_name"] == "KCU Backtesting"
        assert meta["workspace_verified"] is True
        assert meta["live_workspace_protected"] is True
        assert meta["workspace_warning"] is None
        assert meta["workspace_preflight_passed"] is True

    @pytest.mark.asyncio
    async def test_unknown_workspace_metadata_uses_unknown_string(self):
        result = WorkspacePreflightResult(
            workspace_name=None,
            workspace_verified=False,
            live_workspace_protected=True,
            workspace_warning="Override active",
            passed=True,
        )
        meta = result.to_metadata()
        assert meta["workspace_name"] == "unknown"
        assert meta["workspace_verified"] is False
        assert meta["workspace_warning"] == "Override active"

    @pytest.mark.asyncio
    async def test_collect_day_result_has_workspace_metadata(self):
        """collect_day() writes workspace_metadata to CollectionResult."""
        from unittest.mock import patch, AsyncMock

        workspace_config = _make_config(backtest="KCU Backtesting")
        mock_client = _mock_client("KCU Backtesting")

        mock_ctrl = AsyncMock()
        mock_ctrl.load_ticker = AsyncMock()
        mock_ctrl.set_timeframe = AsyncMock()
        mock_ctrl.load_trading_day = AsyncMock()
        mock_ctrl.stop_replay = AsyncMock()
        mock_ctrl.read_next_candle = AsyncMock(return_value=None)  # empty day

        with patch("src.collector.day_collector.TradingViewClient") as MockTV:
            ctx = AsyncMock()
            ctx.__aenter__ = AsyncMock(return_value=mock_client)
            ctx.__aexit__ = AsyncMock(return_value=False)
            MockTV.return_value = ctx

            with patch("src.collector.day_collector.ReplayController", return_value=mock_ctrl):
                with patch("src.collector.day_collector._wait_for_chart_ready", AsyncMock()):
                    with patch("src.collector.day_collector._run_collection_loop") as mock_loop:
                        from src.collector.day_collector import CollectionResult
                        from pathlib import Path
                        mock_loop.return_value = CollectionResult(
                            ticker="TSLA", date="2024-01-15", timeframe="2",
                            output_path=Path("/tmp/test.jsonl"),
                            candles_written=0, candles_skipped=0,
                            complete=False, stop_reason="end_of_data",
                            validation_errors=[],
                        )
                        with patch("src.collector.day_collector.validate_jsonl") as mock_vr:
                            mock_vr.return_value = MagicMock(errors=[], valid=True)
                            with patch("src.collector.day_collector.build_ohlc_quality_report"):
                                from src.collector.day_collector import collect_day
                                result = await collect_day(
                                    ticker="TSLA",
                                    date="2024-01-15",
                                    timeframe="2",
                                    workspace_config=workspace_config,
                                    dry_run=True,
                                )

        assert result.workspace_metadata is not None
        assert result.workspace_metadata["workspace_verified"] is True
        assert result.workspace_metadata["workspace_name"] == "KCU Backtesting"
        assert result.workspace_metadata["live_workspace_protected"] is True
        assert result.workspace_metadata["workspace_preflight_passed"] is True


# ---------------------------------------------------------------------------
# 7. Config loading
# ---------------------------------------------------------------------------

class TestWorkspaceConfigLoading:

    def test_load_workspace_config_from_file(self, tmp_path):
        config_file = tmp_path / "workspace.yaml"
        config_file.write_text(
            "live_workspace_name: 'My Live Charts'\n"
            "backtest_workspace_name: 'My Backtesting'\n"
            "required_workspace: backtesting\n"
            "protected_live_workspace: true\n"
            "allow_unknown_workspace_for_collection: false\n"
        )
        config = load_workspace_config(config_file)
        assert config.live_workspace_name == "My Live Charts"
        assert config.backtest_workspace_name == "My Backtesting"
        assert config.required_workspace == "backtesting"
        assert config.protected_live_workspace is True
        assert config.allow_unknown_workspace_for_collection is False

    def test_invalid_required_workspace_raises(self):
        with pytest.raises(ValueError, match="required_workspace"):
            WorkspaceConfig(
                live_workspace_name="Live",
                backtest_workspace_name="Backtest",
                required_workspace="live",  # invalid
                protected_live_workspace=True,
                allow_unknown_workspace_for_collection=False,
            )

    def test_empty_live_name_raises(self):
        with pytest.raises(ValueError, match="live_workspace_name"):
            WorkspaceConfig(
                live_workspace_name="",
                backtest_workspace_name="Backtest",
                required_workspace="backtesting",
                protected_live_workspace=True,
                allow_unknown_workspace_for_collection=False,
            )

    def test_empty_backtest_name_raises(self):
        with pytest.raises(ValueError, match="backtest_workspace_name"):
            WorkspaceConfig(
                live_workspace_name="Live",
                backtest_workspace_name="",
                required_workspace="backtesting",
                protected_live_workspace=True,
                allow_unknown_workspace_for_collection=False,
            )
