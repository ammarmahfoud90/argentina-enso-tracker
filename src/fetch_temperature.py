"""Fetch CPC Global Temperature data and compute regional monthly averages.

Data source: NOAA PSL CPC Global Temperature (0.5 degree grid, 1979-present).
Files: tmax.YYYY.nc and tmin.YYYY.nc via OPeNDAP or direct download.

The weekly observation refresh uses this reader to extend the monthly
series. The daily build reads and analyzes the validated Parquet files.
"""

from __future__ import annotations

import logging
import os
import tempfile
from contextlib import ExitStack
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


def fetch_cpc_temperature_year(year: int, *, refresh: bool | None = None) -> xr.Dataset | None:
    """Fetch CPC tmax and tmin for a given year.

    Downloads NetCDF files to a local cache directory, then opens them
    with xarray. Returns xarray Dataset subsetted to Argentina domain.
    Returns None if the data is not available.
    """
    import requests

    cache_dir = Path("data/cache/cpc_temp")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # An annual file for the current year keeps growing. Never treat its
    # existence as proof that it contains the latest published days.
    if refresh is None:
        refresh = year >= date.today().year - 1
    try:
        datasets = {}
        with ExitStack() as stack:
            for var in ("tmax", "tmin"):
                local_path = cache_dir / f"{var}.{year}.nc"
                if refresh or not local_path.exists():
                    fd, temporary = tempfile.mkstemp(suffix=".nc", dir=cache_dir)
                    try:
                        with os.fdopen(fd, "wb") as output:
                            with requests.get(_opendap_url(var, year), timeout=(15, 120), stream=True) as resp:
                                resp.raise_for_status()
                                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                                    output.write(chunk)
                        # A truncated download or a successful HTML error page
                        # must not overwrite a previously valid cached file.
                        with xr.open_dataset(temporary) as check:
                            if var not in check or not {"time", "lat", "lon"}.issubset(check[var].dims):
                                raise ValueError(f"Invalid CPC file for {var}")
                            if check[var].attrs.get("units") not in ("degC", "C", "degree_Celsius", "degrees_Celsius"):
                                raise ValueError(f"Unexpected CPC temperature units: {check[var].attrs.get('units')}")
                            if not len(check.time) or not (pd.DatetimeIndex(check.time.values).year == year).all():
                                raise ValueError(f"CPC file has incorrect dates for {year}")
                        os.replace(temporary, local_path)
                        logger.info("Downloaded %s (%.1f MB)", local_path.name, local_path.stat().st_size / 1024 / 1024)
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                datasets[var] = stack.enter_context(xr.open_dataset(local_path))
            tmax, tmin = datasets["tmax"], datasets["tmin"]
            if not np.array_equal(tmax.time.values, tmin.time.values):
                raise ValueError("CPC tmax and tmin have different daily coverage")
            lat_slice = slice(-20, -55) if tmax.lat.values[0] > tmax.lat.values[-1] else slice(-55, -20)
            lon_slice = slice(285, 310) if tmax.lon.values.max() > 180 else slice(-75, -50)
            # Load just the regional subset, then close both global files.
            ds = xr.Dataset({var: datasets[var][var].sel(lat=lat_slice, lon=lon_slice).load()
                             for var in ("tmax", "tmin")})
        logger.info("CPC temp %d: loaded %d days", year, len(ds.time))
        return ds
    except Exception as exc:
        logger.warning("CPC temp %d failed: %s", year, exc)
        return None


def compute_regional_temp_monthly(ds: xr.Dataset, *, through: date | None = None) -> pd.DataFrame:
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

    daily_dates = pd.DatetimeIndex(ds.time.values).normalize()
    if daily_dates.has_duplicates:
        raise ValueError("Duplicate daily dates in CPC temperature input")
    cutoff = pd.Timestamp(through or date.today()).to_period("M") - 1
    complete = set()
    for month in daily_dates.to_period("M").unique():
        expected = pd.date_range(month.start_time, month.end_time.normalize(), freq="D")
        actual = daily_dates[daily_dates.to_period("M") == month]
        if month <= cutoff and len(actual) == len(expected) and expected.isin(actual).all():
            complete.add(month)
        else:
            logger.info("Skipping incomplete or open CPC month %s (%d days)", month, len(actual))
    records = []
    # Group by month
    monthly = tmean.resample(time="ME").mean()

    for t in monthly.time.values:
        if pd.Timestamp(t).to_period("M") not in complete:
            continue
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
                period = pd.Timestamp(t).to_period("M")
                daily_region = tmean.sel(
                    time=slice(period.start_time, period.end_time), lat=lat_sl,
                    lon=slice(min(lon_min, lon_max), max(lon_min, lon_max)))
                counts = daily_region.count(dim=["lat", "lon"]).values
                # Ocean pixels may be consistently missing. Reject a day
                # whose valid support collapses relative to this month's
                # maximum, instead of silently averaging an incomplete month.
                if not len(counts) or counts.max() == 0 or (counts < .9 * counts.max()).any():
                    raise ValueError(f"Incomplete daily regional coverage for {region_name} {period}")
                val = float(region_data.mean(skipna=True).values)
                if not np.isnan(val):
                    row[region_name] = round(val, 2)
            except Exception:
                pass
        records.append(row)

    return pd.DataFrame(records, columns=["date", *REGION_ORDER])


def build_temp_monthly_series(
    start_year: int = 1981, end_year: int | None = None
) -> pd.DataFrame:
    """Build full monthly temperature series for all regions.

    This downloads CPC temperature year by year and computes regional
    means. Called by the weekly refresh, not by daily builds.

    Args:
        start_year: First year to include (CPC starts at 1979).
        end_year: Last year to include (default: current year; full months only).

    Returns:
        DataFrame with columns: date, region1, region2, ...
    """
    if end_year is None:
        end_year = date.today().year

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
