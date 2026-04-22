"""Generate side-by-side ENSO comparison GIF: El Niño 2015-16 vs La Niña 2020-21.

Standalone script — does NOT integrate with the Streamlit dashboard.
Produces a LinkedIn-ready GIF showing monthly precipitation anomalies
over Argentina for two contrasting ENSO events.

Data source: CHIRPS v2.0 monthly via IRI OPeNDAP (same as dashboard pipeline).
Climatology: 1991–2020 (WMO standard 30-year normal).

Usage:
    python -m scripts.generate_enso_gif
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IRI_OPENDAP_URL = (
    "dap2://iridl.ldeo.columbia.edu"
    "/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/dods"
)

# Argentina bounding box (generous)
LAT_MIN, LAT_MAX = -55.0, -21.0
LON_MIN, LON_MAX = -74.0, -53.0

# CHIRPS missing data threshold
MISSING_THRESHOLD = -9990.0

# Cftime epoch for CHIRPS 360-day calendar
_EPOCH = datetime.date(1960, 1, 1)

# Climatology reference period (WMO standard)
CLIM_START, CLIM_END = 1991, 2020

# ENSO events: (label, list of (year, month) tuples for Oct–Mar)
EVENTS = {
    "El Niño 2015-16": [(2015, 10), (2015, 11), (2015, 12),
                         (2016, 1), (2016, 2), (2016, 3)],
    "La Niña 2020-21":  [(2020, 10), (2020, 11), (2020, 12),
                         (2021, 1), (2021, 2), (2021, 3)],
}

# Month labels for subtitle
MONTH_NAMES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Visual
ANOMALY_VMIN, ANOMALY_VMAX = -150, 150
FRAME_DURATION_S = 1.2
FIG_WIDTH_IN, FIG_HEIGHT_IN = 12, 6.75  # → 1200x675 at 100 dpi
DPI = 100

OUTPUT_PATH = Path("outputs/enso_comparison_2015_vs_2020.gif")


# ---------------------------------------------------------------------------
# CHIRPS date helpers (copied from src/fetch_chirps.py to keep standalone)
# ---------------------------------------------------------------------------

def _months_since_epoch_to_date(months_offset: float) -> datetime.date:
    """Convert fractional 'months since 1960-01-01' to a date (day=15)."""
    total_months = int(months_offset)
    year = _EPOCH.year + total_months // 12
    month = _EPOCH.month + total_months % 12
    if month > 12:
        month -= 12
        year += 1
    return datetime.date(year, month, 15)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("data/raw/chirps")


def load_chirps_gridded(start_year: int, end_year: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[datetime.date]]:
    """Load CHIRPS pixel-level data for the Argentina bbox via OPeNDAP.

    Caches the downloaded array locally in data/raw/chirps/ to avoid
    repeated multi-minute OPeNDAP transfers during development.

    Returns:
        (data, lats, lons, dates) where data has shape (n_time, n_lat, n_lon).
    """
    import pickle

    cache_file = _CACHE_DIR / f"chirps_argentina_{start_year}_{end_year}.pkl"
    if cache_file.exists():
        logger.info("Cargando datos CHIRPS desde caché local: %s", cache_file)
        with open(cache_file, "rb") as f:
            cached = pickle.load(f)
        return cached["data"], cached["lats"], cached["lons"], cached["dates"]

    import xarray as xr

    logger.info("Abriendo dataset CHIRPS via OPeNDAP…")
    try:
        ds = xr.open_dataset(IRI_OPENDAP_URL, engine="pydap", decode_times=False)
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo conectar al endpoint IRI OPeNDAP: {exc}\n"
            "Verifique su conexión o consulte https://iridl.ldeo.columbia.edu/"
        ) from exc

    # Build date index
    t_vals = ds["T"].values
    dates_all = [_months_since_epoch_to_date(v) for v in t_vals]

    # Time mask
    time_mask = np.array([(start_year <= d.year <= end_year) for d in dates_all])
    t_indices = np.where(time_mask)[0]

    if len(t_indices) == 0:
        raise RuntimeError(f"Sin datos CHIRPS para {start_year}–{end_year}")

    # Spatial mask
    lat_vals = ds["Y"].values
    lon_vals = ds["X"].values
    lat_mask = (lat_vals >= LAT_MIN) & (lat_vals <= LAT_MAX)
    lon_mask = (lon_vals >= LON_MIN) & (lon_vals <= LON_MAX)
    lat_indices = np.where(lat_mask)[0]
    lon_indices = np.where(lon_mask)[0]

    logger.info(
        "Descargando subconjunto: %d lats × %d lons × %d meses "
        "(%d–%d) via OPeNDAP (puede tardar varios minutos)…",
        len(lat_indices), len(lon_indices), len(t_indices),
        start_year, end_year,
    )

    precip = ds["precipitation"]
    t_slice = slice(int(t_indices[0]), int(t_indices[-1]) + 1)
    lat_slice = slice(int(lat_indices[0]), int(lat_indices[-1]) + 1)
    lon_slice = slice(int(lon_indices[0]), int(lon_indices[-1]) + 1)

    data = precip.isel(T=t_slice, Y=lat_slice, X=lon_slice).values
    lats = lat_vals[lat_slice]
    lons = lon_vals[lon_slice]
    dates = [dates_all[i] for i in range(t_indices[0], t_indices[-1] + 1)]

    logger.info("Datos recibidos: shape=%s", data.shape)
    ds.close()

    # Mask missing values as NaN
    data = data.astype(np.float64)
    data[data < MISSING_THRESHOLD] = np.nan

    # Cache locally for faster re-runs
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "wb") as f:
        pickle.dump({"data": data, "lats": lats, "lons": lons, "dates": dates}, f)
    logger.info("Datos guardados en caché: %s", cache_file)

    return data, lats, lons, dates


# ---------------------------------------------------------------------------
# Climatology & anomalies
# ---------------------------------------------------------------------------

def compute_monthly_climatology(
    data: np.ndarray,
    dates: list[datetime.date],
    clim_start: int = CLIM_START,
    clim_end: int = CLIM_END,
    target_months: set[int] | None = None,
) -> dict[int, np.ndarray]:
    """Compute per-pixel monthly climatological mean for target months.

    Args:
        target_months: Set of months (1-12) to compute. Default: Oct–Mar.

    Returns:
        Dict mapping month number → 2D array (n_lat, n_lon) of mean mm/month.
    """
    if target_months is None:
        target_months = {10, 11, 12, 1, 2, 3}

    climatology: dict[int, list[np.ndarray]] = {m: [] for m in target_months}

    for t_idx, d in enumerate(dates):
        if clim_start <= d.year <= clim_end and d.month in target_months:
            climatology[d.month].append(data[t_idx])

    result = {}
    for m, arrays in climatology.items():
        if not arrays:
            raise RuntimeError(
                f"Sin datos climatológicos para mes {m} en {clim_start}–{clim_end}"
            )
        stacked = np.stack(arrays, axis=0)
        result[m] = np.nanmean(stacked, axis=0)
        n_years = len(arrays)
        logger.info(
            "Climatología mes %02d: %d años, media espacial=%.1f mm/mes",
            m, n_years, np.nanmean(result[m]),
        )

    return result


def compute_anomalies(
    data: np.ndarray,
    dates: list[datetime.date],
    climatology: dict[int, np.ndarray],
    event_months: list[tuple[int, int]],
) -> list[np.ndarray]:
    """Compute anomaly grids for specific (year, month) pairs.

    Returns:
        List of 2D arrays (anomaly = observed - climatology), one per event month.
    """
    date_index = {(d.year, d.month): i for i, d in enumerate(dates)}
    anomalies = []

    for year, month in event_months:
        key = (year, month)
        if key not in date_index:
            raise RuntimeError(
                f"Fecha {year}-{month:02d} no encontrada en los datos CHIRPS. "
                "No se inventan datos — abortando."
            )
        t_idx = date_index[key]
        observed = data[t_idx]
        clim = climatology[month]
        anom = observed - clim
        anomalies.append(anom)

    return anomalies


def verify_anomalies(
    anomalies: list[np.ndarray],
    event_label: str,
    event_months: list[tuple[int, int]],
    warn_threshold: float = 500.0,
) -> None:
    """Log stats per frame and warn if physically implausible values found."""
    for i, (anom, (yr, mo)) in enumerate(zip(anomalies, event_months)):
        valid = anom[~np.isnan(anom)]
        if len(valid) == 0:
            logger.warning("ALERTA: %s %d-%02d — sin datos válidos!", event_label, yr, mo)
            continue

        vmin, vmax = float(np.min(valid)), float(np.max(valid))
        vmean, vmed = float(np.mean(valid)), float(np.median(valid))
        logger.info(
            "%s %d-%02d → mín=%.1f  máx=%.1f  media=%.1f  mediana=%.1f mm/mes",
            event_label, yr, mo, vmin, vmax, vmean, vmed,
        )

        if abs(vmin) > warn_threshold or abs(vmax) > warn_threshold:
            logger.warning(
                "⚠ ALERTA: anomalías extremas detectadas en %s %d-%02d "
                "(|valor| > %.0f mm/mes). Revisar manualmente antes de publicar.",
                event_label, yr, mo, warn_threshold,
            )


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _try_import_cartopy():
    """Try to import cartopy; return None if unavailable."""
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        return ccrs, cfeature
    except ImportError:
        logger.warning(
            "cartopy no disponible — usando fallback con geopandas/matplotlib puro"
        )
        return None, None


def _get_argentina_border():
    """Get Argentina border geometry for plotting (geopandas fallback).

    Downloads Natural Earth 110m countries shapefile directly from GitHub
    (geopandas >=1.0 no longer bundles datasets).
    """
    try:
        import geopandas as gpd

        ne_url = (
            "https://naciscdn.org/naturalearth/110m/cultural/"
            "ne_110m_admin_0_countries.zip"
        )
        world = gpd.read_file(ne_url)
        # Natural Earth uses ADMIN or NAME for country names
        name_col = "ADMIN" if "ADMIN" in world.columns else "NAME"
        argentina = world[world[name_col] == "Argentina"]
        if argentina.empty:
            logger.warning("Argentina no encontrada en Natural Earth dataset")
            return None
        logger.info("Borde de Argentina cargado desde Natural Earth 110m")
        return argentina
    except Exception as exc:
        logger.warning("No se pudo cargar borde de Argentina: %s", exc)
        return None


def generate_frames(
    lats: np.ndarray,
    lons: np.ndarray,
    anomalies_nino: list[np.ndarray],
    anomalies_nina: list[np.ndarray],
) -> list[np.ndarray]:
    """Generate matplotlib frames as RGBA arrays.

    Returns:
        List of numpy arrays (H, W, 4) for each frame.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    import io

    ccrs, cfeature = _try_import_cartopy()
    use_cartopy = ccrs is not None

    # Try geopandas border as fallback decoration
    argentina_gdf = None
    if not use_cartopy:
        argentina_gdf = _get_argentina_border()

    norm = TwoSlopeNorm(vmin=ANOMALY_VMIN, vcenter=0, vmax=ANOMALY_VMAX)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    nino_months = EVENTS["El Niño 2015-16"]
    nina_months = EVENTS["La Niña 2020-21"]

    frames = []

    for i in range(6):
        yr_n, mo_n = nino_months[i]
        yr_a, mo_a = nina_months[i]
        month_label = MONTH_NAMES_ES[mo_n]

        if use_cartopy:
            proj = ccrs.PlateCarree()
            fig, (ax1, ax2) = plt.subplots(
                1, 2,
                figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN),
                dpi=DPI,
                subplot_kw={"projection": proj},
            )
            axes = [ax1, ax2]
        else:
            fig, (ax1, ax2) = plt.subplots(
                1, 2,
                figsize=(FIG_WIDTH_IN, FIG_HEIGHT_IN),
                dpi=DPI,
            )
            axes = [ax1, ax2]

        datasets = [
            (ax1, anomalies_nino[i], "El Niño 2015-16"),
            (ax2, anomalies_nina[i], "La Niña 2020-21"),
        ]

        mappable = None
        for ax, anom, label in datasets:
            cf = ax.contourf(
                lon_grid, lat_grid, anom,
                levels=np.linspace(ANOMALY_VMIN, ANOMALY_VMAX, 31),
                cmap="RdBu",
                norm=norm,
                extend="both",
                **({"transform": ccrs.PlateCarree()} if use_cartopy else {}),
            )
            mappable = cf

            if use_cartopy:
                ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=proj)
                ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor="0.3")
                ax.add_feature(cfeature.COASTLINE, linewidth=0.5, edgecolor="0.3")
                ax.add_feature(
                    cfeature.NaturalEarthFeature(
                        "cultural", "admin_1_states_provinces_lines",
                        "50m", edgecolor="0.5", facecolor="none",
                    ),
                    linewidth=0.3,
                )
            else:
                ax.set_xlim(LON_MIN, LON_MAX)
                ax.set_ylim(LAT_MIN, LAT_MAX)
                ax.set_aspect("auto")
                if argentina_gdf is not None:
                    argentina_gdf.boundary.plot(
                        ax=ax, linewidth=0.6, color="0.3"
                    )

            ax.set_title(label, fontsize=13, fontweight="bold", pad=8)
            ax.tick_params(labelsize=8)

        # Suptitle + subtitle
        fig.suptitle(
            "Anomalía de precipitación — Argentina",
            fontsize=16, fontweight="bold", y=0.97,
        )
        subtitle = (
            f"{month_label} {yr_n} / {month_label} {yr_a}"
        )
        fig.text(
            0.5, 0.91, subtitle,
            ha="center", fontsize=12, style="italic", color="0.3",
        )

        # Shared colorbar
        cbar_ax = fig.add_axes([0.15, 0.08, 0.7, 0.022])
        cbar = fig.colorbar(mappable, cax=cbar_ax, orientation="horizontal")
        cbar.set_label("Anomalía (mm/mes)", fontsize=10)
        cbar.ax.tick_params(labelsize=8)

        # Footer
        fig.text(
            0.5, 0.015,
            "Fuente: CHIRPS v2.0 · Climatología 1991-2020 · argentina-enso-tracker.onrender.com",
            ha="center", fontsize=7, color="0.5",
        )

        fig.subplots_adjust(
            left=0.05, right=0.95, top=0.88, bottom=0.14, wspace=0.12,
        )

        # Render to RGBA array
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DPI, facecolor="white")
        plt.close(fig)
        buf.seek(0)

        from PIL import Image
        img = Image.open(buf).convert("RGB")
        frames.append(np.array(img))

    return frames


