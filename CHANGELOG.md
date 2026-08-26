# Changelog

## 2026-08-26 — v3.1 Final Polish Release

### Critical Fixes
- **IRI forecast visualization**: Replaced broken embedded SVG approach with Plotly stacked bar chart showing El Nino/Neutral/La Nina probabilities per trimester. Probabilities parsed from IRI/CCSR matplotlib SVG during build. Model plume toggle retained as image.
- **Seasonal correlation disaggregation**: Added per-trimester correlations (SON/DEF/MAM/JJA) computed from pairs Parquet. New dropdown selector in the correlation section lets users compare annual vs seasonal signals.

### New Data Sources
- **Pacific SST anomaly map**: Interactive Plotly heatmap of OISST v2.1 equatorial Pacific anomalies (120E-70W, 20S-20N) with Nino region box overlays and 12-month time slider. Data stored in separate `sst_map.json`.
- **IRI forecast data fetcher**: New `src/fetch_iri_forecast.py` parses probability values from the IRI/CCSR figure3_plot SVG, extracting structured data for Plotly rendering.

### Scientific Integrity (from prior session)
- Subsurface heatmap labeled as absolute temperature (not anomaly)
- Teleconnection footnote about SAM (Southern Annular Mode)
- R-squared values in correlation bar chart
- Accurate latency notes per data source
- Stale data warning banner (>15 days)

### Documentation
- README updated with v3.1 features, SST map, IRI parser, seasonal correlations
- CHANGELOG updated with v3.1 release notes

---

## 2026-08-26 — v3.0 Ultimate Enhancement Release

### UX & Navigation
- **Sticky navigation menu**: Horizontal nav with section anchors and scroll-spy active state highlighting
- **Dark mode toggle**: Fixed button with CSS custom properties theming and localStorage persistence
- **ENSO alert banner**: Automatic warning for strong events (|ONI| >= 1.0)

### Visual Upgrades
- **Correlation bar chart**: Plotly bar chart showing best Pearson r per region with significance markers, replacing table-first display
- **SOI Plotly line chart**: Interactive bar chart with 3-month moving average overlay, replacing SVG-only bars
- **IRI forecast panel**: Enhanced with descriptive text, image error fallback, and better toggle labels

### New Features
- **CSV export button**: Download full ONI + SOI time series as CSV from the footer
- **Data sources panel**: Collapsible section with methodology, data sources table, and pipeline description

### SEO & Performance
- **Dynamic meta tags**: OG/Twitter title and description update based on current ENSO phase and ONI value
- **sitemap.xml and robots.txt**: Added for search engine discoverability
- **Data freshness thresholds**: Updated to 3/10 days (from 7/30) for more accurate staleness indication

### CI/CD
- **GitHub Action updated**: Runs at 08:00 UTC and on every push to main (previously only scheduled + manual)

### Documentation
- **README.md**: Added v3 features, GitHub Pages mirror link, "How to Contribute" section
- **CONTRIBUTING.md**: New file with setup instructions and contribution guidelines
- **CHANGELOG.md**: Added v3.0 release notes

---

## 2026-08-26 — Phase 2-5 Enhancement Release

### Phase 2: Visualizations & UX
- **Plotly ONI chart**: Interactive historical ONI chart with zoom, pan, hover tooltips, episode shading, El Nino/La Nina fill regions, and range switcher (1970/2000/2010)
- **Subsurface temperature heatmap**: Equatorial Pacific cross-section (165E-95W, 0-300m) from TAO/TRITON ERDDAP buoy data. Shows thermocline tilt as ENSO diagnostic
- **IRI ENSO forecast panel**: Embedded probability histogram and model plume from IRI/CCSR with toggle between views
- **Data-driven risk advice**: Enhanced advice module using ONI magnitude (weak/moderate/strong/very strong classification), SOI trend context, and recent precipitation anomalies

### Phase 3: Argentina-Specific Context
- **Historical event comparison**: Interactive Plotly overlay of current ENSO trajectory vs major past events (1997-98, 2015-16, 1982-83, etc.) with El Nino/La Nina toggle

### Phase 4: Performance & Deployment
- **`--force-recompute` flag**: Build option to bypass HTTP cache and fetch fresh data
- **Prerender-ready meta tags**: Open Graph and Twitter Card for link previews
- **Mobile responsive improvements**: Better layout on small screens (stacked indicators, resized charts, single-column risk grid)

### Phase 5: Documentation
- **README**: Complete rewrite with feature list, architecture, data sources, and setup instructions
- **BACKLOG**: Updated IRI forecast item as partially resolved
- **CHANGELOG**: Added this file

## 2026-08-26 — Phase 1: Data Pipeline & API Resilience

- **ERDDAP migration**: Nino 3.4 from ncepNinoSSTwk, SOI from erdlasNoix (structured CSV)
- **Dual-source fallback**: ERDDAP primary, CPC ASCII fallback — automatic failover
- **HTTP response cache**: File-based TTL cache (1h) with metadata
- **SOI Tracker section**: 24-month bar chart with trend classification badge
- **Data freshness indicator**: Color-coded dot based on data age
- **ENSOSnapshot extended**: Added soi_series and data_sources fields

## 2026-04-19 — v2 Editorial Redesign

- Static site architecture (Python build -> JSON -> vanilla JS)
- ONI hero section with gradient scale bar
- Correlation heatmap (Pearson, lags 0-3)
- Regional risk section with signal badges
- D3 Argentina map with correlation circles
- CHIRPS v2.0 precipitation correlations (1981-2025)
- Daily GitHub Action auto-refresh
