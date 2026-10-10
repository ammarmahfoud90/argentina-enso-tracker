"""Final CHIRPS v3 monthly rainfall, read at native resolution from CHC COGs.

HTTP range reads transfer only the Argentina window. Values are unweighted
means of valid pixel centres inside the original rectangular sampling boxes.
There is no fallback to v2 or to preliminary rainfall.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

import numpy as np
import pandas as pd
import requests

from src.config import (CHIRPS_BASE_URL, CHIRPS_DATASET_ID, CHIRPS_SOURCE,
                        CHIRPS_START_YEAR, PRECIPITATION_REGIONS, REGION_ORDER)
from src.utils import get_logger

logger = get_logger(__name__)
USGS_MONTHLY_URL = "https://dmsdata.cr.usgs.gov/cogs/fews/chirps_global_month_data/"
PRODUCT_METADATA = {
    "dataset_id": CHIRPS_DATASET_ID, "source": CHIRPS_SOURCE,
    "product_status": "final", "timestep": "monthly", "units": "mm/month",
    "resolution_degrees": 0.05, "sampling_bounds": PRECIPITATION_REGIONS,
    "extraction_method": "native_pixel_centres_unweighted_mean_v1",
}


def validate_product(frame: pd.DataFrame) -> None:
    """Prevent mixing a different product, grid or sampling method into v3."""
    if any(frame.attrs.get(key) != value for key, value in PRODUCT_METADATA.items()):
        raise ValueError("Rainfall product metadata mismatch: run the full CHIRPS v3 migration; versions cannot be mixed")
    support = frame.attrs.get("land_mask_sha256", "")
    counts = frame.attrs.get("valid_pixel_counts", {})
    if not re.fullmatch(r"[0-9a-f]{64}", support) or set(counts) != set(REGION_ORDER) or any(not isinstance(n, int) or n <= 0 for n in counts.values()):
        raise ValueError("Missing CHIRPS spatial support metadata")


def final_months(through: date, start_year: int, end_year: int, *, source: str = "chc") -> list[pd.Period]:
    if source not in ("chc", "usgs"):
        raise ValueError("Unknown CHIRPS distribution source")
    response = requests.get(CHIRPS_BASE_URL if source == "chc" else USGS_MONTHLY_URL, timeout=(10, 90))
    response.raise_for_status()
    if source == "chc":
        available = {pd.Period(f"{y}-{m}", freq="M") for y, m in
                     re.findall(r"chirps-v3\.0\.(\d{4})\.(0[1-9]|1[0-2])\.cog", response.text)}
    else:
        # Use only the final monthly data directory, never prelim or anomalies.
        available = set()
        for start, end in re.findall(r"data_(\d{8})_(\d{8})\.tif", response.text):
            p = pd.Timestamp(start).to_period("M")
            if start != p.start_time.strftime("%Y%m%d") or end != p.end_time.strftime("%Y%m%d"):
                raise ValueError("Unexpected USGS CHIRPS monthly interval")
            available.add(p)
    cutoff = pd.Period(through, freq="M") - 1
    months = sorted(p for p in available if start_year <= p.year <= end_year and p <= cutoff)
    if not months:
        raise ValueError("No complete final CHIRPS v3 months available")
    expected = list(pd.period_range(f"{start_year}-01", months[-1], freq="M"))
    if months != expected:
        raise ValueError("Missing calendar month in final CHIRPS v3 archive")
    return months


def regional_means(values: np.ma.MaskedArray, transform) -> tuple[dict, dict]:
    """Include valid zero rainfall; exclude only the source's missing pixels."""
    lat = transform.f + (np.arange(values.shape[0]) + 0.5) * transform.e
    lon = transform.c + (np.arange(values.shape[1]) + 0.5) * transform.a
    means, counts = {}, {}
    for region, box in PRECIPITATION_REGIONS.items():
        rows = (lat >= box["lat_min"]) & (lat <= box["lat_max"])
        cols = (lon >= box["lon_min"]) & (lon <= box["lon_max"])
        pixels = values[np.ix_(rows, cols)].compressed()
        if not len(pixels) or not np.isfinite(pixels).all() or (pixels < 0).any():
            raise ValueError(f"Missing or invalid CHIRPS pixels in {region}")
        means[region] = float(np.mean(pixels, dtype=np.float64))
        counts[region] = len(pixels)
    return means, counts


def validate_grid(dataset) -> None:
    if (dataset.count != 1 or dataset.shape != (2400, 7200)
            or dataset.crs is None or dataset.crs.to_epsg() != 4326
            or not np.allclose(tuple(dataset.bounds), (-180, -60, 180, 60), atol=1e-5, rtol=0)
            or not np.allclose(dataset.res, (0.05, 0.05), atol=1e-8, rtol=0)
            or dataset.transform.e >= 0 or dataset.transform.b != 0 or dataset.transform.d != 0):
        raise ValueError("Unexpected CHIRPS v3 native grid")


