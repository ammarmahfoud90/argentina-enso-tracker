"""Fetch equatorial Pacific subsurface temperature from TAO/TRITON buoys (ERDDAP).

Produces a longitude x depth cross-section of the equatorial Pacific,
which is a key diagnostic for ENSO state — the thermocline tilt reveals
whether warm water is building (El Nino precursor) or shoaling (La Nina).

Data source: PMEL TAO/TRITON monthly temperature (pmelTaoMonT) via ERDDAP.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from src.config import (
    TAO_ERDDAP_URL,
    TAO_RECENT_MONTHS,
    TAO_TARGET_DEPTHS,
)
from src.utils import fetch_text, get_logger

logger = get_logger(__name__)


def _lon_to_display(lon_e: float) -> str:
    """Convert longitude in degrees East to display label.

    165 -> '165°E', 180 -> '180°', 190 -> '170°W', 265 -> '95°W'
    """
    if lon_e == 180:
        return "180°"
    if lon_e < 180:
        return f"{int(lon_e)}°E"
    return f"{int(360 - lon_e)}°W"


def fetch_subsurface_cross_section() -> dict | None:
    """Fetch and process TAO subsurface temperature into a lon x depth grid.

    Returns:
        Dict with keys: longitudes, depths, temperatures (2D list),
        lon_labels, period_start, period_end, source.
        Returns None if data is unavailable.
    """
    # Build URL with time filter for recent months
    now = datetime.utcnow()
    start = now - timedelta(days=TAO_RECENT_MONTHS * 31 + 15)
    time_filter = f"&time>={start.strftime('%Y-%m-%d')}"
    url = TAO_ERDDAP_URL + time_filter

    try:
        raw = fetch_text(url, label="TAO subsurface", timeout=60)
    except Exception as exc:
        logger.warning("Failed to fetch TAO subsurface data: %s", exc)
        return None

    # Parse ERDDAP CSV (2 header rows: names + units)
    lines = raw.strip().splitlines()
    if len(lines) < 3:
        logger.warning("TAO CSV too short (%d lines)", len(lines))
        return None

    header = lines[0]
    data_lines = [header] + lines[2:]
    csv_clean = "\n".join(data_lines)

    try:
        df = pd.read_csv(io.StringIO(csv_clean))
    except Exception as exc:
        logger.warning("Failed to parse TAO CSV: %s", exc)
        return None

    if df.empty or "T_20" not in df.columns:
        logger.warning("TAO data empty or missing T_20 column")
        return None

    df["time"] = pd.to_datetime(df["time"])
    df = df.dropna(subset=["T_20"])

    if df.empty:
        logger.warning("All TAO temperature values are NaN")
        return None

    # Filter to Pacific equatorial stations only (exclude Atlantic buoys)
    df = df[(df["longitude"] >= 140) & (df["longitude"] <= 280)].copy()

    # Get available longitudes and sort them
    longitudes = sorted(df["longitude"].unique())
    logger.info("TAO longitudes: %s", longitudes)

    # Average across the most recent months to fill gaps
    avg = df.groupby(["longitude", "depth"])["T_20"].mean().reset_index()

    # Find depths that have good coverage — present at most longitudes
    depth_coverage = avg.groupby("depth")["longitude"].nunique()
    min_coverage = max(1, len(longitudes) // 2)
    good_depths = sorted(depth_coverage[depth_coverage >= min_coverage].index)
    logger.info("Depths with good coverage (>=%d lons): %s", min_coverage, good_depths)

    # Prefer target depths, but fall back to whatever is available
    target = set(TAO_TARGET_DEPTHS)
    selected_depths = sorted(d for d in good_depths if d in target)
    if len(selected_depths) < 5:
        # Not enough target depths — use all well-covered depths
        selected_depths = good_depths[:15]
    logger.info("Selected depths: %s", selected_depths)

    if not selected_depths or not longitudes:
        logger.warning("Insufficient data for subsurface cross-section")
        return None

    # Build 2D temperature grid: depths (rows) x longitudes (cols)
    temperatures = []
    for depth in selected_depths:
        row = []
        for lon in longitudes:
            val = avg[(avg["longitude"] == lon) & (avg["depth"] == depth)]["T_20"]
            if len(val) > 0:
                row.append(round(float(val.iloc[0]), 2))
            else:
                row.append(None)
        temperatures.append(row)

    # Period info
    period_start = df["time"].min().strftime("%Y-%m-%d")
    period_end = df["time"].max().strftime("%Y-%m-%d")

    result = {
        "longitudes": [float(lon) for lon in longitudes],
        "lon_labels": [_lon_to_display(lon) for lon in longitudes],
        "depths": [float(d) for d in selected_depths],
        "temperatures": temperatures,
        "period_start": period_start,
        "period_end": period_end,
        "source": "TAO/TRITON ERDDAP (pmelTaoMonT)",
    }

    logger.info(
        "Subsurface cross-section: %d lons x %d depths, period %s to %s",
        len(longitudes), len(selected_depths), period_start, period_end,
    )
    return result
