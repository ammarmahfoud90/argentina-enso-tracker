"""One-shot script: compute ENSO–precipitation correlations and cache to Parquet.

Run this script once (or whenever you want to refresh the historical analysis):

    python -m src.compute_correlations

It will:
1. Download CHIRPS monthly precipitation for 1981–(current year - 1).
2. Fetch ONI monthly time series from NOAA CPC.
3. Compute Pearson and Spearman correlations for each region × lag combination.
4. Save results to ``data/processed/correlations.parquet``.

The Streamlit dashboard reads from the Parquet cache; it never re-runs this
computation at runtime.

Output Parquet schema:
    region          str      Region name (one of REGIONS keys)
    lag             int      ONI lead in months (0, 1, 2, 3)
    pearson_r       float    Pearson correlation coefficient
    pearson_p       float    Pearson p-value (two-tailed)
    spearman_r      float    Spearman correlation coefficient
    spearman_p      float    Spearman p-value (two-tailed)
    n_obs           int      Number of valid paired observations
    start_year      int      First year included
    end_year        int      Last year included
    version         str      Cache version string
    computed_at     str      ISO timestamp of computation
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.config import (
    CHIRPS_START_YEAR,
    CORRELATION_LAGS,
    CORRELATIONS_CACHE_PATH,
    CORRELATIONS_CACHE_VERSION,
    REGIONS,
    SIGNIFICANCE_THRESHOLD,
)
from src.fetch_chirps import build_chirps_monthly_series
from src.fetch_enso import fetch_enso_snapshot
from src.utils import get_logger

logger = get_logger(__name__)


def align_oni_monthly(oni_series: pd.DataFrame) -> pd.DataFrame:
    """Resample ONI to a clean monthly series aligned to the 15th of each month.

    The ONI seasonal series (DJF, JFM, …) is converted to monthly by
    assigning each 3-month season's anomaly to its middle month.  This
    is the same convention used in :func:`parse_oni`.

    Args:
        oni_series: DataFrame from :func:`~src.fetch_enso.parse_oni` with
            columns ``date``, ``season``, ``year``, ``oni``.

    Returns:
        DataFrame with columns ``date`` (monthly, day=15) and ``oni``.
    """
    df = oni_series[["date", "oni"]].copy()
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp() + pd.Timedelta(days=14)
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def compute_correlations(
    chirps_df: pd.DataFrame,
    oni_df: pd.DataFrame,
    lags: list[int] = CORRELATION_LAGS,
) -> pd.DataFrame:
    """Compute Pearson and Spearman correlations between ONI and precipitation.

    For each region and each lag, the ONI series is shifted forward by
    ``lag`` months (so ONI at time t is compared to precipitation at t+lag),
    representing ONI leading precipitation.

    Args:
        chirps_df: Monthly precipitation DataFrame with ``date`` column and
            one column per region (mm/month).
        oni_df: Monthly ONI DataFrame with columns ``date`` and ``oni``.
        lags: List of lag values in months.

    Returns:
        DataFrame with columns:
        ``region``, ``lag``, ``pearson_r``, ``pearson_p``,
        ``spearman_r``, ``spearman_p``, ``n_obs``.
    """
    # Align dates to year-month for merging
    chirps_df = chirps_df.copy()
    oni_df = oni_df.copy()
    chirps_df["ym"] = chirps_df["date"].dt.to_period("M")
    oni_df["ym"] = oni_df["date"].dt.to_period("M")

    records = []
    regions = [c for c in chirps_df.columns if c not in ("date", "ym")]

    for lag in lags:
        # Shift ONI forward by lag months — ONI leads precipitation
        oni_shifted = oni_df.copy()
        oni_shifted["ym"] = oni_shifted["ym"] + lag

        merged = chirps_df.merge(oni_shifted[["ym", "oni"]], on="ym", how="inner")

        for region in regions:
            if region not in merged.columns:
                continue

            paired = merged[["oni", region]].dropna()
            n = len(paired)
            if n < 30:
                logger.warning(
                    "Insuficientes datos para %s lag=%d (n=%d); omitiendo", region, lag, n
                )
                continue

            x = paired["oni"].values
            y = paired[region].values

            pearson_r, pearson_p = stats.pearsonr(x, y)
            spearman_r, spearman_p = stats.spearmanr(x, y)

            records.append(
                {
                    "region": region,
                    "lag": lag,
                    "pearson_r": round(float(pearson_r), 4),
                    "pearson_p": round(float(pearson_p), 4),
                    "spearman_r": round(float(spearman_r), 4),
                    "spearman_p": round(float(spearman_p), 4),
                    "n_obs": n,
                }
            )
            sig = "✓" if pearson_p < SIGNIFICANCE_THRESHOLD else " "
            logger.info(
                "[%s] %s lag=%d  r=%.3f p=%.3f %s",
                sig, region, lag, pearson_r, pearson_p, "(significativo)" if sig == "✓" else "",
            )

    return pd.DataFrame(records)


def run(start_year: int = CHIRPS_START_YEAR, end_year: int | None = None) -> None:
    """Execute the full correlation pipeline and write the Parquet cache.

    Args:
        start_year: First year of CHIRPS data to include.
        end_year: Last year of CHIRPS data (default: current year - 1).
    """
    import datetime as dt

    if end_year is None:
        end_year = dt.date.today().year - 1

    logger.info("=== compute_correlations: inicio (%d–%d) ===", start_year, end_year)

    # 1. Fetch ONI
    logger.info("Obteniendo ONI desde NOAA…")
    snapshot = fetch_enso_snapshot()
    oni_monthly = align_oni_monthly(snapshot.oni_series)
    logger.info("ONI mensual: %d registros", len(oni_monthly))

    # 2. Build CHIRPS series
    logger.info("Construyendo serie CHIRPS…")
    chirps_df = build_chirps_monthly_series(start_year=start_year, end_year=end_year)
    logger.info("CHIRPS: %d registros mensuales", len(chirps_df))

    # 3. Compute correlations
    logger.info("Calculando correlaciones…")
    corr_df = compute_correlations(chirps_df, oni_monthly)

    # 4. Add metadata columns
    computed_at = datetime.now(timezone.utc).isoformat()
    corr_df["start_year"] = start_year
    corr_df["end_year"] = end_year
    corr_df["version"] = CORRELATIONS_CACHE_VERSION
    corr_df["computed_at"] = computed_at

    # 5. Save to Parquet
    out_path = Path(CORRELATIONS_CACHE_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    corr_df.to_parquet(out_path, index=False)
    logger.info("Parquet guardado en %s (%d filas)", out_path, len(corr_df))

    # Summary
    sig_mask = corr_df["pearson_p"] < SIGNIFICANCE_THRESHOLD
    logger.info(
        "=== Resumen: %d/%d correlaciones significativas (p<%.2f) ===",
        sig_mask.sum(), len(corr_df), SIGNIFICANCE_THRESHOLD,
    )
    print(corr_df.to_string())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
