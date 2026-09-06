"""Compute precipitation composites stratified by ENSO intensity class.

Uses the existing ONI-precipitation pairs Parquet to compute mean
precipitation anomalies for each region x season x ENSO intensity bin.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from src.config import ENSO_EL_NINO_THRESHOLD, ENSO_LA_NINA_THRESHOLD, REGION_ORDER
from src.utils import get_logger

logger = get_logger(__name__)

INTENSITY_BINS = {
    "debil":       (0.5, 1.0),
    "moderado":    (1.0, 1.5),
    "fuerte":      (1.5, 2.0),
    "muy_fuerte":  (2.0, 99.0),
}

SEASON_MONTHS = {
    "SON": [9, 10, 11],
    "DEF": [12, 1, 2],
    "MAM": [3, 4, 5],
    "JJA": [6, 7, 8],
}


def _assign_season(month: int) -> str:
    if month in (9, 10, 11):
        return "SON"
    if month in (12, 1, 2):
        return "DEF"
    if month in (3, 4, 5):
        return "MAM"
    return "JJA"


def _classify_intensity(oni: float) -> tuple[str | None, str | None]:
    """Classify ONI into (phase, intensity) tuple. Returns (None, None) for Neutral."""
    if oni >= ENSO_EL_NINO_THRESHOLD:
        for name, (lo, hi) in INTENSITY_BINS.items():
            if lo <= oni < hi:
                return ("nino", name)
        return ("nino", "muy_fuerte")
    elif oni <= ENSO_LA_NINA_THRESHOLD:
        abs_oni = abs(oni)
        for name, (lo, hi) in INTENSITY_BINS.items():
            if lo <= abs_oni < hi:
                return ("nina", name)
        return ("nina", "muy_fuerte")
    return (None, None)


def compute_composites(pairs_df: pd.DataFrame) -> dict:
    """Compute mean precip anomaly by region x season x intensity x phase.

    Args:
        pairs_df: DataFrame with columns date, oni, and one column per region.

    Returns:
        Nested dict: {region: {season: {phase_intensity: {
            mean_anomaly_mm, mean_anomaly_pct, n_seasons
        }}}}
    """
    df = pairs_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["season"] = df["month"].apply(_assign_season)
    df["season_year"] = df["date"].dt.year
    df.loc[df["month"] == 12, "season_year"] = (
        df.loc[df["month"] == 12, "date"].dt.year + 1
    )

    region_cols = [c for c in REGION_ORDER if c in df.columns]

    # Group by season-year and season, compute seasonal means
    grouped = df.groupby(["season_year", "season"])
    precip_total = grouped[region_cols].sum()
    oni_mean = grouped["oni"].mean()
    month_count = grouped["month"].count()

    # Only keep complete seasons (3 months)
    complete = month_count == 3
    precip_total = precip_total[complete]
    oni_mean = oni_mean[complete]

    # Climatological mean per season per region
    clim = precip_total.groupby(level="season").mean()

    result = {}
    for region in region_cols:
        region_result = {}
        for season in ["SON", "DEF", "MAM", "JJA"]:
            season_result = {}
            try:
                s_precip = precip_total.xs(season, level="season")[region]
                s_oni = oni_mean.xs(season, level="season")
                s_clim = float(clim.loc[season, region])
            except KeyError:
                continue

            if s_clim == 0:
                continue

            for phase_label, phase_test in [
                ("nino", lambda o: o >= ENSO_EL_NINO_THRESHOLD),
                ("nina", lambda o: o <= ENSO_LA_NINA_THRESHOLD),
            ]:
                for intensity_name, (lo, hi) in INTENSITY_BINS.items():
                    if phase_label == "nino":
                        mask = (s_oni >= lo) & (s_oni < hi)
                    else:
                        mask = (s_oni <= -lo) & (s_oni > -hi)

                    subset = s_precip[mask]
                    n = len(subset)
                    if n < 1:
                        continue

                    mean_val = float(subset.mean())
                    anomaly = mean_val - s_clim
                    pct = round((anomaly / s_clim) * 100, 1)

                    key = f"{phase_label}_{intensity_name}"
                    season_result[key] = {
                        "mean_anomaly_mm": round(anomaly, 1),
                        "mean_anomaly_pct": pct,
                        "n_seasons": n,
                        "mean_precip_mm": round(mean_val, 1),
                        "clim_precip_mm": round(s_clim, 1),
                    }

            region_result[season] = season_result
        result[region] = region_result

    total_cells = sum(
        len(s) for r in result.values() for s in r.values()
    )
    logger.info("Composites: %d regions, %d total cells", len(result), total_cells)
    return result
