"""DuckDB analytical warehouse for ENSO data.

Star schema with dimensional model:
  dim_region        — 5 Argentine climate regions
  dim_season        — 4 austral seasons + annual pseudo-season
  dim_enso_episode  — Detected El Niño/La Niña episodes
  fact_observations — Monthly ONI × precip × temp × SPI × SAM
  fact_correlations — Region × season × lag correlation results

The warehouse is rebuilt from Parquet files when missing (CI always rebuilds).
Locally, it persists between builds for fast iteration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import duckdb
import pandas as pd

from src.config import (
    CORRELATIONS_CACHE_PATH,
    PAIRS_CACHE_PATH,
    REGIONS,
    REGION_ORDER,
    WAREHOUSE_PATH,
)

logger = logging.getLogger(__name__)

# Deterministic IDs for dimensions
_REGION_IDS = {name: i + 1 for i, name in enumerate(REGION_ORDER)}

_SEASONS = [
    {"season_id": 0, "code": "ANN", "name_es": "Anual", "months": json.dumps([1,2,3,4,5,6,7,8,9,10,11,12])},
    {"season_id": 1, "code": "SON", "name_es": "Primavera", "months": json.dumps([9, 10, 11])},
    {"season_id": 2, "code": "DEF", "name_es": "Verano", "months": json.dumps([12, 1, 2])},
    {"season_id": 3, "code": "MAM", "name_es": "Otoño", "months": json.dumps([3, 4, 5])},
    {"season_id": 4, "code": "JJA", "name_es": "Invierno", "months": json.dumps([6, 7, 8])},
]

_SEASON_CODE_TO_ID = {s["code"]: s["season_id"] for s in _SEASONS}


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS dim_region (
    region_id   INTEGER PRIMARY KEY,
    name        VARCHAR NOT NULL UNIQUE,
    lat_min     DOUBLE,
    lat_max     DOUBLE,
    lon_min     DOUBLE,
    lon_max     DOUBLE,
    description VARCHAR,
    provinces   VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_season (
    season_id   INTEGER PRIMARY KEY,
    code        VARCHAR(3) NOT NULL UNIQUE,
    name_es     VARCHAR NOT NULL,
    months      VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_enso_episode (
    episode_id       INTEGER PRIMARY KEY,
    type             VARCHAR NOT NULL,
    start_date       VARCHAR NOT NULL,
    end_date         VARCHAR NOT NULL,
    duration_months  INTEGER,
    peak_oni         DOUBLE,
    peak_season      VARCHAR,
    category         VARCHAR
);

CREATE TABLE IF NOT EXISTS fact_observations (
    date_key         VARCHAR NOT NULL,
    region_id        INTEGER REFERENCES dim_region(region_id),
    oni              DOUBLE,
    precipitation_mm DOUBLE,
    temperature_c    DOUBLE,
    spi3             DOUBLE,
    sam              DOUBLE,
    PRIMARY KEY (date_key, region_id)
);

CREATE TABLE IF NOT EXISTS fact_correlations (
    region_id   INTEGER REFERENCES dim_region(region_id),
    season_id   INTEGER REFERENCES dim_season(season_id),
    lag         INTEGER NOT NULL,
    variable    VARCHAR NOT NULL,
    pearson_r   DOUBLE,
    pearson_p   DOUBLE,
    spearman_r  DOUBLE,
    spearman_p  DOUBLE,
    n_obs       INTEGER,
    n_eff       INTEGER,
    PRIMARY KEY (region_id, season_id, lag, variable)
);
"""


