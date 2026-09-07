#!/usr/bin/env python3
"""Build script: run the ENSO data pipeline and write site/data/enso.json.

Usage:
    python build.py

Prerequisites:
    - Correlation Parquet must exist: run `python -m src.compute_correlations` first.
    - Internet access to NOAA CPC endpoints for live ENSO indices.

Output:
    site/data/enso.json — consumed by site/index.html and site/map.html.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `src.*` imports work whether
# build.py is run directly or via `python build.py` from the project root.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from src.config import (
    CHIRPS_START_YEAR,
    CORRELATION_LAGS,
    CORRELATIONS_CACHE_PATH,
    ENSO_CONSECUTIVE_MONTHS,
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    LINEAGE_PATH,
    PAIRS_CACHE_PATH,
    PIPELINE_HEALTH_PATH,
    REGION_ORDER,
    REGIONS,
    SIGNIFICANCE_THRESHOLD,
)
from src.compute_composites import compute_composites
from src.compute_spi import compute_all_spi
from src.fetch_enso import fetch_enso_snapshot
from src.fetch_sam import fetch_sam_series
from src.lineage import LineageTracker
from src.parana_data import get_parana_data
from src.pipeline_monitor import PipelineMonitor
from src.fetch_iri_forecast import fetch_iri_forecast
from src.fetch_sst_map import fetch_sst_map
from src.fetch_subsurface import fetch_subsurface_cross_section

try:
    from src.warehouse import ENSOWarehouse
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build")

OUT_PATH = Path("site/data/enso.json")
HISTORY_PATH = Path("site/data/enso-history.json")
SST_MAP_PATH = Path("site/data/sst_map.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sig_stars(p: float) -> str:
    """Return APA-style significance stars for a p-value."""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


IRI_STALE_LIMIT_DAYS = 45
"""Maximum age (in days) for a cached IRI forecast before the build fails."""


def _load_cached_iri_forecast() -> dict | None:
    """Load the last valid IRI forecast from the existing enso.json on disk.

    If found, stamps ``stale_since`` with the current UTC timestamp so the
    frontend can display an appropriate warning.  Returns None if the file
    doesn't exist or has no valid forecast.
    """
    if not OUT_PATH.exists():
        return None
    try:
        with open(OUT_PATH, encoding="utf-8") as fh:
            old = json.load(fh)
        cached = old.get("iri_forecast")
        if cached is None:
            return None
        # Preserve the original fetch date but mark when it went stale
        if "stale_since" not in cached:
            cached["stale_since"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return cached
    except Exception as exc:
        logger.warning("Could not load cached IRI forecast: %s", exc)
        return None


def _signal_strength_label(abs_r: float, is_significant: bool) -> str:
    """Human-readable correlation strength label for region metadata."""
    if not is_significant:
        return "no significativa"
    if abs_r >= 0.35:
        return "fuerte"
    if abs_r >= 0.20:
        return "moderada"
    return "débil"


# ---------------------------------------------------------------------------
# Episode detection — NOAA definition
# ---------------------------------------------------------------------------

def compute_episodes(oni_df: pd.DataFrame) -> list[dict]:
    """Detect El Niño / La Niña episodes from the ONI series.

    NOAA CPC criterion: ONI >= +0.5 (El Niño) or <= -0.5 (La Niña) for at
    least 5 consecutive overlapping 3-month seasons.

    Args:
        oni_df: DataFrame with columns ``date`` (datetime64) and ``oni`` (float),
            sorted chronologically. One row per 3-month season.

    Returns:
        List of episode dicts: [{type, start, end}], sorted by start date.
    """
    episodes: list[dict] = []
    n = len(oni_df)

    phase_configs = [
        ("El Niño",  ENSO_EL_NINO_THRESHOLD,  lambda v, t: v >= t),
        ("La Niña",  ENSO_LA_NINA_THRESHOLD,   lambda v, t: v <= t),
    ]

    for phase_name, threshold, meets_threshold in phase_configs:
        in_ep = False
        ep_start = 0

        for i in range(n):
            val = float(oni_df.iloc[i]["oni"])
            if meets_threshold(val, threshold):
                if not in_ep:
                    in_ep = True
                    ep_start = i
            else:
                if in_ep:
                    length = i - ep_start
                    if length >= ENSO_CONSECUTIVE_MONTHS:
                        episodes.append({
                            "type": phase_name,
                            "start": oni_df.iloc[ep_start]["date"].date().isoformat(),
                            "end":   oni_df.iloc[i - 1]["date"].date().isoformat(),
                        })
                    in_ep = False

        # Close episode if series ends while still inside one
        if in_ep:
            length = n - ep_start
            if length >= ENSO_CONSECUTIVE_MONTHS:
                episodes.append({
                    "type": phase_name,
                    "start": oni_df.iloc[ep_start]["date"].date().isoformat(),
                    "end":   oni_df.iloc[-1]["date"].date().isoformat(),
                })

    episodes.sort(key=lambda e: e["start"])
    logger.info(
        "Episodes: %d total (%d El Niño, %d La Niña)",
        len(episodes),
        sum(1 for e in episodes if e["type"] == "El Niño"),
        sum(1 for e in episodes if e["type"] == "La Niña"),
    )
    return episodes


# ---------------------------------------------------------------------------
# Core build
# ---------------------------------------------------------------------------

def build_payload() -> tuple[dict, PipelineMonitor, LineageTracker]:
    """Fetch live data, read Parquet cache, and assemble the JSON payload.

    Returns (payload_dict, monitor, lineage) so main() can finalize outputs.
    """
    monitor = PipelineMonitor()
    lineage = LineageTracker()

    # 1. ENSO snapshot (live NOAA fetch)
    logger.info("Fetching ENSO indices from NOAA CPC…")
    with monitor.track_source("ENSO indices") as src:
        snapshot = fetch_enso_snapshot()
        src.row_count = len(snapshot.oni_series)
        src.data_freshness_days = (datetime.now(timezone.utc).date() - snapshot.oni_date).days
    logger.info(
        "ONI=%.2f (%s) | Niño3.4=%.2f | SOI=%.1f | Phase: %s",
        snapshot.oni_value, snapshot.oni_season,
        snapshot.nino34_value, snapshot.soi_value, snapshot.phase,
    )
    oni_src = lineage.register_source(
        "NOAA ONI", url="https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
        access_method="live_fetch", status="success",
        row_count=len(snapshot.oni_series),
        date_range_start=snapshot.oni_series.iloc[0]["date"].date().isoformat(),
        date_range_end=snapshot.oni_series.iloc[-1]["date"].date().isoformat(),
        feeds_sections=["current", "oni_series", "episodes"],
    )
    if snapshot.soi_series is not None:
        lineage.register_source(
            "NOAA SOI", access_method="live_fetch", status="success",
            row_count=len(snapshot.soi_series),
            feeds_sections=["soi_series"],
        )

    # 2. Correlations Parquet
    corr_path = Path(CORRELATIONS_CACHE_PATH)
    if not corr_path.exists():
        logger.error(
            "Correlation cache missing at %s — run `python -m src.compute_correlations` first.",
            corr_path,
        )
        sys.exit(1)
    with monitor.track_source("correlations.parquet") as src:
        corr_df = pd.read_parquet(corr_path)
        src.row_count = len(corr_df)
        src.cache_hit = True
        src.status = "cached"
    logger.info("Correlations: %d rows from %s", len(corr_df), corr_path)
    lineage.register_source(
        "CHIRPS correlations", access_method="parquet", status="success",
        row_count=len(corr_df),
        feeds_sections=["correlations", "region_meta"],
    )

    # 3. Episode detection
    episodes = compute_episodes(snapshot.oni_series)
    lineage.register_transform(
        "episode_detection", inputs=["NOAA ONI"], outputs=["episodes"],
        parameters={"threshold": 0.5, "consecutive_months": ENSO_CONSECUTIVE_MONTHS},
        status="success", row_count_in=len(snapshot.oni_series), row_count_out=len(episodes),
    )

    # 4. ONI series — full + last 24 months
    oni_records: list[dict] = []
    for _, row in snapshot.oni_series.iterrows():
        oni_records.append({
            "date":   row["date"].date().isoformat(),
            "season": str(row["season"]),
            "year":   int(row["year"]),
            "oni":    round(float(row["oni"]), 2),
        })
    oni_24m = oni_records[-24:]

    # 4b. SOI series — full + last 24 months (for SOI Tracker section)
    soi_records: list[dict] = []
    if snapshot.soi_series is not None:
        for _, row in snapshot.soi_series.iterrows():
            soi_records.append({
                "date": row["date"].date().isoformat(),
                "soi":  round(float(row["soi"]), 2),
            })
    soi_24m = soi_records[-24:] if soi_records else []
    logger.info("SOI series: %d total, %d last 24m", len(soi_records), len(soi_24m))

    # 5. Correlation records (region × lag)
    #    If the Parquet lacks n_eff (pre-Bretherton cache), compute on-the-fly
    #    from the pairs Parquet.
    _pairs_for_neff: pd.DataFrame | None = None
    _need_neff = "n_eff" not in corr_df.columns
    if _need_neff:
        import numpy as _np_neff
        from scipy import stats as _stats_neff
        from src.compute_correlations import compute_n_eff as _compute_n_eff_annual

        _pp = Path(PAIRS_CACHE_PATH)
        if _pp.exists():
            _pairs_for_neff = pd.read_parquet(_pp)
            _pairs_for_neff["date"] = pd.to_datetime(_pairs_for_neff["date"])
            _pairs_for_neff["ym"] = _pairs_for_neff["date"].dt.to_period("M")
            logger.info("Computing n_eff on-the-fly for annual correlations (Parquet lacks column)")

    corr_records: list[dict] = []
    for _, row in corr_df.iterrows():
        region = str(row["region"])
        lag = int(row["lag"])
        n_obs = int(row["n_obs"])
        pr = float(row["pearson_r"])
        pp_cached = float(row["pearson_p"])

        # Compute n_eff and corrected p-value if not in cache
        n_eff = None
        pp_corrected = pp_cached
        if "n_eff" in row.index:
            n_eff = int(row["n_eff"])
        elif _pairs_for_neff is not None and region in _pairs_for_neff.columns:
            oni_col = _pairs_for_neff[["ym", "oni"]].copy()
            oni_col["ym"] = oni_col["ym"] + lag
            merged = _pairs_for_neff[["ym", region]].merge(oni_col, on="ym", how="inner").dropna()
            if len(merged) >= 30:
                x = merged["oni"].values
                y = merged[region].values
                n_eff = _compute_n_eff_annual(x, y)
                if n_eff > 2 and abs(pr) < 1.0:
                    t_stat = pr * _np_neff.sqrt((n_eff - 2) / (1 - pr ** 2))
                    pp_corrected = float(2 * _stats_neff.t.sf(abs(t_stat), df=n_eff - 2))

        rec = {
            "region":         region,
            "lag":            lag,
            "pearson_r":      round(pr, 4),
            "pearson_p":      round(pp_corrected, 4),
            "pearson_stars":  _sig_stars(pp_corrected),
            "spearman_r":     round(float(row["spearman_r"]), 4),
            "spearman_p":     round(float(row["spearman_p"]), 4),
            "n_obs":          n_obs,
        }
        if n_eff is not None:
            rec["n_eff"] = n_eff
        corr_records.append(rec)

    # 6. Region metadata with signal_strength label
    region_meta: dict[str, dict] = {}
    for region_name in REGION_ORDER:
        reg_rows = corr_df[corr_df["region"] == region_name]
        if reg_rows.empty:
            best_abs_r, is_sig = 0.0, False
        else:
            sig_rows = reg_rows[reg_rows["pearson_p"] < SIGNIFICANCE_THRESHOLD]
            if not sig_rows.empty:
                best_row = sig_rows.loc[sig_rows["pearson_r"].abs().idxmax()]
                best_abs_r = abs(float(best_row["pearson_r"]))
                is_sig = True
            else:
                best_row = reg_rows.loc[reg_rows["pearson_r"].abs().idxmax()]
                best_abs_r = abs(float(best_row["pearson_r"]))
                is_sig = False

        cfg = REGIONS[region_name]
        region_meta[region_name] = {
            "provinces":      cfg["provinces"],
            "description":    cfg["description"],
            "signal_strength": _signal_strength_label(best_abs_r, is_sig),
            # Geographic center of bounding box (lat, lon) — for map positioning
            "center_lat": round((cfg["lat_min"] + cfg["lat_max"]) / 2, 2),
            "center_lon": round((cfg["lon_min"] + cfg["lon_max"]) / 2, 2),
        }

    # 7. Correlation cache metadata (version, period)
    cache_meta: dict = {}
    if "version" in corr_df.columns:
        cache_meta["version"]     = str(corr_df["version"].iloc[0])
        cache_meta["start_year"]  = int(corr_df["start_year"].iloc[0])
        cache_meta["end_year"]    = int(corr_df["end_year"].iloc[0])
        cache_meta["computed_at"] = str(corr_df["computed_at"].iloc[0])

    # 8. 12-month precipitation anomaly per region (from pairs Parquet)
    precip_anomaly_12m: dict = {}
    pairs_path = Path(PAIRS_CACHE_PATH)
    if pairs_path.exists():
        with monitor.track_source("precipitation_pairs.parquet") as src:
            pairs_df = pd.read_parquet(pairs_path)
            pairs_df["date"] = pd.to_datetime(pairs_df["date"])
            pairs_df["month"] = pairs_df["date"].dt.month
            src.row_count = len(pairs_df)
            src.cache_hit = True
            src.status = "cached"
        lineage.register_source(
            "CHIRPS precip pairs", access_method="parquet", status="success",
            row_count=len(pairs_df),
            feeds_sections=["precip_anomaly_12m", "seasonal_correlations",
                            "frequency_stats", "composite_analysis", "spi_series"],
        )
        region_cols = [c for c in REGION_ORDER if c in pairs_df.columns]
        # Climatological mean per calendar month
        clim = pairs_df.groupby("month")[region_cols].mean()
        # Last 12 available months
        recent = pairs_df.sort_values("date").tail(12).reset_index(drop=True)
        for region in REGION_ORDER:
            if region not in pairs_df.columns:
                continue
            bars = []
            for _, row in recent.iterrows():
                m = int(row["month"])
                obs = float(row[region])
                mean_val = float(clim.loc[m, region])
                bars.append({
                    "date": row["date"].date().isoformat(),
                    "month": m,
                    "anomaly_mm": round(obs - mean_val, 1),
                })
            precip_anomaly_12m[region] = bars
        logger.info("Precip anomaly: %d regions, 12 months each", len(precip_anomaly_12m))
    else:
        logger.warning("Pairs Parquet not found at %s — precip_anomaly_12m will be empty", pairs_path)

    # 8b. Seasonal correlations (SON/DEF/MAM/JJA) from pairs Parquet
    seasonal_correlations: dict = {}
    if pairs_path.exists():
        import numpy as _np
        from scipy import stats as _stats
        from src.compute_correlations import compute_n_eff as _compute_n_eff

        pairs_df["ym"] = pairs_df["date"].dt.to_period("M")
        _oni_col = pairs_df[["ym", "oni"]].copy()
        _precip_cols = pairs_df.drop(columns=["oni"]).copy()

        _season_months = {
            "SON": [9, 10, 11],
            "DEF": [12, 1, 2],
            "MAM": [3, 4, 5],
            "JJA": [6, 7, 8],
        }
        for season_name, months_list in _season_months.items():
            season_precip = _precip_cols[_precip_cols["month"].isin(months_list)]
            season_records = []
            for lag in CORRELATION_LAGS:
                # Shift ONI forward by lag months (ONI leads precipitation)
                oni_shifted = _oni_col.copy()
                oni_shifted["ym"] = oni_shifted["ym"] + lag
                season_merged = season_precip.merge(oni_shifted, on="ym", how="inner")
                for region in REGION_ORDER:
                    if region not in season_merged.columns:
                        continue
                    paired = season_merged[["oni", region]].dropna()
                    n = len(paired)
                    if n < 20:
                        continue
                    x = paired["oni"].values
                    y = paired[region].values
                    pr, pp_naive = _stats.pearsonr(x, y)
                    sr, sp = _stats.spearmanr(x, y)
                    n_eff = _compute_n_eff(x, y)
                    if n_eff > 2 and abs(pr) < 1.0:
                        t_stat = pr * _np.sqrt((n_eff - 2) / (1 - pr ** 2))
                        pp = float(2 * _stats.t.sf(abs(t_stat), df=n_eff - 2))
                    else:
                        pp = pp_naive
                    season_records.append({
                        "region": region,
                        "lag": lag,
                        "pearson_r": round(float(pr), 4),
                        "pearson_p": round(float(pp), 4),
                        "pearson_stars": _sig_stars(float(pp)),
                        "spearman_r": round(float(sr), 4),
                        "spearman_p": round(float(sp), 4),
                        "n_obs": n,
                        "n_eff": n_eff,
                    })
            seasonal_correlations[season_name] = season_records
        logger.info(
            "Seasonal correlations: %s",
            {k: len(v) for k, v in seasonal_correlations.items()},
        )
    else:
        logger.warning("Pairs Parquet not found — seasonal correlations skipped")

    # 8c. Frequency stats: how often was rainfall above median during El Niño / La Niña?
    frequency_stats: dict = {}
    frequency_methodology: dict = {}
    if pairs_path.exists():
        import numpy as _np
        from scipy import stats as _stats

        def _assign_season(month: int) -> str:
            if month in (9, 10, 11): return "SON"
            if month in (12, 1, 2):  return "DEF"
            if month in (3, 4, 5):   return "MAM"
            return "JJA"

        _fdf = pairs_df.copy()
        _fdf["season"] = _fdf["month"].apply(_assign_season)
        _fdf["season_year"] = _fdf["date"].dt.year
        _fdf.loc[_fdf["month"] == 12, "season_year"] = _fdf.loc[_fdf["month"] == 12, "date"].dt.year + 1

        _sg = _fdf.groupby(["season_year", "season"])
        _precip_mean = _sg[region_cols].mean()
        _precip_total = _sg[region_cols].sum()
        _oni_mean = _sg["oni"].mean()
        _mcounts = _sg["month"].count()

        _sm = _precip_mean.copy()
        _sm["oni_mean"] = _oni_mean
        _sm = _sm[_mcounts == 3]

        _st = _precip_total.copy()
        _st["oni_mean"] = _oni_mean
        _st = _st[_mcounts == 3]

        _sm["phase"] = "Neutral"
        _sm.loc[_sm["oni_mean"] >= ENSO_EL_NINO_THRESHOLD, "phase"] = "El Niño"
        _sm.loc[_sm["oni_mean"] <= ENSO_LA_NINA_THRESHOLD, "phase"] = "La Niña"
        _st["phase"] = _sm["phase"]

        # Confirmatory cells: prior hypothesis backed by independent r analysis
        _CONFIRMATORY = {
            ("DEF", "Pampa Húmeda", "el_nino"),
            ("DEF", "Pampa Húmeda", "la_nina"),
            ("DEF", "NEA", "el_nino"),
            ("SON", "NEA", "el_nino"),
        }
        _PRELIMINARY = {
            ("MAM", "NEA", "el_nino"),
            ("JJA", "Cuyo", "el_nino"),
        }

        _conf_sig = 0
        _expl_sig = 0

        for _sn in ["SON", "DEF", "MAM", "JJA"]:
            _s_mean = _sm.xs(_sn, level="season")
            _s_total = _st.xs(_sn, level="season")
            _sr = {}

            for _reg in REGION_ORDER:
                if _reg not in region_cols:
                    continue
                _median_all = float(_s_mean[_reg].median())
                _mean_monthly = float(_s_mean[_reg].mean())
                _mean_seasonal = float(_s_total[_reg].mean())

                _entry = {
                    "climatological_median_monthly_mm": round(_median_all, 1),
                    "climatological_mean_monthly_mm": round(_mean_monthly, 1),
                    "climatological_mean_seasonal_mm": round(_mean_seasonal, 1),
                    "total_seasons": len(_s_mean),
                }

                for _pk, _pl in [("el_nino", "El Niño"), ("la_nina", "La Niña")]:
                    _sub_m = _s_mean[_s_mean["phase"] == _pl]
                    _sub_t = _s_total[_s_total["phase"] == _pl]
                    _N = len(_sub_m)
                    if _N == 0:
                        continue
                    _M = int((_sub_m[_reg] > _median_all).sum())

                    _bt = _stats.binomtest(_M, _N, 0.5, alternative="two-sided")
                    _p = round(float(_bt.pvalue), 4)
                    _is_sig = _p < SIGNIFICANCE_THRESHOLD

                    _ck = (_sn, _reg, _pk)
                    _family = "confirmatory" if _ck in _CONFIRMATORY else "exploratory"
                    if _is_sig:
                        if _family == "confirmatory":
                            _conf_sig += 1
                        else:
                            _expl_sig += 1

                    _pm = float(_sub_m[_reg].mean())
                    _dev_m = round(_pm - _mean_monthly, 1)
                    _ps = float(_sub_t[_reg].mean())
                    _dev_s = round(_ps - _mean_seasonal, 1)
                    _dev_pct = round((_dev_s / _mean_seasonal) * 100, 1) if _mean_seasonal > 0 else 0.0

                    _devs_m = _sub_m[_reg] - _mean_monthly
                    _devs_s = _sub_t[_reg] - _mean_seasonal

                    _cell = {
                        "N": _N,
                        "M_above_median": _M,
                        "p_binomial": _p,
                        "significant": _is_sig,
                        "family": _family,
                        "low_n": _N < 10,
                        "mean_deviation_monthly_mm": _dev_m,
                        "mean_deviation_seasonal_mm": _dev_s,
                        "deviation_pct_of_climatology": _dev_pct,
                        "range_monthly_mm": [round(float(_devs_m.min()), 1), round(float(_devs_m.max()), 1)],
                        "range_seasonal_mm": [round(float(_devs_s.min()), 1), round(float(_devs_s.max()), 1)],
                    }

                    if _ck in _PRELIMINARY:
                        _cell["preliminary"] = True

                    if _sn == "JJA" and _reg == "Cuyo" and _pk == "el_nino":
                        _cell["note"] = (
                            "Direccion consistente (7/7) pero magnitud posiblemente "
                            "subestimada: CHIRPS no captura bien la precipitacion nival "
                            "en Cuyo invernal, y N=7 es el minimo de la tabla."
                        )

                    _entry[_pk] = _cell
                _sr[_reg] = _entry
            frequency_stats[_sn] = _sr

        frequency_methodology = {
            "threshold_above_normal": "mediana climatologica (1981-2025) de la region y estacion",
            "deviation_pct_denominator": (
                "media climatologica (no mediana). La mediana se usa como umbral "
                "para clasificar temporadas; la media se usa como referencia para "
                "cuantificar la magnitud del desvio."
            ),
            "oni_classification": (
                "El Nino: ONI estacional medio >= +0.5; "
                "La Nina: ONI estacional medio <= -0.5"
            ),
            "test": "binomtest bilateral (scipy.stats.binomtest, H0: p=0.5)",
            "families": {
                "confirmatory": {
                    "description": (
                        "Hipotesis previa respaldada por el analisis de correlacion "
                        "independiente (r=+0.39*** Pampa Humeda DEF, r=+0.32*** NEA SON) "
                        "y consistente con la literatura de teleconexion ENSO en el "
                        "sudeste de Sudamerica."
                    ),
                    "cells": [
                        "DEF Pampa Humeda El Nino",
                        "DEF Pampa Humeda La Nina",
                        "DEF NEA El Nino",
                        "SON NEA El Nino",
                    ],
                    "n_tests": 4,
                    "significant": _conf_sig,
                },
                "exploratory": {
                    "description": (
                        "Surgieron de recorrer la tabla sin hipotesis previa. No "
                        "sobreviven una correccion por comparaciones multiples dentro "
                        "de su familia y requieren confirmacion con mas temporadas."
                    ),
                    "n_tests": 36,
                    "significant": _expl_sig,
                    "expected_by_chance": round(36 * 0.05, 1),
                },
            },
            "n_variation_note": (
                "N varia entre estaciones (DEF~15, SON~14, MAM~9, JJA~7) porque "
                "los eventos ENSO alcanzan su pico en el verano austral (DEF). En "
                "otono e invierno, menos temporadas cumplen el umbral ONI >= 0.5."
            ),
            "units": {
                "mean_deviation_monthly_mm": (
                    "Desviacion del promedio mensual dentro de la estacion (mm/mes). "
                    "Es el promedio de los 3 desvios mensuales."
                ),
                "mean_deviation_seasonal_mm": (
                    "Desviacion del acumulado estacional (mm/estacion). "
                    "Igual a monthly x 3 porque es el promedio de los desvios "
                    "de las sumas estacionales."
                ),
                "deviation_pct_of_climatology": (
                    "Desviacion como porcentaje de la media climatologica estacional."
                ),
                "range_monthly_mm": (
                    "Rango [min, max] de los desvios mensuales promedio "
                    "por temporada individual."
                ),
                "range_seasonal_mm": (
                    "Rango [min, max] de los desvios del acumulado estacional "
                    "por temporada individual. Calculado directamente desde los "
                    "acumulados, NO escalado desde el rango mensual."
                ),
            },
            "data_source": "CHIRPS v2.0 (1981-2025) via IRI OPeNDAP, ONI de NOAA CPC",
            "chirps_caveat": (
                "CHIRPS es un producto basado en infrarrojo + estaciones. Subestima "
                "la precipitacion nival, especialmente en Cuyo y Patagonia en invierno."
            ),
        }
        logger.info(
            "Frequency stats: confirmatory %d/%d sig, exploratory %d/%d sig (expected ~%.1f)",
            _conf_sig, 4, _expl_sig, 36, 36 * 0.05,
        )
    else:
        logger.warning("Pairs Parquet not found — frequency stats skipped")

    lineage.register_transform(
        "seasonal_correlations", inputs=["CHIRPS precip pairs", "NOAA ONI"],
        outputs=["seasonal_correlations"], status="success",
        row_count_out=sum(len(v) for v in seasonal_correlations.values()),
    )
    lineage.register_transform(
        "frequency_stats", inputs=["CHIRPS precip pairs", "NOAA ONI"],
        outputs=["frequency_stats"], status="success" if frequency_stats else "skipped",
    )

    # 8d. Composite analysis by ENSO intensity
    composite_analysis: dict = {}
    if pairs_path.exists():
        try:
            composite_analysis = compute_composites(pairs_df)
            logger.info("Composite analysis: %d regions", len(composite_analysis))
            lineage.register_transform(
                "composite_analysis", inputs=["CHIRPS precip pairs"],
                outputs=["composite_analysis"], status="success",
                row_count_out=len(composite_analysis),
            )
        except Exception as exc:
            logger.warning("Composite analysis failed: %s", exc)
    else:
        logger.warning("Pairs Parquet not found — composite analysis skipped")

    # 8e. SPI-3 drought index
    spi_series: dict = {}
    spi_current: dict = {}
    if pairs_path.exists():
        try:
            spi_series, spi_current = compute_all_spi(pairs_df)
            logger.info("SPI-3: %d regions", len(spi_current))
            lineage.register_transform(
                "spi_computation", inputs=["CHIRPS precip pairs"],
                outputs=["spi_series", "spi_current"], status="success",
                parameters={"window": 3}, row_count_out=len(spi_current),
            )
        except Exception as exc:
            logger.warning("SPI computation failed: %s", exc)
    else:
        logger.warning("Pairs Parquet not found — SPI skipped")

    # 8f. Temperature correlations (from pre-computed Parquet)
    temp_correlations: list[dict] = []
    seasonal_temp_correlations: dict = {}
    temp_corr_path = Path("data/processed/temp_correlations.parquet")
    temp_pairs_path = Path("data/processed/oni_temp_pairs.parquet")
    if temp_corr_path.exists():
        try:
            with monitor.track_source("temp_correlations.parquet") as src:
                temp_corr_df = pd.read_parquet(temp_corr_path)
                src.row_count = len(temp_corr_df)
                src.cache_hit = True
                src.status = "cached"
            lineage.register_source(
                "CPC temperature correlations", access_method="parquet", status="success",
                row_count=len(temp_corr_df),
                feeds_sections=["temp_correlations", "seasonal_temp_correlations"],
            )
            for _, row in temp_corr_df.iterrows():
                temp_correlations.append({
                    "region": str(row["region"]),
                    "lag": int(row["lag"]),
                    "pearson_r": round(float(row["pearson_r"]), 4),
                    "pearson_p": round(float(row["pearson_p"]), 4),
                    "pearson_stars": _sig_stars(float(row["pearson_p"])),
                    "spearman_r": round(float(row["spearman_r"]), 4),
                    "spearman_p": round(float(row["spearman_p"]), 4),
                    "n_obs": int(row["n_obs"]),
                    "n_eff": int(row["n_eff"]) if "n_eff" in row.index else None,
                })
            logger.info("Temperature correlations: %d rows from %s", len(temp_correlations), temp_corr_path)

            # Compute seasonal temp correlations if pairs available
            if temp_pairs_path.exists():
                import numpy as _np
                from scipy import stats as _stats
                from src.compute_correlations import compute_n_eff as _compute_n_eff

                temp_pairs_df = pd.read_parquet(temp_pairs_path)
                temp_pairs_df["date"] = pd.to_datetime(temp_pairs_df["date"])
                temp_pairs_df["ym"] = temp_pairs_df["date"].dt.to_period("M")
                temp_pairs_df["month"] = temp_pairs_df["date"].dt.month
                _oni_t = temp_pairs_df[["ym", "oni"]].copy()
                _temp_cols = [c for c in REGION_ORDER if c in temp_pairs_df.columns]
                # Drop oni from temp_pairs to avoid suffix collision in merge
                _temp_no_oni = temp_pairs_df.drop(columns=["oni"])

                for season_name, months_list in [("SON",[9,10,11]),("DEF",[12,1,2]),("MAM",[3,4,5]),("JJA",[6,7,8])]:
                    season_temp = _temp_no_oni[_temp_no_oni["month"].isin(months_list)]
                    season_records = []
                    for lag in CORRELATION_LAGS:
                        oni_shifted = _oni_t.copy()
                        oni_shifted["ym"] = oni_shifted["ym"] + lag
                        merged = season_temp.merge(oni_shifted, on="ym", how="inner")
                        for region in _temp_cols:
                            paired = merged[["oni", region]].dropna()
                            n = len(paired)
                            if n < 20:
                                continue
                            x, y = paired["oni"].values, paired[region].values
                            pr, pp_naive = _stats.pearsonr(x, y)
                            sr, sp = _stats.spearmanr(x, y)
                            n_eff = _compute_n_eff(x, y)
                            if n_eff > 2 and abs(pr) < 1.0:
                                t_stat = pr * _np.sqrt((n_eff - 2) / (1 - pr ** 2))
                                pp = float(2 * _stats.t.sf(abs(t_stat), df=n_eff - 2))
                            else:
                                pp = pp_naive
                            season_records.append({
                                "region": region, "lag": lag,
                                "pearson_r": round(float(pr), 4),
                                "pearson_p": round(float(pp), 4),
                                "pearson_stars": _sig_stars(float(pp)),
                                "spearman_r": round(float(sr), 4),
                                "spearman_p": round(float(sp), 4),
                                "n_obs": n, "n_eff": n_eff,
                            })
                    seasonal_temp_correlations[season_name] = season_records
                logger.info("Seasonal temp correlations: %s",
                            {k: len(v) for k, v in seasonal_temp_correlations.items()})
        except Exception as exc:
            logger.warning("Temperature correlations failed: %s", exc)
    else:
        logger.info("Temperature correlations Parquet not found — section will be hidden. "
                     "Run `python -m src.compute_temp_correlations` to generate.")

    # 9. Subsurface temperature cross-section (TAO/TRITON buoys)
    logger.info("Fetching subsurface temperature data…")
    with monitor.track_source("TAO/TRITON subsurface") as src:
        subsurface = fetch_subsurface_cross_section()
        if subsurface:
            src.row_count = len(subsurface.get("longitudes", []))
            logger.info("Subsurface: %d lons x %d depths", len(subsurface["longitudes"]), len(subsurface["depths"]))
        else:
            src.status = "failed"
            src.error_message = "No data returned"
            logger.warning("Subsurface data unavailable — section will be hidden in frontend")
    lineage.register_source(
        "TAO/TRITON", access_method="live_fetch",
        status="success" if subsurface else "failed",
        feeds_sections=["subsurface"],
    )

    # 9b. SAM/AAO index
    logger.info("Fetching SAM/AAO index from NOAA CPC…")
    sam_monthly_records: list[dict] | None = None
    sam_value: float | None = None
    sam_date_str: str | None = None
    with monitor.track_source("NOAA SAM/AAO") as src:
        try:
            sam_df, sam_value, sam_date = fetch_sam_series()
            sam_monthly_records = []
            for _, row in sam_df.iterrows():
                sam_monthly_records.append({
                    "date": row["date"].date().isoformat(),
                    "sam": round(float(row["sam"]), 2),
                })
            sam_date_str = sam_date.isoformat()
            src.row_count = len(sam_monthly_records)
            src.data_freshness_days = (datetime.now(timezone.utc).date() - sam_date).days
            logger.info("SAM: latest=%.2f (%s), %d records", sam_value, sam_date_str, len(sam_monthly_records))
        except Exception as exc:
            src.status = "failed"
            src.error_message = str(exc)[:200]
            logger.warning("SAM/AAO fetch failed: %s — section will be hidden", exc)
    lineage.register_source(
        "NOAA SAM/AAO", access_method="live_fetch",
        status="success" if sam_monthly_records else "failed",
        row_count=len(sam_monthly_records) if sam_monthly_records else 0,
        feeds_sections=["sam_monthly", "current.sam_value"],
    )

    # 10. IRI forecast (parsed probabilities + SVG URLs)
    #     Graceful degradation: if fetch fails, reuse last valid forecast from
    #     the existing enso.json and tag it with stale_since.
    logger.info("Fetching IRI forecast…")
    with monitor.track_source("IRI ENSO forecast") as src:
        iri_forecast = fetch_iri_forecast()
        if iri_forecast:
            src.row_count = len(iri_forecast.get("probabilities") or [])
            logger.info(
                "IRI forecast: %d trimesters, month=%d/%d",
                src.row_count, iri_forecast["year"], iri_forecast["month"],
            )
        else:
            src.status = "cached"
            logger.warning("IRI forecast fetch failed — attempting to reuse cached forecast")
            iri_forecast = _load_cached_iri_forecast()
            if iri_forecast:
                logger.info(
                    "Reusing cached IRI forecast from %d/%d (stale_since: %s)",
                    iri_forecast["year"], iri_forecast["month"],
                    iri_forecast.get("stale_since", "unknown"),
                )
            else:
                src.status = "failed"
                src.error_message = "No live or cached forecast available"
                logger.warning("No cached IRI forecast available either")
    lineage.register_source(
        "IRI forecast", access_method="live_fetch",
        status="success" if iri_forecast else "failed",
        feeds_sections=["iri_forecast"],
    )

    # 11. Assemble final payload
    # Quality checks on key DataFrames
    monitor.track_quality("correlations", corr_df,
                          expected_range={"pearson_r": (-1.0, 1.0), "pearson_p": (0.0, 1.0)})
    if pairs_path.exists():
        monitor.track_quality("precipitation_pairs", pairs_df)

    payload = {
        "current": {
            "oni_value":   round(snapshot.oni_value, 2),
            "oni_season":  snapshot.oni_season,
            "oni_date":    snapshot.oni_date.isoformat(),
            "nino34_value": round(snapshot.nino34_value, 2),
            "nino34_date": snapshot.nino34_date.isoformat(),
            "soi_value":   round(snapshot.soi_value, 1),
            "soi_date":    snapshot.soi_date.isoformat(),
            "conditions":  snapshot.conditions,
            "conditions_intensity": snapshot.conditions_intensity,
            "episode_confirmed": snapshot.episode_confirmed,
            "phase":       snapshot.phase,
            "phase_source": snapshot.phase_source,
            "sam_value":   sam_value,
            "sam_date":    sam_date_str,
        },
        "oni_series":    oni_records,
        "oni_series_24m": oni_24m,
        "soi_series":    soi_records,
        "soi_series_24m": soi_24m,
        "correlations":  corr_records,
        "seasonal_correlations": seasonal_correlations,
        "frequency_stats": frequency_stats,
        "frequency_methodology": frequency_methodology,
        "region_meta":   region_meta,
        "region_order":  REGION_ORDER,
        "episodes":      episodes,
        "correlation_cache": cache_meta,
        "precip_anomaly_12m": precip_anomaly_12m,
        "composite_analysis": composite_analysis,
        "spi_series":    spi_series,
        "spi_current":   spi_current,
        "sam_monthly":   sam_monthly_records,
        "parana_enso":   get_parana_data(),
        "temp_correlations": temp_correlations if temp_correlations else None,
        "seasonal_temp_correlations": seasonal_temp_correlations if seasonal_temp_correlations else None,
        "subsurface":    subsurface,
        "iri_forecast":  iri_forecast,
        "notable_events": [
            {
                "year_range": "1982–83", "name": "El Niño 1982–83",
                "type": "El Niño", "oni_peak": 2.1, "peak_season": "DJF 1983",
                "start_year": 1982, "start_month": 5,
                "argentina_impact": (
                    "Inundaciones extraordinarias en el Litoral y Pampa Húmeda. "
                    "El Paraná alcanzó 7.52 m en Rosario (julio 1983). "
                    "Pérdidas agrícolas masivas en la región pampeana."
                ),
                "category": "muy fuerte",
            },
            {
                "year_range": "1997–98", "name": "El Niño 1997–98",
                "type": "El Niño", "oni_peak": 2.4, "peak_season": "NDJ 1998",
                "start_year": 1997, "start_month": 5,
                "argentina_impact": (
                    "El evento más intenso del siglo XX. Inundaciones severas "
                    "en el NEA y Litoral. Crecidas del Paraná, Uruguay y afluentes. "
                    "Lluvias récord en primavera y verano en la Pampa Húmeda."
                ),
                "category": "muy fuerte",
            },
            {
                "year_range": "2008–09", "name": "La Niña 2008–09",
                "type": "La Niña", "oni_peak": -0.8, "peak_season": "DJF 2009",
                "start_year": 2008, "start_month": 11,
                "argentina_impact": (
                    "Sequía severa en la Pampa Húmeda y el NEA. "
                    "Campaña agrícola 2008/09 con pérdidas de producción de soja y maíz "
                    "estimadas en más de USD 5.000 millones."
                ),
                "category": "moderado",
            },
            {
                "year_range": "2010–12", "name": "La Niña 2010–12",
                "type": "La Niña", "oni_peak": -1.7, "peak_season": "DJF 2011",
                "start_year": 2010, "start_month": 6,
                "argentina_impact": (
                    "Doble La Niña prolongada. Bajante significativa del Paraná. "
                    "Déficit hídrico en la Pampa Húmeda y Litoral, afectando "
                    "la navegación fluvial y la producción agrícola."
                ),
                "category": "fuerte",
            },
            {
                "year_range": "2015–16", "name": "El Niño 2015–16",
                "type": "El Niño", "oni_peak": 2.6, "peak_season": "NDJ 2016",
                "start_year": 2015, "start_month": 3,
                "argentina_impact": (
                    "El más intenso registrado. Inundaciones graves en el Litoral "
                    "y noreste de Buenos Aires. Evacuaciones masivas en Concordia, "
                    "Concepción del Uruguay y zonas ribereñas del Paraná."
                ),
                "category": "muy fuerte",
            },
            {
                "year_range": "2020–23", "name": "Triple La Niña 2020–23",
                "type": "La Niña", "oni_peak": -1.1, "peak_season": "NDJ 2021",
                "start_year": 2020, "start_month": 8,
                "argentina_impact": (
                    "Tres temporadas consecutivas de La Niña — evento inusual. "
                    "Bajante histórica del Paraná en 2021 (mínimos en 77 años). "
                    "Sequía persistente en la Pampa Húmeda, pérdidas agrícolas "
                    "acumuladas superiores a USD 20.000 millones."
                ),
                "category": "moderado (persistente)",
            },
        ],
        "smn_outlook": {
            "url": "https://www.smn.gob.ar/clima/tendencias",
            "title": "Perspectiva Climática Trimestral — SMN Argentina",
            "description": "Pronóstico estacional oficial del Servicio Meteorológico Nacional de Argentina.",
        },
        "data_sources":  snapshot.data_sources or {},
        "last_updated":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": (
            "Índice automático — no constituye declaración oficial de NOAA. "
            "Las correlaciones son promedios espaciales regionales (CHIRPS v2.0, 1981-presente); "
            "el comportamiento puede diferir significativamente entre provincias dentro de una misma región."
        ),
    }
    return payload, monitor, lineage


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build enso.json for the Argentina ENSO Tracker")
    parser.add_argument(
        "--force-recompute", action="store_true",
        help="Bypass HTTP cache — fetch fresh data from all sources",
    )
    args = parser.parse_args()

    if args.force_recompute:
        from src.config import CACHE_DIR
        import shutil
        cache_dir = Path(CACHE_DIR)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Cache cleared: %s", cache_dir)

    logger.info("=== build.py: start ===")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload, monitor, lineage = build_payload()

    # Split heavy series into a separate history file for lazy loading.
    # Core enso.json keeps 24-month slices; full series go to enso-history.json.
    history_keys = ["oni_series", "soi_series", "sam_monthly", "spi_series"]
    history_payload = {}
    for k in history_keys:
        if k in payload and payload[k]:
            history_payload[k] = payload[k]

    with open(HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump(history_payload, fh, ensure_ascii=False)
    logger.info("Written %s (%.1f KB)", HISTORY_PATH, HISTORY_PATH.stat().st_size / 1024)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    logger.info("Written %s (%.1f KB)", OUT_PATH, OUT_PATH.stat().st_size / 1024)
    logger.info(
        "ONI=%.2f (%s) → %s  |  %d episodes  |  %d correlation rows",
        payload["current"]["oni_value"],
        payload["current"]["oni_season"],
        payload["current"]["phase"],
        len(payload["episodes"]),
        len(payload["correlations"]),
    )

    # Record output artifacts
    monitor.record_output(str(OUT_PATH), OUT_PATH.stat().st_size)
    monitor.record_output(str(HISTORY_PATH), HISTORY_PATH.stat().st_size)
    lineage.register_artifact(str(OUT_PATH), OUT_PATH.stat().st_size, "json",
                              key_count=len(payload))
    lineage.register_artifact(str(HISTORY_PATH), HISTORY_PATH.stat().st_size, "json",
                              key_count=len(history_payload))

    # 12. SST anomaly map (separate file to avoid bloating enso.json)
    logger.info("Fetching OISST v2.1 SST anomaly map…")
    with monitor.track_source("OISST SST map") as src:
        sst_map = fetch_sst_map(months=12)
        if sst_map:
            src.row_count = len(sst_map.get("times", []))
        else:
            src.status = "failed"
            src.error_message = "No data returned"
    if sst_map:
        with open(SST_MAP_PATH, "w", encoding="utf-8") as fh:
            json.dump(sst_map, fh, ensure_ascii=False)
        logger.info(
            "Written %s (%.1f KB) — %d snapshots, %dx%d grid",
            SST_MAP_PATH,
            SST_MAP_PATH.stat().st_size / 1024,
            len(sst_map["times"]),
            len(sst_map["lats"]),
            len(sst_map["lons"]),
        )
        monitor.record_output(str(SST_MAP_PATH), SST_MAP_PATH.stat().st_size)
        lineage.register_artifact(str(SST_MAP_PATH), SST_MAP_PATH.stat().st_size, "json")
    else:
        logger.warning("SST map unavailable — frontend will show fallback text")

    # 13. Pipeline monitoring — finalize and write outputs
    build_status = "success"
    failed_sources = [s.source_name for s in monitor._build.sources if s.status == "failed"]
    if failed_sources:
        build_status = "partial"
        monitor.add_warning(f"Data sources failed: {', '.join(failed_sources)}")
    monitor.finalize(build_status)
    monitor.write_health_json()
    monitor.emit_github_annotations()
    monitor.write_job_summary()
    logger.info(
        "Pipeline: %s in %.1fs — %d sources tracked",
        monitor._build.status, monitor._build.duration_seconds or 0,
        len(monitor._build.sources),
    )

    # 14. Lineage — write JSON output
    lineage.write_json()
    logger.info("Written %s", LINEAGE_PATH)

    # 15. DuckDB warehouse — populate from Parquet + live data
    if HAS_DUCKDB:
        try:
            warehouse = ENSOWarehouse()
            warehouse.initialize()
            loaded = warehouse.load_from_parquet()
            warehouse.load_episodes(payload["episodes"])
            lineage.store_in_duckdb(warehouse)
            warehouse.close()
            logger.info("DuckDB warehouse updated: %s", loaded)
        except Exception as exc:
            logger.warning("DuckDB warehouse failed: %s", exc)
    else:
        logger.info("DuckDB not installed — warehouse step skipped")

    logger.info("=== build.py: done ===")


if __name__ == "__main__":
    main()
