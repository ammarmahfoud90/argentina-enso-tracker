"""Fetch fresh NOAA CPC ENSO index files and overwrite stale local copies.

Designed to be called by the GitHub Actions workflow at
.github/workflows/refresh-noaa-data.yml, but also runnable locally:

    python -m scripts.refresh_noaa_data

Exit codes
----------
0  Every source was processed successfully (some may have been unchanged).
1  At least one source could not be fetched or could not be parsed; partial
   updates may have been written.  A parse error is a failure like any other:
   a file whose freshness cannot be checked is a file that quietly stops
   being refreshed, which is exactly how data/raw/soi.txt froze at May 2026.

GitHub Actions integration
--------------------------
When the environment variable ``GITHUB_OUTPUT`` is set (always true inside
Actions), the script appends a ``changed_sources`` output variable so the
workflow step knows whether to create a commit:

    changed_sources=ONI,SOI          # one or more updated
    changed_sources=                 # empty string → nothing changed
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as `python -m scripts.refresh_noaa_data` from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import NOAA_ONI_URL, NOAA_RONI_URL, NOAA_NINO34_URL, NOAA_SOI_URL
from src.fetch_enso import parse_soi
from src.utils import check_noaa_data_freshness, fetch_text, get_logger

logger = get_logger(__name__)


def _soi_last_period(raw_text: str) -> tuple[int, int]:
    """Return the latest ``(year, month)`` of a CPC SOI payload.

    The generic row scanner in :func:`src.utils._parse_last_period` cannot
    read this file: each row carries twelve monthly values, and the year runs
    into the first value when that value is wide (``2030-999.9-999.9...``).
    So this delegates to :func:`src.fetch_enso.parse_soi`, the same parser the
    build uses, instead of keeping a second SOI reader that can drift from it.
    ``parse_soi`` already drops the ``-999.9`` placeholders, so the result is
    the last month that actually carries an observation.

    Args:
        raw_text: Raw content of the CPC SOI file.

    Returns:
        ``(year, month)`` of the newest observation.

    Raises:
        ValueError: If no valid SOI rows can be parsed.
    """
    frame = parse_soi(raw_text)
    if frame.empty:
        raise ValueError("No valid SOI rows found in the provided text.")
    latest = frame["date"].iloc[-1]
    return int(latest.year), int(latest.month)

# ---------------------------------------------------------------------------
# Source registry
# Each entry maps a human label to its URL and the local path where the
# raw ASCII file is persisted.  Paths are relative to the project root so
# git add uses the same paths in the workflow.
# ---------------------------------------------------------------------------

RAW_DIR = Path("data/raw")

SOURCES: list[dict] = [
    {
        "label": "ONI",
        "url": NOAA_ONI_URL,
        "local_path": RAW_DIR / "oni.ascii.txt",
        "description": "Oceanic Niño Index — 3-month running mean of Niño 3.4 SST anomalies",
    },
    {
        "label": "Nino34",
        "url": NOAA_NINO34_URL,
        "local_path": RAW_DIR / "nino34.ascii.txt",
        "description": "Monthly Niño 3.4 SST anomalies (ERSSTv6, input to the ONI)",
    },
    {
        "label": "SOI",
        "url": NOAA_SOI_URL,
        "local_path": RAW_DIR / "soi.txt",
        "description": "Southern Oscillation Index — Tahiti minus Darwin SLP",
        "period_parser": _soi_last_period,
    },
    {
        "label": "RONI",
        "url": NOAA_RONI_URL,
        "local_path": RAW_DIR / "roni.ascii.txt",
        "description": "Relative Oceanic Niño Index — NOAA's operational monitoring index",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_github_output(key: str, value: str) -> None:
    """Append key=value to $GITHUB_OUTPUT when running inside Actions."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")
        logger.info("GitHub Actions output → %s=%s", key, value)


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


# ---------------------------------------------------------------------------
# Main refresh logic
# ---------------------------------------------------------------------------

