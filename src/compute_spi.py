"""Compute SPI-3 (3-month Standardized Precipitation Index) from CHIRPS data.

SPI methodology:
1. Compute 3-month rolling precipitation sum for each region.
2. For each calendar month, fit a gamma distribution to the 3-month totals.
3. Transform to standard normal via the gamma CDF -> inverse normal CDF.

References:
    McKee, T.B., Doesken, N.J., Kleist, J. (1993). The relationship of drought
    frequency and duration to time scales. AMS Conf. on Applied Climatology.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import gamma, norm

from src.config import REGION_ORDER
from src.utils import get_logger

logger = get_logger(__name__)

SPI_WINDOW = 3

SPI_CLASSES = {
    "sequia_extrema":   (-np.inf, -2.0),
    "sequia_severa":    (-2.0, -1.5),
    "sequia_moderada":  (-1.5, -1.0),
    "normal":           (-1.0, 1.0),
    "humedad_moderada": (1.0, 1.5),
    "humedad_severa":   (1.5, 2.0),
    "humedad_extrema":  (2.0, np.inf),
}

SPI_LABELS_ES = {
    "sequia_extrema":   "Sequía extrema",
    "sequia_severa":    "Sequía severa",
    "sequia_moderada":  "Sequía moderada",
    "normal":           "Normal",
    "humedad_moderada": "Humedad moderada",
    "humedad_severa":   "Humedad severa",
    "humedad_extrema":  "Humedad extrema",
}


def classify_spi(value: float) -> str:
    """Classify SPI into drought/wet category."""
    for name, (lo, hi) in SPI_CLASSES.items():
        if lo <= value < hi:
            return name
    return "normal"


def compute_spi(precip_series: pd.Series, window: int = SPI_WINDOW) -> pd.Series:
    """Compute SPI for a single region's monthly precipitation series.

    Uses rolling 3-month accumulation, then fits gamma distribution
    per calendar month, transforms to standard normal.

    Args:
        precip_series: Monthly precipitation (mm) indexed by date.
        window: Accumulation window in months.

    Returns:
        SPI values as pd.Series (same index as input, first window-1 values NaN).
    """
    # Rolling sum
    rolling = precip_series.rolling(window=window, min_periods=window).sum()

    # For each calendar month, fit gamma and transform
    spi = pd.Series(np.nan, index=precip_series.index)
    months = precip_series.index.month

    for m in range(1, 13):
        mask = months == m
        vals = rolling[mask].dropna()
        if len(vals) < 10:
            continue

        # Remove zeros for gamma fitting (gamma is defined for x > 0)
        nonzero = vals[vals > 0]
        q_zero = 1.0 - len(nonzero) / len(vals)

        if len(nonzero) < 5:
            continue

        try:
            # Fit gamma distribution (MLE)
            alpha, loc, beta = gamma.fit(nonzero.values, floc=0)

            # Transform: CDF of gamma -> inverse CDF of normal
            for idx in vals.index:
                x = rolling.loc[idx]
                if np.isnan(x):
                    continue
                if x <= 0:
                    # Handle zero precipitation
                    prob = q_zero / 2
                else:
                    prob = q_zero + (1 - q_zero) * gamma.cdf(x, alpha, loc=0, scale=beta)

                # Clamp to avoid infinite SPI
                prob = np.clip(prob, 0.001, 0.999)
                spi.loc[idx] = float(norm.ppf(prob))
        except Exception:
            # Gamma fit failed for this month — leave as NaN
            continue

    return spi


def compute_all_spi(pairs_df: pd.DataFrame) -> tuple[dict, dict]:
    """Compute SPI-3 for all regions.

    Args:
        pairs_df: DataFrame with columns date and one column per region.

    Returns:
        (spi_series, spi_current)
        spi_series: {region: [{date, spi, classification, label}]}
        spi_current: {region: {spi, classification, label, date}}
    """
    df = pairs_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    region_cols = [c for c in REGION_ORDER if c in df.columns]

    spi_series = {}
    spi_current = {}

    for region in region_cols:
        precip = df[region].dropna()
        if len(precip) < 36:  # Need at least 3 years
            continue

        spi_vals = compute_spi(precip)
        valid = spi_vals.dropna()

        if len(valid) == 0:
            continue

        # Build series records
        records = []
        for dt, val in valid.items():
            cls = classify_spi(val)
            records.append({
                "date": dt.date().isoformat(),
                "spi": round(float(val), 2),
                "classification": cls,
                "label": SPI_LABELS_ES[cls],
            })
        spi_series[region] = records

        # Current value (latest)
        last = records[-1]
        spi_current[region] = {
            "spi": last["spi"],
            "classification": last["classification"],
            "label": last["label"],
            "date": last["date"],
        }

    logger.info(
        "SPI-3: %d regions, %d total records",
        len(spi_series),
        sum(len(v) for v in spi_series.values()),
    )
    return spi_series, spi_current
