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
    """Fetch CPC tmax and tmin for a given year.

    Downloads NetCDF files to a local cache directory, then opens them
    with xarray. Returns xarray Dataset subsetted to Argentina domain.
    Returns None if the data is not available.
    """
    import requests

    cache_dir = Path("data/cache/cpc_temp")
    cache_dir.mkdir(parents=True, exist_ok=True)

    try:
        datasets = {}
        for var in ("tmax", "tmin"):
            local_path = cache_dir / f"{var}.{year}.nc"
            if not local_path.exists():
                url = _opendap_url(var, year)
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
                logger.info("Downloaded %s (%.1f MB)", local_path.name,
                            len(resp.content) / 1024 / 1024)

            ds = xr.open_dataset(local_path)
            datasets[var] = ds

        tmax = datasets["tmax"]
        tmin = datasets["tmin"]

        # Subset to Argentina region (broad box covering all 5 regions)
        # CPC data has descending latitudes (90 → -90) and 0-360 longitudes
        lat_descending = tmax["lat"].values[0] > tmax["lat"].values[-1]
        if lat_descending:
            lat_slice = slice(-20, -55)  # reversed for descending coords
        else:
            lat_slice = slice(-55, -20)

        if tmax["lon"].values.max() > 180:
            lon_slice = slice(285, 310)  # 360 - 75 = 285, 360 - 50 = 310
        else:
            lon_slice = slice(-75, -50)

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

    # Handle coordinate conventions
    lons = tmean.lon.values
    lats = tmean.lat.values
    use_360 = lons.max() > 180
    lat_descending = lats[0] > lats[-1] if len(lats) > 1 else False

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
                if lat_descending:
                    lat_sl = slice(max(lat_min, lat_max), min(lat_min, lat_max))
                else:
                    lat_sl = slice(min(lat_min, lat_max), max(lat_min, lat_max))
                region_data = monthly.sel(
                    time=t,
                    lat=lat_sl,
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
