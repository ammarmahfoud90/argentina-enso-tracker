"""Reproducible, exploratory statistics for the tracker.

Seasonal samples are complete, non-overlapping three-month seasons. ONI is
the published index at the season's central month, not another average of
three already-smoothed ONI values. Inference uses approximate effective
sample sizes and Benjamini-Yekutieli FDR adjustment across the displayed
region/lag/season family. These are associations, not forecast validation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.compute_correlations import compute_n_eff
from src.config import CHIRPS_DATASET_ID, CHIRPS_SOURCE, CORRELATION_LAGS, PRECIPITATION_REGIONS, REGION_ORDER
from src.climatology import reference_frame

SEASONS = {"SON": (9, 10, 11), "DEF": (12, 1, 2),
           "MAM": (3, 4, 5), "JJA": (6, 7, 8)}
CENTRAL_MONTH = {"SON": 10, "DEF": 1, "MAM": 4, "JJA": 7}


def monthly_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Index observations by real calendar month; reject duplicates."""
    out = frame.copy()
    out.index = pd.to_datetime(out.pop("date")).dt.to_period("M")
    if out.index.has_duplicates:
        raise ValueError("Duplicate calendar months in scientific input")
    return out.sort_index()


def complete_seasons(frame: pd.DataFrame, oni: pd.DataFrame | None = None,
                     *, aggregation: str = "sum") -> pd.DataFrame:
    """Aggregate exactly three distinct, contiguous months per season.

    Missing regional values invalidate that regional season. December is
    assigned to the following DEF year. The supplied canonical ONI series
    may extend before/after the climate-data period.
    """
    monthly = monthly_frame(frame)
    index = monthly_frame(oni if oni is not None else frame)["oni"]
    regions = [r for r in REGION_ORDER if r in monthly]
    rows = []
    for year in sorted(set(monthly.index.year) | {int(monthly.index.year.max()) + 1}):
        for season, months in SEASONS.items():
            expected = pd.PeriodIndex([
                pd.Period(year=year - 1 if season == "DEF" and m == 12 else year,
                          month=m, freq="M") for m in months
            ])
            if not expected.isin(monthly.index).all():
                continue
            values = monthly.loc[expected, regions]
            central = pd.Period(year=year, month=CENTRAL_MONTH[season], freq="M")
            totals = values.sum(min_count=3) if aggregation == "sum" else values.mean().where(values.count() == 3)
            row = {"date": central.to_timestamp() + pd.Timedelta(days=14),
                   "season": season, "season_year": year,
                   "oni": float(index.get(central, np.nan))}
            row.update(totals.to_dict())
            rows.append(row)
    return pd.DataFrame(rows, columns=["date", "season", "season_year", "oni", *regions])


