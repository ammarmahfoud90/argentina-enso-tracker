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
pip install -r requirements.txt
```

## Generate Correlation Cache (one-time, ~20 min)

```bash
python -m src.compute_correlations
```

This downloads the CHIRPS subset (~486 MB) and computes correlations.
Result: `data/processed/correlations.parquet` (versioned in repo).

## Build the Site

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
