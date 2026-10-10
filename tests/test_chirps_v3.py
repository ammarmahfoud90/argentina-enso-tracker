"""CHIRPS migration contracts: product identity, spatial support and rollback."""
from datetime import date
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin

from src.config import CHIRPS_BASE_URL, CHIRPS_DATASET_ID, REGION_ORDER
from src.fetch_chirps import (PRODUCT_METADATA, build_chirps_monthly_series, final_months,
                             regional_means, validate_grid, validate_product)
from src.migrate_chirps_v3 import ARCHIVE_NAME, REPORT_NAME, migrate
from src.refresh_observations import SOURCES, merge_observations, refresh

TODAY = date(2026, 10, 10)
SUPPORT = "a" * 64


def frame(start="1981-01", end="2026-08", *, v3=True):
    dates = pd.period_range(start, end, freq="M").to_timestamp() + pd.Timedelta(days=14)
    rng = np.random.default_rng(781)
    rain = pd.DataFrame({"date": dates, **{r: rng.gamma(3, 30, len(dates)) for r in REGION_ORDER}})
    rain["oni"] = np.sin(np.arange(len(dates)) / 15)
    if v3:
        rain.attrs = {**PRODUCT_METADATA, "land_mask_sha256": SUPPORT,
                      "valid_pixel_counts": {r: 100 for r in REGION_ORDER}}
        rain.attrs["extraction_records"] = [
            {"date": str(p), "source_url": f"{CHIRPS_BASE_URL}chirps-v3.0.{p.year}.{p.month:02d}.cog",
             "valid_pixel_counts": rain.attrs["valid_pixel_counts"], "window_sha256": "b" * 64,
             "land_mask_sha256": SUPPORT} for p in rain.date.dt.to_period("M")]
    return rain


def install(tmp_path):
    old = frame(v3=False)
    old.to_parquet(tmp_path / SOURCES["precipitation"][0], index=False)
    temp = frame(v3=False)
    temp[REGION_ORDER] = 20.
    temp.to_parquet(tmp_path / SOURCES["temperature"][0], index=False)
    report = {"schema_version": "1.0.0", "status": "success", "sources": {
        "precipitation": {"source": "CHIRPS v2.0"}, "temperature": {"source": "NOAA CPC Global Temperature"}}}
    (tmp_path / "observations_refresh.json").write_text(json.dumps(report))
    return old


def test_final_catalog_excludes_open_month_and_uses_only_v3_final(monkeypatch):
    names = [f"chirps-v3.0.2026.{m:02d}.cog" for m in range(1, 12)] + ["chirps-v2.0.2026.12.cog"]
    monkeypatch.setattr("requests.get", lambda *a, **kw: SimpleNamespace(text=" ".join(names), raise_for_status=lambda: None))
    assert final_months(TODAY, 2026, 2026) == list(pd.period_range("2026-01", "2026-09", freq="M"))


def test_gap_in_source_archive_fails_before_extraction(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: SimpleNamespace(
        text="chirps-v3.0.2026.01.cog chirps-v3.0.2026.03.cog", raise_for_status=lambda: None))
    with pytest.raises(ValueError, match="Missing calendar"):
        final_months(TODAY, 2026, 2026)


def test_usgs_bulk_catalog_requires_exact_calendar_months(monkeypatch):
    body = "data_20240101_20240131.tif data_20240201_20240229.tif"
    monkeypatch.setattr("requests.get", lambda *a, **kw: SimpleNamespace(text=body, raise_for_status=lambda: None))
    assert final_months(TODAY, 2024, 2024, source="usgs") == list(pd.period_range("2024-01", "2024-02", freq="M"))
    body += " data_20240301_20240325.tif"
    with pytest.raises(ValueError, match="monthly interval"):
        final_months(TODAY, 2024, 2024, source="usgs")


def test_native_box_mean_keeps_zero_and_excludes_masked_ocean():
    values = np.ma.array(np.full((560, 400), 2., dtype=np.float32), mask=False)
    values.mask[1, 399] = True
    values.data[1, 399] = -9999
    values.data[2, 220] = 0
    means, counts = regional_means(values, from_origin(-73, -22, .05, .05))
    assert counts == {"Pampa Húmeda": 35200, "NEA": 25199, "NOA": 19600, "Cuyo": 16000, "Patagonia": 57200}
    assert means["NEA"] == pytest.approx(2 * 25198 / 25199)
    assert means["Patagonia"] == 2


@pytest.mark.parametrize("attribute,value", [("shape", (2000, 7200)), ("crs", CRS.from_epsg(3857)),
                                           ("bounds", (-180, -50, 180, 50)), ("res", (.1, .1))])
def test_changed_source_grid_is_rejected(attribute, value):
    grid = SimpleNamespace(count=1, shape=(2400, 7200), crs=CRS.from_epsg(4326),
                           bounds=(-180, -60, 180, 60), res=(.05, .05), transform=from_origin(-180, 60, .05, .05))
    validate_grid(grid)
    setattr(grid, attribute, value)
    with pytest.raises(ValueError, match="native grid"):
        validate_grid(grid)


def test_different_land_mask_fails_instead_of_silently_changing_means(tmp_path, monkeypatch):
    periods = list(pd.period_range("2026-01", "2026-02", freq="M"))
    monkeypatch.setattr("src.fetch_chirps.final_months", lambda *a: periods)
    def read(period):
        return {"date": str(period), "product_metadata": PRODUCT_METADATA, "values": {r: 20. for r in REGION_ORDER},
                "source_url": "test", "valid_pixel_counts": {r: 100 for r in REGION_ORDER},
                "land_mask_sha256": ("a" if period.month == 1 else "b") * 64, "window_sha256": "c" * 64}
    monkeypatch.setattr("src.fetch_chirps.read_month", read)
    with pytest.raises(ValueError, match="land support"):
        build_chirps_monthly_series(start_year=2026, through=TODAY, cache_dir=tmp_path)


