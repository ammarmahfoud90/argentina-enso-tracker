"""Fetch and parse the SAM/AAO monthly index from NOAA CPC.

The Antarctic Oscillation (AAO), also known as the Southern Annular Mode (SAM),
is the dominant mode of atmospheric variability south of 20S. Positive SAM
is associated with drier conditions in Patagonia and wetter conditions in the
subtropics.

Data source: NOAA CPC monthly AAO index, 1979-present.
Format: fixed-width ASCII table with year + 12 monthly values.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from src.config import NOAA_AAO_URL
from src.utils import fetch_text, get_logger

logger = get_logger(__name__)


def parse_aao(raw_text: str) -> pd.DataFrame:
    """Parse the NOAA CPC AAO monthly ASCII table.

    The format has one row per year with the year followed by 12 monthly
    values separated by whitespace. Missing values are typically very
    large negative numbers (e.g., -99.99 or -999).

    Returns:
        DataFrame with columns: date (datetime64), sam (float).
    """
    records = []
    for line in raw_text.strip().splitlines():
        parts = line.split()
        if len(parts) < 13:
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        if year < 1900 or year > 2100:
            continue

        for month_idx, val_str in enumerate(parts[1:13], start=1):
            try:
                val = float(val_str)
            except ValueError:
                continue
            # Skip missing values
            if val < -90:
                continue
            dt = date(year, month_idx, 15)
            records.append({"date": pd.Timestamp(dt), "sam": round(val, 2)})

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("No valid AAO/SAM data parsed from CPC ASCII")
    df = df.sort_values("date").reset_index(drop=True)
    logger.info("Parsed AAO/SAM: %d records (%s to %s)",
                len(df), df.iloc[0]["date"].date(), df.iloc[-1]["date"].date())
    return df


def fetch_sam_series() -> tuple[pd.DataFrame, float, date]:
    """Fetch AAO/SAM monthly series from NOAA CPC.

    Returns:
        (sam_df, latest_value, latest_date)
    """
    raw = fetch_text(NOAA_AAO_URL, label="NOAA AAO/SAM")
    df = parse_aao(raw)
    latest = df.iloc[-1]
    return df, float(latest["sam"]), latest["date"].date()
