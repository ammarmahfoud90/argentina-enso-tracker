"""Fetch fresh NOAA CPC ENSO index files and overwrite stale local copies.

Designed to be called by the GitHub Actions workflow at
.github/workflows/refresh-noaa-data.yml, but also runnable locally:

    python -m scripts.refresh_noaa_data

Exit codes
----------
0  All sources processed successfully (some may have been unchanged).
1  At least one network fetch failed; partial updates may have been written.

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

from src.config import NOAA_ONI_URL, NOAA_NINO34_URL, NOAA_SOI_URL
from src.utils import check_noaa_data_freshness, fetch_text, get_logger

logger = get_logger(__name__)

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
        "description": "Monthly Niño 3.4 SST anomalies (ERSSTv5, base 1991-2020)",
    },
    {
        "label": "SOI",
        "url": NOAA_SOI_URL,
        "local_path": RAW_DIR / "soi.txt",
        "description": "Southern Oscillation Index — Tahiti minus Darwin SLP",
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

def refresh_all() -> list[str]:
    """Fetch, compare, and conditionally overwrite each NOAA source file.

    Returns
    -------
    list[str]
        Labels of sources whose local files were updated (e.g. ["ONI", "SOI"]).
        Empty list means everything was already current.
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
            report = check_noaa_data_freshness(local_path, live_text)
        except ValueError as exc:
            # Parser could not find data rows — log and skip rather than
            # silently overwriting with potentially corrupt data.
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

    return changed


def main() -> None:
    print("\n" + "=" * 60)
    print("  NOAA ENSO Data Refresh")
    print("=" * 60)

    changed = refresh_all()
    had_errors = any(
        s["label"] not in [c for c in changed]
        and not Path(s["local_path"]).exists()
        for s in SOURCES
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if changed:
        print(f"  UPDATED : {', '.join(changed)}")
    else:
        print("  No sources updated — all local files are current.")
    print("=" * 60 + "\n")

    # ── Emit GitHub Actions output ─────────────────────────────────────────
    # The workflow reads `changed_sources` to decide whether to git-commit.
    # An empty value means "nothing to commit".
    _write_github_output("changed_sources", ",".join(changed))

    sys.exit(1 if had_errors else 0)


if __name__ == "__main__":
    main()
