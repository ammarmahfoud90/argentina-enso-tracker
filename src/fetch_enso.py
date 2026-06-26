"""Fetch and parse ENSO indices from NOAA CPC.

Indices retrieved:
- ONI (Oceanic Niño Index) — 3-month running mean of Niño 3.4 SST anomalies
- Niño 3.4 SST anomaly — monthly values from ERSSTv5
- SOI (Southern Oscillation Index) — Tahiti minus Darwin SLP difference

Sources:
    ONI:    https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
    Niño:   https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii
    SOI:    https://www.cpc.ncep.noaa.gov/data/indices/soi
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.config import (
    ENSO_CONSECUTIVE_MONTHS,
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    NOAA_NINO34_URL,
    NOAA_ONI_URL,
    NOAA_SOI_URL,
)
from src.utils import fetch_text, get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class ENSOSnapshot:
    """Current-state snapshot of ENSO indices.

    Attributes:
        oni_value: Latest ONI value (°C anomaly).
        oni_season: Season label (e.g. "DJF") for the latest ONI entry.
        oni_date: Approximate calendar date of the last ONI entry.
        nino34_value: Latest Niño 3.4 monthly SST anomaly (°C).
        nino34_date: Date of the latest Niño 3.4 reading.
        soi_value: Latest SOI value (standardised).
        soi_date: Date of the latest SOI reading.
        phase: Classified ENSO phase: "El Niño", "La Niña", or "Neutral".
        phase_source: Always "ONI (NOAA CPC)" — for UI provenance label.
        oni_series: Full ONI time series as a DataFrame (columns: date, season, oni).
    """

    oni_value: float
    oni_season: str
    oni_date: date
    nino34_value: float
    nino34_date: date
    soi_value: float
    soi_date: date
    phase: str
    phase_source: str
    oni_series: pd.DataFrame


# ---------------------------------------------------------------------------
# ONI parser
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}


def _season_to_date(year: int, season: str) -> date:
    """Convert a (year, season) pair to an approximate date (15th of last month).

    The ONI season "DJF" labelled with a given year represents the
    Dec-Jan-Feb window centred on January of that year.  We use the
    middle month (month index from _MONTH_MAP) day 15 as the representative
    date.

    Args:
        year: Calendar year of the ONI row.
        season: 3-letter season code (e.g. "DJF").

    Returns:
        :class:`datetime.date` for approximately the middle of the season.
    """
    month = _MONTH_MAP.get(season, 1)
    try:
        return date(year, month, 15)
    except ValueError:
        return date(year, 1, 15)


def parse_oni(raw_text: str) -> pd.DataFrame:
    """Parse the NOAA CPC ONI ASCII text file.

    NOAA has used two header formats over time:
      - Old (5+ cols): ``SEAS  YR  TOTAL  CLIM  ANOM  ...``  → ANOM at index 4
      - New (4 cols):  ``SEAS  YR   TOTAL   ANOM``           → ANOM at index 3

    The parser detects which format is present from the header line.

    Args:
        raw_text: Raw string content of oni.ascii.txt.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``season`` (str),
        ``year`` (int), ``oni`` (float).

    Raises:
        ValueError: If the expected columns are not found.
    """
    lines = [l for l in raw_text.strip().splitlines() if l.strip()]
    if not lines:
        raise ValueError("ONI file is empty")

    # Detect ANOM column index from header
    anom_col_idx = 4  # default (old format)
    for line in lines:
        parts = line.split()
        if parts and parts[0] == "SEAS":
            # Normalise to uppercase for comparison
            cols = [p.upper() for p in parts]
            if "ANOM" in cols:
                anom_col_idx = cols.index("ANOM")
            break

    rows = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        # Skip header line(s)
        if parts[0] == "SEAS":
            continue
        try:
            season = parts[0]
            year = int(parts[1])
            anom = float(parts[anom_col_idx])
            rows.append({"season": season, "year": year, "oni": anom})
        except (IndexError, ValueError):
            logger.debug("Skipping malformed ONI line: %r", line)
            continue

    if not rows:
        raise ValueError("No se encontraron filas válidas en el archivo ONI")

    df = pd.DataFrame(rows)
    df["date"] = df.apply(lambda r: pd.Timestamp(_season_to_date(r["year"], r["season"])), axis=1)
    df = df.sort_values("date").reset_index(drop=True)
    logger.info("ONI: %d registros parseados (%s — %s)", len(df), df["date"].iloc[0].date(), df["date"].iloc[-1].date())
    return df[["date", "season", "year", "oni"]]


# ---------------------------------------------------------------------------
# Niño 3.4 parser
# ---------------------------------------------------------------------------


def parse_nino34(raw_text: str) -> pd.DataFrame:
    """Parse NOAA ERSSTv5 monthly Niño region anomaly file.

    The file has a multi-line header followed by rows:
        YR  MON  NINO1+2  ANOM  NINO3  ANOM  NINO4  ANOM  NINO3.4  ANOM

    We extract year, month and Niño 3.4 anomaly (column index 9).

    Args:
        raw_text: Raw string content of the Niño index file.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``nino34`` (float).

    Raises:
        ValueError: If parsing fails.
    """
    rows = []
    for line in raw_text.strip().splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            year = int(parts[0])
            month = int(parts[1])
            nino34_anom = float(parts[9])
            rows.append({"year": year, "month": month, "nino34": nino34_anom})
        except (ValueError, IndexError):
            continue

    if not rows:
        raise ValueError("No se encontraron filas válidas en el archivo Niño 3.4")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=15))
    df = df.sort_values("date").reset_index(drop=True)
    # Filter out placeholder values (NOAA uses -99.9 for missing)
    df = df[df["nino34"] > -90].reset_index(drop=True)
    logger.info(
        "Niño 3.4: %d registros (%s — %s)",
        len(df), df["date"].iloc[0].date(), df["date"].iloc[-1].date(),
    )
    return df[["date", "nino34"]]


# ---------------------------------------------------------------------------
# SOI parser
# ---------------------------------------------------------------------------


def parse_soi(raw_text: str) -> pd.DataFrame:
    """Parse the NOAA CPC SOI ASCII file.

    The file has an irregular structure with yearly rows.  After the header,
    each data line starts with a 4-digit year followed by 12 monthly values
    (missing coded as -999.9).

    Args:
        raw_text: Raw string content of the SOI file.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``soi`` (float).
    """
    rows = []
    in_data = False
    for line in raw_text.strip().splitlines():
        parts = line.split()
        if not parts:
            continue
        # Detect start of data block: line where first token is a 4-digit year
        if len(parts[0]) == 4 and parts[0].isdigit() and int(parts[0]) >= 1950:
            in_data = True
        if not in_data:
            continue
        try:
            year = int(parts[0])
            # parts[1:13] naturally yields fewer elements for partial-year rows —
            # no minimum-token guard needed; sentinel months (-999.9) are skipped below.
            for month_idx, val_str in enumerate(parts[1:13], start=1):
                val = float(val_str)
                if val <= -999:
                    continue
                rows.append({"year": year, "month": month_idx, "soi": val})
        except (ValueError, IndexError):
            continue

    if not rows:
        raise ValueError("No se encontraron filas válidas en el archivo SOI")

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=15))
    df = df.sort_values("date").reset_index(drop=True)
    logger.info(
        "SOI: %d registros (%s — %s)",
        len(df), df["date"].iloc[0].date(), df["date"].iloc[-1].date(),
    )
    return df[["date", "soi"]]


# ---------------------------------------------------------------------------
# ENSO phase classifier
# ---------------------------------------------------------------------------


def classify_enso_phase(oni_series: pd.DataFrame) -> str:
    """Classify current ENSO phase from ONI time series.

    Phase is declared when ONI exceeds threshold for at least
    ``ENSO_CONSECUTIVE_MONTHS`` consecutive months (NOAA CPC criterion).
    Uses the most recent ``ENSO_CONSECUTIVE_MONTHS`` readings.

    Args:
        oni_series: DataFrame from :func:`parse_oni` with columns
            ``date``, ``season``, ``year``, ``oni``.

    Returns:
        One of ``"El Niño"``, ``"La Niña"``, or ``"Neutral"``.
    """
    recent = oni_series.tail(ENSO_CONSECUTIVE_MONTHS)["oni"].tolist()
    if len(recent) < ENSO_CONSECUTIVE_MONTHS:
        return "Neutral"

    if all(v >= ENSO_EL_NINO_THRESHOLD for v in recent):
        return "El Niño"
    if all(v <= ENSO_LA_NINA_THRESHOLD for v in recent):
        return "La Niña"
    return "Neutral"


# ---------------------------------------------------------------------------
# High-level fetch function
# ---------------------------------------------------------------------------


def fetch_enso_snapshot() -> ENSOSnapshot:
    """Fetch all three ENSO indices and return a current-state snapshot.

    Fetches ONI, Niño 3.4, and SOI from NOAA CPC.  Raises ``RuntimeError``
    (with a user-friendly message) if any source is unavailable.

    Returns:
        :class:`ENSOSnapshot` with the latest available values and the
        classified ENSO phase.

    Raises:
        RuntimeError: If data cannot be fetched or parsed.
    """
    logger.info("=== Iniciando ingesta ENSO ===")

    # --- ONI ---
    oni_raw = fetch_text(NOAA_ONI_URL, label="NOAA ONI")
    oni_df = parse_oni(oni_raw)
    latest_oni = oni_df.iloc[-1]

    # --- Niño 3.4 ---
    nino_raw = fetch_text(NOAA_NINO34_URL, label="NOAA Niño 3.4")
    nino_df = parse_nino34(nino_raw)
    latest_nino = nino_df.iloc[-1]

    # --- SOI ---
    soi_raw = fetch_text(NOAA_SOI_URL, label="NOAA SOI")
    soi_df = parse_soi(soi_raw)
    latest_soi = soi_df.iloc[-1]

    # --- Phase classification ---
    phase = classify_enso_phase(oni_df)

    snapshot = ENSOSnapshot(
        oni_value=float(latest_oni["oni"]),
        oni_season=str(latest_oni["season"]),
        oni_date=latest_oni["date"].date(),
        nino34_value=float(latest_nino["nino34"]),
        nino34_date=latest_nino["date"].date(),
        soi_value=float(latest_soi["soi"]),
        soi_date=latest_soi["date"].date(),
        phase=phase,
        phase_source="ONI (NOAA CPC)",
        oni_series=oni_df,
    )

    logger.info(
        "ENSO snapshot: ONI=%.2f (%s), Niño3.4=%.2f, SOI=%.2f → fase: %s",
        snapshot.oni_value,
        snapshot.oni_season,
        snapshot.nino34_value,
        snapshot.soi_value,
        snapshot.phase,
    )
    return snapshot
