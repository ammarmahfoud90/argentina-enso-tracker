"""Unit tests for scientific computations in the ENSO tracker.

Covers: episode detection, SPI, composites, SAM parsing, n_eff, signal strength.
"""
import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Episode detection
# ---------------------------------------------------------------------------

class TestEpisodeDetection:
    """Tests for build.compute_episodes()."""

    @staticmethod
    def _make_oni(values):
        """Helper: create ONI DataFrame from a list of values."""
        dates = pd.date_range("2000-01-15", periods=len(values), freq="MS") + pd.Timedelta(days=14)
        return pd.DataFrame({"date": dates, "oni": values, "season": "X", "year": 2000})

    def test_el_nino_five_consecutive(self):
        from build import compute_episodes
        oni = self._make_oni([0.0] * 3 + [0.6] * 6 + [0.0] * 3)
        eps = compute_episodes(oni)
        assert len(eps) == 1
        assert eps[0]["type"] == "El Ni\u00f1o"

    def test_la_nina_five_consecutive(self):
        from build import compute_episodes
        oni = self._make_oni([0.0] * 3 + [-0.7] * 7 + [0.0] * 3)
        eps = compute_episodes(oni)
        assert len(eps) == 1
        assert eps[0]["type"] == "La Ni\u00f1a"

    def test_too_short_not_episode(self):
        from build import compute_episodes
        # Only 4 consecutive months >= 0.5 — should NOT trigger
        oni = self._make_oni([0.0] * 3 + [0.8] * 4 + [0.0] * 3)
        eps = compute_episodes(oni)
        assert len(eps) == 0

    def test_neutral_no_episodes(self):
        from build import compute_episodes
        oni = self._make_oni([0.1, -0.2, 0.3, -0.1, 0.0, 0.2])
        eps = compute_episodes(oni)
        assert len(eps) == 0

    def test_episode_at_end_of_series(self):
        from build import compute_episodes
        # Series ends while still in El Nino
        oni = self._make_oni([0.0] * 3 + [1.0] * 8)
        eps = compute_episodes(oni)
        assert len(eps) == 1


# ---------------------------------------------------------------------------
# SPI
# ---------------------------------------------------------------------------

class TestSPI:
    """Tests for src.compute_spi."""

    def test_classify_spi_extreme_drought(self):
        from src.compute_spi import classify_spi
        assert classify_spi(-2.5) == "sequia_extrema"

    def test_classify_spi_normal(self):
        from src.compute_spi import classify_spi
        assert classify_spi(0.0) == "normal"
        assert classify_spi(-0.99) == "normal"
        assert classify_spi(0.99) == "normal"

    def test_classify_spi_wet_extreme(self):
        from src.compute_spi import classify_spi
        assert classify_spi(2.5) == "humedad_extrema"

    def test_classify_spi_boundaries(self):
        """Boundary values: lower bound is inclusive, upper exclusive."""
        from src.compute_spi import classify_spi
        # -2.0 is the upper bound of sequia_extrema (exclusive), so it falls into sequia_severa
        # SPI_CLASSES uses [lo, hi) — first matching range wins
        assert classify_spi(-2.01) == "sequia_extrema"
        assert classify_spi(-2.0) == "sequia_severa"   # -2.0 is lo of sequia_severa
        assert classify_spi(-1.5) == "sequia_moderada"  # -1.5 is lo of sequia_moderada
        assert classify_spi(-1.0) == "normal"           # -1.0 is lo of normal
        assert classify_spi(1.0) == "humedad_moderada"
        assert classify_spi(1.5) == "humedad_severa"
        assert classify_spi(2.0) == "humedad_extrema"

    def test_compute_spi_output_range(self):
        """SPI should produce values roughly in [-3, 3] for normal data."""
        from src.compute_spi import compute_spi
        np.random.seed(42)
        # Simulate 20 years of monthly precipitation (gamma-distributed)
        precip = pd.Series(
            np.random.gamma(shape=2, scale=50, size=240),
            index=pd.date_range("2000-01-15", periods=240, freq="MS"),
        )
        spi = compute_spi(precip)
        valid = spi.dropna()
        assert len(valid) > 200  # most values should be computed
        assert valid.min() > -4  # no wildly extreme values
        assert valid.max() < 4

    def test_compute_spi_mean_near_zero(self):
        """SPI of stationary data should have mean close to 0."""
        from src.compute_spi import compute_spi
        np.random.seed(123)
        precip = pd.Series(
            np.random.gamma(shape=5, scale=20, size=480),
            index=pd.date_range("1980-01-15", periods=480, freq="MS"),
        )
        spi = compute_spi(precip)
        valid = spi.dropna()
        assert abs(valid.mean()) < 0.15  # should be near 0


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------

