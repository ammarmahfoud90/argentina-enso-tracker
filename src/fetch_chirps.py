"""Download and process CHIRPS v2.0 monthly precipitation data.

CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) v2.0:
- Resolution: 0.05°
- Coverage: 50°S–50°N, global, 1981–present

Access strategy:
    Primary: IRI Data Library OPeNDAP endpoint (lazy remote access).
    The OPeNDAP protocol lets xarray request only the Argentina subset,
    avoiding the download of the 7.1 GB consolidated global NetCDF.

    IRI endpoint (OPeNDAP, no auth required):
    dap2://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/dods

    If IRI is unavailable, raise RuntimeError — no silent fallbacks.

Notes:
    - The time axis uses 360-day calendar ("months since 1960-01-01"),
      so we decode manually with cftime / raw month offsets.
    - Latitude runs from south to north (not reversed) in CHIRPS.
    - Missing data coded as ~-9999; filtered before averaging.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.config import (
    CHIRPS_START_YEAR,
    REGIONS,
)
from src.utils import get_logger

logger = get_logger(__name__)

# IRI OPeNDAP endpoint — DAP2 protocol, no authentication required
IRI_OPENDAP_URL = (
    "dap2://iridl.ldeo.columbia.edu"
    "/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/dods"
)

# Cftime epoch: "months since 1960-01-01"
_EPOCH = datetime.date(1960, 1, 1)
_MISSING_THRESHOLD = -9990.0


def _months_since_epoch_to_date(months_offset: float) -> datetime.date:
    """Convert a fractional 'months since 1960-01-01' offset to a date.

    The CHIRPS 360-day calendar assigns 0.5, 1.5, 2.5, … to the middle of
    each month.  We interpret the integer part as full months elapsed.

    Args:
        months_offset: Value from the T coordinate (e.g. 252.5 → Jan 1981).

    Returns:
        :class:`datetime.date` for the 15th of the corresponding month.
    """
    total_months = int(months_offset)  # floor
    year = _EPOCH.year + total_months // 12
    month = _EPOCH.month + total_months % 12
    if month > 12:
        month -= 12
        year += 1
    return datetime.date(year, month, 15)


def _build_date_index(t_values: np.ndarray) -> pd.DatetimeIndex:
    """Convert raw T coordinate array to a pandas DatetimeIndex.

    Args:
        t_values: 1-D array of 'months since 1960-01-01' floats.

    Returns:
        :class:`pandas.DatetimeIndex` with monthly frequency, day=15.
    """
    dates = [_months_since_epoch_to_date(v) for v in t_values]
    return pd.DatetimeIndex([pd.Timestamp(d) for d in dates])


def build_chirps_monthly_series(
    start_year: int = CHIRPS_START_YEAR,
    end_year: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch CHIRPS monthly precipitation series for all Argentine regions.

    Uses IRI Data Library OPeNDAP to retrieve only the Argentina spatial
    subset (lat −55 to −22, lon −73 to −53).  Data is loaded lazily; only
    the slice is transferred over the network.

    Args:
        start_year: First year to include (default: 1981).
        end_year: Last year to include (default: most recent full year).

    Returns:
        DataFrame with column ``date`` (datetime64) and one column per
        region name (mm/month spatial mean), sorted chronologically.

    Raises:
        RuntimeError: If the IRI OPeNDAP endpoint is unreachable or the
            data cannot be loaded.
        ImportError: If ``xarray`` or ``pydap`` is not installed.
    """
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError(
            "xarray es necesario: pip install xarray pydap"
        ) from exc

    if end_year is None:
        end_year = datetime.date.today().year - 1

    logger.info(
        "Cargando CHIRPS v2.0 via IRI OPeNDAP (%d–%d, 5 regiones Argentina)…",
        start_year, end_year,
    )

    try:
        ds = xr.open_dataset(IRI_OPENDAP_URL, engine="pydap", decode_times=False)
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo conectar al endpoint IRI OPeNDAP: {exc}\n"
            "Verifique su conexión o consulte https://iridl.ldeo.columbia.edu/"
        ) from exc

    # Compute Argentina bounding box (union of all regions)
    all_lat_min = min(r["lat_min"] for r in REGIONS.values())
    all_lat_max = max(r["lat_max"] for r in REGIONS.values())
    all_lon_min = min(r["lon_min"] for r in REGIONS.values())
    all_lon_max = max(r["lon_max"] for r in REGIONS.values())

    logger.info(
        "Argentina bbox: lat [%.1f, %.1f] × lon [%.1f, %.1f]",
        all_lat_min, all_lat_max, all_lon_min, all_lon_max,
    )

    # Build date index and filter time range
    t_vals = ds["T"].values
    date_idx = _build_date_index(t_vals)
    time_mask = (date_idx.year >= start_year) & (date_idx.year <= end_year)
    t_indices = np.where(time_mask)[0]

    if len(t_indices) == 0:
        raise RuntimeError(
            f"No hay datos CHIRPS disponibles para el período {start_year}–{end_year}"
        )

    logger.info("Períodos seleccionados: %d meses (%s a %s)",
                len(t_indices),
                date_idx[t_indices[0]].date(),
                date_idx[t_indices[-1]].date())

    # Spatial subset: select Argentina bbox
    lat_vals = ds["Y"].values
    lon_vals = ds["X"].values

    lat_mask = (lat_vals >= all_lat_min) & (lat_vals <= all_lat_max)
    lon_mask = (lon_vals >= all_lon_min) & (lon_vals <= all_lon_max)
    lat_indices = np.where(lat_mask)[0]
    lon_indices = np.where(lon_mask)[0]

    logger.info(
        "Descargando subconjunto: %d lats × %d lons × %d meses…",
        len(lat_indices), len(lon_indices), len(t_indices),
    )

    # Slice dataset — OPeNDAP fetches only this slice from the server
    precip_var = ds["precipitation"]

    # Determine dimension order (IRI uses T, Y, X)
    t_slice = slice(int(t_indices[0]), int(t_indices[-1]) + 1)
    lat_slice = slice(int(lat_indices[0]), int(lat_indices[-1]) + 1)
    lon_slice = slice(int(lon_indices[0]), int(lon_indices[-1]) + 1)

    logger.info("Solicitando datos vía OPeNDAP (puede tardar varios minutos)…")
    subset = precip_var.isel(T=t_slice, Y=lat_slice, X=lon_slice).values
    # subset shape: (n_time, n_lat, n_lon)

    sub_lats = lat_vals[lat_slice]
    sub_lons = lon_vals[lon_slice]
    sub_dates = date_idx[t_indices]

    logger.info("Datos recibidos: shape=%s", subset.shape)
    ds.close()

    # Compute regional spatial means
    records = []
    for t_idx, ts in enumerate(sub_dates):
        row: dict = {"date": pd.Timestamp(ts)}
        month_data = subset[t_idx, :, :]  # (n_lat, n_lon)

        for region_name, bbox in REGIONS.items():
            lat_m = (sub_lats >= bbox["lat_min"]) & (sub_lats <= bbox["lat_max"])
            lon_m = (sub_lons >= bbox["lon_min"]) & (sub_lons <= bbox["lon_max"])

            # 2D boolean mask
            mask_2d = np.outer(lat_m, lon_m)
            valid_pixels = month_data[mask_2d]
            valid_pixels = valid_pixels[valid_pixels > _MISSING_THRESHOLD]

            if len(valid_pixels) == 0:
                logger.warning("Sin píxeles válidos para %s en %s", region_name, ts.date())
                row[region_name] = float("nan")
            else:
                row[region_name] = float(np.nanmean(valid_pixels))

        records.append(row)

    combined = (
        pd.DataFrame(records)
        .sort_values("date")
        .reset_index(drop=True)
    )

    logger.info(
        "Serie CHIRPS completa: %d meses (%s — %s)",
        len(combined),
        combined["date"].iloc[0].date(),
        combined["date"].iloc[-1].date(),
    )
    return combined
