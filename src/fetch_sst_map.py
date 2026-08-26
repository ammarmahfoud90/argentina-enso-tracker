"""Fetch OISST v2.1 SST anomaly grid for the equatorial Pacific.

Produces a time-series of 2D grids (lat x lon) of SST anomalies for the last
~12 months, used to render an interactive Plotly heatmap with Nino region
overlays and a time slider.

Data source: NOAA OISST v2.1 via ERDDAP (ncdcOisst21Agg).
Anomalies are relative to the 1991-2020 climatological baseline.
Spatial resolution downsampled to ~2 degrees for performance.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.utils import fetch_text, get_logger

logger = get_logger(__name__)

# ERDDAP dataset for OISST v2.1 (0-360 longitude convention)
_OISST_DATASET = "ncdcOisst21Agg"
_ERDDAP_BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"

# Spatial bounds: equatorial Pacific
_LAT_MIN, _LAT_MAX = -20.0, 20.0
_LON_MIN, _LON_MAX = 120.0, 290.0  # 120E to 70W in 0-360 convention
_SPATIAL_STRIDE = 8  # every 8th point on 0.25 grid = ~2 degree resolution
_TIME_STRIDE = 30  # every 30th day = ~monthly snapshots from daily data

# Nino monitoring regions (0-360 longitude convention)
NINO_BOXES = [
    {"name": "Nino 4",   "lon0": 160, "lon1": 210, "lat0": -5, "lat1": 5},
    {"name": "Nino 3.4", "lon0": 190, "lon1": 240, "lat0": -5, "lat1": 5},
    {"name": "Nino 3",   "lon0": 210, "lon1": 270, "lat0": -5, "lat1": 5},
    {"name": "Nino 1+2", "lon0": 270, "lon1": 280, "lat0": -10, "lat1": 0},
]


def _lon_label(lon_e: float) -> str:
    """Convert 0-360 longitude to human-readable label."""
    if lon_e == 180:
        return "180"
    if lon_e < 180:
        return f"{lon_e:.0f}E"
    return f"{360 - lon_e:.0f}W"


def fetch_sst_map(months: int = 12) -> dict | None:
    """Fetch OISST v2.1 anomaly grids for the equatorial Pacific.

    Returns dict with keys:
        times:      list of ISO date strings (one per monthly snapshot)
        lats:       list of float (latitude values)
        lons:       list of float (longitude values, 0-360)
        lon_labels: list of str (human-readable longitude labels)
        grids:      list of 2D arrays [time_idx][lat_idx][lon_idx]
        nino_boxes: list of dicts with Nino region coordinates
        source:     str
        baseline:   str
    Returns None if data is unavailable.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30 * months)

    # Use ERDDAP's "last" keyword for the end bound to avoid 404 when
    # requesting dates beyond the dataset's actual last timestamp.
    url = (
        f"{_ERDDAP_BASE}/{_OISST_DATASET}.csv"
        f"?anom"
        f"[({start.strftime('%Y-%m-%dT00:00:00Z')}):{_TIME_STRIDE}:"
        f"(last)]"
        f"[(0.0):1:(0.0)]"  # zlev = 0 (surface)
        f"[({_LAT_MIN}):{_SPATIAL_STRIDE}:({_LAT_MAX})]"
        f"[({_LON_MIN}):{_SPATIAL_STRIDE}:({_LON_MAX})]"
    )

    logger.info("Fetching OISST v2.1 SST anomaly map (%d months)...", months)

    try:
        raw = fetch_text(url, label="OISST SST map", timeout=90)
    except Exception as exc:
        logger.warning("OISST fetch failed: %s", exc)
        return None

    if not raw or len(raw) < 100:
        logger.warning("OISST response too short")
        return None

    # Parse ERDDAP CSV (line 1 = headers, line 2 = units, rest = data)
    lines = raw.strip().splitlines()
    if len(lines) < 3:
        logger.warning("OISST CSV too short: %d lines", len(lines))
        return None

    header = lines[0]
    data_csv = "\n".join([header] + lines[2:])

    try:
        df = pd.read_csv(io.StringIO(data_csv))
    except Exception as exc:
        logger.warning("Failed to parse OISST CSV: %s", exc)
        return None

    # Identify columns — ERDDAP may use 'zlev' or 'altitude'
    anom_col = "anom"
    if anom_col not in df.columns:
        logger.warning("OISST CSV missing 'anom' column. Columns: %s", list(df.columns))
        return None

    df["time_date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
    df[anom_col] = pd.to_numeric(df[anom_col], errors="coerce")

    times = sorted(df["time_date"].unique())
    lats = sorted(df["latitude"].unique())
    lons = sorted(df["longitude"].unique())

    logger.info(
        "OISST parsed: %d time steps, %d lats, %d lons, %d total rows",
        len(times), len(lats), len(lons), len(df),
    )

    if len(times) == 0 or len(lats) < 5 or len(lons) < 10:
        logger.warning("Insufficient OISST data dimensions")
        return None

    # Build 3D array: grids[time_idx][lat_idx][lon_idx]
    lat_idx = {lat: i for i, lat in enumerate(lats)}
    lon_idx = {lon: i for i, lon in enumerate(lons)}

    grids = []
    for t in times:
        grid = [[None] * len(lons) for _ in range(len(lats))]
        t_df = df[df["time_date"] == t]
        for _, row in t_df.iterrows():
            li = lat_idx.get(row["latitude"])
            lj = lon_idx.get(row["longitude"])
            v = row[anom_col]
            if li is not None and lj is not None and pd.notna(v):
                grid[li][lj] = round(float(v), 2)
        grids.append(grid)

    lon_labels = [_lon_label(lon) for lon in lons]

    result = {
        "times": times,
        "lats": [round(float(lat), 2) for lat in lats],
        "lons": [round(float(lon), 2) for lon in lons],
        "lon_labels": lon_labels,
        "grids": grids,
        "nino_boxes": NINO_BOXES,
        "source": "NOAA OISST v2.1 (ERDDAP ncdcOisst21Agg)",
        "baseline": "1991-2020",
    }

    logger.info(
        "SST map ready: %d snapshots, grid %dx%d, period %s to %s",
        len(times), len(lats), len(lons), times[0], times[-1],
    )
    return result
