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

IRI_ENSO_FORECAST_URL = (
    "https://iri.columbia.edu/our-expertise/climate/enso/"
)
"""IRI ENSO forecast page — human-readable plume; no structured API.
Probabilities scraped from JSON embedded in page when available."""

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
        # Covers: centre/south Buenos Aires province, south Santa Fe,
        # south Córdoba — the productive core of Argentina's grain belt.
        "description": "Pampa Húmeda (centro-sur Buenos Aires, sur Santa Fe, sur Córdoba)",
        "provinces": ["Buenos Aires (centro-sur)", "Santa Fe (sur)", "Córdoba (sur)"],
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
        # Covers: Mendoza, San Juan, La Rioja, San Luis
        "description": "Cuyo (Mendoza, San Juan, La Rioja, San Luis)",
        "provinces": ["Mendoza", "San Juan", "La Rioja", "San Luis"],
    },
    "Patagonia": {
        "lat_min": -55.0,
        "lat_max": -37.0,
        "lon_min": -73.0,
        "lon_max": -62.0,
        # Covers: Neuquén, Río Negro, Chubut, Santa Cruz, Tierra del Fuego
        "description": "Patagonia (Neuquén, Río Negro, Chubut, Santa Cruz)",
        "provinces": ["Neuquén", "Río Negro", "Chubut", "Santa Cruz"],
    },
}

# ---------------------------------------------------------------------------
# ENSO phase classification thresholds (NOAA CPC criteria)
# ---------------------------------------------------------------------------

ENSO_EL_NINO_THRESHOLD: float = 0.5   # ONI >= +0.5 for 5+ consecutive months
ENSO_LA_NINA_THRESHOLD: float = -0.5  # ONI <= -0.5 for 5+ consecutive months
ENSO_CONSECUTIVE_MONTHS: int = 5       # minimum consecutive months for phase declaration

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

# ---------------------------------------------------------------------------
# Network settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_SECONDS: int = 30
REQUEST_MAX_RETRIES: int = 3
REQUEST_RETRY_WAIT_SECONDS: int = 5
