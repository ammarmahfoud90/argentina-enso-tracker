"""Diagnostic script: validate check_noaa_data_freshness against live NOAA data.

Run from the project root:
    python -m scripts.test_freshness_check

Tests three scenarios per source:
  1. CURRENT  — local file identical to live fetch  → delta=0, status=CURRENT
  2. STALE    — local file missing the last 2 data rows → delta>0, status=STALE
  3. PARSER   — prints the raw parsed period from live text (format sanity check)
"""

from __future__ import annotations

import sys
import textwrap
import tempfile
from pathlib import Path

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import NOAA_ONI_URL, NOAA_NINO34_URL, NOAA_SOI_URL
from src.utils import (
    fetch_text,
    check_noaa_data_freshness,
    _parse_last_period,   # private but fine for diagnostics
    FreshnessReport,
)

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

SOURCES = [
    {
        "name": "ONI (Oceanic Niño Index)",
        "url": NOAA_ONI_URL,
        "format": "seasonal",   # "DJF  2025  -0.3 ..."
        "note": "3-month running mean; rows are season codes, not integers",
    },
    {
        "name": "Niño 3.4 Monthly",
        "url": NOAA_NINO34_URL,
        "format": "monthly",    # "2025  5  28.32  0.51 ..."
        "note": "Monthly SST anomalies; rows start with YR MON",
    },
    {
        "name": "SOI (Southern Oscillation Index)",
        "url": NOAA_SOI_URL,
        "format": "monthly",    # "2025  5  ..."
        "note": "Monthly SLP anomaly index; rows start with YR MON",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "─" * 68


def _strip_last_n_data_rows(text: str, n: int = 2) -> str:
    """Return *text* with the last *n* non-empty, non-comment rows removed.

    Used to simulate a local file that is a few months behind the live source.
    """
    lines = text.splitlines()
    removed = 0
    result = list(lines)
    for i in range(len(result) - 1, -1, -1):
        stripped = result[i].strip()
        if stripped and not stripped.startswith("#"):
            result.pop(i)
            removed += 1
            if removed >= n:
                break
    return "\n".join(result)


def _fmt_period(period: tuple[int, int]) -> str:
    year, month = period
    month_name = [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][month]
    return f"{month_name} {year}  ({year}-{month:02d})"


def _print_report(label: str, report: FreshnessReport) -> None:
    status_icon = "OK " if report.status == "CURRENT" else "!!!"
    print(f"  [{status_icon}] {label}")
    print(f"        local_last_period  : {_fmt_period(report.local_last_period)}")
    print(f"        remote_last_period : {_fmt_period(report.remote_last_period)}")
    print(f"        period_delta_months: {report.period_delta_months:+d}")
    print(f"        days_since_write   : {report.days_since_write}d")
    print(f"        is_current         : {report.is_current}")
    print(f"        is_stale_by_age    : {report.is_stale_by_age}")
    print(f"        status             : {report.status}")
    print(f"        message            : {textwrap.fill(report.message, width=56, subsequent_indent=' ' * 26)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    all_passed = True

    for source in SOURCES:
        print()
        print(SEP)
        print(f"  SOURCE : {source['name']}")
        print(f"  FORMAT : {source['format']}  |  {source['note']}")
        print(f"  URL    : {source['url']}")
        print(SEP)

        # --- 1. Fetch live data ---
        print("\n  [FETCH] Contacting NOAA CPC...")
        try:
            live_text = fetch_text(source["url"], label=source["name"], timeout=30)
        except RuntimeError as exc:
            print(f"  [FAIL]  Could not fetch: {exc}")
            all_passed = False
            continue
        print(f"  [FETCH] Received {len(live_text):,} bytes")

        # --- 2. Parser sanity check (format probe) ---
        print("\n  [PARSER CHECK]")
        try:
            remote_period = _parse_last_period(live_text)
            print(f"  [OK ] _parse_last_period → {_fmt_period(remote_period)}")
        except ValueError as exc:
            print(f"  [FAIL] Parser error: {exc}")
            print("         First 5 data lines of response:")
            for line in live_text.splitlines():
                if line.strip() and not line.strip().startswith("#"):
                    print(f"           {line!r}")
            all_passed = False
            continue

        # --- 3. Scenario A: CURRENT (local == live) ---
        print("\n  [SCENARIO A] local file == live fetch  →  expect CURRENT, delta=0")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(live_text)
            tmp_current = Path(f.name)

        try:
            report_a = check_noaa_data_freshness(tmp_current, live_text)
            _print_report("Scenario A", report_a)
            if report_a.status != "CURRENT" or report_a.period_delta_months != 0:
                print("  [WARN] Expected CURRENT / delta=0 but got different result")
                all_passed = False
        finally:
            tmp_current.unlink(missing_ok=True)

        # --- 4. Scenario B: STALE (local missing last 2 rows) ---
        print("\n  [SCENARIO B] local file missing last 2 rows  →  expect STALE, delta>0")
        stale_text = _strip_last_n_data_rows(live_text, n=2)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(stale_text)
            tmp_stale = Path(f.name)

        try:
            report_b = check_noaa_data_freshness(tmp_stale, live_text)
            _print_report("Scenario B", report_b)
            if report_b.status != "STALE" or report_b.period_delta_months <= 0:
                print("  [WARN] Expected STALE / delta>0 but got different result")
                all_passed = False
        except ValueError as exc:
            print(f"  [FAIL] Parser failed on truncated file: {exc}")
            all_passed = False
        finally:
            tmp_stale.unlink(missing_ok=True)

    # --- Summary ---
    print()
    print(SEP)
    if all_passed:
        print("  RESULT: ALL CHECKS PASSED — parser and freshness logic are correct.")
    else:
        print("  RESULT: ONE OR MORE CHECKS FAILED — review output above.")
    print(SEP)
    print()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
