"""Recalibrate the entire rainfall history to final CHIRPS v3, once.

The existing v2 Parquet is archived byte-for-byte. All validation and
comparisons finish before the current rainfall file is replaced. The
weekly updater subsequently freezes the new v3 1981–2025 calibration.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from src.climatology import CALIBRATION_PERIOD, reference_frame
from src.compute_spi import classify_spi, compute_spi
from src.config import CHIRPS_BASE_URL, CHIRPS_DATASET_ID, CHIRPS_SOURCE, NOAA_ONI_URL, REGION_ORDER
from src.fetch_chirps import build_chirps_monthly_series, validate_product
from src.fetch_enso import parse_oni
from src.refresh_observations import SOURCES, _atomic_json, validate_monthly
from src.scientific import correlations
from src.utils import fetch_text

ARCHIVE_NAME = "oni_precip_pairs_v2.parquet"
REPORT_NAME = "chirps_v3_migration.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare_versions(old: pd.DataFrame, new: pd.DataFrame, oni: pd.DataFrame) -> dict:
    """Use common months and the same scientific method for both products."""
    old = old.copy().set_index(old.date.dt.to_period("M"))
    new = new.copy().set_index(new.date.dt.to_period("M"))
    common = old.index.intersection(new.index).sort_values()
    left, right = old.loc[common].reset_index(drop=True), new.loc[common].reset_index(drop=True)
    result = {"comparison_start": str(common[0]), "comparison_end": str(common[-1]),
              "common_months": len(common), "calibration_period": list(CALIBRATION_PERIOD),
              "interpretation": "Before/after published-series comparison with unchanged nominal boxes and statistical method. The legacy IRI v2 X axis reports edge-aligned longitudes and includes an additional column per box; v3 uses native pixel centres. Differences include both the product change and this sampling-coordinate convention change. This is not independent station validation or evidence of forecast skill.",
              "regions": {}}
    for region in REGION_ORDER:
        a, b = left[region].to_numpy(float), right[region].to_numpy(float)
        spi_a = compute_spi(left.set_index("date")[region], calibration_period=CALIBRATION_PERIOD)
        spi_b = compute_spi(right.set_index("date")[region], calibration_period=CALIBRATION_PERIOD)
        valid = spi_a.notna() & spi_b.notna()
        delta = (spi_b[valid] - spi_a[valid]).to_numpy()
        changed = sum(classify_spi(x) != classify_spi(y) for x, y in zip(spi_a[valid], spi_b[valid]))
        result["regions"][region] = {
            "v2_mean_mm_month": float(a.mean()), "v3_mean_mm_month": float(b.mean()),
            "mean_change_mm_month": float((b - a).mean()),
            "mean_change_pct": float((b.mean() / a.mean() - 1) * 100),
            "monthly_mean_absolute_change_mm": float(np.abs(b - a).mean()),
            "monthly_max_absolute_change_mm": float(np.abs(b - a).max()),
            "monthly_climatology_v2_mm": reference_frame(left, CALIBRATION_PERIOD).groupby(left.date.dt.month)[region].mean().to_dict(),
            "monthly_climatology_v3_mm": reference_frame(right, CALIBRATION_PERIOD).groupby(right.date.dt.month)[region].mean().to_dict(),
            "spi_comparable_months": int(valid.sum()),
            "spi_mean_absolute_change": float(np.abs(delta).mean()),
            "spi_max_absolute_change": float(np.abs(delta).max()),
            "spi_category_changed_months": changed,
            "spi_category_changed_pct": float(100 * changed / valid.sum()),
            "latest_common_month_spi_v2": float(spi_a[valid].iloc[-1]),
            "latest_common_month_spi_v3": float(spi_b[valid].iloc[-1]),
        }
    def records(frame):
        annual, seasonal = correlations(frame, oni, calibration_period=CALIBRATION_PERIOD)
        return {(r["region"], r["lag"], season): r for season, rows in
                [("annual", annual), *seasonal.items()] for r in rows}
    old_corr, new_corr = records(left), records(right)
    if old_corr.keys() != new_corr.keys() or any(old_corr[k]["n_obs"] != new_corr[k]["n_obs"] for k in old_corr):
        raise ValueError("Correlation comparison does not use matching samples")
    result["correlation_comparison"] = [{
        "region": region, "lag": lag, "season": season,
        "n_obs": old_corr[(region, lag, season)]["n_obs"],
        "pearson_r_v2": old_corr[(region, lag, season)]["pearson_r"],
        "pearson_r_v3": new_corr[(region, lag, season)]["pearson_r"],
        "pearson_q_v2": old_corr[(region, lag, season)]["pearson_q"],
        "pearson_q_v3": new_corr[(region, lag, season)]["pearson_q"],
        "significant_v2": old_corr[(region, lag, season)]["significant"],
        "significant_v3": new_corr[(region, lag, season)]["significant"],
    } for region, lag, season in sorted(old_corr)]
    return result


def migrate(*, directory: Path = Path("data/processed"), through: date | None = None,
            candidate: pd.DataFrame | None = None, oni: pd.DataFrame | None = None,
            distribution_validation: list[dict] | None = None) -> dict:
    today = through or date.today()
    path = directory / SOURCES["precipitation"][0]
    old_bytes = path.read_bytes()
    old = validate_monthly(pd.read_parquet(path), "precipitation", today)
    archive = directory / ARCHIVE_NAME
    report_path = directory / REPORT_NAME
    if old.attrs.get("dataset_id") == CHIRPS_DATASET_ID:
        validate_product(old)
        report = json.loads(report_path.read_text())
        if _sha(archive.read_bytes()) != report["v2_archive_sha256"]:
            raise ValueError("Archived v2 rainfall does not match the migration record")
        return report
    if old.attrs.get("dataset_id") is not None:
        raise ValueError("Migration requires the original v2 rainfall history")
    new = validate_monthly(candidate if candidate is not None else build_chirps_monthly_series(through=today), "precipitation", today)
    validate_product(new)
    if (str(new.date.min().to_period("M")) != "1981-01"
            or len(reference_frame(new, CALIBRATION_PERIOD)) != 540
            or new.date.max().to_period("M") < old.date.max().to_period("M")):
        raise ValueError("Migration requires the complete 1981–2025 v3 history and cannot lose recent months")
    extraction_records = new.attrs.pop("extraction_records", [])
    if len(extraction_records) != len(new) or [r["date"] for r in extraction_records] != new.date.dt.to_period("M").astype(str).tolist():
        raise ValueError("Missing monthly source provenance for v3 migration")
    if any(r["land_mask_sha256"] != new.attrs["land_mask_sha256"]
           or r["valid_pixel_counts"] != new.attrs["valid_pixel_counts"] for r in extraction_records):
        raise ValueError("Monthly provenance disagrees with CHIRPS spatial support")
    has_mirror = any(r["source_url"].startswith("https://dmsdata.cr.usgs.gov/") for r in extraction_records)
    if has_mirror and (not distribution_validation or len(distribution_validation) < 5
                       or not all(r.get("pixel_identical") for r in distribution_validation)):
        raise ValueError("USGS bulk mirror requires documented native-window parity checks against CHC")
    if archive.exists() and archive.read_bytes() != old_bytes:
        raise ValueError("Refusing to overwrite a different archived v2 rainfall file")
    oni = oni if oni is not None else parse_oni(fetch_text(NOAA_ONI_URL, label="NOAA ONI migration"))
    comparison = compare_versions(old, new, oni)
    attrs = new.attrs.copy()
    canonical = oni.set_index(pd.to_datetime(oni.date).dt.to_period("M"))["oni"]
    new["oni"] = new.date.dt.to_period("M").map(canonical)
    new.attrs = attrs
    new = new.reindex(columns=old.columns)
    validate_product(new)
    checked_at = datetime.now(timezone.utc).isoformat()
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".parquet")
    os.close(fd)
    try:
        new.to_parquet(temporary, index=False)
        restored = pd.read_parquet(temporary)
        pd.testing.assert_frame_equal(new, restored)
        if restored.attrs != new.attrs:
            raise ValueError("Parquet lost CHIRPS v3 product metadata")
        new_sha = _sha(Path(temporary).read_bytes())
        report = {"schema_version": "1.0.0", "migrated_at": checked_at,
                  "source": CHIRPS_SOURCE, "dataset_id": CHIRPS_DATASET_ID, "source_url": CHIRPS_BASE_URL,
                  "product_status": "final", "calibration_period": list(CALIBRATION_PERIOD),
                  "spatial_domains_unchanged": True, "product_metadata": new.attrs,
                  "sampling_coordinate_transition": {
                      "v2_access": "IRI monthly v2 OPeNDAP, latitude centres and reported X edge coordinates",
                      "v3_access": "Native monthly final v3 raster pixel centres",
                      "nominal_bounds_unchanged": True,
                      "v2_longitude_columns": dict(zip(REGION_ORDER, (161, 181, 141, 101, 221))),
                      "v3_longitude_columns": dict(zip(REGION_ORDER, (160, 180, 140, 100, 220))),
                      "note": "Comparison is against the exact previously published v2 series, not a newly resampled v2 raster; changes cannot be attributed solely to v3."},
                  "v2_archive": ARCHIVE_NAME, "v2_archive_sha256": _sha(old_bytes),
                  "initial_v3_parquet_sha256": new_sha, "months": len(new),
                  "observations_start": new.date.min().date().isoformat(),
                  "observations_end": new.date.max().date().isoformat(),
                  "comparison": comparison, "monthly_sources": extraction_records,
                  "distribution_validation": distribution_validation or []}
        manifest_path = directory / "observations_refresh.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.update(checked_at=checked_at, schema_version="1.1.0")
        manifest["sources"]["precipitation"] = {
            "source": CHIRPS_SOURCE, "dataset_id": CHIRPS_DATASET_ID, "product_status": "final",
            "url": CHIRPS_BASE_URL, "units": "mm/month", "status": "migrated",
            "observations_start": report["observations_start"], "observations_end": report["observations_end"],
            "months_before": len(old), "months_after": len(new), "months_added": len(new) - len(old),
            "source_latest_month": str(new.date.max().to_period("M")), "sha256": new_sha}
        # Serialize before any mutation. The rainfall replacement is the commit point.
        json.dumps(report, allow_nan=False)
        json.dumps(manifest, allow_nan=False)
        if not archive.exists():
            fd, archived_temporary = tempfile.mkstemp(dir=directory, suffix=".parquet")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(old_bytes)
                os.replace(archived_temporary, archive)
            finally:
                Path(archived_temporary).unlink(missing_ok=True)
        _atomic_json(report, report_path)
        _atomic_json(manifest, manifest_path)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/processed"))
    parser.add_argument("--candidate", type=Path, help="Previously extracted complete v3 Parquet")
    parser.add_argument("--mirror-validation", type=Path, help="Native-window parity checks when using the USGS bulk mirror")
    args = parser.parse_args()
    candidate = pd.read_parquet(args.candidate) if args.candidate else None
    distribution_validation = json.loads(args.mirror_validation.read_text()) if args.mirror_validation else None
    report = migrate(directory=args.directory, candidate=candidate, distribution_validation=distribution_validation)
    print(json.dumps({k: report[k] for k in ("source", "months", "observations_start", "observations_end", "v2_archive_sha256")}, indent=2))


if __name__ == "__main__":
    main()