class ENSOWarehouse:
    """Embedded analytical database built from Parquet files + live data."""

    def __init__(self, db_path: str | Path = WAREHOUSE_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.db_path))

    def initialize(self) -> None:
        """Create schema and populate dimension tables."""
        self._create_schema()
        self._populate_dim_region()
        self._populate_dim_season()
        logger.info("Warehouse initialized at %s", self.db_path)

    def _create_schema(self) -> None:
        """Execute DDL for the star schema."""
        for stmt in _SCHEMA_DDL.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.con.execute(stmt)

    def _populate_dim_region(self) -> None:
        """Insert 5 regions from config (idempotent: deletes first)."""
        self.con.execute("DELETE FROM dim_region")
        for name, rid in _REGION_IDS.items():
            cfg = REGIONS[name]
            self.con.execute(
                "INSERT INTO dim_region VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    rid,
                    name,
                    cfg["lat_min"],
                    cfg["lat_max"],
                    cfg["lon_min"],
                    cfg["lon_max"],
                    cfg.get("description", ""),
                    json.dumps(cfg.get("provinces", []), ensure_ascii=False),
                ],
            )

    def _populate_dim_season(self) -> None:
        """Insert season dimension (idempotent: deletes first)."""
        self.con.execute("DELETE FROM dim_season")
        for s in _SEASONS:
            self.con.execute(
                "INSERT INTO dim_season VALUES (?, ?, ?, ?)",
                [s["season_id"], s["code"], s["name_es"], s["months"]],
            )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_from_parquet(self) -> dict[str, int]:
        """Bulk-load fact tables from committed Parquet files.

        Returns dict of {table_name: rows_loaded}.
        """
        loaded: dict[str, int] = {}

        # Correlations
        corr_path = Path(CORRELATIONS_CACHE_PATH)
        if corr_path.exists():
            corr_df = pd.read_parquet(corr_path)
            n = self._load_correlations_df(corr_df, variable="precip", season_code="ANN")
            loaded["fact_correlations_precip"] = n
            logger.info("Loaded %d precip correlation rows", n)

        # Temperature correlations
        temp_corr_path = Path("data/processed/temp_correlations.parquet")
        if temp_corr_path.exists():
            temp_df = pd.read_parquet(temp_corr_path)
            n = self._load_correlations_df(temp_df, variable="temp", season_code="ANN")
            loaded["fact_correlations_temp"] = n
            logger.info("Loaded %d temp correlation rows", n)

        # Observations from precipitation pairs
        pairs_path = Path(PAIRS_CACHE_PATH)
        if pairs_path.exists():
            pairs_df = pd.read_parquet(pairs_path)
            n = self._load_observations_from_pairs(pairs_df, var_type="precip")
            loaded["fact_observations_precip"] = n
            logger.info("Loaded %d precipitation observation rows", n)

        # Observations from temperature pairs
        temp_pairs_path = Path("data/processed/oni_temp_pairs.parquet")
        if temp_pairs_path.exists():
            temp_pairs_df = pd.read_parquet(temp_pairs_path)
            n = self._load_observations_from_pairs(temp_pairs_df, var_type="temp")
            loaded["fact_observations_temp"] = n
            logger.info("Loaded %d temperature observation rows", n)

        return loaded

    def _load_correlations_df(
        self, df: pd.DataFrame, variable: str, season_code: str
    ) -> int:
        """Insert correlations from a DataFrame into fact_correlations."""
        season_id = _SEASON_CODE_TO_ID.get(season_code, 0)
        count = 0
        for _, row in df.iterrows():
            region_name = row.get("region", "")
            rid = _REGION_IDS.get(region_name)
            if rid is None:
                continue
            lag = int(row.get("lag", 0))
            self.con.execute(
                """INSERT INTO fact_correlations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (region_id, season_id, lag, variable) DO UPDATE SET
                   pearson_r = EXCLUDED.pearson_r, pearson_p = EXCLUDED.pearson_p,
                   spearman_r = EXCLUDED.spearman_r, spearman_p = EXCLUDED.spearman_p,
                   n_obs = EXCLUDED.n_obs, n_eff = EXCLUDED.n_eff""",
                [
                    rid,
                    season_id,
                    lag,
                    variable,
                    float(row.get("pearson_r", 0)),
                    float(row.get("pearson_p", 1)),
                    float(row.get("spearman_r", 0)) if "spearman_r" in row else None,
                    float(row.get("spearman_p", 1)) if "spearman_p" in row else None,
                    int(row.get("n_obs", 0)) if "n_obs" in row else None,
                    int(row.get("n_eff", 0)) if "n_eff" in row else None,
                ],
            )
            count += 1
        return count

    def _load_observations_from_pairs(
        self, df: pd.DataFrame, var_type: str
    ) -> int:
        """Load fact_observations from ONI + regional pairs DataFrame.

        The pairs DataFrames have columns: date, oni, Region1, Region2, ...
        """
        count = 0
        region_cols = [c for c in df.columns if c in _REGION_IDS]
        for _, row in df.iterrows():
            date_key = str(row["date"])[:10]
            oni_val = float(row["oni"]) if pd.notna(row.get("oni")) else None
            for region_name in region_cols:
                rid = _REGION_IDS[region_name]
                val = float(row[region_name]) if pd.notna(row[region_name]) else None
                if val is None:
                    continue
                if var_type == "precip":
                    self.con.execute("""
                        INSERT INTO fact_observations
                        (date_key, region_id, oni, precipitation_mm)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT (date_key, region_id) DO UPDATE SET
                        oni = EXCLUDED.oni, precipitation_mm = EXCLUDED.precipitation_mm
                    """, [date_key, rid, oni_val, val])
                else:
                    self.con.execute("""
                        INSERT INTO fact_observations
                        (date_key, region_id, oni, temperature_c)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT (date_key, region_id) DO UPDATE SET
                        temperature_c = EXCLUDED.temperature_c
                    """, [date_key, rid, oni_val, val])
                count += 1
        return count

    def load_episodes(self, episodes: list[dict]) -> int:
        """Insert detected ENSO episodes into dim_enso_episode."""
        self.con.execute("DELETE FROM dim_enso_episode")
        for i, ep in enumerate(episodes, 1):
            self.con.execute(
                "INSERT INTO dim_enso_episode VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    i,
                    ep.get("type", ""),
                    ep.get("start", ""),
                    ep.get("end", ""),
                    ep.get("duration_months"),
                    ep.get("peak_oni"),
                    ep.get("peak_season", ""),
                    ep.get("category", ""),
                ],
            )
        logger.info("Loaded %d ENSO episodes", len(episodes))
        return len(episodes)

    # ------------------------------------------------------------------
    # Analytical queries
    # ------------------------------------------------------------------

    def strongest_enso_signal(
        self, season_code: str = "ANN", variable: str = "precip"
    ) -> list[dict]:
        """Which region has the strongest ENSO signal?

        Returns correlations sorted by |pearson_r| descending.
        """
        sid = _SEASON_CODE_TO_ID.get(season_code, 0)
        result = self.con.execute("""
            SELECT r.name AS region, c.lag, c.pearson_r, c.pearson_p,
                   c.n_obs, c.n_eff
            FROM fact_correlations c
            JOIN dim_region r ON c.region_id = r.region_id
            WHERE c.season_id = ? AND c.variable = ?
            ORDER BY ABS(c.pearson_r) DESC
        """, [sid, variable]).fetchall()
        cols = ["region", "lag", "pearson_r", "pearson_p", "n_obs", "n_eff"]
        return [dict(zip(cols, row)) for row in result]

    def region_correlations(self, region_name: str) -> list[dict]:
        """Get all correlations for a region across seasons and lags."""
        rid = _REGION_IDS.get(region_name)
        if rid is None:
            return []
        result = self.con.execute("""
            SELECT s.code AS season, c.lag, c.variable,
                   c.pearson_r, c.pearson_p, c.n_obs, c.n_eff
            FROM fact_correlations c
            JOIN dim_season s ON c.season_id = s.season_id
            WHERE c.region_id = ?
            ORDER BY s.season_id, c.lag
        """, [rid]).fetchall()
        cols = ["season", "lag", "variable", "pearson_r", "pearson_p", "n_obs", "n_eff"]
        return [dict(zip(cols, row)) for row in result]

    def episode_summary(self) -> list[dict]:
        """Summary of all detected episodes with duration and peak ONI."""
        result = self.con.execute("""
            SELECT type, start_date, end_date, duration_months,
                   peak_oni, peak_season, category
            FROM dim_enso_episode
            ORDER BY start_date
        """).fetchall()
        cols = ["type", "start_date", "end_date", "duration_months",
                "peak_oni", "peak_season", "category"]
        return [dict(zip(cols, row)) for row in result]

    def observation_coverage(self) -> dict[str, Any]:
        """Date range coverage per variable."""
        result: dict[str, Any] = {}
        for col, label in [
            ("oni", "ONI"),
            ("precipitation_mm", "Precipitation"),
            ("temperature_c", "Temperature"),
            ("spi3", "SPI-3"),
            ("sam", "SAM"),
        ]:
            row = self.con.execute(f"""
                SELECT MIN(date_key), MAX(date_key), COUNT({col})
                FROM fact_observations
                WHERE {col} IS NOT NULL
            """).fetchone()
            if row and row[2] > 0:
                result[label] = {
                    "start": row[0],
                    "end": row[1],
                    "count": row[2],
                }
        return result

    def seasonal_anomaly_by_episode(
        self, region_name: str, season_code: str
    ) -> list[dict]:
        """Mean precip anomaly during each episode for a region + season."""
        rid = _REGION_IDS.get(region_name)
        if rid is None:
            return []
        months = json.loads(
            dict((s["code"], s["months"]) for s in _SEASONS).get(season_code, "[]")
        )
        if not months:
            return []
        month_list = ",".join(str(m) for m in months)
        result = self.con.execute(f"""
            SELECT e.type, e.start_date, e.end_date, e.peak_oni, e.category,
                   AVG(o.precipitation_mm) AS mean_precip,
                   COUNT(*) AS n_months
            FROM fact_observations o
            JOIN dim_enso_episode e
              ON o.date_key >= e.start_date AND o.date_key <= e.end_date
            WHERE o.region_id = ?
              AND CAST(SUBSTR(o.date_key, 6, 2) AS INTEGER) IN ({month_list})
              AND o.precipitation_mm IS NOT NULL
            GROUP BY e.episode_id, e.type, e.start_date, e.end_date, e.peak_oni, e.category
            ORDER BY e.start_date
        """, [rid]).fetchall()
        cols = ["type", "start_date", "end_date", "peak_oni", "category",
                "mean_precip", "n_months"]
        return [dict(zip(cols, row)) for row in result]

    def execute(self, sql: str, params: list | None = None) -> Any:
        """Execute arbitrary SQL."""
        if params:
            return self.con.execute(sql, params)
        return self.con.execute(sql)

    def close(self) -> None:
        """Close the database connection."""
        self.con.close()

    def __enter__(self) -> ENSOWarehouse:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