def read_month(period: pd.Period, *, source: str = "chc") -> dict:
    import rasterio
    from rasterio.windows import from_bounds

    url = f"{CHIRPS_BASE_URL}chirps-v3.0.{period.year:04d}.{period.month:02d}.cog"
    if source == "usgs":
        url = f"{USGS_MONTHLY_URL}data_{period.start_time:%Y%m%d}_{period.end_time:%Y%m%d}.tif"
    elif source != "chc":
        raise ValueError("Unknown CHIRPS distribution source")
    options = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
               "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".cog,.tif",
               "GDAL_HTTP_CONNECTTIMEOUT": "10", "GDAL_HTTP_TIMEOUT": "90",
               "GDAL_HTTP_MAX_RETRY": "2", "GDAL_HTTP_RETRY_DELAY": "1",
               "GDAL_HTTP_VERSION": "1.1"}
    # Reuse an explicitly configured trusted CA bundle; TLS verification stays on.
    ca_bundle = os.environ.get("GDAL_CURL_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if ca_bundle:
        os.environ.setdefault("GDAL_CURL_CA_BUNDLE", ca_bundle)
        options["GDAL_CURL_CA_BUNDLE"] = ca_bundle
    with rasterio.Env(**options), rasterio.open(url) as dataset:
        validate_grid(dataset)
        window = from_bounds(-73, -50, -53, -22, dataset.transform).round_offsets().round_lengths()
        values = dataset.read(1, window=window, masked=True)
        if values.shape != (560, 400):
            raise ValueError("Unexpected CHIRPS extraction window")
        raw = np.asarray(values.data)
        if not np.isfinite(raw).all() or ((raw < 0) & (raw != -9999)).any():
            raise ValueError("Invalid CHIRPS source pixels")
        # Official COGs encode ocean as -9999, including files without a nodata tag.
        values = np.ma.array(raw, mask=np.ma.getmaskarray(values) | (raw == -9999))
        means, counts = regional_means(values, dataset.window_transform(window))
        mask = np.ma.getmaskarray(values).astype("uint8").tobytes()
        digest = hashlib.sha256(values.filled(np.nan).astype("<f4").tobytes() + mask).hexdigest()
    return {"date": str(period), "source_url": url, "product_metadata": PRODUCT_METADATA,
            "values": means, "valid_pixel_counts": counts, "window_sha256": digest,
            "land_mask_sha256": hashlib.sha256(mask).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).isoformat()}


def _month(period: pd.Period, cache_dir: Path, refresh: bool, source: str = "chc") -> dict:
    path = cache_dir / f"{period}.json"
    if path.exists() and not refresh:
        try:
            saved = json.loads(path.read_text())
            if (saved["date"] == str(period) and saved["product_metadata"] == PRODUCT_METADATA
                    and set(saved["values"]) == set(REGION_ORDER)
                    and all(np.isfinite(v) and 0 <= v <= 3000 for v in saved["values"].values())
                    and all(saved["valid_pixel_counts"][r] > 0 for r in REGION_ORDER)
                    and len(saved["land_mask_sha256"]) == 64 and len(saved["window_sha256"]) == 64):
                return saved
        except (ValueError, KeyError, TypeError):
            pass
    time.sleep(2)  # Keep native range reads modest; bulk transfers prefer rsync/FTP.
    result = read_month(period) if source == "chc" else read_month(period, source=source)
    fd, temporary = tempfile.mkstemp(dir=cache_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, allow_nan=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


def build_chirps_monthly_series(start_year: int = CHIRPS_START_YEAR, end_year: int | None = None,
                               *, through: date | None = None,
                               cache_dir: Path = Path("data/cache/chirps_v3"),
                               workers: int = 1, source: str = "chc") -> pd.DataFrame:
    today = through or date.today()
    months = (final_months(today, start_year, end_year or today.year) if source == "chc" else
              final_months(today, start_year, end_year or today.year, source=source))
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("CHIRPS v3 final: %d months, %s to %s", len(months), months[0], months[-1])
    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(_month, p, cache_dir, p.year >= today.year - 1, source): p for p in months}
        try:
            for future in as_completed(pending):
                try:
                    records.append(future.result())
                except Exception as exc:
                    raise RuntimeError(f"Final CHIRPS v3 month {pending[future]} failed: {exc}") from exc
                if len(records) % 24 == 0:
                    logger.info("CHIRPS v3 regional months read: %d/%d", len(records), len(months))
        except Exception:
            for future in pending:
                future.cancel()
            raise
    records.sort(key=lambda r: r["date"])
    if len({r["land_mask_sha256"] for r in records}) != 1:
        raise ValueError("CHIRPS land support changed between months; refusing inconsistent regional means")
    frame = pd.DataFrame([{"date": pd.Timestamp(r["date"]) + pd.Timedelta(days=14), **r["values"]} for r in records])
    frame.attrs = {**PRODUCT_METADATA, "land_mask_sha256": records[0]["land_mask_sha256"],
                   "valid_pixel_counts": records[0]["valid_pixel_counts"], "extraction_records": [
        {key: r[key] for key in ("date", "source_url", "valid_pixel_counts", "window_sha256", "land_mask_sha256")}
        for r in records]}
    validate_product(frame)
    return frame
