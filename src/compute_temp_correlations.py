"""One-shot script: compute ENSO-temperature correlations and cache to Parquet.

Run this script once (or whenever you want to refresh the temperature analysis):

    python -m src.compute_temp_correlations

It will:
1. Download CPC Global Temperature data for all regions (1981-present).
2. Fetch ONI monthly time series from NOAA CPC.
3. Compute Pearson and Spearman correlations with n_eff correction.
4. Save results to data/processed/temp_correlations.parquet.

The daily build.py reads from the Parquet cache and includes it in enso.json.
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
    REGION_ORDER,
    SIGNIFICANCE_THRESHOLD,
)
from src.compute_correlations import align_oni_monthly, compute_n_eff
from src.fetch_enso import fetch_enso_snapshot
from src.fetch_temperature import build_temp_monthly_series
from src.utils import get_logger

logger = get_logger(__name__)

TEMP_CORRELATIONS_CACHE_PATH = "data/processed/temp_correlations.parquet"
TEMP_PAIRS_CACHE_PATH = "data/processed/oni_temp_pairs.parquet"

SEASON_MONTHS = {
    "SON": [9, 10, 11],
    "DEF": [12, 1, 2],
    "MAM": [3, 4, 5],
    "JJA": [6, 7, 8],
}


def _sig_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def compute_temp_correlations(
    temp_df: pd.DataFrame,
    oni_df: pd.DataFrame,
    lags: list[int] = CORRELATION_LAGS,
) -> pd.DataFrame:
    """Compute Pearson and Spearman correlations between ONI and temperature.

    Same methodology as precipitation correlations: ONI leads temperature
    by lag months, with Bretherton n_eff correction.
    """
    temp_df = temp_df.copy()
    oni_df = oni_df.copy()
    temp_df["ym"] = temp_df["date"].dt.to_period("M")
    oni_df["ym"] = oni_df["date"].dt.to_period("M")

    records = []
    regions = [c for c in temp_df.columns if c not in ("date", "ym")]

    for lag in lags:
        oni_shifted = oni_df.copy()
        oni_shifted["ym"] = oni_shifted["ym"] + lag
        merged = temp_df.merge(oni_shifted[["ym", "oni"]], on="ym", how="inner")

        for region in regions:
            if region not in merged.columns:
                continue
            paired = merged[["oni", region]].dropna()
            n = len(paired)
            if n < 30:
                continue

            x = paired["oni"].values
            y = paired[region].values

            pr, pp_naive = stats.pearsonr(x, y)
            sr, sp = stats.spearmanr(x, y)
            n_eff = compute_n_eff(x, y)

            if n_eff > 2 and abs(pr) < 1.0:
                t_stat = pr * np.sqrt((n_eff - 2) / (1 - pr**2))
                pp = float(2 * stats.t.sf(abs(t_stat), df=n_eff - 2))
            else:
                pp = pp_naive

            records.append({
                "region": region,
                "lag": lag,
                "pearson_r": round(float(pr), 4),
                "pearson_p": round(float(pp), 4),
                "pearson_stars": _sig_stars(pp),
                "spearman_r": round(float(sr), 4),
                "spearman_p": round(float(sp), 4),
                "n_obs": n,
                "n_eff": n_eff,
            })

    return pd.DataFrame(records)


def compute_seasonal_temp_correlations(
    temp_df: pd.DataFrame,
    oni_df: pd.DataFrame,
    lags: list[int] = CORRELATION_LAGS,
) -> dict:
    """Compute seasonal temperature correlations (SON/DEF/MAM/JJA)."""
    temp_df = temp_df.copy()
    oni_df = oni_df.copy()
    temp_df["ym"] = temp_df["date"].dt.to_period("M")
    temp_df["month"] = temp_df["date"].dt.month
    oni_df["ym"] = oni_df["date"].dt.to_period("M")

    result = {}
    for season_name, months_list in SEASON_MONTHS.items():
        season_temp = temp_df[temp_df["month"].isin(months_list)]
        records = []
        for lag in lags:
            oni_shifted = oni_df.copy()
            oni_shifted["ym"] = oni_shifted["ym"] + lag
            merged = season_temp.merge(oni_shifted[["ym", "oni"]], on="ym", how="inner")

            for region in REGION_ORDER:
                if region not in merged.columns:
                    continue
                paired = merged[["oni", region]].dropna()
                n = len(paired)
                if n < 20:
                    continue
                x = paired["oni"].values
                y = paired[region].values

                pr, pp_naive = stats.pearsonr(x, y)
                sr, sp = stats.spearmanr(x, y)
                n_eff = compute_n_eff(x, y)

                if n_eff > 2 and abs(pr) < 1.0:
                    t_stat = pr * np.sqrt((n_eff - 2) / (1 - pr**2))
                    pp = float(2 * stats.t.sf(abs(t_stat), df=n_eff - 2))
                else:
                    pp = pp_naive

                records.append({
                    "region": region,
                    "lag": lag,
                    "pearson_r": round(float(pr), 4),
                    "pearson_p": round(float(pp), 4),
                    "pearson_stars": _sig_stars(pp),
                    "spearman_r": round(float(sr), 4),
                    "spearman_p": round(float(sp), 4),
                    "n_obs": n,
                    "n_eff": n_eff,
                })
        result[season_name] = records
    return result


def run(start_year: int = CHIRPS_START_YEAR, end_year: int | None = None) -> None:
    """Execute the full temperature correlation pipeline."""
    import datetime as dt

    if end_year is None:
        end_year = dt.date.today().year - 1

    logger.info("=== compute_temp_correlations: start (%d-%d) ===", start_year, end_year)

    # 1. Fetch ONI
    logger.info("Fetching ONI from NOAA...")
    snapshot = fetch_enso_snapshot()
    oni_monthly = align_oni_monthly(snapshot.oni_series)

    # 2. Build temperature series
    logger.info("Building CPC temperature series...")
    temp_df = build_temp_monthly_series(start_year=start_year, end_year=end_year)

    # 3. Compute annual correlations
    logger.info("Computing temperature correlations...")
    corr_df = compute_temp_correlations(temp_df, oni_monthly)

    # 4. Save correlations
    computed_at = datetime.now(timezone.utc).isoformat()
    corr_df["start_year"] = start_year
    corr_df["end_year"] = end_year
    corr_df["computed_at"] = computed_at

    out_path = Path(TEMP_CORRELATIONS_CACHE_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    corr_df.to_parquet(out_path, index=False)
    logger.info("Saved %s (%d rows)", out_path, len(corr_df))

    # 5. Save ONI-temperature pairs
    temp_ym = temp_df.copy()
    temp_ym["ym"] = temp_ym["date"].dt.to_period("M")
    oni_ym = oni_monthly.copy()
    oni_ym["ym"] = oni_monthly["date"].dt.to_period("M")
    pairs = temp_ym.merge(oni_ym[["ym", "oni"]], on="ym", how="inner").drop(columns=["ym"])
    pairs_path = Path(TEMP_PAIRS_CACHE_PATH)
    pairs.to_parquet(pairs_path, index=False)
    logger.info("Saved %s (%d rows)", pairs_path, len(pairs))

    # Summary
    sig_mask = corr_df["pearson_p"] < SIGNIFICANCE_THRESHOLD
    logger.info(
        "=== Summary: %d/%d significant (p<%.2f) ===",
        sig_mask.sum(), len(corr_df), SIGNIFICANCE_THRESHOLD,
    )
    print(corr_df.to_string())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
