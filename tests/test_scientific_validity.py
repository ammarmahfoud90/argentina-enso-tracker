"""Regression checks for scientific definitions and calendar alignment."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src.compute_spi import classify_spi, compute_spi
from src.fetch_enso import fetch_operational_reference, parse_advisory, parse_oni
from src.scientific import (
    adjust_fdr,
    complete_seasons,
    correlations,
    frequencies,
    monthly_frame,
    notable_events,
)


def test_fdr_known_values_and_full_precision():
    records = [{"p": p} for p in [0.00000123, 0.01, 0.04, 0.2]]
    adjust_fdr(records, "p", "q")
    # Four-test harmonic factor is 25/12; independent analytic example.
    assert [r["q"] for r in records] == pytest.approx([0.00001025, 1/24, 1/9, 5/12])
    assert records[0]["p"] == 0.00000123  # must not round small p to zero


def test_fdr_dependent_family_not_selected_post_hoc():
    cells = [{"p": .02}] + [{"p": .5} for _ in range(39)]
    adjust_fdr(cells, "p", "q")
    assert cells[0]["q"] > .05


@pytest.mark.parametrize("p", [np.nan, -.1, 1.1])
def test_fdr_rejects_invalid_input(p):
    with pytest.raises(ValueError):
        adjust_fdr([{"p": p}], "p", "q")


def test_season_is_not_a_second_smoothing_of_oni():
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-12-15", "2021-01-15", "2021-02-15"]),
                          "oni": [-.2, -.8, .3], "NEA": [10., 20., 30.]})
    result = complete_seasons(frame)
    assert len(result) == 1
    assert result.iloc[0]["season"] == "DEF"
    assert result.iloc[0]["season_year"] == 2021
    assert result.iloc[0]["oni"] == -.8
    assert result.iloc[0]["NEA"] == 60.


def test_missing_month_and_missing_value_are_not_complete_totals():
    dates = pd.to_datetime(["2020-09-15", "2020-10-15", "2020-11-15"])
    frame = pd.DataFrame({"date": dates, "oni": [.6]*3, "NEA": [10., np.nan, 20.]})
    assert np.isnan(complete_seasons(frame).iloc[0]["NEA"])
    assert complete_seasons(frame.iloc[[0,2]]).empty


def test_calendar_duplicates_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        monthly_frame(pd.DataFrame({"date": ["2020-01-01", "2020-01-31"], "oni": [.5,.6]}))


def test_spi_missing_calendar_month_invalidates_three_windows():
    rng = np.random.default_rng(210)
    frame = pd.Series(rng.gamma(2, 50, 480), index=pd.date_range("1980-01-01", periods=480, freq="MS"))
    frame = frame.drop(pd.Timestamp("2000-03-01"))
    result = compute_spi(frame)
    assert np.isnan(result.loc["2000-03-15"])
    assert np.isnan(result.loc["2000-04-01"])
    assert np.isnan(result.loc["2000-05-01"])
    assert np.isfinite(result.loc["2000-06-01"])


@pytest.mark.parametrize("value,expected", [(-2,"sequia_extrema"),(-1.5,"sequia_severa"),(-1,"sequia_moderada"),(1,"humedad_moderada"),(1.5,"humedad_severa"),(2,"humedad_extrema")])
def test_wmo_spi_boundaries(value, expected):
    assert classify_spi(value) == expected


def test_roni_three_column_format():
    result = parse_oni("SEAS YR ANOM\nJJA 2026 1.36\nJAS 2026 1.69\n")
    assert result.iloc[-1].oni == 1.69
    assert result.iloc[-1].date == pd.Timestamp("2026-08-15")


def test_dated_official_advisory():
    result = parse_advisory("<p>Issued: 8 October 2026</p><b>ENSO Alert System Status:</b> El Ni&ntilde;o Advisory")
    assert result["issued"] == "2026-10-08"
    assert result["phase"] == "El Niño"
    watch = parse_advisory("Issued: 1 January 2026 ENSO Alert System Status: La Nina Watch")
    assert watch["phase"] is None


def test_unknown_advisory_cannot_be_substituted_with_oni():
    with pytest.raises(ValueError):
        parse_advisory("El Niño Advisory without a recognized issue date")


def test_noaa_real_discussion_header_format():
    raw = "<p>issued by CLIMATE PREDICTION CENTER/NCEP/NWS</p><p>8 October 2026</p><p>ENSO Alert System Status: El Ni&ntilde;o Advisory</p>"
    assert parse_advisory(raw)["issued"] == "2026-10-08"


def test_reference_failure_explicit(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unavailable")
    monkeypatch.setattr("src.fetch_enso.fetch_text", fail)
    result = fetch_operational_reference()
    assert result["roni"] is None and result["advisory"] is None
    assert len(result["errors"]) == 2


def test_event_peak_year_and_intensity_derived_from_series():
    oni = parse_oni("SEAS YR ANOM\nOND 1997 2.3\nNDJ 1997 2.4\nDJF 1998 2.2\nDJF 1999 -1.6\nDJF 2009 -0.89\n")
    result = notable_events(oni)
    assert result[0]["peak_season"] == "NDJ 1997"
    assert result[0]["oni_peak"] == 2.4
    assert result[1]["category"] == "débil"


def test_statistics_match_independent_seasonal_aggregation_and_family():
    rng = np.random.default_rng(40)
    dates = pd.date_range("1980-01-01", periods=552, freq="MS")
    oni = pd.DataFrame({"date": dates, "oni": rng.normal(size=len(dates))})
    frame = pd.DataFrame({"date": dates[12:], "NEA": rng.gamma(2, 50, 540)})
    annual, seasonal = correlations(frame, oni)
    family = annual + [r for rows in seasonal.values() for r in rows]
    assert len(family) == 20  # one region, four lags, annual plus four seasons
    assert all(r["family_n_tests"] == 20 for r in family)
    son = frame[frame.date.dt.month.isin([9,10,11])].copy()
    independent_y = son.groupby(son.date.dt.year).NEA.sum()
    independent_x = oni[oni.date.dt.month == 10].set_index(oni[oni.date.dt.month == 10].date.dt.year).oni.loc[independent_y.index]
    record = next(r for r in seasonal["SON"] if r["lag"] == 0)
    assert record["n_obs"] == 45
    assert record["pearson_r"] == pytest.approx(stats.pearsonr(independent_x, independent_y).statistic, abs=5e-5)
    assert record["pearson_q"] >= record["pearson_p"]
    freq, metadata = frequencies(frame, oni)
    assert "confirmatory" not in metadata["families"]
    assert all(c["significant"] == (c["q_binomial"] < .05) for entry in freq.values() for r in entry.values() for k,c in r.items() if k in ("el_nino", "la_nina"))


def test_warehouse_calendar_and_repeated_build(tmp_path):
    from src.warehouse import ENSOWarehouse
    with ENSOWarehouse(tmp_path / "science.duckdb") as warehouse:
        warehouse.initialize()
        rain = pd.DataFrame({"date": ["2025-01-15"], "oni": [.3], "NEA": [100.]})
        temp = pd.DataFrame({"date": ["2025-01-31"], "oni": [.3], "NEA": [20.]})
        warehouse._load_observations_from_pairs(rain, "precip")
        warehouse._load_observations_from_pairs(temp, "temp")
        warehouse.initialize()  # dimensions must not delete referenced rows
        row = warehouse.execute("SELECT date_key, precipitation_mm, temperature_c FROM fact_observations").fetchall()
        assert row == [("2025-01-15", 100., 20.)]
        warehouse.load_validated_correlations({"oni_series": [{"date":"2025-01-15", "oni":.4}]})
        assert warehouse.execute("SELECT oni FROM fact_observations").fetchone() == (.4,)
