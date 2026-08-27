"""Fetch and parse ENSO indices from NOAA CPC and ERDDAP.

Indices retrieved:
- ONI (Oceanic Niño Index) — 3-month running mean of Niño 3.4 SST anomalies
- Niño 3.4 SST anomaly — monthly values from ERSSTv5 / ERDDAP weekly
- SOI (Southern Oscillation Index) — Tahiti minus Darwin SLP difference

Primary sources (ERDDAP — structured CSV):
    Niño 3.4: https://coastwatch.pfeg.noaa.gov/erddap/tabledap/ncepNinoSSTwk
    SOI:      https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdlasNoix

Fallback sources (CPC ASCII text):
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
    ERDDAP_NINO34_URL,
    ERDDAP_SOI_URL,
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
        conditions: Current ENSO conditions from latest ONI: "El Niño", "La Niña", or "Neutral".
        conditions_intensity: ONI intensity: "débil", "moderado", "fuerte", "muy fuerte", or None.
        episode_confirmed: Whether a formal CPC episode (5 consecutive seasons) is active.
        phase: Classified ENSO phase (episode-based): "El Niño", "La Niña", or "Neutral".
        phase_source: Always "ONI (NOAA CPC)" — for UI provenance label.
        oni_series: Full ONI time series as a DataFrame (columns: date, season, oni).
        soi_series: Full SOI time series as a DataFrame (columns: date, soi).
        data_sources: Dict mapping index name to the source used ("ERDDAP" or "CPC").
    """

    oni_value: float
    oni_season: str
    oni_date: date
    nino34_value: float
    nino34_date: date
    soi_value: float
    soi_date: date
    conditions: str
    conditions_intensity: Optional[str]
    episode_confirmed: bool
    phase: str
    phase_source: str
    oni_series: pd.DataFrame
    soi_series: pd.DataFrame = None
    data_sources: dict = None


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


def _split_soi_tokens(raw_tokens: list[str]) -> list[str]:
    """Split SOI tokens that may be concatenated without spaces.

    The CPC SOI file sometimes concatenates adjacent values when a negative
    number immediately follows another (e.g. "-2.4-999.9").  This helper
    re-splits on interior minus signs to recover individual values.
    """
    import re
    result = []
    for tok in raw_tokens:
        # Split on minus signs that follow a digit (interior sign = new value)
        parts = re.split(r'(?<=\d)-', tok)
        for i, p in enumerate(parts):
            result.append(p if i == 0 else '-' + p)
    return result


def parse_soi(raw_text: str) -> pd.DataFrame:
    """Parse the NOAA CPC SOI ASCII file.

    The CPC file contains TWO sections: raw anomaly data followed by
    standardised data (after the "STANDARDIZED" header).  We read only
    the standardised section, which matches the convention used by ERDDAP
    erdlasNoix and by this tracker.  If no "STANDARDIZED" header is found,
    we fall back to reading the entire file (single-section format).

    Args:
        raw_text: Raw string content of the SOI file.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``soi`` (float).
    """
    all_lines = raw_text.strip().splitlines()

    # Find the start of the standardised section
    std_start = None
    for i, line in enumerate(all_lines):
        if "STANDARDIZED" in line.upper():
            std_start = i + 1
            break

    # Use only the standardised section if found; otherwise use all lines
    lines_to_parse = all_lines[std_start:] if std_start is not None else all_lines

    rows = []
    in_data = False
    for line in lines_to_parse:
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
            # Re-split tokens to handle concatenated values (e.g. "-2.4-999.9")
            val_tokens = _split_soi_tokens(parts[1:13])
            for month_idx, val_str in enumerate(val_tokens[:12], start=1):
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
# ERDDAP parsers — structured CSV access (primary for Niño 3.4 & SOI)
# ---------------------------------------------------------------------------


