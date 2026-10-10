"""Publication invariants for complete monthly observations and stable SPI."""
from datetime import date
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.climatology import CALIBRATION_PERIOD
from src.compute_spi import compute_spi
from src.fetch_temperature import compute_regional_temp_monthly
from src.refresh_observations import SOURCES, merge_observations, refresh, validate_monthly
from src.config import REGION_ORDER
from src.fetch_chirps import PRODUCT_METADATA

TODAY = date(2026, 10, 10)


def observations(start, end, *, temperature=False):
    periods = pd.period_range(start, end, freq="M")
    values = np.linspace(12, 20, len(periods)) if temperature else np.linspace(20, 140, len(periods))
    frame = pd.DataFrame({"date": periods.to_timestamp() + pd.Timedelta(days=14),
                          **{region: values for region in REGION_ORDER}})
    if not temperature:
        frame.attrs = {**PRODUCT_METADATA, "land_mask_sha256": "0" * 64,
                       "valid_pixel_counts": {r: 100 for r in REGION_ORDER}}
    return frame


def install_history(tmp_path):
    for variable, spec in SOURCES.items():
        frame = observations("1981-01", "2025-12", temperature=variable == "temperature")
        frame["oni"] = .1
        frame.to_parquet(tmp_path / spec[0], index=False)


def fetchers():
    return {"precipitation": lambda **kw: observations("2026-01", "2026-08"),
            "temperature": lambda **kw: observations("2026-01", "2026-09", temperature=True)}


def hashes(tmp_path):
    return {key: hashlib.sha256((tmp_path / spec[0]).read_bytes()).hexdigest()
            for key, spec in SOURCES.items()}


def test_new_months_then_repeated_run_are_idempotent(tmp_path):
    install_history(tmp_path)
    history = {key: pd.read_parquet(tmp_path / spec[0]) for key, spec in SOURCES.items()}
    first = refresh(directory=tmp_path, through=TODAY, fetchers=fetchers())
    assert [s["months_added"] for s in first["sources"].values()] == [8, 9]
    initial_hashes = hashes(tmp_path)
    second = refresh(directory=tmp_path, through=TODAY, fetchers=fetchers())
    assert hashes(tmp_path) == initial_hashes
    assert all(s["status"] == "unchanged" for s in second["sources"].values())
    for key, spec in SOURCES.items():
        actual = pd.read_parquet(tmp_path / spec[0]).iloc[:540]
        pd.testing.assert_frame_equal(actual, history[key], check_dtype=False)


def test_failed_download_preserves_all_existing_parquet_bytes(tmp_path):
    install_history(tmp_path)
    before = hashes(tmp_path)
    def fail(**kw):
        raise TimeoutError("source timed out")
    result = refresh(directory=tmp_path, through=TODAY, fetchers={key: fail for key in SOURCES})
    assert hashes(tmp_path) == before
    assert result["status"] == "partial"
    assert all(s["status"] == "retained_after_error" for s in result["sources"].values())


def test_one_source_failure_does_not_discard_the_other_source(tmp_path):
    install_history(tmp_path)
    before = hashes(tmp_path)
    jobs = fetchers()
    jobs["temperature"] = lambda **kw: (_ for _ in ()).throw(ConnectionError("offline"))
    result = refresh(directory=tmp_path, through=TODAY, fetchers=jobs)
    assert result["sources"]["precipitation"]["months_added"] == 8
    assert hashes(tmp_path)["temperature"] == before["temperature"]


@pytest.mark.parametrize("problem", ["duplicate", "gap", "nonfinite", "negative", "partial"])
def test_invalid_new_data_cannot_replace_valid_observations(tmp_path, problem):
    install_history(tmp_path)
    before = hashes(tmp_path)
    new = observations("2026-01", "2026-08")
    if problem == "duplicate": new = pd.concat([new, new.iloc[[0]]], ignore_index=True)
    if problem == "gap": new = new.drop(index=3)
    if problem == "nonfinite": new.loc[0, "NEA"] = np.nan
    if problem == "negative": new.loc[0, "NEA"] = -1
    if problem == "partial": new.loc[new.index[-1], "date"] = pd.Timestamp("2026-10-01")
    result = refresh(directory=tmp_path, through=TODAY, fetchers={key: lambda **kw: new for key in SOURCES})
    assert result["sources"]["precipitation"]["status"] == "retained_after_error"
    assert hashes(tmp_path)["precipitation"] == before["precipitation"]