@pytest.mark.parametrize("problem", ["v2", "preliminary", "bounds", "support", "backwards"])
def test_weekly_merge_rejects_version_or_sampling_changes(problem):
    old = frame()
    new = frame(start="2026-01")
    if problem == "v2": new.attrs = {}
    if problem == "preliminary": new.attrs["product_status"] = "preliminary"
    if problem == "bounds": new.attrs["sampling_bounds"] = {"Patagonia": {"lat_min": -55}}
    if problem == "support": new.attrs["land_mask_sha256"] = "b" * 64
    if problem == "backwards": new = new.iloc[:-1].copy()
    with pytest.raises(ValueError):
        merge_observations(old, new, "precipitation", TODAY)


def test_weekly_update_refuses_unmigrated_v2_before_any_mutation(tmp_path):
    install(tmp_path)
    paths = list(tmp_path.iterdir())
    before = {p: p.read_bytes() for p in paths}
    calls = []
    with pytest.raises(ValueError, match="metadata mismatch"):
        refresh(directory=tmp_path, through=TODAY, fetchers={v: lambda **kw: calls.append(v) for v in SOURCES})
    assert not calls and before == {p: p.read_bytes() for p in paths}


def test_full_migration_archives_v2_and_is_repeatable(tmp_path):
    old = install(tmp_path)
    path = tmp_path / SOURCES["precipitation"][0]
    before = path.read_bytes()
    temp_before = (tmp_path / SOURCES["temperature"][0]).read_bytes()
    candidate = frame()
    candidate[REGION_ORDER] *= 1.1
    report = migrate(directory=tmp_path, through=TODAY, candidate=candidate, oni=old[["date", "oni"]])
    assert (tmp_path / ARCHIVE_NAME).read_bytes() == before
    restored = pd.read_parquet(path)
    validate_product(restored)
    assert restored.attrs["dataset_id"] == CHIRPS_DATASET_ID
    assert "extraction_records" not in restored.attrs
    assert len(restored) == 548
    assert report["v2_archive_sha256"] == hashlib.sha256(before).hexdigest()
    assert report["initial_v3_parquet_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    for stats in report["comparison"]["regions"].values():
        assert stats["mean_change_pct"] == pytest.approx(10)
        assert stats["spi_mean_absolute_change"] < 1e-8  # SPI is invariant to a uniform scale change.
    after = path.read_bytes()
    assert migrate(directory=tmp_path, through=TODAY) == json.loads((tmp_path / REPORT_NAME).read_text())
    assert path.read_bytes() == after
    assert (tmp_path / SOURCES["temperature"][0]).read_bytes() == temp_before


def test_mirror_history_without_parity_evidence_cannot_replace_v2(tmp_path):
    old = install(tmp_path)
    candidate = frame()
    candidate.attrs["extraction_records"][0]["source_url"] = "https://dmsdata.cr.usgs.gov/test.tif"
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="parity checks"):
        migrate(directory=tmp_path, through=TODAY, candidate=candidate, oni=old[["date", "oni"]])
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


def test_changed_monthly_support_provenance_cannot_replace_v2(tmp_path):
    old = install(tmp_path)
    candidate = frame()
    candidate.attrs["extraction_records"][0]["land_mask_sha256"] = "b" * 64
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="spatial support"):
        migrate(directory=tmp_path, through=TODAY, candidate=candidate, oni=old[["date", "oni"]])
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("problem", ["no_history", "partial", "wrong_product", "missing_provenance", "invalid_values"])
def test_invalid_migration_preserves_original_rainfall_and_manifest(tmp_path, problem):
    old = install(tmp_path)
    candidate = frame()
    if problem == "no_history": candidate = candidate.iloc[12:].copy()
    if problem == "partial": candidate.loc[len(candidate) - 1, "date"] = pd.Timestamp("2026-10-15")
    if problem == "wrong_product": candidate.attrs["dataset_id"] = "CHIRPS-v2"
    if problem == "missing_provenance": candidate.attrs.pop("extraction_records")
    if problem == "invalid_values": candidate.loc[0, "NEA"] = np.nan
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        migrate(directory=tmp_path, through=TODAY, candidate=candidate, oni=old[["date", "oni"]])
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}


def test_annual_cache_rebuild_keeps_all_months_and_product_attrs(tmp_path, monkeypatch):
    import src.compute_correlations as module
    rain = frame()
    pairs = tmp_path / "rain.parquet"
    output = tmp_path / "correlations.parquet"
    rain.to_parquet(pairs, index=False)
    before = pairs.read_bytes()
    monkeypatch.setattr(module, "PAIRS_CACHE_PATH", str(pairs))
    monkeypatch.setattr(module, "CORRELATIONS_CACHE_PATH", str(output))
    monkeypatch.setattr(module, "fetch_enso_snapshot", lambda: SimpleNamespace(oni_series=rain.iloc[:-1][["date", "oni"]]))
    module.run()
    assert pairs.read_bytes() == before
    cached = pd.read_parquet(output)
    assert set(cached.version) == {"3.0.0"}
    assert cached.attrs["dataset_id"] == CHIRPS_DATASET_ID
    assert "pearson_q" in cached