def parse_erddap_nino34(csv_text: str) -> pd.DataFrame:
    """Parse ERDDAP Niño 3.4 weekly CSV into monthly averages.

    The ERDDAP dataset returns weekly SST anomalies. We resample to
    monthly to match the CPC monthly format.

    Args:
        csv_text: Raw CSV from ERDDAP ncepNinoSSTwk endpoint.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``nino34`` (float).
    """
    # ERDDAP CSV has 2 header rows: column names + units
    lines = csv_text.strip().splitlines()
    if len(lines) < 3:
        raise ValueError("ERDDAP Niño 3.4 CSV too short")

    # Skip the units row (second line)
    header = lines[0]
    data_lines = [header] + lines[2:]
    csv_clean = "\n".join(data_lines)

    df = pd.read_csv(io.StringIO(csv_clean))
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"Nino34_ssta": "nino34"})
    df = df.dropna(subset=["nino34"])

    # Resample weekly → monthly (mean)
    df = df.set_index("time")
    monthly = df.resample("MS").mean().reset_index()
    monthly["date"] = monthly["time"] + pd.Timedelta(days=14)
    monthly = monthly[monthly["nino34"].notna()].reset_index(drop=True)

    logger.info(
        "ERDDAP Niño 3.4: %d monthly records (%s — %s)",
        len(monthly), monthly["date"].iloc[0].date(), monthly["date"].iloc[-1].date(),
    )
    return monthly[["date", "nino34"]]


