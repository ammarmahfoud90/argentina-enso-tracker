"""Download and process CHIRPS v2.0 monthly precipitation data.

CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) v2.0:
- Resolution: 0.05°
- Coverage: 50°S–50°N, global, 1981–present
- Source: https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/netcdf/

This module downloads one NetCDF file per year, computes spatial averages
over each Argentine region bounding box, and returns a monthly time-series
DataFrame suitable for correlation analysis.

Large files (~130 MB/year) are written to ``data/raw/`` (gitignored).
Progress is logged at INFO level.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.config import (
    CHIRPS_BASE_URL,
    CHIRPS_START_YEAR,
    REGIONS,
)
from src.utils import fetch_binary, get_logger

logger = get_logger(__name__)

RAW_DATA_DIR = Path("data/raw/chirps")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _chirps_filename(year: int) -> str:
    """Return the CHIRPS NetCDF filename for a given year.

    Args:
        year: Four-digit year.

    Returns:
        Filename string, e.g. ``"chirps-v2.0.2020.months_p05.nc"``.
    """
    return f"chirps-v2.0.{year}.months_p05.nc"


def _chirps_url(year: int) -> str:
    """Build the full download URL for a given year's CHIRPS NetCDF.

    Args:
        year: Four-digit year.

    Returns:
        Full URL string.
    """
    return CHIRPS_BASE_URL + _chirps_filename(year)


def download_chirps_year(year: int, force_download: bool = False) -> Path:
    """Download CHIRPS NetCDF for *year* to the local raw cache.

    Skips download if the file already exists and ``force_download`` is False.

    Args:
        year: Calendar year to download.
        force_download: If True, re-download even if the file exists.

    Returns:
        :class:`pathlib.Path` to the local NetCDF file.

    Raises:
        RuntimeError: If the download fails (propagated from :func:`fetch_binary`).
    """
    out_path = RAW_DATA_DIR / _chirps_filename(year)
    if out_path.exists() and not force_download:
        logger.info("CHIRPS %d ya en caché: %s", year, out_path)
        return out_path

    url = _chirps_url(year)
    logger.info("Descargando CHIRPS %d desde %s", year, url)
    content = fetch_binary(url, timeout=300, label=f"CHIRPS {year}")
    out_path.write_bytes(content)
    logger.info("CHIRPS %d guardado: %s (%d MB)", year, out_path, len(content) // 1_000_000)
    return out_path


def extract_regional_means(nc_path: Path) -> pd.DataFrame:
    """Compute spatial mean precipitation per region from a CHIRPS NetCDF.

    Args:
        nc_path: Path to a CHIRPS monthly NetCDF file (one year, 12 months).

    Returns:
        DataFrame with columns ``date``, and one column per region name
        (mm/month spatial average).

    Raises:
        ImportError: If ``xarray`` or ``netCDF4`` is not installed.
        ValueError: If expected variables are missing in the NetCDF.
    """
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError("xarray es necesario para procesar CHIRPS. Instalar con: pip install xarray netCDF4") from exc

    logger.info("Procesando %s", nc_path.name)
    ds = xr.open_dataset(nc_path)

    # CHIRPS uses variable 'precip' and dimensions 'latitude','longitude','time'
    if "precip" not in ds:
        available = list(ds.data_vars)
        raise ValueError(f"Variable 'precip' no encontrada en {nc_path.name}. Disponibles: {available}")

    precip = ds["precip"]  # shape: (time, latitude, longitude)

    # Normalise dimension names (some CHIRPS versions use 'lat'/'lon')
    rename_map = {}
    if "lat" in precip.dims and "latitude" not in precip.dims:
        rename_map["lat"] = "latitude"
    if "lon" in precip.dims and "longitude" not in precip.dims:
        rename_map["lon"] = "longitude"
    if rename_map:
        precip = precip.rename(rename_map)

    records = []
    times = pd.to_datetime(ds["time"].values)

    for t_idx, t in enumerate(times):
        row: dict = {"date": pd.Timestamp(t).replace(day=15)}
        monthly = precip.isel(time=t_idx)

        for region_name, bbox in REGIONS.items():
            mask_lat = (monthly["latitude"] >= bbox["lat_min"]) & (monthly["latitude"] <= bbox["lat_max"])
            mask_lon = (monthly["longitude"] >= bbox["lon_min"]) & (monthly["longitude"] <= bbox["lon_max"])
            subset = monthly.where(mask_lat & mask_lon, drop=True)

            # Valid pixels only (CHIRPS uses -9999 for missing)
            valid = subset.values[subset.values > -9990]
            if len(valid) == 0:
                logger.warning("Sin datos válidos para %s en %s", region_name, t)
                row[region_name] = float("nan")
            else:
                row[region_name] = float(np.nanmean(valid))

        records.append(row)

    ds.close()
    return pd.DataFrame(records)


def build_chirps_monthly_series(
    start_year: int = CHIRPS_START_YEAR,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Build a complete monthly precipitation time-series for all regions.

    Downloads and processes CHIRPS NetCDF files year by year.  Files are
    cached locally in ``data/raw/chirps/``.

    Args:
        start_year: First year to include (default: 1981).
        end_year: Last year to include (default: current year minus 1, to
            ensure full-year files are available).

    Returns:
        DataFrame indexed by ``date`` with one column per region (mm/month).
        Sorted chronologically.

    Raises:
        RuntimeError: If a year's download fails (propagated).
    """
    import datetime

    if end_year is None:
        end_year = datetime.date.today().year - 1

    logger.info("Construyendo serie CHIRPS %d–%d para %d regiones", start_year, end_year, len(REGIONS))
    frames = []

    for year in range(start_year, end_year + 1):
        try:
            nc_path = download_chirps_year(year)
            df_year = extract_regional_means(nc_path)
            frames.append(df_year)
        except RuntimeError as exc:
            logger.error("Error descargando CHIRPS %d: %s — saltando año", year, exc)
            continue
        except Exception as exc:
            logger.error("Error procesando CHIRPS %d: %s — saltando año", year, exc)
            continue

    if not frames:
        raise RuntimeError("No se pudo obtener ningún año de datos CHIRPS")

    combined = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    logger.info(
        "Serie CHIRPS completa: %d meses (%s — %s)",
        len(combined),
        combined["date"].iloc[0].date(),
        combined["date"].iloc[-1].date(),
    )
    return combined