# ---------------------------------------------------------------------------
# GIF assembly
# ---------------------------------------------------------------------------

def assemble_gif(frames: list[np.ndarray], output_path: Path) -> None:
    """Assemble frames into an optimized looping GIF."""
    from PIL import Image

    output_path.parent.mkdir(parents=True, exist_ok=True)

    pil_frames = [Image.fromarray(f) for f in frames]

    duration_ms = int(FRAME_DURATION_S * 1000)

    pil_frames[0].save(
        output_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("GIF guardado: %s (%.2f MB)", output_path, size_mb)

    if size_mb > 8:
        logger.warning(
            "⚠ El GIF pesa %.1f MB — supera el objetivo de 8 MB. "
            "Considere reducir resolución o número de niveles de contorno.",
            size_mb,
        )


# ---------------------------------------------------------------------------
# Tests (minimal, per spec)
# ---------------------------------------------------------------------------

def _run_self_tests() -> None:
    """Run minimal sanity checks on core functions."""
    logger.info("Ejecutando tests internos…")

    # Test 1: anomaly = 0 when observed == climatology
    fake_clim = np.array([[100.0, 200.0], [50.0, 150.0]])
    fake_data = np.stack([fake_clim, fake_clim * 1.5], axis=0)
    fake_dates = [datetime.date(2015, 10, 15), datetime.date(2015, 11, 15)]
    clim = {10: fake_clim, 11: fake_clim}

    anoms = compute_anomalies(fake_data, fake_dates, clim, [(2015, 10)])
    assert np.allclose(anoms[0], 0.0, atol=1e-10), "Anomaly should be zero when obs == clim"

    anoms2 = compute_anomalies(fake_data, fake_dates, clim, [(2015, 11)])
    expected = fake_clim * 1.5 - fake_clim
    assert np.allclose(anoms2[0], expected, atol=1e-10), "Anomaly calculation mismatch"

    # Test 2: date conversion round-trip
    d = _months_since_epoch_to_date(252.5)  # Jan 1981
    assert d.year == 1981 and d.month == 1, f"Expected Jan 1981, got {d}"

    # Test 3: missing date raises RuntimeError
    try:
        compute_anomalies(fake_data, fake_dates, clim, [(2099, 1)])
        assert False, "Should have raised RuntimeError for missing date"
    except RuntimeError:
        pass

    logger.info("✓ Todos los tests internos pasaron correctamente.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _run_self_tests()

    # We need data from 1991 to 2021 (climatology 1991-2020 + La Niña extends to Mar 2021)
    data, lats, lons, dates = load_chirps_gridded(start_year=1991, end_year=2021)

    logger.info("Calculando climatología mensual 1991–2020 (Oct–Mar)…")
    climatology = compute_monthly_climatology(data, dates)

    # Compute anomalies for each event
    logger.info("Calculando anomalías para El Niño 2015-16…")
    anom_nino = compute_anomalies(
        data, dates, climatology, EVENTS["El Niño 2015-16"]
    )
    verify_anomalies(anom_nino, "El Niño", EVENTS["El Niño 2015-16"])

    logger.info("Calculando anomalías para La Niña 2020-21…")
    anom_nina = compute_anomalies(
        data, dates, climatology, EVENTS["La Niña 2020-21"]
    )
    verify_anomalies(anom_nina, "La Niña", EVENTS["La Niña 2020-21"])

    logger.info("Generando frames del GIF…")
    frames = generate_frames(lats, lons, anom_nino, anom_nina)

    logger.info("Ensamblando GIF…")
    assemble_gif(frames, OUTPUT_PATH)

    logger.info("¡Listo! Archivo: %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