def test_a_missing_first_new_month_is_rejected():
    old = observations("1981-01", "2025-12")
    with pytest.raises(ValueError, match="Missing calendar month"):
        merge_observations(old, observations("2026-02", "2026-08"), "precipitation", TODAY)


def daily_temperature(start, end):
    time = pd.date_range(start, end, freq="D")
    values = np.full((len(time), 71, 51), 20., dtype=np.float32)
    return xr.Dataset({"tmax": (("time", "lat", "lon"), values + 5),
                       "tmin": (("time", "lat", "lon"), values - 5)},
                      coords={"time": time, "lat": np.linspace(-20, -55, 71), "lon": np.linspace(285, 310, 51)})


def test_complete_leap_month_accepted_partial_and_missing_days_rejected():
    complete = daily_temperature("2024-02-01", "2024-02-29")
    result = compute_regional_temp_monthly(complete, through=TODAY)
    assert len(result) == 1
    assert result.NEA.iloc[0] == 20
    missing = complete.isel(time=[i for i in range(29) if i != 10])
    assert compute_regional_temp_monthly(missing, through=TODAY).empty
    assert compute_regional_temp_monthly(daily_temperature("2026-10-01", "2026-10-09"), through=TODAY).empty


def test_present_daily_timestamp_with_missing_values_is_not_complete_data():
    sample = daily_temperature("2026-01-01", "2026-01-31")
    sample["tmax"].values[10, :, :] = np.nan
    result = compute_regional_temp_monthly(sample, through=TODAY)
    assert result[REGION_ORDER].isna().all().all()
    with pytest.raises(ValueError, match="Missing/nonfinite"):
        validate_monthly(result, "temperature", TODAY)


def test_spi_reference_is_unchanged_when_extreme_new_observations_arrive():
    rng = np.random.default_rng(782)
    old = pd.Series(rng.gamma(2, 45, 540), index=pd.date_range("1981-01-01", periods=540, freq="MS"))
    new = pd.Series(np.full(9, 800.), index=pd.date_range("2026-01-01", periods=9, freq="MS"))
    before = compute_spi(old, calibration_period=CALIBRATION_PERIOD)
    extended = compute_spi(pd.concat([old, new]), calibration_period=CALIBRATION_PERIOD)
    pd.testing.assert_series_equal(before, extended.loc[before.index])
    assert np.isfinite(extended.loc["2026-09-01"])
    assert extended.loc["2026-09-01"] > 2


def test_year_cache_is_refreshed_and_failed_download_keeps_old_file(tmp_path, monkeypatch):
    from src.fetch_temperature import fetch_cpc_temperature_year
    monkeypatch.chdir(tmp_path)
    cache = Path("data/cache/cpc_temp")
    cache.mkdir(parents=True)
    old = cache / "tmax.2026.nc"
    old.write_bytes(b"previous cache bytes")
    called = []
    def fail(url, **kwargs):
        called.append(url)
        raise ConnectionError("download interrupted")
    monkeypatch.setattr("requests.get", fail)
    assert fetch_cpc_temperature_year(2026, refresh=True) is None
    assert called and old.read_bytes() == b"previous cache bytes"


def test_workflow_refresh_and_pages_are_connected():
    root = Path(__file__).resolve().parents[1]
    weekly = (root / ".github/workflows/refresh-climate-observations.yml").read_text()
    daily = (root / ".github/workflows/daily-build.yml").read_text()
    pages = (root / ".github/workflows/deploy-pages.yml").read_text()
    assert "python -m src.refresh_observations" in weekly
    assert "python build.py" in weekly
    assert "enso-data-${{ github.ref }}" in weekly and "enso-data-${{ github.ref }}" in daily
    assert "Refresh regional climate observations" in pages