class TestComposites:
    """Tests for src.compute_composites."""

    @staticmethod
    def _make_pairs():
        """Create synthetic ONI-precipitation pairs for 20 years."""
        np.random.seed(42)
        dates = pd.date_range("2000-01-15", periods=240, freq="MS")
        df = pd.DataFrame({
            "date": dates,
            "oni": np.tile([0.0, 0.3, 0.8, 1.2, 1.8, 2.5,
                            -0.3, -0.8, -1.2, -1.8, -2.5, 0.0], 20),
            "Pampa H\u00fameda": np.random.gamma(3, 30, 240),
            "NEA": np.random.gamma(4, 25, 240),
        })
        return df

    def test_composites_structure(self):
        from src.compute_composites import compute_composites
        pairs = self._make_pairs()
        result = compute_composites(pairs)
        assert "Pampa H\u00fameda" in result
        assert "NEA" in result
        for region in result.values():
            for season in region.values():
                for cell in season.values():
                    assert "mean_anomaly_mm" in cell
                    assert "mean_anomaly_pct" in cell
                    assert "n_seasons" in cell
                    assert cell["n_seasons"] >= 1

    def test_intensity_classification(self):
        from src.compute_composites import _classify_intensity
        assert _classify_intensity(0.7) == ("nino", "debil")
        assert _classify_intensity(1.3) == ("nino", "moderado")
        assert _classify_intensity(1.8) == ("nino", "fuerte")
        assert _classify_intensity(2.5) == ("nino", "muy_fuerte")
        assert _classify_intensity(-0.7) == ("nina", "debil")
        assert _classify_intensity(-2.5) == ("nina", "muy_fuerte")
        assert _classify_intensity(0.3) == (None, None)
        assert _classify_intensity(0.0) == (None, None)


# ---------------------------------------------------------------------------
# SAM parsing
# ---------------------------------------------------------------------------

class TestSAMParsing:
    """Tests for src.fetch_sam.parse_aao."""

    SAMPLE_DATA = """\
 1979   0.25  -0.54   1.30   0.93  -1.10   0.06  -0.97   1.47  -0.64   0.01   0.32  -1.23
 1980  -0.11   0.88   0.27  -1.45   0.63  -0.78   1.12  -0.35   0.55  -0.02   0.74  -0.99
"""

    def test_parse_aao_basic(self):
        from src.fetch_sam import parse_aao
        df = parse_aao(self.SAMPLE_DATA)
        assert len(df) == 24  # 2 years x 12 months
        assert df.iloc[0]["sam"] == 0.25
        assert df.iloc[-1]["sam"] == -0.99

    def test_parse_aao_dates(self):
        from src.fetch_sam import parse_aao
        df = parse_aao(self.SAMPLE_DATA)
        assert df.iloc[0]["date"].year == 1979
        assert df.iloc[0]["date"].month == 1
        assert df.iloc[12]["date"].year == 1980

    def test_parse_aao_missing_values(self):
        """Values < -90 should be skipped."""
        from src.fetch_sam import parse_aao
        data = " 2020   0.50  -99.99   1.00  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99  -99.99   0.75\n"
        df = parse_aao(data)
        assert len(df) == 3  # only 3 valid values

    def test_parse_aao_empty_raises(self):
        from src.fetch_sam import parse_aao
        with pytest.raises(RuntimeError, match="No valid AAO"):
            parse_aao("header line only\n")

    def test_parse_aao_header_lines_skipped(self):
        """Lines with too few columns or non-numeric years are skipped."""
        from src.fetch_sam import parse_aao
        data = "Year  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec\n"
        data += " 2021   0.10   0.20   0.30   0.40   0.50   0.60   0.70   0.80   0.90   1.00   1.10   1.20\n"
        df = parse_aao(data)
        assert len(df) == 12


# ---------------------------------------------------------------------------
# n_eff (Bretherton correction)
# ---------------------------------------------------------------------------

class TestNEff:
    """Tests for compute_correlations.compute_n_eff."""

    def test_white_noise_neff_near_n(self):
        """White noise has no autocorrelation, so n_eff ~ n."""
        from src.compute_correlations import compute_n_eff
        np.random.seed(42)
        x = np.random.randn(100)
        y = np.random.randn(100)
        n_eff = compute_n_eff(x, y)
        assert n_eff >= 80  # should be close to 100

    def test_autocorrelated_reduces_neff(self):
        """Strongly autocorrelated series should have n_eff << n."""
        from src.compute_correlations import compute_n_eff
        np.random.seed(42)
        # Create autocorrelated series (AR1)
        n = 200
        x = np.zeros(n)
        y = np.zeros(n)
        for i in range(1, n):
            x[i] = 0.9 * x[i-1] + np.random.randn()
            y[i] = 0.9 * y[i-1] + np.random.randn()
        n_eff = compute_n_eff(x, y)
        assert n_eff < 100  # much less than 200
        assert n_eff >= 3   # minimum floor

    def test_short_series_returns_n(self):
        """Series < 10 should return n directly."""
        from src.compute_correlations import compute_n_eff
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        assert compute_n_eff(x, y) == 5


# ---------------------------------------------------------------------------
# Signal strength label
# ---------------------------------------------------------------------------

class TestSignalStrength:
    """Tests for build._signal_strength_label."""

    def test_not_significant(self):
        from build import _signal_strength_label
        assert _signal_strength_label(0.5, False) == "no significativa"

    def test_strong(self):
        from build import _signal_strength_label
        assert _signal_strength_label(0.40, True) == "fuerte"

    def test_moderate(self):
        from build import _signal_strength_label
        assert _signal_strength_label(0.25, True) == "moderada"

    def test_weak(self):
        from build import _signal_strength_label
        assert _signal_strength_label(0.15, True) == "d\u00e9bil"


# ---------------------------------------------------------------------------
# Significance stars
# ---------------------------------------------------------------------------

class TestSigStars:
    """Tests for build._sig_stars."""

    def test_three_stars(self):
        from build import _sig_stars
        assert _sig_stars(0.0005) == "***"

    def test_two_stars(self):
        from build import _sig_stars
        assert _sig_stars(0.005) == "**"

    def test_one_star(self):
        from build import _sig_stars
        assert _sig_stars(0.03) == "*"

    def test_no_stars(self):
        from build import _sig_stars
        assert _sig_stars(0.1) == ""
