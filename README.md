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
| `build.py` | Fetches live NOAA/ERDDAP indices, reads correlation Parquet, detects ENSO episodes, fetches TAO subsurface data, parses IRI forecast probabilities from SVG, computes seasonal correlations, fetches OISST SST map, writes `site/data/enso.json` + `sst_map.json` |
| `site/data/enso.json` | Single source of truth for the frontend. Updated daily by GitHub Action |
| `site/data/sst_map.json` | OISST v2.1 SST anomaly grids for the equatorial Pacific (12 months, ~2 deg resolution) |
| `site/index.html` | Editorial dashboard: ONI hero + scale bar, indicators, interactive Plotly ONI chart, SOI tracker, subsurface temperature heatmap, Pacific SST anomaly map, IRI forecast Plotly stacked bar chart + model plume, historical event comparison, correlation heatmap with seasonal dropdown, regional risk section |
| `site/map.html` | Argentina map with D3 v7 + topojson; circles proportional to \|Pearson r\| |
| `site/js/advice.js` | Data-driven risk advice — conditioned on ONI magnitude, SOI trend, precipitation anomaly |
| `.github/workflows/daily-build.yml` | Cron 08:00 UTC + push to main — runs `build.py`, validates JSON, commits `enso.json` + `sst_map.json` if changed |

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
- **Pacific SST anomaly map**: Interactive Plotly heatmap of equatorial Pacific OISST v2.1 anomalies with Nino region overlays and 12-month time slider
- **IRI ENSO forecast panel**: Plotly stacked bar chart of El Nino/Neutral/La Nina probabilities per trimester (parsed from IRI SVG), plus model plume toggle
- **Data-driven risk advice**: Regional guidance using ONI magnitude, SOI trend, and recent precipitation anomalies
- **Correlation bar chart**: Plotly bar chart of best Pearson r per region with significance indicators and seasonal dropdown (SON/DEF/MAM/JJA)
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
| RONI (operational NOAA monitoring since Feb 2026) | NOAA CPC ERSSTv6 | No ONI substitution | Monthly |
| NOAA operational ENSO advisory | NOAA CPC | Explicit unavailable status | Dated advisory |
| ONI (legacy historical analysis) | NOAA CPC | — | Monthly |
| Nino 3.4 SST anomaly | ERDDAP (ncepNinoSSTwk) | NOAA CPC ERSSTv5 | Weekly -> monthly |
| SOI (standardized CPC scale) | NOAA CPC | ERDDAP (different normalization, explicitly labeled) | Monthly |
| Subsurface temperature | ERDDAP (pmelTaoMonT) | — | Monthly |
| SST anomaly map | OISST v2.1 final (ERDDAP ncdcOisst21Agg), native anom relative to 1971–2000 | Last dated grids labeled stale if fetch fails | Daily snapshots every 30 days; final product has its own latency |
| Precipitation observations | CHIRPS v2.0 final monthly (UCSB via IRI) | Last validated monthly series | Checked weekly; only complete published months |
| Regional temperature observations | NOAA PSL CPC Global Temperature, (tmax+tmin)/2 | Last validated monthly series | Checked weekly; only months with all calendar days |
| ENSO forecast | IRI Columbia (ensoforecast2 SVG) | NOAA CPC | Monthly |

---

## Regions Analyzed

| Region | Bounding Box (lat/lon) | Provinces |
|---|---|---|
| **Pampa Humeda** | -40/-29S, -65/-57W | BA (center-south), Santa Fe (south), Cordoba (south) |
| **NEA** | -29/-22S, -62/-53W | Chaco, Formosa, Corrientes, Misiones |
| **NOA** | -29/-22S, -69/-62W | Salta, Jujuy, Tucuman, Catamarca, Santiago del Estero |
| **Cuyo** | -36/-28S, -70/-65W | Mendoza, San Juan, La Rioja, San Luis |
| **Patagonia rainfall sample** | -50/-37S, -73/-62W | Partial Patagonia; excludes Tierra del Fuego and southernmost Santa Cruz |

These are approximate rectangular sampling domains, not verified administrative boundaries. CHIRPS v2 spans 50°S–50°N. Regional observations are arithmetic means of valid pixels, without national masks or area weighting; they include land outside Argentina and overlapping boxes. Temperature retains the requested full Patagonia box (-55/-37S), so rainfall and temperature do not share identical southern coverage.

---

## Correlation Methodology

1. **Annual association:** calendar-month rainfall or temperature anomalies relative to each month’s mean in the fixed 1981–2025 project calibration period. This reproduces the reference used before adding 2026; it is not a WMO climatological normal. Values are aligned to the current canonical NOAA ONI by actual calendar month.
2. **Seasonal association:** one observation per complete SON/DEF/MAM/JJA season; three-month rainfall totals or temperature means. December belongs to the following DEF year. The ONI is the published value for the central month, not an average of three overlapping ONI values.
3. **Inference:** approximate two-sided Pearson and rank-Spearman p values use estimated effective sample sizes. Benjamini–Yekutieli adjustment uses unrounded p values across region × lag × annual/four-season families (100 tests per variable and coefficient when all inputs are available). Colors and stars require corrected q, not nominal p.
4. **Frequency table:** one exploratory family across all phase/region/season cells, approximate two-sided binomial diagnostics with BY-adjusted q. No post hoc confirmatory subset or claim of independent validation. Threshold is the seasonal median in 1981–2025; anomaly percentages use that reference's seasonal mean. New complete seasons extend the analyzed sample without changing its reference. Counts and ranges are historical descriptions, not forecast probabilities or prediction intervals.
5. **ONI episodes:** five consecutive overlapping seasons beyond ±0.5 °C under the legacy ONI historical rule. This does not replace NOAA’s operational RONI-based advisory, which considers ocean-atmosphere coupling. Latest RONI values are provisional.
6. **SPI-3:** gamma-CDF standardization by calendar month fitted only to 1981–2025 three-month totals. New rainfall months are transformed with that fixed calibration. Missing calendar months invalidate three-month totals. WMO negative boundaries -1/-1.5/-2 enter moderate/severe/extreme drought respectively. SPI describes the dated observed period, not present drought if the source file is old.

