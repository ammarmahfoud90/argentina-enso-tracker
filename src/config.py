"""Configuration: region bounding boxes, source URLs, ENSO thresholds.

All geographic bounds are defined as (lat_min, lat_max, lon_min, lon_max)
in decimal degrees, WGS-84.  Bounding boxes are derived from the
provincial boundaries reported by IGN (Instituto Geográfico Nacional,
Argentina) and cross-checked against GADM level-1 polygons.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# ENSO index source URLs — all NOAA CPC public endpoints
# ---------------------------------------------------------------------------

NOAA_ONI_URL = (
    "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
)
"""ONI (Oceanic Niño Index) — 3-month running mean of ERSST.v5 Niño 3.4 SST
anomalies, base period 1991-2020.  Updated monthly."""

NOAA_NINO34_URL = (
    "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"
)
"""Monthly Niño region SST anomalies (regions 1+2, 3, 4, 3.4) from
ERSSTv5, base period 1991-2020."""

NOAA_SOI_URL = (
    "https://www.cpc.ncep.noaa.gov/data/indices/soi"
)
"""Southern Oscillation Index (SOI) — standardised difference of
sea-level pressure between Tahiti and Darwin.  Updated monthly."""

# ---------------------------------------------------------------------------
# ERDDAP endpoints — structured CSV/JSON access (primary for Niño 3.4 & SOI)
# ---------------------------------------------------------------------------

ERDDAP_NINO34_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/tabledap/ncepNinoSSTwk.csv"
    "?time,Nino34_ssta"
)
"""ERDDAP weekly Niño 3.4 SST anomaly from OISST v2 (NCEP).
Returns CSV: time (ISO), Nino34_ssta (°C). Weekly, 1981–present."""

ERDDAP_SOI_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdlasNoix.csv"
    "?soi[(1950-01-16T12:00:00Z):1:(last)]"
)
"""ERDDAP monthly SOI from NOAA ERD oscillation indices.
Returns CSV: time (ISO), soi (standardised). Monthly, 1948–present."""

# ---------------------------------------------------------------------------
# TAO/TRITON subsurface temperature (ERDDAP)
# ---------------------------------------------------------------------------

TAO_ERDDAP_URL = (
    "https://coastwatch.pfeg.noaa.gov/erddap/tabledap/pmelTaoMonT.csv"
    "?time,longitude,depth,T_20"
    "&latitude=0"
    "&longitude>=165&longitude<=265"
    "&depth<=300"
    "&orderBy(%22time,longitude,depth%22)"
)
"""TAO/TRITON monthly temperature at equatorial Pacific buoy locations.
Latitude fixed at 0°, longitudes 165°E–265°E (95°W), depths 0–300m.
Returns CSV: time, longitude, depth, T_20 (°C)."""

TAO_RECENT_MONTHS: int = 3
"""Number of recent months to average for subsurface cross-section."""

TAO_TARGET_DEPTHS: list[int] = [1, 25, 50, 80, 100, 125, 150, 200, 250, 300]
"""Depth levels (m) to extract from TAO data for the heatmap."""

IRI_ENSO_FORECAST_URL = (
    "https://iri.columbia.edu/our-expertise/climate/enso/"
)
"""IRI ENSO forecast page — human-readable plume; no structured API.
Probabilities scraped from JSON embedded in page when available."""

IRI_FORECAST_PROBS_SVG = (
    "https://ensoforecast.iri.columbia.edu/figure3_plot/{year}/{month}"
)
"""IRI/CCSR model-based ENSO probability forecast — stacked bar chart (SVG).
Shows El Nino / Neutral / La Nina probabilities per trimester."""

IRI_FORECAST_PLUME_SVG = (
    "https://ensoforecast.iri.columbia.edu/figure4_plot/{year}/{month}"
)
"""IRI ENSO model predictions plume — individual model Nino 3.4 forecasts (SVG)."""

NOAA_CPC_ADVISORY_URL = (
    "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/"
)
"""NOAA CPC ENSO advisory — used as authoritative reference / fallback link."""

# ---------------------------------------------------------------------------
# CHIRPS precipitation source
# ---------------------------------------------------------------------------

CHIRPS_BASE_URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/netcdf/"
)
"""CHIRPS v2.0 global monthly NetCDF files (0.05° resolution, 1981-present).
File naming: chirps-v2.0.YYYY.months_p05.nc"""

IRI_CHIRPS_BASE_URL = (
    "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/"
)
"""IRI Data Library endpoint for CHIRPS — alternative access via OpenDAP."""

# ---------------------------------------------------------------------------
# Argentine regional bounding boxes
# lat/lon in decimal degrees (south latitudes are negative)
# Format: (lat_min, lat_max, lon_min, lon_max)
#
# Criterion: provincial administrative boundaries from IGN Argentina
# (https://www.ign.gob.ar/NuestrasActividades/InformacionGeoespacial/CapasVectoriales)
# then enlarged slightly (+0.1°) to ensure full coverage of border pixels
# in CHIRPS 0.05° grid.
# ---------------------------------------------------------------------------

REGIONS: dict[str, dict] = {
    "Pampa Húmeda": {
        "lat_min": -40.0,
        "lat_max": -29.0,
        "lon_min": -65.0,
        "lon_max": -57.0,
        # Covers: Buenos Aires (north/centre), all of Santa Fe, most of Córdoba,
        # and portions of Entre Ríos and La Pampa.  This is a rectangular
        # lat/lon box, not an administrative polygon.
        "description": "Pampa Húmeda (Buenos Aires norte y centro, Santa Fe, Córdoba, porciones de Entre Ríos y La Pampa)",
        "provinces": ["Buenos Aires (norte-centro)", "Santa Fe", "Córdoba", "Entre Ríos (parcial)", "La Pampa (este)"],
    },
    "NEA": {
        "lat_min": -29.0,
        "lat_max": -22.0,
        "lon_min": -62.0,
        "lon_max": -53.0,
        # Covers: Chaco, Formosa, Corrientes, Misiones
        "description": "Noreste Argentino (Chaco, Formosa, Corrientes, Misiones)",
        "provinces": ["Chaco", "Formosa", "Corrientes", "Misiones"],
    },
    "NOA": {
        "lat_min": -29.0,
        "lat_max": -22.0,
        "lon_min": -69.0,
        "lon_max": -62.0,
        # Covers: Salta, Jujuy, Tucumán, Catamarca, Santiago del Estero
        "description": "Noroeste Argentino (Salta, Jujuy, Tucumán, Catamarca, Stgo. del Estero)",
        "provinces": ["Salta", "Jujuy", "Tucumán", "Catamarca", "Santiago del Estero"],
    },
    "Cuyo": {
        "lat_min": -36.0,
        "lat_max": -28.0,
        "lon_min": -70.0,
        "lon_max": -65.0,
        # Covers: Mendoza, San Juan, La Rioja, San Luis.
        # Rectangular box — minor overlap with NOA at lat -29 to -28.
        "description": "Cuyo (Mendoza, San Juan, La Rioja, San Luis)",
        "provinces": ["Mendoza", "San Juan", "La Rioja", "San Luis"],
    },
    "Patagonia": {
        "lat_min": -55.0,
        "lat_max": -37.0,
        "lon_min": -73.0,
        "lon_max": -62.0,
        # Covers: Neuquén, Río Negro, Chubut, Santa Cruz, Tierra del Fuego.
        # Rectangular box — minor overlap with Pampa Húmeda in eastern La Pampa area.
        "description": "Patagonia (Neuquén, Río Negro, Chubut, Santa Cruz, Tierra del Fuego)",
        "provinces": ["Neuquén", "Río Negro", "Chubut", "Santa Cruz", "Tierra del Fuego"],
    },
}

# ---------------------------------------------------------------------------
# Canonical region display order (used in Section 3 tables and charts)
# ---------------------------------------------------------------------------

REGION_ORDER: list[str] = ["Pampa Húmeda", "NEA", "NOA", "Cuyo", "Patagonia"]

# ---------------------------------------------------------------------------
# ENSO phase classification thresholds (NOAA CPC criteria)
# ---------------------------------------------------------------------------

ENSO_EL_NINO_THRESHOLD: float = 0.5   # ONI >= +0.5 for 5+ consecutive months
ENSO_LA_NINA_THRESHOLD: float = -0.5  # ONI <= -0.5 for 5+ consecutive months
ENSO_CONSECUTIVE_MONTHS: int = 5       # minimum consecutive months for phase declaration

# Alert banner settings (Feature 2)
ONI_ALERT_WINDOW: int = 3  # recent seasons inspected for trend / transition detection

# ---------------------------------------------------------------------------
# Correlation analysis settings
# ---------------------------------------------------------------------------

CHIRPS_START_YEAR: int = 1981  # CHIRPS data availability start
CORRELATION_LAGS: list[int] = [0, 1, 2, 3]  # months ONI leads precipitation
SIGNIFICANCE_THRESHOLD: float = 0.05  # p-value cutoff for "significant"

# ---------------------------------------------------------------------------
# Correlation cache
# ---------------------------------------------------------------------------

CORRELATIONS_CACHE_PATH: str = "data/processed/correlations.parquet"
CORRELATIONS_CACHE_VERSION: str = "1.0.0"
PAIRS_CACHE_PATH: str = "data/processed/oni_precip_pairs.parquet"

# ---------------------------------------------------------------------------
# Data freshness
# ---------------------------------------------------------------------------

DATA_STALENESS_THRESHOLD_DAYS: int = 60
"""Warn when any individual data source's latest date lags the most-recent
source by more than this many days (indicates a source has stopped updating)."""

# ---------------------------------------------------------------------------
# API response cache
# ---------------------------------------------------------------------------

CACHE_DIR: str = "data/cache"
CACHE_TTL_SECONDS: int = 3600  # 1 hour — prevents rate-limiting during builds

# ---------------------------------------------------------------------------
# Network settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS: int = 30
REQUEST_MAX_RETRIES: int = 3
REQUEST_RETRY_WAIT_SECONDS: int = 5
