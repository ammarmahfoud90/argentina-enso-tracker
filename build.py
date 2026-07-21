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
    CORRELATIONS_CACHE_PATH,
    ENSO_CONSECUTIVE_MONTHS,
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    REGION_ORDER,
    REGIONS,
    SIGNIFICANCE_THRESHOLD,
)
from src.fetch_enso import fetch_enso_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build")

OUT_PATH = Path("site/data/enso.json")


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

def build_payload() -> dict:
    """Fetch live data, read Parquet cache, and assemble the JSON payload."""

    # 1. ENSO snapshot (live NOAA fetch)
    logger.info("Fetching ENSO indices from NOAA CPC…")
    snapshot = fetch_enso_snapshot()
    logger.info(
        "ONI=%.2f (%s) | Niño3.4=%.2f | SOI=%.1f | Phase: %s",
        snapshot.oni_value, snapshot.oni_season,
        snapshot.nino34_value, snapshot.soi_value, snapshot.phase,
    )

    # 2. Correlations Parquet
    corr_path = Path(CORRELATIONS_CACHE_PATH)
    if not corr_path.exists():
        logger.error(
            "Correlation cache missing at %s — run `python -m src.compute_correlations` first.",
            corr_path,
        )
        sys.exit(1)
    corr_df = pd.read_parquet(corr_path)
    logger.info("Correlations: %d rows from %s", len(corr_df), corr_path)

    # 3. Episode detection
    episodes = compute_episodes(snapshot.oni_series)

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

    # 5. Correlation records (region × lag)
    corr_records: list[dict] = []
    for _, row in corr_df.iterrows():
        corr_records.append({
            "region":         str(row["region"]),
            "lag":            int(row["lag"]),
            "pearson_r":      round(float(row["pearson_r"]), 4),
            "pearson_p":      round(float(row["pearson_p"]), 4),
            "pearson_stars":  _sig_stars(float(row["pearson_p"])),
            "spearman_r":     round(float(row["spearman_r"]), 4),
            "spearman_p":     round(float(row["spearman_p"]), 4),
            "n_obs":          int(row["n_obs"]),
        })

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

    # 8. Assemble final payload
    payload = {
        "current": {
            "oni_value":   round(snapshot.oni_value, 2),
            "oni_season":  snapshot.oni_season,
            "oni_date":    snapshot.oni_date.isoformat(),
            "nino34_value": round(snapshot.nino34_value, 2),
            "nino34_date": snapshot.nino34_date.isoformat(),
            "soi_value":   round(snapshot.soi_value, 1),
            "soi_date":    snapshot.soi_date.isoformat(),
            "phase":       snapshot.phase,
            "phase_source": snapshot.phase_source,
        },
        "oni_series":    oni_records,
        "oni_series_24m": oni_24m,
        "correlations":  corr_records,
        "region_meta":   region_meta,
        "region_order":  REGION_ORDER,
        "episodes":      episodes,
        "correlation_cache": cache_meta,
        "last_updated":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disclaimer": (
            "Índice automático — no constituye declaración oficial de NOAA. "
            "Las correlaciones son promedios espaciales regionales (CHIRPS v2.0, 1981-presente); "
            "el comportamiento puede diferir significativamente entre provincias dentro de una misma región."
        ),
    }
    return payload


def main() -> None:
    logger.info("=== build.py: start ===")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = build_payload()

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
    logger.info("=== build.py: done ===")


if __name__ == "__main__":
    main()
