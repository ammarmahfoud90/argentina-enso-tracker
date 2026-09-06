"""Fetch CPC Global Temperature data and compute regional monthly averages.

Data source: NOAA PSL CPC Global Temperature (0.5 degree grid, 1979-present).
Files: tmax.YYYY.nc and tmin.YYYY.nc via OPeNDAP or direct download.

This module is used by compute_temp_correlations.py (one-time computation),
NOT by the daily build.py. The daily build reads pre-computed Parquet files.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from src.config import CPC_TEMP_BASE_URL, REGIONS, REGION_ORDER
from src.utils import get_logger

logger = get_logger(__name__)


def _opendap_url(variable: str, year: int) -> str:
    """Build OPeNDAP URL for CPC global temperature file."""
    return f"{CPC_TEMP_BASE_URL}{variable}.{year}.nc"


def fetch_cpc_temperature_year(year: int) -> xr.Dataset | None:
    """Fetch CPC tmax and tmin for a given year via OPeNDAP.

    Returns xarray Dataset with tmax and tmin variables,
    subsetted to South American domain (-60 to -20 lat, -75 to -50 lon).
    Returns None if the data is not available.
    """
    try:
        tmax_url = _opendap_url("tmax", year)
        tmin_url = _opendap_url("tmin", year)

        # Open with OPeNDAP subsetting to South America bounding box
        tmax = xr.open_dataset(tmax_url)
        tmin = xr.open_dataset(tmin_url)

        # Subset to Argentina region (broad box covering all 5 regions)
        lat_slice = slice(-55, -20)
        lon_slice = slice(-75, -50)

        # Handle different longitude conventions (0-360 vs -180 to 180)
        if tmax["lon"].values.max() > 180:
            lon_slice = slice(285, 310)  # 360 - 75 = 285, 360 - 50 = 310

        tmax_sub = tmax["tmax"].sel(lat=lat_slice, lon=lon_slice)
        tmin_sub = tmin["tmin"].sel(lat=lat_slice, lon=lon_slice)

        ds = xr.Dataset({"tmax": tmax_sub, "tmin": tmin_sub})
        logger.info("CPC temp %d: loaded %d days", year, len(ds.time))
        return ds
    except Exception as exc:
        logger.warning("CPC temp %d failed: %s", year, exc)
        return None


def compute_regional_temp_monthly(ds: xr.Dataset) -> pd.DataFrame:
    """Compute regional mean temperature (tmax+tmin)/2 per month.

    Args:
        ds: xarray Dataset with tmax and tmin variables,
            dimensions (time, lat, lon).

    Returns:
        DataFrame with columns: date, and one column per region with
        monthly mean temperature (C).
    """
    # Mean temperature = (tmax + tmin) / 2
    tmean = (ds["tmax"] + ds["tmin"]) / 2

    # Handle longitude convention
    lons = tmean.lon.values
    use_360 = lons.max() > 180

    records = []
    # Group by month
    monthly = tmean.resample(time="ME").mean()

    for t in monthly.time.values:
        row = {"date": pd.Timestamp(t)}
        for region_name in REGION_ORDER:
            cfg = REGIONS[region_name]
            lat_min, lat_max = cfg["lat_min"], cfg["lat_max"]
            lon_min, lon_max = cfg["lon_min"], cfg["lon_max"]

            if use_360:
                lon_min = lon_min % 360
                lon_max = lon_max % 360

            try:
                region_data = monthly.sel(
                    time=t,
                    lat=slice(min(lat_min, lat_max), max(lat_min, lat_max)),
                    lon=slice(min(lon_min, lon_max), max(lon_min, lon_max)),
                )
                val = float(region_data.mean(skipna=True).values)
                if not np.isnan(val):
                    row[region_name] = round(val, 2)
            except Exception:
                pass
        records.append(row)

    return pd.DataFrame(records)


def build_temp_monthly_series(
    start_year: int = 1981, end_year: int | None = None
) -> pd.DataFrame:
    """Build full monthly temperature series for all regions.

    This downloads CPC temperature year by year and computes regional
    means. Designed for one-time computation, not daily builds.

    Args:
        start_year: First year to include (CPC starts at 1979).
        end_year: Last year to include (default: previous year).

    Returns:
        DataFrame with columns: date, region1, region2, ...
    """
    if end_year is None:
        end_year = date.today().year - 1

    all_dfs = []
    for year in range(start_year, end_year + 1):
        logger.info("Fetching CPC temperature for %d...", year)
        ds = fetch_cpc_temperature_year(year)
        if ds is not None:
            df = compute_regional_temp_monthly(ds)
            all_dfs.append(df)
            ds.close()

    if not all_dfs:
        raise RuntimeError("No CPC temperature data could be loaded")

    result = pd.concat(all_dfs, ignore_index=True)
    result = result.sort_values("date").reset_index(drop=True)
    logger.info("Temperature series: %d months, %d-%d",
                len(result), start_year, end_year)
    return result
