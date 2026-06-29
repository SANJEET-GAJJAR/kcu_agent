"""Unit tests for chart preflight — Task 1 of Phase 4C.

All tests are offline (no TradingView connection required).
Preflight logic is tested via ChartPreflight.validate(dict) directly.
"""
from __future__ import annotations

import ast
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.collector.chart_preflight import (
    ChartPreflightConfig,
    ChartPreflight,
    PreflightResult,
    PreflightFailedError,
    load_preflight_config,
    validate_collection,
    write_preflight_companion,
    _extract_indicators,
    _detect_kcu_version,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = ChartPreflightConfig(
    required_template="only KCU indicator",
    required_indicators=["Stop Loss Widget", "KCU Indicator", "Volume"],
    kcu_indicator_keys=["KCU Indicator", "KCU", "KCU_Indicator", "KCU Backtesting"],
    chart_state_tool="chart_get_state",
    collection_version="1.0.0",
    collector_version="1.0.0",
)


def _good_chart_state(
    template: str = "only KCU indicator",
    indicators: list | None = None,
) -> dict:
    if indicators is None:
        indicators = [
            {"name": "Stop Loss Widget", "version": None},
            {"name": "KCU Indicator", "version": "1.2.3"},
            {"name": "Volume", "version": None},
        ]
    return {"success": True, "template_name": template, "studies": indicators}


def _pf() -> ChartPreflight:
    return ChartPreflight(_DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# ChartPreflightConfig
# ---------------------------------------------------------------------------

class TestChartPreflightConfig:
    def test_valid_construction(self):
        cfg = _DEFAULT_CONFIG
        assert cfg.required_template == "only KCU indicator"
        assert "Stop Loss Widget" in cfg.required_indicators
        assert "KCU Indicator" in cfg.kcu_indicator_keys

    def test_empty_template_raises(self):
        with pytest.raises(ValueError, match="required_template"):
            ChartPreflightConfig(
                required_template="",
                required_indicators=["KCU Indicator"],
                kcu_indicator_keys=["KCU Indicator"],
                chart_state_tool="chart_get_state",
                collection_version="1.0.0",
                collector_version="1.0.0",
            )

    def test_empty_required_indicators_raises(self):
        with pytest.raises(ValueError, match="required_indicators"):
            ChartPreflightConfig(
                required_template="only KCU indicator",
                required_indicators=[],
                kcu_indicator_keys=["KCU Indicator"],
                chart_state_tool="chart_get_state",
                collection_version="1.0.0",
                collector_version="1.0.0",
            )

    def test_empty_kcu_keys_raises(self):
        with pytest.raises(ValueError, match="kcu_indicator_keys"):
            ChartPreflightConfig(
                required_template="only KCU indicator",
                required_indicators=["KCU Indicator"],
                kcu_indicator_keys=[],
                chart_state_tool="chart_get_state",
                collection_version="1.0.0",
                collector_version="1.0.0",
            )

    def test_load_from_yaml(self):
        cfg = load_preflight_config()
        assert cfg.required_template == "only KCU indicator"
        assert "Stop Loss Widget" in cfg.required_indicators
        assert "KCU Indicator" in cfg.required_indicators
        assert "Volume" in cfg.required_indicators
        assert "KCU Indicator" in cfg.kcu_indicator_keys
        assert cfg.collection_version
        assert cfg.collector_version


# ---------------------------------------------------------------------------
# PreflightResult
# ---------------------------------------------------------------------------

class TestPreflightResult:
    def _make(self, passed: bool = True) -> PreflightResult:
        return PreflightResult(
            template_name="only KCU indicator",
            indicator_names=["Stop Loss Widget", "KCU Indicator", "Volume"],
            required_indicators_present=passed,
            kcu_indicator_version="1.2.3" if passed else "unknown",
            preflight_passed=passed,
            collection_version="1.0.0",
            collector_version="1.0.0",
            failure_reasons=[] if passed else ["missing something"],
        )

    def test_to_dict_has_all_required_fields(self):
        r = self._make(True)
        d = r.to_dict()
        assert d["template_name"] == "only KCU indicator"
        assert d["indicator_names"] == ["Stop Loss Widget", "KCU Indicator", "Volume"]
        assert d["required_indicators_present"] is True
        assert d["kcu_indicator_version"] == "1.2.3"
        assert d["preflight_passed"] is True
        assert d["collection_version"] == "1.0.0"
        assert d["collector_version"] == "1.0.0"
        assert d["failure_reasons"] == []

    def test_to_metadata_subset(self):
        r = self._make(True)
        m = r.to_metadata()
        assert "template_name" in m
        assert "indicator_names" in m
        assert "required_indicators_present" in m
        assert "kcu_indicator_version" in m
        assert "preflight_passed" in m
        assert "collection_version" in m
        assert "collector_version" in m
        # failure_reasons NOT in metadata (internal detail)
        assert "failure_reasons" not in m

    def test_validate_passes_for_valid_result(self):
        r = self._make(True)
        errors = r.validate()
        assert errors == []

    def test_validate_catches_empty_versions(self):
        r = PreflightResult(
            template_name="x", indicator_names=[], required_indicators_present=False,
            kcu_indicator_version="", preflight_passed=False,
            collection_version="1.0.0", collector_version="1.0.0",
        )
        errors = r.validate()
        assert any("kcu_indicator_version" in e for e in errors)


# ---------------------------------------------------------------------------
# ChartPreflight.validate — passing cases
# ---------------------------------------------------------------------------

class TestChartPreflightValidatePassing:
    def test_all_present_passes(self):
        result = _pf().validate(_good_chart_state())
        assert result.preflight_passed is True
        assert result.failure_reasons == []
        assert result.required_indicators_present is True

    def test_kcu_version_captured(self):
        result = _pf().validate(_good_chart_state())
        assert result.kcu_indicator_version == "1.2.3"

    def test_indicator_names_in_result(self):
        result = _pf().validate(_good_chart_state())
        assert "Stop Loss Widget" in result.indicator_names
        assert "KCU Indicator" in result.indicator_names
        assert "Volume" in result.indicator_names

    def test_template_name_captured(self):
        result = _pf().validate(_good_chart_state())
        assert result.template_name == "only KCU indicator"

    def test_versions_in_metadata(self):
        result = _pf().validate(_good_chart_state())
        meta = result.to_metadata()
        assert meta["collection_version"] == "1.0.0"
        assert meta["collector_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# ChartPreflight.validate — failure: missing indicators
# ---------------------------------------------------------------------------

class TestMissingStopLossWidget:
    def test_missing_stop_loss_widget_fails(self):
        state = _good_chart_state(indicators=[
            {"name": "KCU Indicator", "version": "1.0"},
            {"name": "Volume", "version": None},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert result.required_indicators_present is False
        assert any("Stop Loss Widget" in r for r in result.failure_reasons)

    def test_missing_stop_loss_preflight_passed_false(self):
        state = _good_chart_state(indicators=[
            {"name": "KCU Indicator", "version": "1.0"},
            {"name": "Volume", "version": None},
        ])
        assert _pf().validate(state).preflight_passed is False


class TestMissingKCUIndicator:
    def test_missing_kcu_indicator_fails(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "Volume", "version": None},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert result.required_indicators_present is False

    def test_missing_kcu_version_is_unknown_when_no_kcu(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "Volume", "version": None},
        ])
        result = _pf().validate(state)
        assert result.kcu_indicator_version == "unknown"

    def test_kcu_under_alias_name_is_accepted(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "KCU Backtesting", "version": "2.1.0"},
            {"name": "Volume", "version": None},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is True
        assert result.kcu_indicator_version == "2.1.0"


class TestMissingVolume:
    def test_missing_volume_fails(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "KCU Indicator", "version": "1.0"},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert any("Volume" in r for r in result.failure_reasons)

    def test_missing_volume_required_indicators_false(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "KCU Indicator", "version": "1.0"},
        ])
        assert _pf().validate(state).required_indicators_present is False


# ---------------------------------------------------------------------------
# Wrong template
# ---------------------------------------------------------------------------

class TestWrongTemplate:
    def test_wrong_template_fails(self):
        state = _good_chart_state(template="default")
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert any("template" in r.lower() for r in result.failure_reasons)

    def test_none_template_passes_with_warning_when_indicators_present(self):
        # MCP never returns template_name (protocol limitation).
        # When all required indicators are present the preflight PASSES with
        # preflight_warning=True and template_name="unknown" recorded.
        state = {"success": True, "studies": [
            {"name": "Stop Loss Widget"}, {"name": "KCU Indicator", "version": "1.0"}, {"name": "Volume"},
        ]}
        result = _pf().validate(state)
        assert result.preflight_passed is True
        assert result.preflight_warning is True
        assert result.template_name == "unknown"

    def test_none_template_fails_when_indicators_also_missing(self):
        # Even without a template check, missing indicators still block collection.
        state = {"success": True, "studies": []}
        result = _pf().validate(state)
        assert result.preflight_passed is False

    def test_correct_template_but_missing_indicator_still_fails(self):
        state = _good_chart_state(
            template="only KCU indicator",
            indicators=[{"name": "KCU Indicator", "version": "1.0"}, {"name": "Volume"}],
        )
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert any("Stop Loss Widget" in r for r in result.failure_reasons)


# ---------------------------------------------------------------------------
# Unknown KCU version
# ---------------------------------------------------------------------------

class TestKCUVersion:
    def test_unknown_version_allowed_when_indicator_exists(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget", "version": None},
            {"name": "KCU Indicator", "version": None},  # no version
            {"name": "Volume", "version": None},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is True
        assert result.kcu_indicator_version == "unknown"

    def test_unknown_version_not_allowed_when_no_kcu_at_all(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget"},
            {"name": "Volume"},
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert result.kcu_indicator_version == "unknown"

    def test_version_string_captured_correctly(self):
        state = _good_chart_state(indicators=[
            {"name": "Stop Loss Widget"},
            {"name": "KCU Indicator", "version": "3.7.2"},
            {"name": "Volume"},
        ])
        result = _pf().validate(state)
        assert result.kcu_indicator_version == "3.7.2"


# ---------------------------------------------------------------------------
# Indicator format handling
# ---------------------------------------------------------------------------

class TestIndicatorFormats:
    def test_plain_string_list(self):
        state = {
            "success": True,
            "template_name": "only KCU indicator",
            "studies": ["Stop Loss Widget", "KCU Indicator", "Volume"],
        }
        result = _pf().validate(state)
        assert result.preflight_passed is True
        assert result.kcu_indicator_version == "unknown"

    def test_indicators_alias(self):
        state = {
            "success": True,
            "template_name": "only KCU indicator",
            "indicators": [
                {"name": "Stop Loss Widget"},
                {"name": "KCU Indicator", "version": "1.0"},
                {"name": "Volume"},
            ],
        }
        result = _pf().validate(state)
        assert result.preflight_passed is True

    def test_template_alias(self):
        state = {
            "success": True,
            "template": "only KCU indicator",
            "studies": [
                {"name": "Stop Loss Widget"},
                {"name": "KCU Indicator", "version": "1.0"},
                {"name": "Volume"},
            ],
        }
        result = _pf().validate(state)
        assert result.preflight_passed is True

    def test_empty_studies_list_fails(self):
        state = {"success": True, "template_name": "only KCU indicator", "studies": []}
        result = _pf().validate(state)
        assert result.preflight_passed is False
        assert result.required_indicators_present is False

    def test_case_insensitive_indicator_check(self):
        state = _good_chart_state(indicators=[
            {"name": "stop loss widget"},  # lowercase
            {"name": "KCU Indicator", "version": "1.0"},
            {"name": "VOLUME"},  # uppercase
        ])
        result = _pf().validate(state)
        assert result.preflight_passed is True


# ---------------------------------------------------------------------------
# ChartPreflight.run — async tests
# ---------------------------------------------------------------------------

class TestChartPreflightRun:
    @pytest.mark.asyncio
    async def test_run_passes_when_chart_state_valid(self, tmp_path):
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = _good_chart_state()
        pf = _pf()
        result = await pf.run(mock_client, tmp_path)
        assert result.preflight_passed is True
        mock_client.call_tool.assert_called_once_with("chart_get_state", {})

    @pytest.mark.asyncio
    async def test_run_raises_on_failure(self, tmp_path):
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = _good_chart_state(indicators=[
            {"name": "KCU Indicator", "version": "1.0"},
        ])  # missing Stop Loss Widget and Volume
        pf = _pf()
        with pytest.raises(PreflightFailedError):
            await pf.run(mock_client, tmp_path)

    @pytest.mark.asyncio
    async def test_run_writes_failure_file(self, tmp_path):
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = {"success": True, "template_name": "wrong"}
        pf = _pf()
        with pytest.raises(PreflightFailedError):
            await pf.run(mock_client, tmp_path)
        failure_file = tmp_path / "preflight_failed.json"
        assert failure_file.exists()
        data = json.loads(failure_file.read_text())
        assert data["preflight_passed"] is False

    @pytest.mark.asyncio
    async def test_run_does_not_write_failure_file_on_success(self, tmp_path):
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = _good_chart_state()
        pf = _pf()
        await pf.run(mock_client, tmp_path)
        assert not (tmp_path / "preflight_failed.json").exists()

    @pytest.mark.asyncio
    async def test_run_aborts_on_client_exception(self, tmp_path):
        mock_client = AsyncMock()
        mock_client.call_tool.side_effect = Exception("Connection failed")
        pf = _pf()
        with pytest.raises(PreflightFailedError):
            await pf.run(mock_client, tmp_path)


# ---------------------------------------------------------------------------
# Collection validation
# ---------------------------------------------------------------------------

class TestCollectionValidation:
    def test_valid_collection_with_companion_file(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text(json.dumps({"preflight_passed": True}))
        assert validate_collection(collection) is True

    def test_collection_without_companion_is_invalid(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text("")
        assert validate_collection(collection) is False

    def test_collection_with_failed_preflight_is_invalid(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text(json.dumps({"preflight_passed": False}))
        assert validate_collection(collection) is False

    def test_collection_with_corrupt_companion_is_invalid(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text("")
        companion = tmp_path / "TSLA_2024-01-15_2m_preflight.json"
        companion.write_text("not json {{")
        assert validate_collection(collection) is False

    def test_write_preflight_companion_creates_file(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        result = PreflightResult(
            template_name="only KCU indicator",
            indicator_names=["Stop Loss Widget", "KCU Indicator", "Volume"],
            required_indicators_present=True,
            kcu_indicator_version="1.0",
            preflight_passed=True,
            collection_version="1.0.0",
            collector_version="1.0.0",
        )
        companion = write_preflight_companion(result, collection)
        assert companion.exists()
        data = json.loads(companion.read_text())
        assert data["preflight_passed"] is True

    def test_companion_validates_collection(self, tmp_path):
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        result = PreflightResult(
            template_name="only KCU indicator",
            indicator_names=["Stop Loss Widget", "KCU Indicator", "Volume"],
            required_indicators_present=True,
            kcu_indicator_version="1.0",
            preflight_passed=True,
            collection_version="1.0.0",
            collector_version="1.0.0",
        )
        write_preflight_companion(result, collection)
        assert validate_collection(collection) is True


# ---------------------------------------------------------------------------
# Prove collection cannot start without passing preflight
# ---------------------------------------------------------------------------

class TestCollectionRequiresPreflight:
    @pytest.mark.asyncio
    async def test_preflight_failure_raises_before_collection(self, tmp_path):
        """Collection must not proceed if preflight fails."""
        mock_client = AsyncMock()
        # Returns chart state missing all required indicators
        mock_client.call_tool.return_value = {
            "success": True,
            "template_name": "wrong template",
            "studies": [],
        }
        pf = ChartPreflight(_DEFAULT_CONFIG)
        with pytest.raises(PreflightFailedError) as exc_info:
            await pf.run(mock_client, tmp_path)
        assert "preflight failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_preflight_success_allows_collection(self, tmp_path):
        """Successful preflight does not raise — collection may proceed."""
        mock_client = AsyncMock()
        mock_client.call_tool.return_value = _good_chart_state()
        pf = ChartPreflight(_DEFAULT_CONFIG)
        result = await pf.run(mock_client, tmp_path)
        assert result.preflight_passed is True
        # No exception raised — collection may proceed

    def test_invalid_collection_cannot_be_backtested(self, tmp_path):
        """Collections without valid preflight companion are rejected."""
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text('{"timestamp": 1}')
        assert validate_collection(collection) is False

    def test_stale_collection_missing_preflight_is_invalid(self, tmp_path):
        """Pre-preflight collections (no companion file) are invalid."""
        collection = tmp_path / "TSLA_2024-01-15_2m.jsonl"
        collection.write_text('{"timestamp": 1}')
        # No companion file = pre-preflight = invalid
        assert validate_collection(collection) is False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestExtractIndicators:
    def test_dict_format(self):
        state = {"studies": [
            {"name": "RSI", "version": "1.0"},
            {"name": "VWAP", "version": None},
        ]}
        names, versions = _extract_indicators(state)
        assert names == ["RSI", "VWAP"]
        assert versions["RSI"] == "1.0"
        assert versions["VWAP"] is None

    def test_string_format(self):
        state = {"studies": ["RSI", "VWAP"]}
        names, versions = _extract_indicators(state)
        assert names == ["RSI", "VWAP"]
        assert versions["RSI"] is None

    def test_empty_studies(self):
        names, versions = _extract_indicators({"studies": []})
        assert names == []
        assert versions == {}

    def test_no_studies_key(self):
        names, versions = _extract_indicators({"success": True})
        assert names == []


class TestDetectKCUVersion:
    def test_detects_version(self):
        v = _detect_kcu_version(
            ["Stop Loss Widget", "KCU Indicator", "Volume"],
            {"Stop Loss Widget": None, "KCU Indicator": "2.3.4", "Volume": None},
            ["KCU Indicator", "KCU"],
        )
        assert v == "2.3.4"

    def test_returns_unknown_when_no_version(self):
        v = _detect_kcu_version(
            ["KCU Indicator"],
            {"KCU Indicator": None},
            ["KCU Indicator"],
        )
        assert v == "unknown"

    def test_returns_unknown_when_not_found(self):
        v = _detect_kcu_version(
            ["Volume", "RSI"],
            {"Volume": None, "RSI": None},
            ["KCU Indicator"],
        )
        assert v == "unknown"

    def test_detects_via_alias(self):
        v = _detect_kcu_version(
            ["KCU Backtesting"],
            {"KCU Backtesting": "5.0"},
            ["KCU Indicator", "KCU", "KCU Backtesting"],
        )
        assert v == "5.0"


# ---------------------------------------------------------------------------
# No trading logic in source
# ---------------------------------------------------------------------------

class TestNoTradingLogicInPreflight:
    _TRADING_TERMS = [
        "entry", "stop_loss", "take_profit", "position_size",
        "risk_reward", "target_price",
    ]
    _SOURCE_FILES = [
        "src/collector/chart_preflight.py",
    ]

    @pytest.mark.parametrize("source_file", _SOURCE_FILES)
    def test_no_trading_terms(self, source_file):
        path = Path(source_file)
        source = path.read_text().lower()
        for term in self._TRADING_TERMS:
            assert term not in source, (
                f"Trading term {term!r} found in {source_file}"
            )

    def test_no_entry_signals_in_preflight_result(self):
        """PreflightResult must not contain trade-management fields."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(PreflightResult)}
        trade_fields = {"entry", "stop", "target", "size", "risk", "reward"}
        overlap = field_names & trade_fields
        assert overlap == set(), f"Trade fields found in PreflightResult: {overlap}"
