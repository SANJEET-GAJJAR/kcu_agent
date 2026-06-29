"""Replay controller — orchestrates TradingView MCP for deterministic candle-by-candle replay.

Responsibilities:
  - Load a ticker
  - Load a specific trading day (scroll + start replay)
  - Switch timeframe
  - Advance exactly one candle
  - Read the current candle as a CandleSnapshot
  - Read raw indicator values visible on the chart
  - Export a single validated candle snapshot to JSON

No trading logic. No analysis. No interpretation.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .candle_schema import CandleSnapshot, export_snapshot
from .tv_client import TradingViewClient, TVClientError

log = logging.getLogger(__name__)

_SUPPORTED_TIMEFRAMES = {"1", "2", "3", "5", "10", "15", "30", "60", "D"}


class ReplayControllerError(Exception):
    """Raised when the replay controller detects an invalid state."""


class ReplayController:
    """Controls TradingView replay via the MCP client.

    All methods are async. The controller tracks minimal state (current symbol,
    timeframe, and replay_date) to build validated CandleSnapshot objects.

    Usage:
        async with TradingViewClient() as client:
            ctrl = ReplayController(client)
            await ctrl.load_ticker("TSLA")
            await ctrl.set_timeframe("2")
            await ctrl.load_trading_day("2024-01-15")
            candle = await ctrl.read_current_candle()
            await ctrl.advance_one_candle()
    """

    def __init__(self, client: TradingViewClient) -> None:
        self._client = client
        self._symbol: str | None = None
        self._timeframe: str | None = None
        self._replay_date: str | None = None
        self._replay_active: bool = False

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def load_ticker(self, symbol: str) -> dict[str, Any]:
        """Set the chart symbol. Must be called before starting replay."""
        if not symbol or not isinstance(symbol, str):
            raise ReplayControllerError(f"symbol must be a non-empty string, got {symbol!r}")
        symbol = symbol.upper().strip()

        log.info("Loading ticker: %s", symbol)
        result = await self._client.call_tool("chart_set_symbol", {"symbol": symbol})
        _require_success(result, "chart_set_symbol")

        self._symbol = symbol
        self._replay_active = False
        log.info("Ticker loaded: %s", symbol)
        return {"symbol": self._symbol, "success": True}

    async def set_timeframe(self, timeframe: str) -> dict[str, Any]:
        """Switch the chart timeframe. Valid values: 1, 2, 3, 5, 10, 15, 30, 60, D."""
        if str(timeframe) not in _SUPPORTED_TIMEFRAMES:
            raise ReplayControllerError(
                f"Unsupported timeframe {timeframe!r}. Valid: {sorted(_SUPPORTED_TIMEFRAMES)}"
            )
        log.info("Setting timeframe: %s", timeframe)
        result = await self._client.call_tool("chart_set_timeframe", {"timeframe": str(timeframe)})
        _require_success(result, "chart_set_timeframe")

        self._timeframe = str(timeframe)
        self._replay_active = False
        log.info("Timeframe set: %s", timeframe)
        return {"timeframe": self._timeframe, "success": True}

    async def load_trading_day(self, date: str) -> dict[str, Any]:
        """Scroll to date and start replay at the open of that day.

        date: ISO format YYYY-MM-DD (e.g. "2024-01-15").
        Replay is started and positioned at the first candle of the day.
        """
        _validate_date(date)
        if not self._symbol:
            raise ReplayControllerError("load_ticker() must be called before load_trading_day()")
        if not self._timeframe:
            raise ReplayControllerError("set_timeframe() must be called before load_trading_day()")

        log.info("Loading trading day: %s", date)

        # Stop any existing replay first to guarantee clean cursor state.
        # If the previous session crashed without calling stop, the replay cursor
        # may be at an arbitrary position which causes replay_start to seek
        # incorrectly. Always reset before starting a new session.
        try:
            await self._client.call_tool("replay_stop", {})
            log.debug("Stopped existing replay before restarting")
        except Exception:
            pass  # Not in replay — safe to ignore

        # Scroll chart to the date so replay starts at the right position.
        await self._client.call_tool("chart_scroll_to_date", {"date": date})

        # Start replay at the date.
        result = await self._client.call_tool("replay_start", {"date": date})
        _require_success(result, "replay_start")

        self._replay_date = date
        self._replay_active = True
        log.info("Replay started on %s for %s @ %s", date, self._symbol, self._timeframe)

        # TradingView may show "Continue your last replay?" dialog after replay_start
        # initiates a new replay session.  The dialog is rendered asynchronously, so
        # we poll for up to 1 second after replay_start returns.  Clicking "Start new"
        # is always correct here — we are explicitly starting a fresh replay.
        # If the dialog never appears the attempts fail silently.
        await self._dismiss_replay_resume_dialog()

        return {
            "success": True,
            "symbol": self._symbol,
            "timeframe": self._timeframe,
            "replay_date": self._replay_date,
        }

    # ------------------------------------------------------------------
    # Replay control
    # ------------------------------------------------------------------

    async def advance_one_candle(self) -> dict[str, Any]:
        """Move exactly one candle forward in replay. Returns the new current_date."""
        self._require_replay_active()
        log.debug("Advancing one candle")
        result = await self._client.call_tool("replay_step", {})
        _require_success(result, "replay_step")
        return {"success": True, "current_date": result.get("current_date")}

    async def get_replay_status(self) -> dict[str, Any]:
        """Return raw replay status from TradingView."""
        result = await self._client.call_tool("replay_status", {})
        _require_success(result, "replay_status")
        return result

    async def stop_replay(self) -> dict[str, Any]:
        """Stop replay and return to realtime mode."""
        result = await self._client.call_tool("replay_stop", {})
        self._replay_active = False
        return result

    # ------------------------------------------------------------------
    # Data reading
    # ------------------------------------------------------------------

    async def read_current_candle(self) -> CandleSnapshot:
        """Read the current candle from the replay position.

        Uses replay_status to obtain the authoritative current-bar timestamp,
        then locates the matching bar in OHLCV data.  This is necessary
        because for higher timeframes (5m+) TradingView loads all session
        bars at once, so bars.lastIndex() always points to the last bar of
        the day regardless of the replay cursor; using bars[-1] would always
        return the final bar.  For lower timeframes (2m and below) bars load
        incrementally and bars[-1] would also be correct, so the approach is
        safe for all timeframes.

        Raises ReplayControllerError if the candle cannot be read.
        """
        self._require_replay_active()

        # Step 1: get the replay cursor timestamp from the authoritative source.
        status = await self._client.call_tool("replay_status", {})
        _require_success(status, "replay_status")
        current_ts = status.get("current_date")  # unix seconds

        # Step 2: fetch a window of bars.
        # count=500 ensures we have enough context even for high timeframes.
        raw = await self._client.call_tool("data_get_ohlcv", {"count": 500, "summary": False})
        _require_success(raw, "data_get_ohlcv")

        bars = raw.get("bars")
        if not bars or len(bars) == 0:
            raise ReplayControllerError("No bars returned from data_get_ohlcv")

        # Step 3: find the bar whose period contains current_ts.
        # replay_status.current_date returns a timestamp near the END of the
        # current bar (bar.time + tf_seconds - 1), not the bar's open time.
        # Exact equality fails; instead find the bar where:
        #   bar.time <= current_ts < bar.time + tf_seconds
        bar: dict | None = None
        if current_ts is not None:
            tf_secs = _timeframe_to_seconds(self._timeframe)
            for b in bars:
                bar_start = b.get("time")
                if bar_start is not None and bar_start <= current_ts < bar_start + tf_secs:
                    bar = b
                    break

        if bar is None:
            first_bar_ts = bars[0].get("time", 0) if bars else 0
            if current_ts is not None and current_ts < first_bar_ts:
                # Cursor is in the pre-session gap (before the first available bar).
                # This happens after replay_start positions at midnight UTC of the date,
                # before any replay_step advances to bar 0.  Using bars[-1] here would
                # return the last bar of the day (session-end), causing the collection
                # loop to immediately stop.  bars[0] is the correct starting position.
                bar = bars[0]
                log.debug(
                    "Cursor ts=%d precedes first bar ts=%d; using bars[0]",
                    current_ts, first_bar_ts,
                )
            else:
                bar = bars[-1]
                if current_ts is not None:
                    log.warning(
                        "Bar containing ts=%d not found in OHLCV window (%d bars, tf=%ss); "
                        "using bars[-1] ts=%d",
                        current_ts, len(bars), self._timeframe, bar.get("time", -1),
                    )

        try:
            snapshot = CandleSnapshot(
                timestamp=int(bar["time"]),
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=float(bar.get("volume", 0)),
                symbol=self._symbol,
                timeframe=self._timeframe,
                replay_date=self._replay_date,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ReplayControllerError(f"Failed to build CandleSnapshot from bar {bar!r}: {exc}") from exc

        log.debug("Current candle: ts=%d O=%.2f H=%.2f L=%.2f C=%.2f V=%.0f",
                  snapshot.timestamp, snapshot.open, snapshot.high,
                  snapshot.low, snapshot.close, snapshot.volume)
        return snapshot

    async def read_indicator_values(self) -> dict[str, Any]:
        """Return raw indicator values currently visible on the chart.

        Values are returned as-is from TradingView — no interpretation,
        no transformation. The caller is responsible for any parsing.
        """
        self._require_replay_active()
        result = await self._client.call_tool("data_get_study_values", {})
        _require_success(result, "data_get_study_values")
        return result

    async def export_candle_snapshot(self, path: Path) -> Path:
        """Read the current candle and export it as a validated JSON file.

        Returns the Path the file was written to.
        """
        snapshot = await self.read_current_candle()
        out = export_snapshot(snapshot, path)
        log.info("Exported candle snapshot to %s", out)
        return out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _dismiss_replay_resume_dialog(self) -> None:
        """Click 'Start new' on TradingView's replay-resume dialog if it appears.

        The dialog is rendered asynchronously after replay_start initiates a new
        replay session.  We poll up to 3 times with 400 ms gaps (1.2 s total).
        Each attempt uses ui_click which throws if the button is not in the DOM —
        we catch and retry silently.
        """
        for attempt in range(1, 4):
            await asyncio.sleep(0.4)
            try:
                result = await self._client.call_tool(
                    "ui_click", {"by": "text", "value": "Start new"}
                )
                if result.get("success"):
                    log.info("Dismissed 'Continue your last replay?' dialog (attempt %d)", attempt)
                    await asyncio.sleep(0.3)  # let the dialog finish closing
                    return
            except Exception:
                pass  # button not in DOM yet — try again

    def _require_replay_active(self) -> None:
        if not self._replay_active:
            raise ReplayControllerError(
                "Replay is not active. Call load_trading_day() first."
            )

    @property
    def symbol(self) -> str | None:
        return self._symbol

    @property
    def timeframe(self) -> str | None:
        return self._timeframe

    @property
    def replay_date(self) -> str | None:
        return self._replay_date

    @property
    def is_replay_active(self) -> bool:
        return self._replay_active


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _require_success(result: Any, tool_name: str) -> None:
    """Raise TVClientError if the MCP tool result indicates failure."""
    if not isinstance(result, dict):
        raise TVClientError(f"{tool_name} returned unexpected type: {type(result)}")
    if not result.get("success", False):
        error = result.get("error", "unknown error")
        raise TVClientError(f"{tool_name} failed: {error}")


def _timeframe_to_seconds(timeframe: str | None) -> int:
    """Return the bar period in seconds for a given timeframe string."""
    if timeframe is None:
        return 60  # safe default
    tf = timeframe.upper()
    if tf == "D":
        return 86400
    try:
        return int(tf) * 60
    except ValueError:
        return 60


def _validate_date(date: str) -> None:
    import re
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ReplayControllerError(
            f"date must be YYYY-MM-DD format, got {date!r}"
        )
