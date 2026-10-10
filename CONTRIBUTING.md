# Contributing to Argentina ENSO Tracker

## Prerequisites

- Python 3.11+
- Internet access (for NOAA/ERDDAP data fetching)

## Local Setup

```bash
# Clone the repo
git clone https://github.com/ammarmahfoud90/argentina-enso-tracker.git
cd argentina-enso-tracker

# Install dependencies
pip install -r requirements-data.txt
```

## Rebuild the Correlation Cache

```bash
python -m src.compute_correlations
```

This reads validated CHIRPS v3 observations and computes correlations using
the site's corrected method. It does not overwrite or truncate rainfall.
For a v2 checkout, run `python -m src.migrate_chirps_v3` first; this archives
v2 and recalibrates the full v3 history.
Result: `data/processed/correlations.parquet` (versioned in repo).

## Build the Site

To extend the observations before rebuilding:

```bash
pip install -r requirements-data.txt
python -m src.refresh_observations
```

The refresh validates each source independently and retains its previous
series on failure. Only complete months are accepted. The daily build does
not download climate observations; the weekly workflow does that separately.
Calibration stays fixed at 1981–2025 within CHIRPS v3. Product and spatial
support metadata prevent mixing versions or domains. Read `observations_refresh.json` for
the source cutoffs and the status of the last attempt.

```bash
python build.py                   # uses HTTP cache
python build.py --force-recompute # bypasses cache, fetches fresh data
```

Output: `site/data/enso.json`

## View Locally

```bash
python -m http.server 8080 --directory site
# Open http://localhost:8080
```

## Run Tests

```bash
pytest -m "not integration"   # unit tests (no network)
pytest                        # includes NOAA live integration tests
```

## Project Structure

- `build.py` — Data pipeline that generates `site/data/enso.json`
- `site/` — Static site (HTML/JS/CSS) served in production
- `src/` — Python modules for data fetching and processing
- `data/processed/` — Cached correlation Parquet files

## Guidelines

- All numbers displayed on the site must come from `enso.json` (no hardcoded values)
- Every data source must be documented in the README
- Test changes locally before pushing
- The GitHub Action runs `build.py` daily — do not commit stale `enso.json` manually
