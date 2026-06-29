"""Debug script: diagnose OHLCV + indicator data quality during TradingView replay.

Run from project root with TradingView Desktop open and replay active:
    python scripts/debug_ohlcv_replay.py [--ticker TSLA] [--date 2026-06-22]

Prerequisites:
    - TradingView Desktop open with CDP on port 9222
    - Symbol loaded: {ticker}
    - Replay mode active for {date}
    - At least one replay_step() already taken (so bars[-1] and bars[-2] both exist)

What this script probes:
    R1  data_get_raw_bar(offset=0) — full raw array of current bar (indices 0-15)
    R2  data_get_raw_bar(offset=1) — full raw array of previous (completed) bar
    Q   quote_get — current bar quote via bars.valueAt(lastIndex())
    S   data_get_study_values — all indicator data-window values (raw study payload)
    O   data_get_ohlcv (10 bars) — what the collector currently receives
    I   Indicator analysis: study names, all fields, KCU presence, candle-specificity

Writes full payload to outputs/debug/ohlcv_debug_<timestamp>.json.
Prints a clear diagnosis and fix recommendation to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.collector.tv_client import TradingViewClient

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "debug"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_BANNER = "=" * 70


async def main(ticker: str, date: str) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"ohlcv_debug_{timestamp}.json"

    print(_BANNER)
    print("OHLCV Replay Debug Probe")
    print(f"  Ticker : {ticker}    Date: {date}")
    print(f"  Output : {output_path}")
    print(_BANNER)
    print()

    payload: dict = {
        "debug_timestamp": timestamp,
        "ticker": ticker,
        "date": date,
        "probes": {},
        "diagnosis": {},
    }

    async with TradingViewClient() as client:

        # ── replay_status ──────────────────────────────────────────────────
        print("Checking replay status...")
        try:
            status = await client.call_tool("replay_status", {})
            payload["replay_status"] = status
            print(f"  is_replay_started : {status.get('is_replay_started')}")
            print(f"  current_date      : {status.get('current_date')}")
        except Exception as e:
            payload["replay_status"] = {"error": str(e)}
            print(f"  replay_status failed: {e}")
        print()

        # ── R1: raw bar array — current bar (offset=0) ─────────────────────
        print("R1: data_get_raw_bar(offset=0) — current bar raw indices...")
        try:
            r1 = await client.call_tool("data_get_raw_bar", {"bar_offset": 0})
            payload["probes"]["R1_current_bar"] = r1
            print(f"  bar_index    : {r1.get('bar_index')}")
            print(f"  array_length : {r1.get('array_length')}")
            print(f"  all_ohlc_equal : {r1.get('all_ohlc_equal')}")
            print(f"  raw_indices  : {r1.get('raw_indices')}")
            dw = r1.get("datawindow_items", [])
            if dw:
                print(f"  data_window  : {dw}")
            lt = r1.get("legend_text")
            if lt:
                print(f"  legend_text  : {lt}")
        except Exception as e:
            payload["probes"]["R1_current_bar"] = {"error": str(e)}
            print(f"  ERROR: {e}")
            print("  NOTE: Make sure the MCP server was restarted after adding data_get_raw_bar.")
        print()

        # ── R2: raw bar array — previous (completed) bar (offset=1) ───────
        print("R2: data_get_raw_bar(offset=1) — previous bar raw indices...")
        try:
            r2 = await client.call_tool("data_get_raw_bar", {"bar_offset": 1})
            payload["probes"]["R2_prev_bar"] = r2
            print(f"  bar_index    : {r2.get('bar_index')}")
            print(f"  all_ohlc_equal : {r2.get('all_ohlc_equal')}")
            print(f"  raw_indices  : {r2.get('raw_indices')}")
            dw = r2.get("datawindow_items", [])
            if dw:
                print(f"  data_window  : {dw}")
        except Exception as e:
            payload["probes"]["R2_prev_bar"] = {"error": str(e)}
            print(f"  ERROR: {e}")
        print()

        # ── Q: quote_get ───────────────────────────────────────────────────
        print("Q: quote_get — current bar via last-bar read...")
        try:
            q = await client.call_tool("quote_get", {})
            payload["probes"]["Q_quote_get"] = q
            print(f"  open={q.get('open')}  high={q.get('high')}  "
                  f"low={q.get('low')}  close={q.get('close')}  last={q.get('last')}")
            o, h, l, c = q.get("open"), q.get("high"), q.get("low"), q.get("close")
            if o is not None and o == h == l == c:
                print("  DEGENERATE: quote also has open=high=low=close")
            elif o is not None and not (o == h == l == c):
                print("  quote has real OHLC spread — quote_get may be a valid alternative")
        except Exception as e:
            payload["probes"]["Q_quote_get"] = {"error": str(e)}
            print(f"  ERROR: {e}")
        print()

        # ── O: data_get_ohlcv (collector path) ────────────────────────────
        print("O: data_get_ohlcv (10 bars) — what the collector currently reads...")
        try:
            ohlcv = await client.call_tool("data_get_ohlcv", {"count": 10, "summary": False})
            bars = ohlcv.get("bars", [])
            payload["probes"]["O_ohlcv"] = ohlcv
            print(f"  {len(bars)} bars returned")
            degenerate = sum(
                1 for b in bars
                if b.get("open") == b.get("high") == b.get("low") == b.get("close")
            )
            print(f"  Degenerate bars (O=H=L=C): {degenerate}/{len(bars)}")
            for b in bars[-3:]:
                deg = "*" if b.get("open") == b.get("high") == b.get("low") == b.get("close") else " "
                print(f"  {deg} ts={b.get('time')}  O={b.get('open')}  H={b.get('high')}  "
                      f"L={b.get('low')}  C={b.get('close')}  V={b.get('volume')}")
        except Exception as e:
            payload["probes"]["O_ohlcv"] = {"error": str(e)}
            print(f"  ERROR: {e}")
        print()

        # ── S: data_get_study_values — full raw indicator payload ──────────
        print("S: data_get_study_values — raw study payload + indicator analysis...")
        try:
            sv = await client.call_tool("data_get_study_values", {})
            payload["probes"]["S_study_values"] = sv
            studies = sv.get("studies", [])
            print(f"  {len(studies)} studies in data window")

            # Print every study: name + all fields
            for s in studies:
                name = s.get("name", "?")
                values = s.get("values", {})
                print(f"\n  Study: [{name}]")
                for k, v in values.items():
                    print(f"    {k}: {v!r}")

            # Check if any study has O/H/L/C values by key name
            ohlcv_studies = [
                s for s in studies
                if any(k in ("O", "H", "L", "C", "Open", "High", "Low", "Close")
                       for k in (s.get("values") or {}).keys())
            ]
            if ohlcv_studies:
                print(f"\n  FOUND studies with O/H/L/C keys: {[s.get('name') for s in ohlcv_studies]}")
                payload["probes"]["ohlcv_in_study_values"] = ohlcv_studies

            # KCU indicator analysis
            kcu_studies = [s for s in studies if "kcu" in s.get("name", "").lower()]
            if kcu_studies:
                print(f"\n  KCU studies found ({len(kcu_studies)}):")
                for ks in kcu_studies:
                    print(f"    {ks.get('name')}: {ks.get('values')}")
                payload["probes"]["kcu_studies"] = kcu_studies
            else:
                print("\n  WARNING: No KCU study found in data window.")
                print("  Ensure KCU indicator is visible on the TradingView chart.")

            # Candle-specificity probe: compare current bar values vs previous position
            # (cannot do this automatically — documents the limitation)
            payload["probes"]["candle_specificity_note"] = (
                "To verify candle-specificity: call this script twice at different "
                "replay positions and compare S_study_values.studies.values. "
                "If the values change between positions, they are candle-specific."
            )

        except Exception as e:
            payload["probes"]["S_study_values"] = {"error": str(e)}
            print(f"  ERROR: {e}")
        print()

        # ── Diagnosis ──────────────────────────────────────────────────────
        print(_BANNER)
        print("DIAGNOSIS")
        print(_BANNER)

        ohlcv_bars = payload.get("probes", {}).get("O_ohlcv", {}).get("bars", [])
        degenerate_count = sum(
            1 for b in ohlcv_bars
            if b.get("open") == b.get("high") == b.get("low") == b.get("close")
        )
        total = len(ohlcv_bars)

        r1_data = payload.get("probes", {}).get("R1_current_bar", {})
        r2_data = payload.get("probes", {}).get("R2_prev_bar", {})
        q_data = payload.get("probes", {}).get("Q_quote_get", {})

        diag = {}

        # Check raw array
        if r1_data.get("all_ohlc_equal") is True:
            diag["raw_bar_degenerate"] = True
            print("  CONFIRMED: bars.valueAt(i) has v[1]=v[2]=v[3]=v[4] (all equal to close).")
            print("  Root cause: TradingView replay stores bars as tick-level data,")
            print("  not full OHLCV candles, in the mainSeries bars() series.")
        elif r1_data.get("raw_indices"):
            print(f"  Raw indices: {r1_data['raw_indices']}")
            v = r1_data["raw_indices"]
            if v.get("1") != v.get("4"):
                print("  OHLCV IS PRESENT in raw indices — mapping may be wrong.")
                diag["raw_bar_has_ohlcv"] = True

        # Check data window items
        dw_items = r1_data.get("datawindow_items", []) or r2_data.get("datawindow_items", [])
        ohlcv_in_dw = [item for item in dw_items
                       if item.get("title") in ("O", "H", "L", "C", "Open", "High", "Low", "Close")]
        if ohlcv_in_dw:
            diag["ohlcv_in_datawindow"] = True
            print()
            print("  GOOD NEWS: dataWindowView() items contain O/H/L/C values:")
            for item in ohlcv_in_dw:
                print(f"    {item.get('title')}: {item.get('value')}")
            print()
            print("  FIX: Update getOhlcv() in core/data.js to read O/H/L/C/V from")
            print("  mainSeries().dataWindowView().items() instead of bars.valueAt().")
        else:
            print("  Data window items do NOT contain O/H/L/C labels.")

        # Check quote_get
        qo, qh, ql, qc = q_data.get("open"), q_data.get("high"), q_data.get("low"), q_data.get("close")
        if qo is not None and not (qo == qh == ql == qc):
            diag["quote_get_has_real_ohlcv"] = True
            print()
            print("  GOOD NEWS: quote_get returns real OHLCV (O≠H≠L≠C).")
            print("  FIX: In replay_controller.read_current_candle(), call quote_get")
            print("  instead of data_get_ohlcv to get real OHLCV for the current bar.")

        # Check legend text
        lt = r1_data.get("legend_text") or r2_data.get("legend_text")
        if lt and "error" not in str(lt):
            diag["legend_text_found"] = True
            print()
            print(f"  Chart legend/header text found: {lt}")
            print("  FIX (fallback): Parse O/H/L/C from the chart legend DOM.")

        # Check prev bar
        if r2_data.get("all_ohlc_equal") is False:
            diag["prev_bar_has_real_ohlcv"] = True
            print()
            print("  Previous bar (offset=1) has real OHLCV spread.")
            print("  FIX: Read bars[-2] (completed bar) instead of bars[-1] (forming bar).")
            print("  This introduces a 1-bar lag — only valid if replay is bar-accurate.")

        if not diag:
            print("  No alternative OHLCV source found.")
            print("  LIMITATION: The MCP server can only expose close-only OHLCV during replay.")
            print("  PROPOSED: Add a Pine Script indicator that plots O/H/L/C/V via")
            print("  label.new() or table.new() and read via data_get_pine_labels/tables.")
            diag["confirmed_mcp_limitation"] = True

        payload["diagnosis"] = diag

    output_path.write_text(json.dumps(payload, indent=2, default=str))
    print()
    print(f"Full debug payload: {output_path}")
    print()
    print("After identifying the fix, run re-collection:")
    print(f"  python scripts/run_collection.py --ticker {ticker} --date {date}")
    print()
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OHLCV replay diagnostic probe")
    parser.add_argument("--ticker", default="TSLA")
    parser.add_argument("--date", default="2026-06-22")
    args = parser.parse_args()
    asyncio.run(main(ticker=args.ticker, date=args.date))