def adjust_fdr(records: list[dict], p_key: str, q_key: str) -> None:
    """BY controls FDR under arbitrary dependence, using unrounded p values."""
    if not records:
        return
    p = np.asarray([r[p_key] for r in records], dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid p values for FDR adjustment")
    q = stats.false_discovery_control(p, method="by")
    for record, value in zip(records, q):
        record[q_key] = float(value)


def _p_for_r(r: float, n_eff: int) -> float:
    if not np.isfinite(r) or n_eff <= 2:
        return 1.0
    if abs(r) >= 1:
        return 0.0
    return float(2 * stats.t.sf(abs(r) * np.sqrt((n_eff - 2) / (1 - r*r)), n_eff - 2))


def _record(region: str, lag: int, paired: pd.DataFrame, *, seasonal: bool) -> dict | None:
    paired = paired[["oni", region]].dropna()
    if len(paired) < 20:
        return None
    x, y = paired["oni"].to_numpy(), paired[region].to_numpy()
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    pr = float(stats.pearsonr(x, y).statistic)
    sr = float(stats.spearmanr(x, y).statistic)
    n_eff = compute_n_eff(x, y)
    rank_n_eff = compute_n_eff(stats.rankdata(x), stats.rankdata(y))
    # Do not compress calendar gaps into adjacent time steps for inference.
    steps = np.diff(paired.index.astype("int64"))
    contiguous = bool(np.all(steps == (12 if seasonal else 1)))
    return {"region": region, "lag": lag, "pearson_r": round(pr, 4),
            "pearson_p": _p_for_r(pr, n_eff) if contiguous else 1.0,
            "spearman_r": round(sr, 4),
            "spearman_p": _p_for_r(sr, rank_n_eff) if contiguous else 1.0,
            "n_obs": len(paired), "n_eff": n_eff,
            "spearman_n_eff": rank_n_eff, "inference_available": contiguous,
            "sample_unit": "complete season" if seasonal else "calendar-month anomaly"}


def correlations(frame: pd.DataFrame, oni: pd.DataFrame, *, variable: str = "precipitation",
                 calibration_period: tuple[int, int] | None = None) -> tuple[list[dict], dict]:
    """Recompute annual and seasonal correlations from dated observations."""
    monthly = monthly_frame(frame)
    canonical = monthly_frame(oni)["oni"]
    regions = [r for r in REGION_ORDER if r in monthly]
    annual, seasonal = [], {}
    reference = monthly_frame(reference_frame(frame, calibration_period))
    means = reference[regions].groupby(reference.index.month).mean()
    climatology = means.reindex(monthly.index.month).set_axis(monthly.index)
    anomalies = monthly[regions] - climatology
    seasons = complete_seasons(frame, oni, aggregation="mean" if variable == "temperature" else "sum")
    for name, source in [("ANN", anomalies), *[
        (s, monthly_frame(seasons[seasons["season"] == s])) for s in SEASONS]]:
        records = []
        for lag in CORRELATION_LAGS:
            shifted = canonical.copy()
            shifted.index = shifted.index + lag
            paired = source[regions].join(shifted.rename("oni"))
            for region in regions:
                record = _record(region, lag, paired, seasonal=name != "ANN")
                if record:
                    records.append(record)
        if name == "ANN":
            annual = records
        else:
            seasonal[name] = records
    family = annual + [r for records in seasonal.values() for r in records]
    for p_key, q_key in [("pearson_p", "pearson_q"), ("spearman_p", "spearman_q")]:
        adjust_fdr(family, p_key, q_key)
    for r in family:
        q = r["pearson_q"]
        r.update(significant=q < .05, pearson_stars="***" if q < .001 else "**" if q < .01 else "*" if q < .05 else "",
                 correction="Benjamini-Yekutieli", family_n_tests=len(family))
    return annual, seasonal


def frequencies(frame: pd.DataFrame, oni: pd.DataFrame, *,
                calibration_period: tuple[int, int] | None = None) -> tuple[dict, dict]:
    """Descriptive counts and exploratory, approximate binomial diagnostics."""
    seasons = complete_seasons(frame, oni)
    reference = complete_seasons(reference_frame(frame, calibration_period), oni)
    regions = [r for r in REGION_ORDER if r in seasons]
    result, cells = {}, []
    for season in SEASONS:
        sample = seasons[seasons["season"] == season]
        result[season] = {}
        for region in regions:
            valid = sample.dropna(subset=[region, "oni"])
            if valid.empty:
                continue
            baseline = reference.loc[reference.season == season].dropna(subset=[region, "oni"])
            if baseline.empty:
                continue
            mean, median = float(baseline[region].mean()), float(baseline[region].median())
            entry = {"climatological_median_monthly_mm": round(median / 3, 1),
                     "climatological_mean_monthly_mm": round(mean / 3, 1),
                     "climatological_mean_seasonal_mm": round(mean, 1),
                     "total_seasons": len(valid)}
            for phase, mask in [("el_nino", valid.oni >= .5), ("la_nina", valid.oni <= -.5)]:
                subset = valid.loc[mask, region]
                n = len(subset)
                if not n:
                    continue
                m = int((subset > median).sum())
                deviation = subset - mean
                cell = {"N": n, "M_above_median": m,
                        "p_binomial": float(stats.binomtest(m, n, .5).pvalue),
                        "family": "exploratory", "low_n": n < 10,
                        "mean_deviation_monthly_mm": round(float(deviation.mean()) / 3, 1),
                        "mean_deviation_seasonal_mm": round(float(deviation.mean()), 1),
                        "deviation_pct_of_climatology": round(float(deviation.mean()) / mean * 100, 1) if mean > 0 else 0,
                        "range_monthly_mm": [round(float(deviation.min()) / 3, 1), round(float(deviation.max()) / 3, 1)],
                        "range_seasonal_mm": [round(float(deviation.min()), 1), round(float(deviation.max()), 1)]}
                entry[phase] = cell
                cells.append(cell)
            result[season][region] = entry
    adjust_fdr(cells, "p_binomial", "q_binomial")
    for cell in cells:
        cell["significant"] = cell["q_binomial"] < .05
    metadata = {
        "oni_classification": "ONI NOAA publicado para el mes central de la estación; umbrales ±0.5 °C",
        "threshold_above_normal": "Mediana de estaciones completas del período de calibración documentado",
        "calibration_period": list(calibration_period) if calibration_period else None,
        "deviation_pct_denominator": "Media climatológica estacional, no mediana",
        "test": "Binomial bilateral aproximado; independencia entre estaciones no garantizada",
        "correction": "Benjamini-Yekutieli FDR, q < 0.05",
        "families": {"exploratory": {"n_tests": len(cells), "significant": sum(c["significant"] for c in cells)}},
        "interpretation": "Frecuencias históricas descriptivas. Sin validación fuera de muestra ni independencia respecto de las correlaciones. No son probabilidades de pronóstico.",
        "units": {"mean_deviation_monthly_mm": "mm/mes (total estacional / 3)",
                  "mean_deviation_seasonal_mm": "mm/estación", "deviation_pct_of_climatology": "% de la media estacional"},
        "data_source": f"{frame.attrs.get('source', 'CHIRPS')}, cajas rectangulares y período documentados en precipitation_metadata; ONI NOAA CPC",
        "chirps_caveat": "La muestra de lluvia de Patagonia conserva el límite de 50°S. La nieve y el relieve limitan su precisión."}
    return result, metadata


def notable_events(oni: pd.DataFrame) -> list[dict]:
    """Derive dated peaks from the canonical series, without unverified impacts."""
    definitions = [("1982–83", "El Niño", "1982-05", "1983-12"),
                   ("1997–98", "El Niño", "1997-05", "1998-12"),
                   ("2008–09", "La Niña", "2008-11", "2009-04"),
                   ("2010–12", "La Niña", "2010-06", "2012-12"),
                   ("2015–16", "El Niño", "2015-03", "2016-12"),
                   ("2020–23", "La Niña", "2020-08", "2023-03")]
    records = []
    monthly = monthly_frame(oni)
    for label, phase, start, end in definitions:
        subset = monthly.loc[start:end]
        subset = subset[subset.oni >= .5 if phase == "El Niño" else subset.oni <= -.5]
        if subset.empty:
            continue
        peak = subset.loc[subset.oni.idxmax() if phase == "El Niño" else subset.oni.idxmin()]
        magnitude = abs(float(peak.oni))
        category = "muy fuerte" if magnitude >= 2 else "fuerte" if magnitude >= 1.5 else "moderado" if magnitude >= 1 else "débil"
        records.append({"year_range": label, "name": f"{phase} {label}", "type": phase,
                        "oni_peak": float(peak.oni), "peak_season": f"{peak['season']} {int(peak['year'])}",
                        "start_year": int(start[:4]), "start_month": int(start[-2:]),
                        "category": category, "source": "NOAA CPC ONI (serie histórica)",
                        "argentina_impact": "Pico calculado a partir del ONI histórico publicado por NOAA. Esta ficha no atribuye impactos regionales ni niveles fluviales al evento."})
    return records


def validate_publication(payload: dict, sst: dict | None = None) -> None:
    """Fail publication when metadata or corrected-inference contracts break."""
    for annual_key, seasonal_key in [("correlations", "seasonal_correlations"),
                                      ("temp_correlations", "seasonal_temp_correlations")]:
        family = list(payload.get(annual_key) or [])
        for season, rows in (payload.get(seasonal_key) or {}).items():
            if season not in SEASONS:
                raise ValueError("Unknown scientific season")
            if any(r["sample_unit"] != "complete season" for r in rows):
                raise ValueError("Seasonal inference must use complete seasons")
            family.extend(rows)
        for p_key, q_key in [("pearson_p", "pearson_q"), ("spearman_p", "spearman_q")]:
            expected = stats.false_discovery_control([r[p_key] for r in family], method="by") if family else []
            for record, q in zip(family, expected):
                if not np.isfinite(record[q_key]) or not np.isclose(record[q_key], q, rtol=1e-10, atol=1e-15):
                    raise ValueError("Publication contains uncorrected/mismatched statistical q")
                if record["family_n_tests"] != len(family):
                    raise ValueError("Incorrect multiple-comparison family")
                if not 3 <= record["n_eff"] <= record["n_obs"]:
                    raise ValueError("Invalid effective sample size")
        if any(r["significant"] != (r["pearson_q"] < .05) for r in family):
            raise ValueError("Significance disagrees with corrected q")
    metadata = payload["precipitation_metadata"]
    if pd.Timestamp(metadata["observations_end"]) < pd.Timestamp(metadata["observations_start"]):
        raise ValueError("Invalid observation dates")
    if metadata["regional_coverage"]["Patagonia"]["lat_min"] < -50:
        raise ValueError("The calibrated project rainfall domain ends at 50°S")
    version = payload.get("scientific_methodology", {}).get("version")
    if version == "3.0.0":
        if (metadata.get("dataset_id") != CHIRPS_DATASET_ID or metadata.get("source") != CHIRPS_SOURCE
                or metadata.get("product_status") != "final"
                or metadata.get("regional_coverage") != PRECIPITATION_REGIONS
                or metadata.get("global_latitude_coverage") != [-60, 60]
                or CHIRPS_SOURCE not in payload["frequency_methodology"]["data_source"]):
            raise ValueError("Inconsistent CHIRPS v3 publication metadata")
        refreshed = payload.get("observation_refresh", {}).get("sources", {}).get("precipitation", {})
        if refreshed and (refreshed.get("dataset_id") != CHIRPS_DATASET_ID or refreshed.get("source") != CHIRPS_SOURCE):
            raise ValueError("Weekly rainfall manifest refers to another product")
    if version in ("2.1.0", "3.0.0"):
        for entry in (metadata, payload.get("temperature_metadata")):
            if not entry:
                raise ValueError("Missing climate observation metadata")
            month = pd.Timestamp(entry["observations_end"]).to_period("M")
            if month >= pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M"):
                raise ValueError("An incomplete current month cannot be published")
            if (entry["climatology_start_year"], entry["climatology_end_year"]) != (1981, 2025):
                raise ValueError("Unexpected change of climate calibration period")
        for region in REGION_ORDER:
            current = payload.get("spi_current", {}).get(region)
            if not current or pd.Timestamp(current["date"]).to_period("M") != pd.Timestamp(metadata["observations_end"]).to_period("M"):
                raise ValueError("SPI must cover the latest validated rainfall month in every region")
    cells = [entry[phase] for season in payload["frequency_stats"].values()
             for entry in season.values() for phase in ("el_nino", "la_nina") if phase in entry]
    expected = stats.false_discovery_control([c["p_binomial"] for c in cells], method="by") if cells else []
    for cell, q in zip(cells, expected):
        if not 0 <= cell["M_above_median"] <= cell["N"] or cell["N"] == 0:
            raise ValueError("Invalid historical frequency count")
        if not np.isclose(cell["q_binomial"], q, rtol=1e-10, atol=1e-15) or cell["significant"] != (q < .05):
            raise ValueError("Incorrect frequency significance")
        if cell["family"] != "exploratory":
            raise ValueError("Post hoc confirmatory family is not allowed")
    reference = payload["operational_reference"]
    if reference["monitoring_index"] != "RONI":
        raise ValueError("Official monitoring index must be distinguished from ONI")
    if payload["parana_enso"].get("summary"):
        raise ValueError("Unverified manual river levels cannot be published")
    if sst and sst.get("baseline") != "1971-2000":
        raise ValueError("OISST native anom baseline mislabeled")