def refresh_all() -> tuple[list[str], list[str]]:
    """Fetch, compare, and conditionally overwrite each NOAA source file.

    Returns
    -------
    tuple[list[str], list[str]]
        ``(changed, failed)``: labels of the sources whose local files were
        updated, and labels of the sources that could not be fetched or
        parsed.  An empty *changed* means everything was already current; a
        non-empty *failed* must make the run fail.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []
    fetch_errors: list[str] = []

    for source in SOURCES:
        label = source["label"]
        url = source["url"]
        local_path: Path = source["local_path"]

        _section(f"{label}  —  {source['description']}")
        print(f"  URL        : {url}")
        print(f"  Local file : {local_path}")

        # ── 1. Fetch live data ─────────────────────────────────────────────
        print(f"\n  [FETCH] Contacting NOAA CPC...")
        try:
            live_text = fetch_text(url, label=label, timeout=30)
        except RuntimeError as exc:
            print(f"  [FAIL]  Network error: {exc}")
            logger.error("Could not fetch %s: %s", label, exc)
            fetch_errors.append(label)
            continue

        print(f"  [FETCH] Received {len(live_text):,} bytes")

        # ── 2. First-time bootstrap: no local file yet ─────────────────────
        if not local_path.exists():
            print(f"  [NEW]   No local file found — writing fresh copy.")
            local_path.write_text(live_text, encoding="utf-8")
            changed.append(label)
            print(f"  [SAVED] {local_path}  (first-time bootstrap)")
            continue

        # ── 3. Freshness check against existing local file ─────────────────
        print(f"\n  [CHECK] Running freshness comparison...")
        try:
            report = check_noaa_data_freshness(
                local_path, live_text, period_parser=source.get("period_parser")
            )
        except ValueError as exc:
            # Parser could not find data rows — do not overwrite with
            # possibly corrupt data, and do not let the run pass either: a
            # file that cannot be checked quietly stops being refreshed.
            print(f"  [FAIL]  Parser error during freshness check: {exc}")
            logger.error("Parser failed for %s: %s", label, exc)
            fetch_errors.append(label)
            continue

        # Print every field so the Actions log is a permanent audit trail.
        local_yr, local_mo = report.local_last_period
        remote_yr, remote_mo = report.remote_last_period
        print(f"  local_last_period   : {local_yr}-{local_mo:02d}")
        print(f"  remote_last_period  : {remote_yr}-{remote_mo:02d}")
        print(f"  period_delta_months : {report.period_delta_months:+d}")
        print(f"  days_since_write    : {report.days_since_write}d")
        print(f"  is_current          : {report.is_current}")
        print(f"  is_stale_by_age     : {report.is_stale_by_age}")
        print(f"  status              : {report.status}")
        print(f"  message             : {report.message}")

        # ── 4. Overwrite only when the remote has newer data ───────────────
        if report.status == "STALE" and report.period_delta_months > 0:
            local_path.write_text(live_text, encoding="utf-8")
            changed.append(label)
            print(f"\n  [UPDATED] Overwrote {local_path} with {remote_yr}-{remote_mo:02d} data.")
        elif report.status == "CURRENT":
            print(f"\n  [OK]    Local file is current — no write needed.")
        else:
            # Stale by age only, or remote is behind local (unusual).
            # Log it but do not overwrite; the commit step will be skipped.
            print(f"\n  [SKIP]  Status is {report.status!r} but delta={report.period_delta_months:+d}. "
                  f"No overwrite — see message above.")

    return changed, fetch_errors


def main() -> None:
    print("\n" + "=" * 60)
    print("  NOAA ENSO Data Refresh")
    print("=" * 60)

    changed, failed = refresh_all()

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if changed:
        print(f"  UPDATED : {', '.join(changed)}")
    else:
        print("  No sources updated — all local files are current.")
    if failed:
        print(f"  FAILED  : {', '.join(failed)}")
        print("  A source that cannot be fetched or parsed stops being")
        print("  refreshed, so this run is a failure.")
        for label in failed:
            print(f"::error::Refresh failed for {label}")
    print("=" * 60 + "\n")

    # ── Emit GitHub Actions output ─────────────────────────────────────────
    # The workflow reads `changed_sources` to decide whether to git-commit.
    # An empty value means "nothing to commit".
    _write_github_output("changed_sources", ",".join(changed))
    _write_github_output("failed_sources", ",".join(failed))

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
