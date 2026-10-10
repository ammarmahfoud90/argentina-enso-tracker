"""Extend regional climate observations without sacrificing valid history.

Run weekly with ``python -m src.refresh_observations``. Each source is
independent: a failed download or invalid candidate keeps its previous
Parquet byte-for-byte. The publication build recomputes scientific outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from src.climatology import CALIBRATION_PERIOD
from src.config import REGION_ORDER
from src.fetch_chirps import build_chirps_monthly_series
from src.fetch_temperature import build_temp_monthly_series
from src.utils import get_logger

logger = get_logger(__name__)
REPORT_NAME = "observations_refresh.json"
SOURCES = {
    "precipitation": ("oni_precip_pairs.parquet", "CHIRPS v2.0", "mm/month",
                      "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/"),
    "temperature": ("oni_temp_pairs.parquet", "NOAA CPC Global Temperature", "degC",
                    "https://downloads.psl.noaa.gov/Datasets/cpc_global_temp/"),
}


def validate_monthly(frame: pd.DataFrame, variable: str, through: date) -> pd.DataFrame:
    required = {"date", *REGION_ORDER}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError(f"Missing months/regions in {variable}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out.date, errors="raise")
    if out.date.isna().any():
        raise ValueError("Missing observation date")
    months = out.date.dt.to_period("M")
    if months.duplicated().any():
        raise ValueError("Duplicate calendar months")
    if (months >= pd.Period(through, freq="M")).any():
        raise ValueError("Current or future partial month in observations")
    values = out[REGION_ORDER].to_numpy(dtype=float)
    lower, upper = (0, 3000) if variable == "precipitation" else (-90, 60)
    if not np.isfinite(values).all() or ((values < lower) | (values > upper)).any():
        raise ValueError(f"Missing/nonfinite/out-of-range {variable} values")
    out = out.sort_values("date").reset_index(drop=True)
    expected = pd.period_range(out.date.iloc[0], out.date.iloc[-1], freq="M")
    if len(expected) != len(out):
        raise ValueError("Missing calendar month in observations")
    return out


def merge_observations(old: pd.DataFrame, incoming: pd.DataFrame, variable: str,
                       through: date) -> pd.DataFrame:
    old = validate_monthly(old, variable, through)
    incoming = validate_monthly(incoming, variable, through)
    incoming = incoming.loc[incoming.date.dt.year > CALIBRATION_PERIOD[1]].copy()
    if incoming.empty:
        return old
    if "oni" in old and "oni" not in incoming:
        incoming["oni"] = np.nan  # build uses the live canonical NOAA series
    incoming = incoming.reindex(columns=old.columns)
    periods = incoming.date.dt.to_period("M")
    # Keep ONI cache cells on overlapping dates. They are legacy provenance,
    # not an input to the refreshed scientific calculations.
    if "oni" in old:
        indexed = old.set_index(old.date.dt.to_period("M"))
        incoming["oni"] = [indexed.at[p, "oni"] if p in indexed.index else np.nan for p in periods]
    incoming["date"] = (periods.dt.to_timestamp() + pd.Timedelta(days=14)
                        if variable == "precipitation" else periods.dt.to_timestamp(how="end").dt.normalize())
    combined = pd.concat([old.loc[~old.date.dt.to_period("M").isin(periods)], incoming], ignore_index=True)
    combined = validate_monthly(combined, variable, through)
    if combined.date.max().to_period("M") < old.date.max().to_period("M"):
        raise ValueError("Source would move observations backwards")
    return combined


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    fd, name = tempfile.mkstemp(suffix=".parquet", dir=path.parent)
    os.close(fd)
    try:
        frame.to_parquet(name, index=False)
        pd.testing.assert_frame_equal(frame, pd.read_parquet(name))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _atomic_json(payload: dict, path: Path) -> None:
    fd, name = tempfile.mkstemp(suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, allow_nan=False)
            fh.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def refresh(*, directory: Path = Path("data/processed"), through: date | None = None,
            fetchers: dict[str, Callable] | None = None) -> dict:
    today = through or date.today()
    fetchers = fetchers or {"precipitation": build_chirps_monthly_series,
                            "temperature": build_temp_monthly_series}
    checked_at = datetime.now(timezone.utc).isoformat()
    report = {"schema_version": "1.0.0", "checked_at": checked_at,
              "check_frequency": "weekly", "calibration_period": list(CALIBRATION_PERIOD),
              "complete_months_only": True, "sources": {}}
    previous = {variable: validate_monthly(pd.read_parquet(directory / spec[0]), variable, today)
                for variable, spec in SOURCES.items()}
    for variable, (name, source, units, url) in SOURCES.items():
        path = directory / name
        # Corrupt existing data is a hard error, before any source mutation.
        old = previous[variable]
        info = {"source": source, "url": url, "units": units, "status": "unchanged",
                "observations_start": old.date.min().date().isoformat(),
                "observations_end": old.date.max().date().isoformat(),
                "months_before": len(old), "months_after": len(old), "months_added": 0}
        try:
            start_year = max(CALIBRATION_PERIOD[1] + 1, int(old.date.max().year))
            new = fetchers[variable](start_year=start_year, end_year=today.year)
            candidate = merge_observations(old, new, variable, today)
            if not candidate.equals(old):
                _atomic_parquet(candidate, path)
                info["status"] = "updated"
            info.update(observations_end=candidate.date.max().date().isoformat(),
                        months_after=len(candidate), months_added=len(candidate) - len(old),
                        source_latest_month=str(new.date.max().to_period("M")))
        except Exception as exc:
            info.update(status="retained_after_error", error=str(exc)[:300])
            logger.warning("%s update failed; retaining previous observations: %s", variable, exc)
            print(f"::warning::{variable}: previous valid observations retained ({exc})")
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        report["sources"][variable] = info
        logger.info("%s: %s, through %s (%d new months)", variable, info["status"], info["observations_end"], info["months_added"])
    report["status"] = "partial" if any(s["status"] == "retained_after_error" for s in report["sources"].values()) else "success"
    _atomic_json(report, directory / REPORT_NAME)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    print(json.dumps(refresh(directory=args.directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
