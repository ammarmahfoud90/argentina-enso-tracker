"""Tests for src/fetch_enso.py.

Tests:
    - NOAA source URLs are reachable (HTTP 200).
    - ONI parser returns expected schema and sensible values.
    - Niño 3.4 parser returns expected schema.
    - SOI parser returns expected schema.
    - ENSO phase classifier works for all three cases.
"""

from __future__ import annotations

import pytest
import pandas as pd

from src.fetch_enso import (
    classify_enso_phase,
    parse_nino34,
    parse_oni,
    parse_soi,
)
from src.config import (
    NOAA_ONI_URL,
    NOAA_NINO34_URL,
    NOAA_SOI_URL,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal synthetic ASCII snippets
# ---------------------------------------------------------------------------

ONI_SAMPLE = """\
 SEAS  YR   TOTAL   ANOM
  DJF 1950  24.72  -0.25
  JFM 1950  25.17   0.30
  FMA 1950  25.75   0.50
  MAM 1950  26.10   0.60
  AMJ 1950  26.20   0.60
  MJJ 1997  28.50   2.00
  JJA 1997  29.00   2.20
  JAS 1997  29.10   2.20
  ASO 1997  28.90   2.20
  SON 1997  28.80   2.20
  OND 1998  24.00  -2.30
  NDJ 1998  24.10  -2.30
  DJF 1999  24.20  -2.30
  JFM 1999  24.30  -2.30
  FMA 1999  24.40  -2.30
"""

NINO34_SAMPLE = """\
 YR  MON  NINO1+2  ANOM  NINO3  ANOM  NINO4  ANOM  NINO3.4  ANOM
1981   1   24.00  -0.10  26.00  -0.20  27.00  0.10  26.50   0.05
1981   2   24.50  -0.15  26.20  -0.15  27.10  0.05  26.60   0.10
1997   6   28.00   1.50  29.00   2.00  28.50  1.20  29.50   2.10
1997   7   29.00   2.20  30.00   2.50  28.80  1.30  30.00   2.50
"""

SOI_SAMPLE = """\
STANDARDIZED    TAHITI - DARWIN  SEA LEVEL PRESSURES
YEAR JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC
1951   1.4  2.0  0.5  1.2 -0.3  0.4  1.5  1.0  0.8  0.5  1.1  0.7
1952  -0.5  0.8  1.1 -0.2  0.9  0.5 -0.3  0.4  1.0 -0.1  0.6  0.2
1997  -2.1 -1.8 -1.5 -2.0 -2.5 -2.8 -2.3 -1.9 -2.2 -2.4 -2.1 -1.9
"""


# ---------------------------------------------------------------------------
# Unit tests — parsers
# ---------------------------------------------------------------------------

class TestParseONI:
    def test_returns_dataframe(self):
        df = parse_oni(ONI_SAMPLE)
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns(self):
        df = parse_oni(ONI_SAMPLE)
        for col in ("date", "season", "year", "oni"):
            assert col in df.columns, f"Missing column: {col}"

    def test_sorted_by_date(self):
        df = parse_oni(ONI_SAMPLE)
        assert df["date"].is_monotonic_increasing

    def test_oni_values_reasonable(self):
        df = parse_oni(ONI_SAMPLE)
        assert df["oni"].between(-5, 5).all(), "ONI values outside plausible range"

    def test_parses_known_value(self):
        df = parse_oni(ONI_SAMPLE)
        djf_1950 = df[(df["year"] == 1950) & (df["season"] == "DJF")]
        assert len(djf_1950) == 1
        assert abs(djf_1950["oni"].iloc[0] - (-0.25)) < 0.01

    def test_raises_on_empty_input(self):
        with pytest.raises(ValueError):
            parse_oni("")


class TestParseNino34:
    def test_returns_dataframe(self):
        df = parse_nino34(NINO34_SAMPLE)
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns(self):
        df = parse_nino34(NINO34_SAMPLE)
        for col in ("date", "nino34"):
            assert col in df.columns

    def test_nino34_values_reasonable(self):
        df = parse_nino34(NINO34_SAMPLE)
        assert df["nino34"].between(-5, 5).all()

    def test_filters_missing_values(self):
        sample_with_missing = NINO34_SAMPLE + "1999   3   -99.9  -99.9  -99.9  -99.9  -99.9  -99.9  -99.9  -99.9\n"
        df = parse_nino34(sample_with_missing)
        assert (df["nino34"] > -90).all()


class TestParseSOI:
    def test_returns_dataframe(self):
        df = parse_soi(SOI_SAMPLE)
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns(self):
        df = parse_soi(SOI_SAMPLE)
        for col in ("date", "soi"):
            assert col in df.columns

    def test_soi_values_reasonable(self):
        df = parse_soi(SOI_SAMPLE)
        assert df["soi"].between(-10, 10).all()


# ---------------------------------------------------------------------------
# Unit tests — ENSO phase classifier
# ---------------------------------------------------------------------------

def _make_oni_df(values: list[float]) -> pd.DataFrame:
    """Helper: create a minimal ONI DataFrame from a list of values."""
    dates = pd.date_range("2020-01-15", periods=len(values), freq="MS") + pd.Timedelta(days=14)
    return pd.DataFrame({
        "date": dates,
        "season": ["DJF"] * len(values),
        "year": [2020] * len(values),
        "oni": values,
    })


class TestClassifyENSOPhase:
    def test_el_nino(self):
        df = _make_oni_df([0.6, 0.7, 0.8, 0.9, 1.0])
        assert classify_enso_phase(df) == "El Niño"

    def test_la_nina(self):
        df = _make_oni_df([-0.6, -0.7, -0.8, -0.9, -1.0])
        assert classify_enso_phase(df) == "La Niña"

    def test_neutral_below_threshold(self):
        df = _make_oni_df([0.1, 0.2, 0.3, 0.4, 0.4])
        assert classify_enso_phase(df) == "Neutral"

    def test_neutral_mixed(self):
        # Four months El Niño, one neutral — should be Neutral (not 5 consecutive)
        df = _make_oni_df([0.6, 0.7, 0.8, 0.9, 0.3])
        assert classify_enso_phase(df) == "Neutral"

    def test_insufficient_data(self):
        df = _make_oni_df([0.6, 0.7])
        assert classify_enso_phase(df) == "Neutral"

    def test_exact_threshold_el_nino(self):
        df = _make_oni_df([0.5, 0.5, 0.5, 0.5, 0.5])
        assert classify_enso_phase(df) == "El Niño"

    def test_exact_threshold_la_nina(self):
        df = _make_oni_df([-0.5, -0.5, -0.5, -0.5, -0.5])
        assert classify_enso_phase(df) == "La Niña"


# ---------------------------------------------------------------------------
# Integration tests — URL availability (network, can be slow)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSourceURLs:
    """Verify that NOAA source URLs respond with HTTP 200.

    Marked 'integration' — skip in CI without network:
        pytest -m 'not integration'
    """

    def test_oni_url_responds(self):
        import requests
        resp = requests.get(NOAA_ONI_URL, timeout=15)
        assert resp.status_code == 200, f"ONI URL returned {resp.status_code}"

    def test_nino34_url_responds(self):
        import requests
        resp = requests.get(NOAA_NINO34_URL, timeout=15)
        assert resp.status_code == 200, f"Niño 3.4 URL returned {resp.status_code}"

    def test_soi_url_responds(self):
        import requests
        resp = requests.get(NOAA_SOI_URL, timeout=15)
        assert resp.status_code == 200, f"SOI URL returned {resp.status_code}"

    def test_oni_parse_live(self):
        """Fetch live ONI and verify it parses to a non-empty DataFrame."""
        import requests
        resp = requests.get(NOAA_ONI_URL, timeout=15)
        df = parse_oni(resp.text)
        assert len(df) > 100, "Expected more than 100 ONI rows from live feed"
        assert df["oni"].notna().all()
