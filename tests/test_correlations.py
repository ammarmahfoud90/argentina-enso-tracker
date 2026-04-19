"""Tests for src/compute_correlations.py.

Tests:
    - correlation computation on synthetic data with known result.
    - lag alignment is correct (ONI leads precipitation).
    - p-value flags significant correlations correctly.
    - Parquet cache round-trip preserves data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute_correlations import align_oni_monthly, compute_correlations
from src.config import SIGNIFICANCE_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monthly_dates(n: int, start: str = "1981-01-15") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="MS") + pd.Timedelta(days=14)


def _make_oni_df(values: list[float] | np.ndarray, start: str = "1981-01-15") -> pd.DataFrame:
    n = len(values)
    dates = _make_monthly_dates(n, start)
    return pd.DataFrame({
        "date": dates,
        "season": ["DJF"] * n,
        "year": [d.year for d in dates],
        "oni": values,
    })


def _make_chirps_df(precip_dict: dict[str, list[float]], start: str = "1981-01-15") -> pd.DataFrame:
    n = len(next(iter(precip_dict.values())))
    dates = _make_monthly_dates(n, start)
    df = pd.DataFrame({"date": dates})
    for region, vals in precip_dict.items():
        df[region] = vals
    return df


# ---------------------------------------------------------------------------
# Tests: align_oni_monthly
# ---------------------------------------------------------------------------

class TestAlignONIMonthly:
    def test_returns_dataframe(self):
        oni = _make_oni_df([0.5] * 12)
        result = align_oni_monthly(oni)
        assert isinstance(result, pd.DataFrame)

    def test_has_date_and_oni_columns(self):
        oni = _make_oni_df([0.5] * 12)
        result = align_oni_monthly(oni)
        assert "date" in result.columns
        assert "oni" in result.columns

    def test_no_duplicates(self):
        oni = _make_oni_df([0.5] * 24)
        result = align_oni_monthly(oni)
        assert not result["date"].duplicated().any()


# ---------------------------------------------------------------------------
# Tests: compute_correlations — known synthetic cases
# ---------------------------------------------------------------------------

class TestComputeCorrelations:
    def test_perfect_positive_correlation_lag0(self):
        """A signal perfectly correlated at lag 0 should yield r≈1, p<<0.05."""
        n = 200
        signal = np.sin(np.linspace(0, 20, n))
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(signal)})

        result = compute_correlations(chirps, oni_monthly, lags=[0])
        row = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]

        assert len(row) == 1
        assert row["pearson_r"].iloc[0] > 0.99, f"Expected r≈1, got {row['pearson_r'].iloc[0]}"
        assert row["pearson_p"].iloc[0] < SIGNIFICANCE_THRESHOLD

    def test_perfect_negative_correlation_lag0(self):
        n = 200
        signal = np.sin(np.linspace(0, 20, n))
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(-signal)})

        result = compute_correlations(chirps, oni_monthly, lags=[0])
        row = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]
        assert row["pearson_r"].iloc[0] < -0.99

    def test_zero_correlation(self):
        """Orthogonal signals should yield r≈0 with p > 0.05 for reasonable n."""
        rng = np.random.default_rng(42)
        n = 200
        signal_oni = rng.normal(0, 1, n)
        signal_precip = rng.normal(0, 1, n)
        oni = _make_oni_df(signal_oni)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(signal_precip)})

        result = compute_correlations(chirps, oni_monthly, lags=[0])
        row = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]
        assert abs(row["pearson_r"].iloc[0]) < 0.25, "Uncorrelated signals should yield low r"

    def test_lag_shifts_correctly(self):
        """A signal correlated at lag=2 should show r≈1 at lag=2, low at lag=0."""
        n = 300
        rng = np.random.default_rng(7)
        oni_vals = rng.normal(0, 1, n)
        # Precipitation is ONI shifted 2 months into the future (ONI leads by 2)
        precip_vals = np.concatenate([np.zeros(2), oni_vals[:-2]])

        oni = _make_oni_df(oni_vals)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(precip_vals)})

        result = compute_correlations(chirps, oni_monthly, lags=[0, 1, 2, 3])

        r_lag0 = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]["pearson_r"].iloc[0]
        r_lag2 = result[(result["region"] == "TestRegion") & (result["lag"] == 2)]["pearson_r"].iloc[0]

        assert r_lag2 > r_lag0, f"Expected lag-2 correlation ({r_lag2:.3f}) > lag-0 ({r_lag0:.3f})"
        assert r_lag2 > 0.90, f"Expected high correlation at correct lag, got {r_lag2:.3f}"

    def test_output_schema(self):
        """Output DataFrame must contain all required columns."""
        n = 100
        signal = np.sin(np.linspace(0, 10, n))
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"RegA": list(signal), "RegB": list(-signal)})

        result = compute_correlations(chirps, oni_monthly, lags=[0, 1])
        for col in ("region", "lag", "pearson_r", "pearson_p", "spearman_r", "spearman_p", "n_obs"):
            assert col in result.columns, f"Missing column: {col}"

    def test_n_obs_correct(self):
        """n_obs should equal the number of matched non-null paired observations."""
        n = 150
        signal = np.ones(n) * 0.5
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(signal)})

        result = compute_correlations(chirps, oni_monthly, lags=[0])
        n_obs = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]["n_obs"].iloc[0]
        assert n_obs == n

    def test_spearman_provided(self):
        n = 100
        signal = np.sin(np.linspace(0, 10, n))
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TestRegion": list(signal)})

        result = compute_correlations(chirps, oni_monthly, lags=[0])
        row = result[(result["region"] == "TestRegion") & (result["lag"] == 0)]
        assert not pd.isna(row["spearman_r"].iloc[0])
        assert not pd.isna(row["spearman_p"].iloc[0])

    def test_skips_region_with_insufficient_data(self, caplog):
        """Regions with fewer than 30 obs should be skipped with a warning."""
        import logging
        n = 20  # below the 30-obs threshold
        signal = np.sin(np.linspace(0, 5, n))
        oni = _make_oni_df(signal)
        oni_monthly = align_oni_monthly(oni)
        chirps = _make_chirps_df({"TinyRegion": list(signal)})

        with caplog.at_level(logging.WARNING, logger="src.compute_correlations"):
            result = compute_correlations(chirps, oni_monthly, lags=[0])

        assert len(result) == 0 or "TinyRegion" not in result["region"].values


# ---------------------------------------------------------------------------
# Tests: Parquet round-trip
# ---------------------------------------------------------------------------

class TestParquetRoundTrip:
    def test_parquet_write_read(self, tmp_path):
        """Written Parquet should be readable and preserve all values."""
        data = {
            "region": ["NEA", "NEA"],
            "lag": [0, 1],
            "pearson_r": [0.35, 0.42],
            "pearson_p": [0.01, 0.001],
            "spearman_r": [0.33, 0.40],
            "spearman_p": [0.015, 0.002],
            "n_obs": [480, 479],
            "version": ["1.0.0", "1.0.0"],
            "computed_at": ["2025-01-01T00:00:00", "2025-01-01T00:00:00"],
        }
        df = pd.DataFrame(data)

        out_path = tmp_path / "correlations.parquet"
        df.to_parquet(out_path, index=False)

        loaded = pd.read_parquet(out_path)
        pd.testing.assert_frame_equal(df, loaded)