The displayed coefficients are generated by `src/scientific.py` at each build. The old correlation Parquet files remain legacy provenance; their precomputed p flags are not used for published scientific conclusions. The build overwrites DuckDB correlations with the same annual and seasonal results and stores adjusted q values.

### Scientific scope and limits

Monthly climate observations start in 1981 and extend to each source's latest validated complete month. The exact cutoffs are generated in `precipitation_metadata` and `temperature_metadata`; they need not coincide. A daily build refreshes ENSO indices and forecasts. The separate weekly observation workflow incorporates newly published climate months and rebuilds anomalies, SPI, correlations, composites and frequency tables.

### Weekly observation updates

`Refresh regional climate observations` runs every Monday at 09:00 UTC (06:00 Argentina), on relevant code changes and on manual dispatch. It performs the following steps:

1. Read and validate both existing monthly series. Download CHIRPS v2 final monthly subsets and refresh CPC annual tmax/tmin files, including the growing current year.
2. Exclude the open current month. Temperature also requires every calendar day, matching tmax/tmin dates and no duplicate daily dates. Each day must retain at least 90% of the month's maximum valid regional pixel count; permanently missing ocean cells are excluded. Monthly regional inputs must have finite, bounded values, all five regions, unique dates and no calendar gaps.
3. Merge by calendar month. The 1981–2025 observations remain fixed. Later months may be refreshed for source revisions. Validate and round-trip a temporary Parquet before atomic replacement; unchanged data files are not rewritten.
4. On a download or candidate-validation failure, retain that variable's last valid Parquet byte-for-byte. The other variable can still update. `observations_refresh.json` records the checked date, status, source, units, cutoffs, row counts and file SHA-256. The site displays separate dates and reports retained data after an error.
5. Rebuild and scientifically validate the site before committing any outputs. Publication jobs share a concurrency group; Pages deploys after a successful daily or weekly workflow. Failed builds do not publish partial outputs.

Run locally with `python -m src.refresh_observations`, followed by `python build.py`. Raw CPC NetCDF caches are excluded from git. Tests cover real calendar continuity, repeat-run idempotency, independent source failures, invalid candidates, leap-month completeness, interrupted downloads, and the invariance of historical SPI when new extremes are appended.

This update retains the CHIRPS v2 product and original sampling domains. CHIRPS v3 migration, national masks, area weighting and station validation remain separate tasks. The updater cannot invent a month that the source has not published.

This is an exploratory association dashboard. No out-of-sample hindcast, causal attribution, temperature detrending, local flood model or river-level prediction is implemented. Autocorrelation correction and binomial p values remain approximate; FDR adjustment does not remove those assumptions. Composites with N<10 are explicitly small samples. Historical event peaks and years are derived from NOAA’s ONI series. Manual Paraná levels and impact amounts were removed because no per-observation traceable sources were available; the INA monitoring link remains.

Full-Patagonia rainfall would require a separately validated wider-coverage dataset and a new historical calibration. A CHIRPS v3 migration, country polygons or area weighting must not be silently mixed into the current CHIRPS v2 historical sample.

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
   at 08:00 UTC and commits `site/data/enso.json` if changed.
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
|       +-- sst_map.json         # OISST SST anomaly grids (generated)
+-- src/                          # Data pipeline (used by build.py)
|   +-- config.py                 # Regions, URLs, thresholds
|   +-- fetch_enso.py             # ONI, Nino 3.4, SOI from NOAA/ERDDAP
|   +-- fetch_subsurface.py       # TAO/TRITON subsurface temperature
|   +-- fetch_sst_map.py          # OISST v2.1 SST anomaly map
|   +-- fetch_iri_forecast.py     # IRI forecast probability parser
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

1. **IRI forecast**: Probabilities parsed from IRI/CCSR matplotlib SVG — format changes may require parser updates.
2. **CHIRPS single source**: No cross-validation with ERA5 in production pipeline.
3. **Causality**: Correlations are statistical, not causal.
4. **Spatial coverage**: Unweighted rectangular pixel means include foreign land; CHIRPS Patagonia only samples 37–50°S. Temperature has a different southern domain.
5. **Time and operational status**: ONI/RONI dates represent central months of three-month windows, not instantaneous observations; official advisories and observation cutoffs have separate dates.
6. **Subsurface data**: TAO buoy coverage varies; some depths may have gaps.

---

## Sources and Citations

- **RONI operational switch:** [NWS notice, effective February 1, 2026](https://www.weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf)
- **RONI definition / provisional values:** [NOAA CPC ERSSTv6](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/)
- **Operational diagnosis:** [NOAA CPC dated ENSO advisory](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml)
- **OISST map native baseline:** [ERDDAP ncdcOisst21Agg anom metadata](https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg.html)
- **CHIRPS geographic coverage:** [UCSB Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps)
- **SPI boundaries and interpretation:** [WMO SPI User Guide (2012)](https://www.droughtmanagement.info/literature/WMO_standardized_precipitation_index_user_guide_en_2012.pdf)
- **Dependent multiple comparisons:** [SciPy false_discovery_control, BY method and primary references](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html)
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