def parse_erddap_soi(csv_text: str) -> pd.DataFrame:
    """Parse ERDDAP SOI griddap CSV.

    Args:
        csv_text: Raw CSV from ERDDAP erdlasNoix endpoint.

    Returns:
        DataFrame with columns: ``date`` (datetime64), ``soi`` (float).
    """
    lines = csv_text.strip().splitlines()
    if len(lines) < 3:
        raise ValueError("ERDDAP SOI CSV too short")

    # Skip the units row (second line)
    header = lines[0]
    data_lines = [header] + lines[2:]
    csv_clean = "\n".join(data_lines)

    df = pd.read_csv(io.StringIO(csv_clean))
    df["time"] = pd.to_datetime(df["time"])
    df = df.dropna(subset=["soi"])
    df["date"] = df["time"].dt.normalize() + pd.Timedelta(days=14)

    logger.info(
        "ERDDAP SOI: %d records (%s — %s)",
        len(df), df["date"].iloc[0].date(), df["date"].iloc[-1].date(),
    )
    return df[["date", "soi"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# ENSO phase classifier
# ---------------------------------------------------------------------------


def classify_enso_conditions(oni_value: float) -> tuple[str, Optional[str]]:
    """Classify current ENSO conditions from the latest ONI value alone.

    This is the simple threshold check: is the current ONI above/below
    the El Niño/La Niña threshold?  Unlike episode detection, this does
    NOT require 5 consecutive seasons.

    Returns:
        (conditions, intensity) — e.g. ("El Niño", "fuerte") or ("Neutral", None).
    """
    a = abs(oni_value)
    if oni_value >= ENSO_EL_NINO_THRESHOLD:
        cond = "El Niño"
    elif oni_value <= ENSO_LA_NINA_THRESHOLD:
        cond = "La Niña"
    else:
        return "Neutral", None

    if a >= 2.0:
        intensity = "muy fuerte"
    elif a >= 1.5:
        intensity = "fuerte"
    elif a >= 1.0:
        intensity = "moderado"
    else:
        intensity = "débil"
    return cond, intensity


def classify_enso_phase(oni_series: pd.DataFrame) -> str:
    """Classify current ENSO phase (episode) from ONI time series.

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


def _fetch_with_fallback(
    primary_url: str,
    primary_label: str,
    primary_parser,
    fallback_url: str,
    fallback_label: str,
    fallback_parser,
) -> tuple:
    """Try primary source (ERDDAP), fall back to secondary (CPC) on failure.

    Returns:
        (DataFrame, source_label) — the parsed data and which source was used.
    """
    # Try primary (ERDDAP)
    try:
        raw = fetch_text(primary_url, label=primary_label, timeout=45)
        df = primary_parser(raw)
        if len(df) > 0:
            return df, "ERDDAP"
    except Exception as exc:
        logger.warning("Primary source %s failed: %s — trying fallback", primary_label, exc)

    # Fallback (CPC text)
    try:
        raw = fetch_text(fallback_url, label=fallback_label)
        df = fallback_parser(raw)
        return df, "CPC"
    except Exception as exc:
        raise RuntimeError(
            f"Both primary ({primary_label}) and fallback ({fallback_label}) failed. "
            f"Last error: {exc}"
        ) from exc


def fetch_enso_snapshot() -> ENSOSnapshot:
    """Fetch all three ENSO indices and return a current-state snapshot.

    Uses ERDDAP as primary source for Niño 3.4 and SOI (structured CSV),
    with CPC ASCII text files as fallback. ONI is always from CPC (canonical).

    Returns:
        :class:`ENSOSnapshot` with the latest available values and the
        classified ENSO phase.

    Raises:
        RuntimeError: If data cannot be fetched or parsed.
    """
    logger.info("=== Iniciando ingesta ENSO ===")
    data_sources = {}

    # --- ONI (always from CPC — canonical source, no ERDDAP equivalent) ---
    oni_raw = fetch_text(NOAA_ONI_URL, label="NOAA ONI")
    oni_df = parse_oni(oni_raw)
    latest_oni = oni_df.iloc[-1]
    data_sources["oni"] = "CPC"

    # --- Niño 3.4 (ERDDAP primary, CPC fallback) ---
    nino_df, nino_source = _fetch_with_fallback(
        primary_url=ERDDAP_NINO34_URL,
        primary_label="ERDDAP Niño 3.4",
        primary_parser=parse_erddap_nino34,
        fallback_url=NOAA_NINO34_URL,
        fallback_label="CPC Niño 3.4",
        fallback_parser=parse_nino34,
    )
    latest_nino = nino_df.iloc[-1]
    data_sources["nino34"] = nino_source

    # --- SOI (CPC primary, ERDDAP fallback) ---
    # CPC standardised SOI is primary: erdlasNoix uses a different
    # standardisation base period, producing values that diverge >0.5 from
    # CPC in ~54% of months.  Since thresholds in advice.js are calibrated
    # for the CPC scale, CPC must be canonical.
    soi_df, soi_source = _fetch_with_fallback(
        primary_url=NOAA_SOI_URL,
        primary_label="CPC SOI",
        primary_parser=parse_soi,
        fallback_url=ERDDAP_SOI_URL,
        fallback_label="ERDDAP SOI",
        fallback_parser=parse_erddap_soi,
    )
    latest_soi = soi_df.iloc[-1]
    data_sources["soi"] = soi_source

    # --- Phase classification ---
    phase = classify_enso_phase(oni_df)
    conditions, conditions_intensity = classify_enso_conditions(float(latest_oni["oni"]))
    episode_confirmed = phase != "Neutral"

    snapshot = ENSOSnapshot(
        oni_value=float(latest_oni["oni"]),
        oni_season=str(latest_oni["season"]),
        oni_date=latest_oni["date"].date(),
        nino34_value=float(latest_nino["nino34"]),
        nino34_date=latest_nino["date"].date(),
        soi_value=float(latest_soi["soi"]),
        soi_date=latest_soi["date"].date(),
        conditions=conditions,
        conditions_intensity=conditions_intensity,
        episode_confirmed=episode_confirmed,
        phase=phase,
        phase_source="ONI (NOAA CPC)",
        oni_series=oni_df,
        soi_series=soi_df,
        data_sources=data_sources,
    )

    logger.info(
        "ENSO snapshot: ONI=%.2f (%s), Niño3.4=%.2f, SOI=%.2f → fase: %s",
        snapshot.oni_value,
        snapshot.oni_season,
        snapshot.nino34_value,
        snapshot.soi_value,
        snapshot.phase,
    )
    logger.info("Data sources: %s", data_sources)
    return snapshot
