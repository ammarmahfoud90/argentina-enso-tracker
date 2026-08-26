# Argentina ENSO Impact Tracker

Primer entregable de **FRIS (FloodRisk Intelligence System)**.
Sitio editorial estatico que muestra el estado actual del ENSO (El Nino / La Nina)
y su correlacion historica con precipitacion en 5 regiones de Argentina.

**Live (Render):** [argentina-enso-tracker.onrender.com](https://argentina-enso-tracker.onrender.com/)
**Mirror (GitHub Pages):** [ammarmahfoud90.github.io/argentina-enso-tracker](https://ammarmahfoud90.github.io/argentina-enso-tracker/)

---

## Arquitectura

El proyecto es un **sitio estatico** generado por un pipeline Python.
No hay servidor de aplicacion en produccion.

```
build.py  ->  site/data/enso.json  ->  site/index.html  (Plotly + vanilla JS)
                                   ->  site/map.html     (D3 v7 + topojson)
```

| Componente | Descripcion |
|---|---|
| `build.py` | Fetches live NOAA/ERDDAP indices, reads correlation Parquet, detects ENSO episodes, fetches TAO subsurface data, computes IRI forecast URLs, writes `site/data/enso.json` |
| `site/data/enso.json` | Single source of truth for the frontend. Updated daily by GitHub Action |
| `site/index.html` | Editorial dashboard: ONI hero + scale bar, indicators, interactive Plotly ONI chart, SOI tracker, subsurface temperature heatmap, IRI forecast panel, historical event comparison, correlation heatmap, regional risk section |
| `site/map.html` | Argentina map with D3 v7 + topojson; circles proportional to \|Pearson r\| |
| `site/js/advice.js` | Data-driven risk advice — conditioned on ONI magnitude, SOI trend, precipitation anomaly |
| `.github/workflows/daily-build.yml` | Cron 07:00 UTC — runs `build.py`, validates JSON, commits if changed |

**Data rule:** every number rendered on the site comes from `enso.json`
(generated from NOAA CPC + ERDDAP + Parquet CHIRPS). No synthetic data generators.

---

## Features

### Data Pipeline (Phase 1)
- **ERDDAP migration**: Nino 3.4 and SOI fetched from ERDDAP structured CSV with CPC ASCII fallback
- **HTTP response cache**: file-based TTL cache (1h) prevents rate-limiting during builds
- **Dual-source fallback**: automatic failover between ERDDAP (primary) and CPC (fallback)
- **Data freshness indicator**: green/yellow/red dot based on data age

### Visualizations (Phase 2)
- **Interactive ONI chart**: Plotly.js with zoom, pan, hover tooltips, episode shading, range switcher
- **SOI Tracker**: 24-month bar chart with trend classification (early warning indicator)
- **Subsurface temperature heatmap**: Equatorial Pacific cross-section (165E-95W, 0-300m depth) from TAO/TRITON buoys via ERDDAP — shows thermocline tilt as ENSO diagnostic
- **IRI ENSO forecast panel**: Embedded probability histogram and model plume from IRI/CCSR with toggle
- **Data-driven risk advice**: Regional guidance using ONI magnitude, SOI trend, and recent precipitation anomalies
- **Correlation bar chart**: Plotly bar chart of best Pearson r per region with significance indicators
- **SOI Plotly chart**: Interactive bar + line chart with 3-month moving average overlay

### Argentina Context (Phase 3)
- **Historical event comparison**: Interactive overlay of current ENSO trajectory against major past events (1997-98, 2015-16, 1982-83, etc.)
- **Regional impact map**: D3 choropleth with correlation-sized signal circles

### UX & Navigation (v3)
- **Sticky navigation menu**: Section anchors with scroll-spy highlighting
- **Dark mode toggle**: CSS custom properties + localStorage persistence
- **ENSO alert banner**: Automatic warning for strong events (|ONI| >= 1.0)
- **CSV export**: Download ONI + SOI series as CSV
- **Data sources panel**: Collapsible methodology and sources table

### Performance (Phase 4 + v3)
- **`--force-recompute` flag**: Bypasses HTTP cache for fresh data
- **Prerender-ready**: Dynamic Open Graph and Twitter Card meta tags (phase + ONI value)
- **Mobile responsive**: Optimized layout for small screens
- **SEO**: sitemap.xml, robots.txt, dynamic page title

---

## Data Sources

| Index | Primary Source | Fallback | Update Frequency |
|---|---|---|---|
| ONI (Oceanic Nino Index) | NOAA CPC | — | Monthly |
| Nino 3.4 SST anomaly | ERDDAP (ncepNinoSSTwk) | NOAA CPC ERSSTv5 | Weekly -> monthly |
| SOI | ERDDAP (erdlasNoix) | NOAA CPC | Monthly |
| Subsurface temperature | ERDDAP (pmelTaoMonT) | — | Monthly |
| Precipitation (historical) | CHIRPS v2.0 (UCSB) | — | Annual |
| ENSO forecast | IRI Columbia / NOAA CPC | — | Monthly |

---

## Regions Analyzed

| Region | Bounding Box (lat/lon) | Provinces |
|---|---|---|
| **Pampa Humeda** | -40/-29S, -65/-57W | BA (center-south), Santa Fe (south), Cordoba (south) |
| **NEA** | -29/-22S, -62/-53W | Chaco, Formosa, Corrientes, Misiones |
| **NOA** | -29/-22S, -69/-62W | Salta, Jujuy, Tucuman, Catamarca, Santiago del Estero |
| **Cuyo** | -36/-28S, -70/-65W | Mendoza, San Juan, La Rioja, San Luis |
| **Patagonia** | -55/-37S, -73/-62W | Neuquen, Rio Negro, Chubut, Santa Cruz |

Boundaries derived from IGN Argentina vector data, adjusted +0.1 for full CHIRPS pixel coverage.

---

## Correlation Methodology

1. **Monthly precipitation** per region: spatial average of CHIRPS v2.0 (0.05 resolution, 1981-present)
2. **ONI monthly**: Nino 3.4 anomaly 3-month running mean (NOAA CPC, base 1991-2020)
3. **Correlation**: Pearson and Spearman between ONI and precipitation, lags 0-3 months
4. **Significance**: two-tailed p-value (threshold p < 0.05)
5. **Episode detection**: ONI >= +0.5 / <= -0.5 for >= 5 consecutive overlapping seasons (NOAA CPC criterion)

### Results (CHIRPS 1981-2025)

| Region | Best Pearson r | Lag | p-value |
|---|---|---|---|
| NEA | +0.223 | 0m | \*\*\* |
| Pampa Humeda | +0.186 | 0m | \*\*\* |
| NOA | - | - | n.s. |
| Cuyo | - | - | n.s. |
| Patagonia | - | - | n.s. |

---

## Local Setup

### Requirements
```
Python 3.11+
pip install -r requirements-data.txt   # for build.py
pip install -r requirements.txt        # for everything
```

### Generate correlation cache (one-time, ~20 min)
```bash
python -m src.compute_correlations
```
Downloads CHIRPS subset via IRI OPeNDAP (~486 MB, 1981-2025).
Result saved to `data/processed/correlations.parquet` (versioned in repo).

### Build the site JSON
```bash
python build.py                   # uses HTTP cache
python build.py --force-recompute # bypasses cache, fetches fresh data
# -> site/data/enso.json
```
Requires internet for NOAA/ERDDAP fetch. Reads cached Parquet, does not re-run CHIRPS.

### View locally
```bash
python -m http.server 8080 --directory site
# -> http://localhost:8080
```

### Tests
```bash
pytest -m "not integration"   # unit tests (no network)
pytest                        # includes NOAA live integration tests
```

---

## Deploy (Render Static Site)

1. Push to GitHub.
2. Render: **New -> Static Site -> connect repo**.
3. Configure:
   - **Publish directory:** `site`
   - **Build command:** *(empty — JSON is committed by GitHub Action)*
4. GitHub Action (`.github/workflows/daily-build.yml`) runs `build.py` daily
   at 07:00 UTC and commits `site/data/enso.json` if changed.
   Render detects the new commit and redeploys automatically.

---

## Repo Structure

```
argentina-enso-tracker/
+-- build.py                      # Pipeline -> site/data/enso.json
+-- render.yaml                   # Render static site config
+-- requirements.txt
+-- requirements-data.txt
+-- pyproject.toml                # ruff + black + pytest config
+-- .github/
|   +-- workflows/
|       +-- daily-build.yml       # Daily cron: fetch -> JSON -> commit
+-- site/                         # Static site (served in production)
|   +-- index.html                # Main dashboard (Plotly + vanilla JS)
|   +-- map.html                  # D3 map + topojson
|   +-- js/
|   |   +-- advice.js             # Data-driven risk advice
|   +-- data/
|       +-- enso.json             # Generated by build.py (versioned)
+-- src/                          # Data pipeline (used by build.py)
|   +-- config.py                 # Regions, URLs, thresholds
|   +-- fetch_enso.py             # ONI, Nino 3.4, SOI from NOAA/ERDDAP
|   +-- fetch_subsurface.py       # TAO/TRITON subsurface temperature
|   +-- fetch_chirps.py           # CHIRPS download and processing
|   +-- compute_correlations.py   # One-shot correlation computation
|   +-- utils.py                  # HTTP retry, caching, logging
+-- data/
|   +-- raw/                      # gitignored (CHIRPS NetCDF)
|   +-- processed/
|       +-- correlations.parquet  # Versioned - no CHIRPS re-run in prod
+-- tests/
    +-- test_correlations.py
    +-- test_fetch_enso.py
```

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and contribution guidelines.

---

## Known Limitations

1. **IRI forecast**: No structured API — SVGs are embedded from IRI servers (may be unavailable occasionally).
2. **CHIRPS single source**: No cross-validation with ERA5 in production pipeline.
3. **Causality**: Correlations are statistical, not causal.
4. **Spatial resolution**: Bounding boxes average over heterogeneous administrative units.
5. **ONI latency**: The index has ~2 month publication lag.
6. **Subsurface data**: TAO buoy coverage varies; some depths may have gaps.

---

## Sources and Citations

- **ONI / SOI**: NOAA Climate Prediction Center — `https://www.cpc.ncep.noaa.gov/`
- **Nino 3.4 SST**: NOAA ERSSTv5 / ERDDAP — `https://coastwatch.pfeg.noaa.gov/erddap/`
- **TAO/TRITON**: NOAA PMEL — `https://www.pmel.noaa.gov/tao/`
- **CHIRPS v2.0**: Funk, C. et al. (2015). *The climate hazards infrared precipitation with stations.* Scientific Data, 2, 150066. DOI: [10.1038/sdata.2015.66](https://doi.org/10.1038/sdata.2015.66)
- **ENSO Forecast**: IRI Columbia University — `https://iri.columbia.edu/`

---

## Disclaimer

This tracker is a **technical demonstration** developed as part of the
FRIS (FloodRisk Intelligence System) portfolio. **It does not constitute
professional advice of any kind.** For operational risk analysis contact
the FRIS team.

Indices are computed automatically from public sources — they do not
constitute an official NOAA declaration.
