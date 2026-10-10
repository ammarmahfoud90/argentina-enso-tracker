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

from src.compute_composites import compute_composites
from src.compute_spi import compute_all_spi
from src.climatology import CALIBRATION_PERIOD, reference_frame
from src.config import (
    CORRELATIONS_CACHE_PATH,
    ENSO_CONSECUTIVE_MONTHS,
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    LINEAGE_PATH,
    PAIRS_CACHE_PATH,
    REGION_ORDER,
    REGIONS,
)
from src.fetch_enso import fetch_enso_snapshot, fetch_operational_reference
from src.fetch_iri_forecast import fetch_iri_forecast
from src.fetch_sam import fetch_sam_series
from src.fetch_sst_map import fetch_sst_map
from src.fetch_subsurface import fetch_subsurface_cross_section
from src.lineage import LineageTracker
from src.parana_data import get_parana_data
from src.pipeline_monitor import PipelineMonitor
from src.refresh_observations import validate_monthly
from src.scientific import correlations as validated_correlations
from src.scientific import frequencies, notable_events, validate_publication

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
    lineage.register_source(
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

    # Recompute from dated observations and the current canonical ONI series.
    # The stored correlations Parquet is legacy provenance, not UI inference.
    pairs_path = Path(PAIRS_CACHE_PATH)
    if not pairs_path.exists():
        raise RuntimeError("Dated precipitation pairs are required for scientific statistics")
    pairs_df = pd.read_parquet(pairs_path)
    pairs_df["date"] = pd.to_datetime(pairs_df["date"])
    validate_monthly(pairs_df, "precipitation", datetime.now(timezone.utc).date())
    corr_records, seasonal_correlations = validated_correlations(
        pairs_df, snapshot.oni_series, calibration_period=CALIBRATION_PERIOD)

    region_meta = {}
    for region_name in REGION_ORDER:
        rows = [r for r in corr_records if r["region"] == region_name]
        significant = [r for r in rows if r["significant"]]
        best = max(significant or rows, key=lambda r: abs(r["pearson_r"]), default=None)
        cfg = REGIONS[region_name]
        bounds = {key: cfg[key] for key in ("lat_min", "lat_max", "lon_min", "lon_max")}
        bounds["lat_min"] = max(-50.0, bounds["lat_min"])
        region_meta[region_name] = {
            "provinces": cfg["provinces"] if region_name != "Patagonia" else ["Patagonia en la caja 37–50°S; sin Tierra del Fuego ni extremo sur"],
            "description": cfg["description"] if region_name != "Patagonia" else "Patagonia: muestra rectangular CHIRPS entre 37 y 50°S, no toda la región",
            "signal_strength": _signal_strength_label(abs(best["pearson_r"]) if best else 0, bool(significant)),
            "center_lat": round((bounds["lat_min"] + bounds["lat_max"]) / 2, 2),
            "center_lon": round((bounds["lon_min"] + bounds["lon_max"]) / 2, 2),
            "precipitation_bounds": bounds,
            "spatial_method": "Media aritmética de píxeles válidos en caja rectangular; sin máscara nacional ni ponderación de área. Incluye áreas fuera de Argentina."
        }

    # 7. Correlation cache metadata (version, period)
    cache_meta: dict = {}
    if "version" in corr_df.columns:
        cache_meta["version"]     = str(corr_df["version"].iloc[0])
        cache_meta["start_year"]  = int(corr_df["start_year"].iloc[0])
        cache_meta["end_year"]    = int(corr_df["end_year"].iloc[0])
        cache_meta["computed_at"] = str(corr_df["computed_at"].iloc[0])

    cache_meta["legacy_end_year"] = cache_meta.get("end_year")
    cache_meta["start_year"] = int(pairs_df.date.dt.year.min())
    cache_meta["end_year"] = int(pairs_df.date.dt.year.max())
    cache_meta["analysis_version"] = "2.1.0"
    cache_meta["computed_at"] = datetime.now(timezone.utc).isoformat()
    cache_meta["method"] = "Recomputed from dated climate observations and current canonical ONI; BY FDR"

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
        clim = reference_frame(pairs_df, CALIBRATION_PERIOD).groupby("month")[region_cols].mean()
        # Last 12 available months
        recent = pairs_df.sort_values("date").tail(12).reset_index(drop=True)
        for region in REGION_ORDER:
            if region not in pairs_df.columns:
                continue
            bars = []
            for _, row in recent.iterrows():
                m = int(row["month"])
                if pd.isna(row[region]):
                    continue
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

    # Seasonal correlations and frequency families share an explicit calendar.
    frequency_stats, frequency_methodology = frequencies(
        pairs_df, snapshot.oni_series, calibration_period=CALIBRATION_PERIOD)

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
            composite_analysis = compute_composites(
                pairs_df, snapshot.oni_series, calibration_period=CALIBRATION_PERIOD)
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
            spi_series, spi_current = compute_all_spi(pairs_df, calibration_period=CALIBRATION_PERIOD)
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

    # Temperature correlations use monthly anomalies and complete seasons too.
    temp_correlations, seasonal_temp_correlations = [], {}
    temperature_metadata = None
    temp_pairs_path = Path("data/processed/oni_temp_pairs.parquet")
    if temp_pairs_path.exists():
        temp_pairs_df = pd.read_parquet(temp_pairs_path)
        temp_pairs_df["date"] = pd.to_datetime(temp_pairs_df.date)
        validate_monthly(temp_pairs_df, "temperature", datetime.now(timezone.utc).date())
        temp_correlations, seasonal_temp_correlations = validated_correlations(
            temp_pairs_df, snapshot.oni_series, variable="temperature",
            calibration_period=CALIBRATION_PERIOD)
        temperature_metadata = {
            "source": "NOAA CPC Global Temperature", "units": "degC",
            "observations_start": temp_pairs_df.date.min().date().isoformat(),
            "observations_end": temp_pairs_df.date.max().date().isoformat(),
            "latest_complete_month": str(temp_pairs_df.date.max().to_period("M")),
            "definition": "Daily (tmax+tmin)/2; monthly means require every calendar day; then unweighted spatial pixel means",
            "daily_support_rule": "Every day must retain at least 90% of that month's maximum valid regional pixel count; permanently missing ocean cells do not count",
            "climatology_start_year": CALIBRATION_PERIOD[0],
            "climatology_end_year": CALIBRATION_PERIOD[1],
            "regional_coverage": {r: {k: REGIONS[r][k] for k in ("lat_min", "lat_max", "lon_min", "lon_max")} for r in REGION_ORDER},
        }

    refresh_path = Path("data/processed/observations_refresh.json")
    observation_refresh = json.loads(refresh_path.read_text()) if refresh_path.exists() else None
    if observation_refresh:
        for variable, state in observation_refresh["sources"].items():
            if state["status"] == "retained_after_error":
                monitor.add_warning(f"Weekly {variable} refresh failed; valid observations retained through {state['observations_end']}")

    with monitor.track_source("NOAA operational ENSO reference") as src:
        operational_reference = fetch_operational_reference()
        if operational_reference["errors"]:
            src.status = "failed"
            src.error_message = "; ".join(operational_reference["errors"])
    lineage.register_source(
        "NOAA RONI and advisory", url="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/",
        access_method="live_fetch", status="partial" if operational_reference["errors"] else "success",
        feeds_sections=["operational_reference", "roni_series"],
    )
    roni_series = operational_reference.pop("roni_series", [])

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
        "operational_reference": operational_reference,
        "roni_series": roni_series,
        "roni_series_24m": roni_series[-24:],
        "scientific_methodology": {
            "version": "2.1.0", "computed_at": datetime.now(timezone.utc).isoformat(),
            "calibration_period": list(CALIBRATION_PERIOD),
            "calibration_note": "Referencia fija 1981–2025 para mantener continuidad con la publicación previa. Es calibración del proyecto, no una normal WMO. Los meses nuevos amplían la muestra analizada, no la referencia.",
            "correlations": "Anomalías mensuales respecto de la climatología de cada mes; estaciones completas independientes en el calendario (sumas de lluvia, medias de temperatura). ONI del mes central publicado por NOAA, desplazado por lag en meses.",
            "inference": "p aproximado con n_eff por autocorrelación, también para rangos Spearman. q Benjamini-Yekutieli para cada familia de 100 pruebas región × lag × anual/estación, separada por variable y coeficiente. Los asteriscos usan q, no p nominal.",
            "limitations": "Estudio exploratorio sin validación fuera de muestra; temperatura sin detrendado. Tendencias, dependencia residual y revisión de índices pueden influir. Lag no equivale a anticipación operativa: ONI incluye tres meses y se publica después de cerrar la estación. No es un modelo de pronóstico ni una atribución causal.",
        },
        "precipitation_metadata": {
            "source": "CHIRPS v2.0", "observations_start": pairs_df.date.min().date().isoformat(),
            "observations_end": pairs_df.date.max().date().isoformat(),
            "latest_complete_month": str(pairs_df.date.max().to_period("M")),
            "last_month_end": pairs_df.date.max().to_period("M").end_time.date().isoformat(),
            "observation_age_days": (datetime.now(timezone.utc).date() - pairs_df.date.max().to_period("M").end_time.date()).days,
            "climatology_start_year": CALIBRATION_PERIOD[0],
            "climatology_end_year": CALIBRATION_PERIOD[1],
            "global_latitude_coverage": [-50, 50],
            "regional_coverage": {r: m["precipitation_bounds"] for r, m in region_meta.items()},
            "spatial_method": "Cajas rectangulares; media aritmética de píxeles válidos, sin máscara de Argentina ni ponderación de área",
            "limitations": "Patagonia: 37–50°S solamente. No incluye Tierra del Fuego ni todo Santa Cruz. La precipitación nival y orográfica tiene limitaciones. El SPI describe el último período observado, no la sequía actual si el archivo está atrasado.",
        },
        "temperature_metadata": temperature_metadata,
        "observation_refresh": observation_refresh,
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
        "parana_enso": get_parana_data(),
        "temp_correlations": temp_correlations if temp_correlations else None,
        "seasonal_temp_correlations": seasonal_temp_correlations if seasonal_temp_correlations else None,
        "subsurface":    subsurface,
        "iri_forecast":  iri_forecast,
        "notable_events": notable_events(snapshot.oni_series),
        "smn_outlook": {
            "url": "https://www.smn.gob.ar/clima/tendencias",
            "title": "Perspectiva Climática Trimestral — SMN Argentina",
            "description": "Pronóstico estacional oficial del Servicio Meteorológico Nacional de Argentina.",
        },
        "data_sources":  snapshot.data_sources or {},
        "last_updated":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": (
            "Índice automático — no constituye declaración oficial de NOAA. "
            "Análisis exploratorio de cajas rectangulares CHIRPS v2.0 (período disponible en precipitation_metadata); Patagonia solo hasta 50°S. "
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
        import shutil

        from src.config import CACHE_DIR
        cache_dir = Path(CACHE_DIR)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Cache cleared: %s", cache_dir)

    logger.info("=== build.py: start ===")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload, monitor, lineage = build_payload()
    validate_publication(payload)

    # Split heavy series into a separate history file for lazy loading.
    # Core enso.json keeps 24-month slices; full series go to enso-history.json.
    history_keys = ["oni_series", "roni_series", "soi_series", "sam_monthly", "spi_series"]
    history_payload = {}
    for k in history_keys:
        if k in payload and payload[k]:
            history_payload[k] = payload[k]

    with open(HISTORY_PATH, "w", encoding="utf-8") as fh:
        json.dump(history_payload, fh, ensure_ascii=False, allow_nan=False)
    logger.info("Written %s (%.1f KB)", HISTORY_PATH, HISTORY_PATH.stat().st_size / 1024)

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, allow_nan=False)

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
    if not sst_map and SST_MAP_PATH.exists():
        sst_map = json.loads(SST_MAP_PATH.read_text())
        sst_map.update(baseline="1971-2000", temporal_aggregation="daily snapshots at 30-day intervals")
        sst_map.setdefault("stale_since", datetime.now(timezone.utc).isoformat())
    if sst_map:
        with open(SST_MAP_PATH, "w", encoding="utf-8") as fh:
            json.dump(sst_map, fh, ensure_ascii=False, allow_nan=False)
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
            loaded["validated_correlations"] = warehouse.load_validated_correlations(payload)
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
