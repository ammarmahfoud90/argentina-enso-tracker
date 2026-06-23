"""Argentina ENSO Impact Tracker — Streamlit dashboard.

Entry point: ``streamlit run app.py``

Sections:
    1. Estado ENSO actual (ONI, Niño 3.4, SOI + fase)
    2. Pronóstico ENSO a 6 meses (IRI / NOAA)
    3. Correlación histórica ENSO vs precipitación (desde Parquet cache)
    4. Implicaciones de riesgo por región
    5. Metadata y footer
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from src.config import (
    CORRELATIONS_CACHE_PATH,
    CORRELATIONS_CACHE_VERSION,
    DATA_STALENESS_THRESHOLD_DAYS,
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    NOAA_CPC_ADVISORY_URL,
    NOAA_NINO34_URL,
    NOAA_ONI_URL,
    NOAA_SOI_URL,
    ONI_ALERT_WINDOW,
    PAIRS_CACHE_PATH,
    REGIONS,
    SIGNIFICANCE_THRESHOLD,
)
from src.fetch_enso import ENSOSnapshot, fetch_enso_snapshot
from src.fetch_forecast import ENSOForecast, ForecastQuarter, fetch_enso_forecast

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Argentina ENSO Impact Tracker",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Data-Dense Dashboard design system
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

    /* ── Base typography ── */
    html, body, [class*="css"] {
        font-family: 'Fira Sans', sans-serif;
    }
    h1, h2, h3, h4 {
        font-family: 'Fira Code', monospace !important;
        color: #1E3A8A !important;
        letter-spacing: -0.02em;
    }

    /* ── App background — use Streamlit CSS variable so dark mode works ── */
    .stApp {
        background-color: var(--background-color, #F8FAFC);
    }

    /* ── Sidebar — always dark navy regardless of theme ── */
    [data-testid="stSidebar"] {
        background-color: #1E3A8A;
    }
    [data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }
    [data-testid="stSidebar"] a {
        color: #93C5FD !important;
        text-decoration: none;
        transition: color 150ms ease;
    }
    [data-testid="stSidebar"] a:hover {
        color: #BFDBFE !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: #2D4FA0 !important;
    }

    /* ── Metric cards ── */
    [data-testid="metric-container"] {
        background: var(--secondary-background-color, #FFFFFF);
        border: 1px solid rgba(30, 64, 175, 0.18);
        border-top: 3px solid #1E40AF;
        border-radius: 8px;
        padding: 16px 20px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        transition: box-shadow 200ms ease;
    }
    [data-testid="metric-container"]:hover {
        box-shadow: 0 4px 12px rgba(30,64,175,0.12);
    }
    [data-testid="metric-container"] [data-testid="stMetricLabel"] {
        font-family: 'Fira Sans', sans-serif !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        /* color intentionally unset — inherits from Streamlit theme */
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Fira Code', monospace !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        /* color intentionally unset — inherits from Streamlit theme */
    }

    /* ── Section headers ── */
    h2 {
        border-bottom: 2px solid rgba(219, 234, 254, 0.7);
        padding-bottom: 8px;
        margin-top: 8px !important;
    }

    /* ── Containers with border — use CSS variable for background ── */
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 10px !important;
        border: 1px solid rgba(219, 234, 254, 0.6) !important;
        background: var(--secondary-background-color, #FFFFFF) !important;
        box-shadow: 0 1px 4px rgba(30,64,175,0.06);
        transition: box-shadow 200ms ease, border-color 200ms ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div:hover {
        box-shadow: 0 4px 16px rgba(30,64,175,0.10);
        border-color: rgba(147, 197, 253, 0.8) !important;
    }

    /* ── Link buttons ── */
    [data-testid="stLinkButton"] > a {
        background-color: #1E40AF !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        font-family: 'Fira Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        border: none !important;
        transition: background-color 150ms ease, box-shadow 150ms ease;
    }
    [data-testid="stLinkButton"] > a:hover {
        background-color: #1D4ED8 !important;
        box-shadow: 0 4px 12px rgba(30,64,175,0.30) !important;
    }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        border: 1px solid rgba(226, 232, 240, 0.6) !important;
        border-radius: 8px !important;
        background: var(--secondary-background-color, #FFFFFF) !important;
        margin-bottom: 8px;
        transition: border-color 150ms ease;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(147, 197, 253, 0.8) !important;
    }
    [data-testid="stExpander"] summary {
        font-family: 'Fira Sans', sans-serif !important;
        font-weight: 600 !important;
        /* color inherits from Streamlit theme */
        cursor: pointer;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        border: 1px solid rgba(226, 232, 240, 0.5) !important;
        overflow: hidden;
    }

    /* ── Divider ── */
    hr {
        border-color: rgba(226, 232, 240, 0.6) !important;
        margin: 24px 0 !important;
    }

    /* ── Caption ── */
    [data-testid="stCaptionContainer"] {
        font-size: 0.78rem !important;
        /* color inherits from Streamlit theme */
    }

    /* ── Warning / Error ── */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        font-family: 'Fira Sans', sans-serif !important;
    }

    /* ── Title ── */
    [data-testid="stAppViewContainer"] h1 {
        font-size: 2rem !important;
        font-weight: 700 !important;
    }

    /* ── Dark mode overrides ──────────────────────────────────────────────── */
    /* Streamlit sets data-theme="dark" on the wrapping div when dark mode is active */

    [data-theme="dark"] h1,
    [data-theme="dark"] h2,
    [data-theme="dark"] h3,
    [data-theme="dark"] h4 {
        color: #60A5FA !important;   /* lighter blue readable on dark backgrounds */
    }

    [data-theme="dark"] h2 {
        border-bottom-color: rgba(96, 165, 250, 0.25) !important;
    }

    [data-theme="dark"] [data-testid="metric-container"] {
        border-color: rgba(96, 165, 250, 0.25) !important;
        border-top-color: #3B82F6 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.30);
    }

    [data-theme="dark"] [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-color: rgba(96, 165, 250, 0.18) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.20);
    }

    [data-theme="dark"] [data-testid="stExpander"] {
        border-color: rgba(96, 165, 250, 0.18) !important;
    }

    [data-theme="dark"] hr {
        border-color: rgba(96, 165, 250, 0.15) !important;
    }

    /* ── Mobile responsiveness ── */
    @media (max-width: 640px) {
        [data-testid="column"] {
            flex: 0 0 100% !important;
            max-width: 100% !important;
            min-width: 100% !important;
        }
        [data-testid="stAppViewContainer"] > div > div > div > div > div > div > div:first-child {
            font-size: 1.4rem !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHASE_COLORS = {
    "El Niño": {"bg": "#FEF2F2", "border": "#EF4444", "text": "#B91C1C", "dot": "#EF4444"},
    "La Niña": {"bg": "#EFF6FF", "border": "#3B82F6", "text": "#1D4ED8", "dot": "#3B82F6"},
    "Neutral":  {"bg": "#F0FDF4", "border": "#22C55E", "text": "#15803D", "dot": "#22C55E"},
}

# Plotly base layout shared across charts
_PLOTLY_BASE = dict(
    font=dict(family="Fira Sans, sans-serif", color="#334155"),
    plot_bgcolor="#F8FAFC",
    paper_bgcolor="#FFFFFF",
    margin=dict(t=40, b=40, l=50, r=30),
    xaxis=dict(
        gridcolor="#E2E8F0",
        linecolor="#CBD5E1",
        tickfont=dict(size=11, color="#64748B"),
    ),
    yaxis=dict(
        gridcolor="#E2E8F0",
        linecolor="#CBD5E1",
        tickfont=dict(size=11, color="#64748B"),
    ),
)


# Province centroids for the choropleth bubble map (approximate geographic centers).
# Ordered by latitude descending so hover labels stack north→south.
_PROVINCE_DATA: list[tuple[str, float, float, str]] = [
    # (province, lat, lon, region)
    ("Jujuy",               -23.3, -65.7, "NOA"),
    ("Formosa",             -24.5, -61.5, "NEA"),
    ("Salta",               -24.8, -65.4, "NOA"),
    ("Misiones",            -26.8, -54.5, "NEA"),
    ("Tucumán",             -26.8, -65.2, "NOA"),
    ("Chaco",               -26.0, -61.0, "NEA"),
    ("Santiago del Estero", -27.8, -63.3, "NOA"),
    ("Corrientes",          -28.0, -58.5, "NEA"),
    ("Catamarca",           -28.5, -65.8, "NOA"),
    ("La Rioja",            -30.0, -66.5, "Cuyo"),
    ("Santa Fe",            -30.7, -60.7, "Pampa Húmeda"),
    ("San Juan",            -31.5, -68.5, "Cuyo"),
    ("Entre Ríos",          -31.8, -58.5, "Pampa Húmeda"),
    ("Córdoba",             -31.4, -64.2, "Pampa Húmeda"),
    ("CABA",                -34.6, -58.4, "Pampa Húmeda"),
    ("Mendoza",             -34.0, -68.0, "Cuyo"),
    ("San Luis",            -33.8, -66.0, "Cuyo"),
    ("La Pampa",            -37.1, -66.1, "Pampa Húmeda"),
    ("Buenos Aires",        -36.7, -60.0, "Pampa Húmeda"),
    ("Neuquén",             -38.5, -69.5, "Patagonia"),
    ("Río Negro",           -40.8, -67.0, "Patagonia"),
    ("Chubut",              -44.0, -68.5, "Patagonia"),
    ("Santa Cruz",          -51.0, -69.5, "Patagonia"),
    ("Tierra del Fuego",    -54.5, -67.5, "Patagonia"),
]


def _phase_badge(phase: str) -> str:
    colors = PHASE_COLORS.get(phase, {"dot": "#94A3B8", "text": "#475569"})
    dot = f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:{colors['dot']};margin-right:8px;vertical-align:middle'></span>"
    return f"{dot}<strong style='color:{colors['text']}'>{phase}</strong>"


def _sig_marker(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    elif p_value < 0.01:
        return "**"
    elif p_value < 0.05:
        return "*"
    return ""


def _generate_risk_text(region: str, corr_df: pd.DataFrame) -> str:
    """Generate a parametric risk implication text for a region.

    Examines all lag × phase combinations and returns the most noteworthy
    relationship.  If nothing is significant, says so explicitly.

    Args:
        region: Region name (key in REGIONS).
        corr_df: Correlations DataFrame loaded from Parquet.

    Returns:
        Multi-line string (max 3 sentences) suitable for display.
    """
    region_data = corr_df[corr_df["region"] == region].copy()
    if region_data.empty:
        return f"No hay datos de correlación disponibles para {region}."

    sig = region_data[region_data["pearson_p"] < SIGNIFICANCE_THRESHOLD].copy()

    if sig.empty:
        min_p = region_data["pearson_p"].min()
        return (
            f"La correlación entre ONI y precipitación mensual en **{region}** "
            f"no es estadísticamente significativa en ningún lag analizado "
            f"(p mínima = {min_p:.3f}, umbral p < {SIGNIFICANCE_THRESHOLD})."
        )

    # Find the lag with strongest significant correlation
    best = sig.loc[sig["pearson_r"].abs().idxmax()]
    r = best["pearson_r"]
    lag = int(best["lag"])
    p = best["pearson_p"]
    n = int(best["n_obs"])

    direction = "positiva" if r > 0 else "negativa"
    effect = (
        "mayor precipitación" if r > 0 else "menor precipitación"
    )

    lag_str = "sin retardo (simultáneo)" if lag == 0 else f"con {lag} mes(es) de retardo (ONI lidera)"

    lines = [
        f"**{region}** muestra correlación {direction} significativa entre ONI y precipitación "
        f"(r = {r:.3f}, p = {p:.4f}, n = {n}), {lag_str}.",
        f"Esto sugiere que condiciones El Niño/La Niña se asocian con {effect} en esta región.",
    ]

    # Add Spearman note if different
    spear_r = best["spearman_r"]
    if abs(spear_r - r) > 0.05:
        lines.append(
            f"La correlación de Spearman es {spear_r:.3f}, indicando que la relación "
            f"es moderadamente no-lineal."
        )

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_enso_snapshot() -> tuple[ENSOSnapshot | None, str | None]:
    """Load ENSO snapshot with error handling.

    Returns:
        Tuple of (snapshot_or_None, error_message_or_None).
    """
    try:
        return fetch_enso_snapshot(), None
    except Exception as exc:
        logger.error("Error obteniendo ENSO snapshot: %s", exc)
        return None, str(exc)


@st.cache_data(show_spinner=False)
def load_correlations() -> tuple[pd.DataFrame | None, str | None]:
    """Load correlations from Parquet cache.

    Returns:
        Tuple of (dataframe_or_None, error_message_or_None).
    """
    path = Path(CORRELATIONS_CACHE_PATH)
    if not path.exists():
        return None, (
            f"Cache de correlaciones no encontrado en `{CORRELATIONS_CACHE_PATH}`. "
            "Ejecute `python -m src.compute_correlations` para generarlo."
        )
    try:
        df = pd.read_parquet(path)
        return df, None
    except Exception as exc:
        return None, f"Error leyendo Parquet: {exc}"


@st.cache_data(ttl=3600, show_spinner=False)
def load_forecast() -> ENSOForecast:
    """Fetch IRI/NOAA ENSO forecast (structured when available, fallback link otherwise)."""
    return fetch_enso_forecast()


@st.cache_data(show_spinner=False)
def load_precip_pairs() -> tuple[pd.DataFrame | None, str | None]:
    """Load raw ONI–precipitation pairs Parquet (generated by compute_correlations).

    Returns:
        Tuple of (dataframe_or_None, error_message_or_None).
        DataFrame columns: date, oni, <region_name>...
    """
    path = Path(PAIRS_CACHE_PATH)
    if not path.exists():
        return None, "Pairs cache not found — re-run `python -m src.compute_correlations`."
    try:
        return pd.read_parquet(path), None
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Chart helpers — ONI scatter and forecast probability bars
# ---------------------------------------------------------------------------

def _render_oni_scatter(region: str, pairs_df: pd.DataFrame, corr_df: pd.DataFrame) -> None:
    """Scatter chart of ONI vs regional precipitation anomaly for the best lag.

    Args:
        region: Region name matching corr_df and pairs_df columns.
        pairs_df: Monthly (date, oni, region…) DataFrame from load_precip_pairs().
        corr_df: Correlations DataFrame from load_correlations().
    """
    import numpy as np

    if region not in pairs_df.columns:
        return

    region_rows = corr_df[corr_df["region"] == region]
    sig = region_rows[region_rows["pearson_p"] < SIGNIFICANCE_THRESHOLD]
    if not sig.empty:
        best = sig.loc[sig["pearson_r"].abs().idxmax()]
    else:
        best = region_rows.loc[region_rows["pearson_r"].abs().idxmax()] if not region_rows.empty else None

    if best is None:
        return

    lag = int(best["lag"])
    r_val = float(best["pearson_r"])
    p_val = float(best["pearson_p"])

    # Align: oni[t] with precip[t+lag] by shifting oni forward by lag
    df = pairs_df[["date", "oni", region]].copy().dropna()
    df["oni_aligned"] = df["oni"].shift(lag)
    df = df.dropna(subset=["oni_aligned", region])

    precip_mean = df[region].mean()
    df["precip_anom"] = df[region] - precip_mean

    # Color by ENSO phase of the aligned ONI value
    def _phase_color(v: float) -> str:
        if v >= ENSO_EL_NINO_THRESHOLD:
            return "#EF4444"
        if v <= ENSO_LA_NINA_THRESHOLD:
            return "#3B82F6"
        return "#94A3B8"

    phase_labels = df["oni_aligned"].apply(
        lambda v: "El Niño" if v >= ENSO_EL_NINO_THRESHOLD
        else ("La Niña" if v <= ENSO_LA_NINA_THRESHOLD else "Neutral")
    )

    fig = go.Figure()
    for phase, color in [("El Niño", "#EF4444"), ("Neutral", "#94A3B8"), ("La Niña", "#3B82F6")]:
        mask = phase_labels == phase
        sub = df[mask]
        if sub.empty:
            continue
        # Pre-format hover text to avoid Plotly d3-format edge cases with '+' sign flag
        hover_texts = [
            f"ONI: {ox:+.2f} °C<br>Anomalía precip: {oy:+.0f} mm"
            for ox, oy in zip(sub["oni_aligned"], sub["precip_anom"])
        ]
        fig.add_trace(go.Scatter(
            x=sub["oni_aligned"],
            y=sub["precip_anom"],
            mode="markers",
            name=phase,
            marker=dict(color=color, size=5, opacity=0.65),
            text=hover_texts,
            hovertemplate=f"<b>{phase}</b><br>%{{text}}<extra></extra>",
        ))

    # Regression line
    if len(df) >= 10:
        x_arr = df["oni_aligned"].values
        y_arr = df["precip_anom"].values
        m, b = np.polyfit(x_arr, y_arr, 1)
        x_line = np.linspace(x_arr.min(), x_arr.max(), 80)
        fig.add_trace(go.Scatter(
            x=x_line,
            y=m * x_line + b,
            mode="lines",
            name=f"Regresión (r = {r_val:+.3f})",
            line=dict(color="#1E3A8A", width=2, dash="dash"),
        ))

    sig_str = f"p = {p_val:.4f}" + (" ✓" if p_val < SIGNIFICANCE_THRESHOLD else " (n.s.)")
    lag_str = "simultáneo" if lag == 0 else f"lag {lag}m"

    layout = dict(**_PLOTLY_BASE)
    layout.update(
        title=dict(
            text=f"ONI vs Precipitación — {region} ({lag_str}, r = {r_val:+.3f}, {sig_str})",
            font=dict(size=12, family="Fira Code, monospace", color="#1E3A8A"),
        ),
        xaxis_title="ONI (°C)",
        yaxis_title="Anomalía precipitación (mm/mes)",
        height=320,
        legend=dict(orientation="h", y=-0.25, font=dict(size=10)),
        margin=dict(t=50, b=70, l=60, r=30),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Cada punto = un mes (1981–pres.). ONI desplazado {lag} mes(es) para alinear con precipitación. "
        "Anomalía calculada respecto a la media del período."
    )


def _render_forecast_probability_bars(quarters: list[ForecastQuarter]) -> None:
    """Horizontal stacked bar chart of El Niño / Neutral / La Niña probabilities per season."""
    labels = [q.label for q in quarters]
    el_nino_vals = [q.el_nino_pct for q in quarters]
    neutral_vals = [q.neutral_pct for q in quarters]
    la_nina_vals = [q.la_nina_pct for q in quarters]

    fig = go.Figure()
    for name, vals, color in [
        ("El Niño",  el_nino_vals, "#EF4444"),
        ("Neutral",  neutral_vals, "#94A3B8"),
        ("La Niña",  la_nina_vals, "#3B82F6"),
    ]:
        fig.add_trace(go.Bar(
            name=name,
            y=labels,
            x=vals,
            orientation="h",
            marker_color=color,
            marker_opacity=0.85,
            text=[f"{v:.0f}%" if v >= 7 else "" for v in vals],
            textposition="inside",
            textfont=dict(color="#FFFFFF", size=11, family="Fira Sans, sans-serif"),
            hovertemplate=f"<b>{name}</b>: %{{x:.0f}}%<extra></extra>",
        ))

    layout = dict(**_PLOTLY_BASE)
    layout.update(
        barmode="stack",
        height=max(180, 44 * len(quarters)),
        margin=dict(t=10, b=30, l=70, r=30),
        xaxis=dict(range=[0, 100], ticksuffix="%", title=None, gridcolor="#E2E8F0"),
        yaxis=dict(title=None, autorange="reversed"),
        legend=dict(orientation="h", y=-0.18, font=dict(size=11)),
        showlegend=True,
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Feature 2 helpers — ONI anomaly alert banner
# ---------------------------------------------------------------------------

def _oni_phase(val: float) -> str:
    if val >= ENSO_EL_NINO_THRESHOLD:
        return "El Niño"
    if val <= ENSO_LA_NINA_THRESHOLD:
        return "La Niña"
    return "Neutral"


def _get_oni_alert(snapshot: ENSOSnapshot) -> dict | None:
    """Inspect recent ONI values and return alert metadata dict, or None."""
    recent = snapshot.oni_series.tail(ONI_ALERT_WINDOW + 1)
    if len(recent) < 2:
        return None

    latest = recent.iloc[-1]
    prev = recent.iloc[-2]
    latest_oni = float(latest["oni"])
    prev_oni = float(prev["oni"])
    latest_season = str(latest["season"])

    current_phase = _oni_phase(latest_oni)
    prev_phase = _oni_phase(prev_oni)
    transition = current_phase != prev_phase

    if current_phase == "El Niño":
        icon = "\u26a0\ufe0f"
        if transition:
            msg = (
                f"El Ni\u00f1o emergente \u2014 ONI cruz\u00f3 +{ENSO_EL_NINO_THRESHOLD} "
                f"en {latest_season} (ONI = {latest_oni:+.2f}\u00b0C, anterior: {prev_oni:+.2f}\u00b0C)."
            )
        else:
            msg = (
                f"Condiciones El Ni\u00f1o activas \u2014 ONI = {latest_oni:+.2f}\u00b0C "
                f"({latest_season}), por encima del umbral +{ENSO_EL_NINO_THRESHOLD}."
            )
        bg, border, text = "#FEF2F2", "#EF4444", "#B91C1C"

    elif current_phase == "La Ni\u00f1a":
        icon = "\u26a0\ufe0f"
        if transition:
            msg = (
                f"La Ni\u00f1a emergente \u2014 ONI cruz\u00f3 \u2212{abs(ENSO_LA_NINA_THRESHOLD)} "
                f"en {latest_season} (ONI = {latest_oni:+.2f}\u00b0C, anterior: {prev_oni:+.2f}\u00b0C)."
            )
        else:
            msg = (
                f"Condiciones La Ni\u00f1a activas \u2014 ONI = {latest_oni:+.2f}\u00b0C "
                f"({latest_season}), por debajo del umbral \u2212{abs(ENSO_LA_NINA_THRESHOLD)}."
            )
        bg, border, text = "#EFF6FF", "#3B82F6", "#1D4ED8"

    else:
        icon = "\u2705"
        if transition:
            msg = (
                f"Transici\u00f3n a Neutral \u2014 ONI = {latest_oni:+.2f}\u00b0C "
                f"({latest_season}), fase anterior: {prev_phase}."
            )
        else:
            msg = (
                f"ENSO Neutral \u2014 ONI = {latest_oni:+.2f}\u00b0C ({latest_season}), "
                f"dentro del rango neutral (\u00b1{ENSO_EL_NINO_THRESHOLD})."
            )
        bg, border, text = "#F0FDF4", "#22C55E", "#15803D"

    return {
        "phase": current_phase,
        "icon": icon,
        "msg": msg,
        "bg": bg,
        "border": border,
        "text": text,
        "transition": transition,
    }


# ---------------------------------------------------------------------------
# Feature 1 helpers — forecast-driven regional risk
# ---------------------------------------------------------------------------

def _get_dominant_phase(quarter: ForecastQuarter) -> tuple[str, float]:
    """Return (dominant_phase_name, probability_pct) for a ForecastQuarter."""
    phases = {
        "El Ni\u00f1o": quarter.el_nino_pct,
        "Neutral": quarter.neutral_pct,
        "La Ni\u00f1a": quarter.la_nina_pct,
    }
    dominant = max(phases, key=lambda k: phases[k])
    return dominant, phases[dominant]


def _forecast_risk_for_region(
    region: str,
    corr_df: pd.DataFrame,
    dominant_phase: str,
    prob_pct: float,
    season_label: str,
) -> dict:
    """Compute forecast risk for one region.

    Returns dict: significant (bool), risk (str), score (float), statement (str).
    Only produces a directional signal when pearson_p < SIGNIFICANCE_THRESHOLD.
    """
    region_data = corr_df[corr_df["region"] == region]
    sig = region_data[region_data["pearson_p"] < SIGNIFICANCE_THRESHOLD]

    if sig.empty:
        return {
            "significant": False,
            "risk": "no_signal",
            "score": 0.0,
            "statement": "sin se\u00f1al estad\u00edsticamente significativa",
        }

    best = sig.loc[sig["pearson_r"].abs().idxmax()]
    r = float(best["pearson_r"])
    lag = int(best["lag"])
    p = float(best["pearson_p"])
    n = int(best["n_obs"])

    if dominant_phase == "Neutral":
        return {
            "significant": True,
            "risk": "neutral",
            "score": 0.0,
            "statement": (
                f"Pron\u00f3stico ENSO neutral ({prob_pct:.0f}% probabilidad, {season_label}) \u2014 "
                f"sin se\u00f1al direccional clara a pesar de correlaci\u00f3n hist\u00f3rica significativa "
                f"(r = {r:+.3f}, p = {p:.4f}, n = {n})."
            ),
        }

    # El Niño → ONI positive. r > 0 means more precip with higher ONI → excess.
    # La Niña → ONI negative. r > 0 means less precip → deficit.
    nino_sign = 1 if dominant_phase == "El Ni\u00f1o" else -1
    precip_sign = nino_sign * (1 if r > 0 else -1)

    lag_str = "" if lag == 0 else f" (con {lag} mes{'es' if lag > 1 else ''} de retardo)"

    if precip_sign > 0:
        risk, score = "excess", 1.0
        effect = "precipitaci\u00f3n hist\u00f3ricamente sobre lo normal"
        implication = "\u2192 riesgo de exceso h\u00eddrico"
    else:
        risk, score = "deficit", -1.0
        effect = "precipitaci\u00f3n hist\u00f3ricamente bajo lo normal"
        implication = "\u2192 riesgo de d\u00e9ficit h\u00eddrico"

    statement = (
        f"IRI/NOAA pronostica {prob_pct:.0f}% {dominant_phase} ({season_label}){lag_str} "
        f"\u2192 {effect} {implication}. "
        f"(Correlaci\u00f3n: r = {r:+.3f}, p = {p:.4f}, n = {n})"
    )

    return {"significant": True, "risk": risk, "score": score, "statement": statement}


# (Feature 3 map uses _PROVINCE_DATA centroid scatter — see render_risk_map below)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Feature 2 — Anomaly detection / alert banner
# ---------------------------------------------------------------------------

def render_anomaly_banner() -> None:
    """Show prominent ONI alert banner at the top of the app."""
    snapshot, error = load_enso_snapshot()
    if error or snapshot is None:
        return

    alert = _get_oni_alert(snapshot)
    if alert is None:
        return

    transition_badge = ""
    if alert["transition"]:
        transition_badge = (
            "<span style='background:#FEF9C3;color:#92400E;font-size:0.7rem;"
            "font-weight:700;text-transform:uppercase;letter-spacing:0.06em;"
            "padding:2px 8px;border-radius:4px;margin-left:10px'>CAMBIO DE FASE</span>"
        )

    st.markdown(
        f"<div style='background:{alert['bg']};border:1px solid {alert['border']};"
        f"border-left:4px solid {alert['border']};border-radius:8px;"
        f"padding:12px 18px;margin-bottom:16px'>"
        f"<div style='font-size:1.0rem;font-weight:700;color:{alert['text']};"
        f"font-family:Fira Sans,sans-serif'>"
        f"{alert['icon']} Estado ENSO: {alert['msg']}"
        f"</div>"
        f"{transition_badge}"
        f"<div style='font-size:0.74rem;color:#64748B;margin-top:4px'>"
        f"Umbral NOAA CPC: ONI \u2265 +{ENSO_EL_NINO_THRESHOLD} = El Ni\u00f1o \u00b7 "
        f"ONI \u2264 \u2212{abs(ENSO_LA_NINA_THRESHOLD)} = La Ni\u00f1a \u00b7 "
        f"Valor autom\u00e1tico \u2014 no constituye declaraci\u00f3n oficial NOAA."
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Feature 3 — Argentina regional risk map
# ---------------------------------------------------------------------------

def render_risk_map(risk_results: dict) -> None:
    """Province-centroid bubble map of Argentina coloured by forecast risk.

    Uses go.Scattermap with carto-positron — no Mapbox token required.
    One bubble per province, coloured by its region's risk level.
    """
    _RISK_META = {
        "excess":    ("#1D4ED8", "Exceso h\u00eddrico (pron\u00f3stico)"),
        "deficit":   ("#F97316", "D\u00e9ficit h\u00eddrico (pron\u00f3stico)"),
        "neutral":   ("#94A3B8", "ENSO Neutral / Sin se\u00f1al"),
        "no_signal": ("#94A3B8", "Sin se\u00f1al estad\u00edsticamente significativa"),
    }

    # Group provinces by risk key, collapsing neutral+no_signal into one trace
    groups: dict[str, list] = {"excess": [], "deficit": [], "gray": []}
    for prov, lat, lon, region in _PROVINCE_DATA:
        res = risk_results.get(region, {})
        rk = res.get("risk", "no_signal")
        risk_label = _RISK_META.get(rk, _RISK_META["no_signal"])[1]
        entry = (prov, lat, lon, region, risk_label)
        if rk == "excess":
            groups["excess"].append(entry)
        elif rk == "deficit":
            groups["deficit"].append(entry)
        else:
            groups["gray"].append(entry)

    trace_config = {
        "excess": ("#1D4ED8", "Exceso h\u00eddrico"),
        "deficit": ("#F97316", "D\u00e9ficit h\u00eddrico"),
        "gray":    ("#94A3B8", "Sin se\u00f1al significativa"),
    }

    fig = go.Figure()
    for key, (color, legend_label) in trace_config.items():
        entries = groups[key]
        if not entries:
            continue
        provs, lats, lons, regs, risk_labels = zip(*entries)
        # go.Scattermap replaces the deprecated go.Scattermapbox (Plotly ≥5.15)
        fig.add_trace(go.Scattermap(
            lat=lats,
            lon=lons,
            mode="markers",
            name=legend_label,
            marker=dict(size=22, color=color, opacity=0.70),
            customdata=[[p, r, rl] for p, r, rl in zip(provs, regs, risk_labels)],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Regi\u00f3n: %{customdata[1]}<br>"
                "%{customdata[2]}<extra></extra>"
            ),
        ))

    fig.update_layout(
        map_style="carto-positron",
        map_zoom=2.5,
        map_center={"lat": -38.0, "lon": -64.5},
        margin=dict(t=0, b=0, l=0, r=0),
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            y=-0.06,
            x=0,
            font=dict(size=11, family="Fira Sans, sans-serif"),
            bgcolor="rgba(255,255,255,0.80)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            "<div style='padding:16px 0 8px; font-family:Fira Code,monospace; "
            "font-size:1.1rem; font-weight:700; color:#BFDBFE; letter-spacing:-0.02em'>"
            "ENSO Tracker</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:0.75rem; color:#94A3B8; margin-bottom:16px'>"
            "Argentina · NOAA CPC · CHIRPS v2.0</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div style='font-size:0.7rem; font-weight:600; text-transform:uppercase; "
            "letter-spacing:0.08em; color:#64748B; margin-bottom:8px'>Fuentes de datos</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"- [ONI (NOAA CPC)]({NOAA_ONI_URL})\n"
            f"- [Niño 3.4 (NOAA)]({NOAA_NINO34_URL})\n"
            f"- [SOI (NOAA CPC)]({NOAA_SOI_URL})\n"
            f"- [CHIRPS v2.0 (CHG/UCSB)](https://www.chc.ucsb.edu/data/chirps)\n"
            f"- [IRI ENSO Forecast](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/)"
        )
        st.divider()

        github_url = os.getenv("GITHUB_REPO_URL", "#")
        st.markdown(f"[Repositorio GitHub]({github_url})")

        st.divider()
        st.markdown(
            "<div style='font-size:0.72rem;color:#94A3B8;line-height:1.6'>"
            "Desarrollado por<br>"
            "<strong style='color:#BFDBFE'>Ing. Ammar Mahfoud</strong>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()
        contact = os.getenv("CONTACT_EMAIL", "contacto@example.com")
        st.caption(
            "**Disclaimer:** Demostración técnica. "
            "No constituye asesoría profesional. "
            f"Contacto: [{contact}](mailto:{contact})."
        )


# ---------------------------------------------------------------------------
# Section 1: Estado ENSO actual
# ---------------------------------------------------------------------------

def render_enso_status() -> None:
    st.header("1. Estado ENSO actual")

    with st.spinner("Cargando índices ENSO desde NOAA…"):
        snapshot, error = load_enso_snapshot()

    if error or snapshot is None:
        st.error(
            f"**Error obteniendo datos ENSO:** {error}\n\n"
            "Los datos no están disponibles. No se muestran valores de reemplazo."
        )
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label=f"ONI · {snapshot.oni_season}",
            value=f"{snapshot.oni_value:+.2f} °C",
            help="Oceanic Niño Index: media móvil 3 meses de anomalía SST Niño 3.4, base 1991-2020",
        )
        st.caption(f"Actualizado: {snapshot.oni_date} · [Fuente]({NOAA_ONI_URL})")

    with col2:
        st.metric(
            label="Niño 3.4 SST Anomalía",
            value=f"{snapshot.nino34_value:+.2f} °C",
            help="Anomalía mensual de temperatura superficial del mar en la región Niño 3.4 (ERSSTv5)",
        )
        st.caption(f"Actualizado: {snapshot.nino34_date} · [Fuente]({NOAA_NINO34_URL})")

    with col3:
        # Normalize negative-zero: -0.04 rounds to "-0.0" — replace with "+0.0"
        _soi_str = f"{snapshot.soi_value:+.1f}"
        if _soi_str == "-0.0":
            _soi_str = "+0.0"
        st.metric(
            label="SOI",
            value=_soi_str,
            help="Índice de Oscilación del Sur: diferencia estandarizada de presión Tahití − Darwin",
        )
        st.caption(f"Actualizado: {snapshot.soi_date} · [Fuente]({NOAA_SOI_URL})")

    # ONI time series chart
    st.subheader("Serie histórica ONI")
    _render_oni_chart(snapshot.oni_series)


def _render_oni_chart(oni_df: pd.DataFrame) -> None:
    fig = go.Figure()

    oni_max = oni_df["oni"].max()
    oni_min = oni_df["oni"].min()

    # Phase bands
    fig.add_hrect(
        y0=0.5, y1=oni_max + 0.2,
        fillcolor="#FEE2E2", opacity=0.45, line_width=0,
    )
    fig.add_hrect(
        y0=oni_min - 0.2, y1=-0.5,
        fillcolor="#DBEAFE", opacity=0.45, line_width=0,
    )

    # ONI line
    fig.add_trace(go.Scatter(
        x=oni_df["date"],
        y=oni_df["oni"],
        mode="lines",
        name="ONI",
        line=dict(color="#1E40AF", width=1.6),
        hovertemplate="<b>%{x|%Y %b}</b><br>ONI: %{y:.2f} °C<extra></extra>",
    ))

    # Threshold lines — annotations on the LEFT to avoid colliding with the
    # "you are here" marker/label that appears at the right edge.
    fig.add_hline(
        y=0.5, line_dash="dot", line_color="#EF4444", line_width=1.2,
        annotation_text="El Niño +0.5", annotation_position="top left",
        annotation=dict(font_size=10, font_color="#EF4444"),
    )
    fig.add_hline(
        y=-0.5, line_dash="dot", line_color="#3B82F6", line_width=1.2,
        annotation_text="La Niña −0.5", annotation_position="bottom left",
        annotation=dict(font_size=10, font_color="#3B82F6"),
    )
    fig.add_hline(y=0, line_color="#CBD5E1", line_width=0.8)

    # "You are here" — marker on the latest data point
    last_row = oni_df.iloc[-1]
    last_color = (
        "#EF4444" if last_row["oni"] >= 0.5
        else "#3B82F6" if last_row["oni"] <= -0.5
        else "#22C55E"
    )
    # If the ONI is within 0.15 of a threshold, push the label downward so it
    # doesn't stack on top of the threshold dashed-line label area.
    _oni_val = float(last_row["oni"])
    if abs(_oni_val - 0.5) < 0.15 or abs(_oni_val + 0.5) < 0.15:
        _text_pos = "bottom right"
    else:
        _text_pos = "middle right"
    fig.add_trace(go.Scatter(
        x=[last_row["date"]],
        y=[last_row["oni"]],
        mode="markers+text",
        marker=dict(size=10, color=last_color, line=dict(color="#FFFFFF", width=2)),
        text=[f"  {last_row['oni']:+.2f}"],
        textposition=_text_pos,
        textfont=dict(size=10, color=last_color, family="Fira Code, monospace"),
        hovertemplate=(
            f"<b>Último dato: {last_row['season']} {last_row['year']}</b>"
            f"<br>ONI: {last_row['oni']:+.2f} °C<extra></extra>"
        ),
        showlegend=False,
    ))

    layout = dict(**_PLOTLY_BASE)
    layout.update(
        height=310,
        margin=dict(t=20, b=30, l=100, r=60),  # l enlarged for left-side threshold labels
        yaxis_title="ONI (°C)",
        xaxis_title=None,
        showlegend=False,
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 2: Pronóstico ENSO oficial (curated links)
# ---------------------------------------------------------------------------

_FORECAST_RESOURCES = [
    {
        "title": "NOAA ENSO Advisory",
        "label": "Mensual",
        "description": (
            "Diagnóstico y pronóstico oficial de NOAA Climate Prediction Center. "
            "Actualización mensual con probabilidades por fase para los próximos trimestres."
        ),
        "button_label": "Ver advisory",
        "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/",
    },
    {
        "title": "IRI ENSO Forecast",
        "label": "Probabilístico",
        "description": (
            "Pronóstico del International Research Institute for Climate and Society "
            "(Columbia University). Incluye gráfico plume de probabilidades por trimestre."
        ),
        "button_label": "Ver pronóstico IRI",
        "url": "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/",
    },
    {
        "title": "NOAA ONI — series",
        "label": "Histórico",
        "description": (
            "Serie histórica del Oceanic Niño Index y valores proyectados "
            "publicados por NOAA CPC."
        ),
        "button_label": "Ver ONI",
        "url": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    },
]


def render_forecast() -> None:
    st.header("2. Pronóstico ENSO oficial")

    forecast = load_forecast()

    if forecast.is_structured and forecast.quarters:
        nearest = forecast.quarters[0]
        dominant_phase, prob_pct = _get_dominant_phase(nearest)
        st.markdown(
            f"<div style='background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;"
            f"padding:8px 14px;font-size:0.82rem;color:#1D4ED8;margin-bottom:12px'>"
            f"Datos estructurados IRI/NOAA disponibles \u00b7 "
            f"Pr\u00f3xima temporada: <strong>{nearest.label}</strong> \u00b7 "
            f"Fase dominante: <strong>{dominant_phase}</strong> ({prob_pct:.0f}%)"
            f"</div>",
            unsafe_allow_html=True,
        )
        _render_forecast_probability_bars(forecast.quarters)
        st.caption(
            "Probabilidades IRI/NOAA. Cada barra = una temporada futura (hasta 6). "
            "Fuente: IRI Columbia University. No constituye certeza."
        )
    else:
        st.markdown(
            "El pron\u00f3stico ENSO operacional lo emiten centros especializados (NOAA, IRI). "
            "Datos estructurados no disponibles en este momento \u2014 consultar fuentes oficiales."
        )

    st.markdown("<div style='margin-top:16px'>", unsafe_allow_html=True)
    cols = st.columns(3)
    for col, resource in zip(cols, _FORECAST_RESOURCES):
        with col:
            with st.container(border=True):
                st.markdown(
                    f"<div style='display:flex;align-items:baseline;gap:8px;margin-bottom:4px'>"
                    f"<span style='font-family:Fira Code,monospace;font-weight:700;"
                    f"color:#1E3A8A;font-size:0.95rem'>{resource['title']}</span>"
                    f"<span style='font-size:0.7rem;font-weight:600;text-transform:uppercase;"
                    f"letter-spacing:0.06em;color:#3B82F6;background:#EFF6FF;"
                    f"padding:1px 6px;border-radius:4px'>{resource['label']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.caption(resource["description"])
                st.link_button(resource["button_label"] + " \u2192", resource["url"], use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 3: Correlaciones históricas
# ---------------------------------------------------------------------------

def render_correlations() -> None:
    st.header("3. Correlación histórica ENSO vs Precipitación")

    corr_df, error = load_correlations()

    if error or corr_df is None:
        st.warning(f"**{error}**")
        st.code("python -m src.compute_correlations", language="bash")
        return

    # Metadata from cache
    if "version" in corr_df.columns:
        version = corr_df["version"].iloc[0]
        computed_at = corr_df.get("computed_at", pd.Series(["?"])).iloc[0]
        start_year = int(corr_df.get("start_year", pd.Series([0])).iloc[0])
        end_year = int(corr_df.get("end_year", pd.Series([0])).iloc[0])
        st.markdown(
            f"<div style='background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;"
            f"padding:8px 14px;font-size:0.78rem;color:#1D4ED8;margin-bottom:12px'>"
            f"Cache <strong>v{version}</strong> &middot; CHIRPS {start_year}–{end_year} "
            f"&middot; Generado: {str(computed_at)[:10]} "
            f"&middot; <a href='https://www.chc.ucsb.edu/data/chirps' "
            f"style='color:#1D4ED8'>CHIRPS v2.0</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Display table
    display_cols = ["region", "lag", "pearson_r", "pearson_p", "spearman_r", "spearman_p", "n_obs"]
    table_df = corr_df[[c for c in display_cols if c in corr_df.columns]].copy()

    # Add significance markers
    table_df["sig"] = table_df["pearson_p"].apply(_sig_marker)
    table_df["pearson_r_display"] = table_df.apply(
        lambda r: f"{r['pearson_r']:+.3f}{r['sig']}", axis=1
    )

    st.markdown(
        "Correlación de Pearson entre ONI y precipitación mensual regional (CHIRPS v2.0). "
        "**Lag** = meses que ONI lidera la precipitación. "
        "&nbsp;&nbsp;\\* p<0.05 &nbsp; \\*\\* p<0.01 &nbsp; \\*\\*\\* p<0.001"
    )

    # Pivot for readability
    pivot = table_df.pivot_table(
        index="region",
        columns="lag",
        values="pearson_r_display",
        aggfunc="first",
    )
    pivot.columns = [f"Lag {c}m" for c in pivot.columns]
    pivot.index.name = "Región"

    st.dataframe(pivot, use_container_width=True)

    # Full detail table
    with st.expander("Ver tabla completa — Pearson + Spearman + p-values"):
        detail = table_df.drop(columns=["sig", "pearson_r_display"]).rename(columns={
            "region": "Región",
            "lag": "Lag (meses)",
            "pearson_r": "r (Pearson)",
            "pearson_p": "p (Pearson)",
            "spearman_r": "r (Spearman)",
            "spearman_p": "p (Spearman)",
            "n_obs": "N obs",
        })

        def highlight_sig(row: pd.Series) -> list[str]:
            p_col = "p (Pearson)"
            if p_col in row.index and row[p_col] < SIGNIFICANCE_THRESHOLD:
                return ["background-color: #EFF6FF; color: #1E3A8A"] * len(row)
            return [""] * len(row)

        st.dataframe(
            detail.style.apply(highlight_sig, axis=1),
            use_container_width=True,
        )

    # Heatmap
    _render_correlation_heatmap(table_df)


def _render_correlation_heatmap(table_df: pd.DataFrame) -> None:
    """Render a heatmap of Pearson correlations (region × lag)."""
    regions = list(REGIONS.keys())
    lags = sorted(table_df["lag"].unique())

    z = []
    text = []
    for region in regions:
        row_z = []
        row_text = []
        for lag in lags:
            subset = table_df[(table_df["region"] == region) & (table_df["lag"] == lag)]
            if subset.empty:
                row_z.append(None)
                row_text.append("")
            else:
                r = float(subset["pearson_r"].iloc[0])
                p = float(subset["pearson_p"].iloc[0])
                is_sig = p < SIGNIFICANCE_THRESHOLD
                sig_marker = _sig_marker(p)
                # Mute non-significant cells: push z toward 0 so they appear near-white.
                # Actual r shown as text with "(n.s.)" so users still see the value.
                row_z.append(r if is_sig else r * 0.15)
                # Explicitly label which test: "(Pears. n.s.)" reminds the
                # reader that this refers to Pearson p-value only; Spearman
                # may differ (check the detail table in the expander below).
                row_text.append(
                    f"{r:+.3f}{sig_marker}" if is_sig else f"{r:+.3f}\n(Pears. n.s.)"
                )
        z.append(row_z)
        text.append(row_text)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[f"Lag {l}m" for l in lags],
        y=regions,
        text=text,
        texttemplate="%{text}",
        textfont=dict(size=11, family="Fira Code, monospace"),
        colorscale=[
            [0.0, "#1D4ED8"],
            [0.4, "#93C5FD"],
            [0.5, "#F8FAFC"],
            [0.6, "#FCA5A5"],
            [1.0, "#B91C1C"],
        ],
        zmid=0,
        zmin=-0.6,
        zmax=0.6,
        colorbar=dict(
            title=dict(text="r (Pearson)", font=dict(size=11)),
            tickfont=dict(size=10, family="Fira Code, monospace"),
            thickness=14,
            len=0.9,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}<br>r = %{z:.3f}<extra></extra>",
    ))

    layout = dict(**_PLOTLY_BASE)
    layout.update(
        title=dict(
            text="Correlación ONI–Precipitación por región y lag",
            font=dict(size=13, family="Fira Code, monospace", color="#1E3A8A"),
        ),
        height=360,
        margin=dict(t=50, b=40, l=150, r=40),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Celdas brillantes = Pearson p < 0.05. Celdas opacas con '(Pears. n.s.)' = Pearson no significativo "
        "— el Spearman puede diferir; ver tabla detallada en el desplegable superior."
    )


# ---------------------------------------------------------------------------
# Section 4: Implicaciones de riesgo
# ---------------------------------------------------------------------------

def render_risk_implications() -> None:
    st.header("4. Implicaciones de riesgo por región")

    corr_df, error = load_correlations()
    if error or corr_df is None:
        st.warning("Cache de correlaciones no disponible. Ejecutar `python -m src.compute_correlations`.")
        return

    # ── Feature 1: Forecast-driven risk ──────────────────────────────────────
    st.subheader("4a. Señal forward-looking (pronóstico × correlación histórica)")

    with st.spinner("Obteniendo pronóstico ENSO…"):
        forecast = load_forecast()

    risk_results: dict = {}

    if forecast.is_structured and forecast.quarters:
        nearest = forecast.quarters[0]
        dominant_phase, prob_pct = _get_dominant_phase(nearest)

        st.markdown(
            f"<div style='background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;"
            f"padding:8px 14px;font-size:0.82rem;color:#1D4ED8;margin-bottom:14px'>"
            f"Fuente: IRI/NOAA \u00b7 Temporada: <strong>{nearest.label}</strong> \u00b7 "
            f"Fase dominante: <strong>{dominant_phase}</strong> ({prob_pct:.0f}%) \u00b7 "
            f"El Ni\u00f1o {nearest.el_nino_pct:.0f}% / Neutral {nearest.neutral_pct:.0f}% "
            f"/ La Ni\u00f1a {nearest.la_nina_pct:.0f}%"
            f"</div>",
            unsafe_allow_html=True,
        )

        for region_name in REGIONS:
            result = _forecast_risk_for_region(
                region_name, corr_df, dominant_phase, prob_pct, nearest.label
            )
            risk_results[region_name] = result

        for region_name in REGIONS:
            result = risk_results[region_name]
            if result["significant"] and result["risk"] == "excess":
                icon, bg, border, tc = "\U0001f535", "#EFF6FF", "#93C5FD", "#1D4ED8"
            elif result["significant"] and result["risk"] == "deficit":
                icon, bg, border, tc = "\U0001f7e0", "#FFF7ED", "#FED7AA", "#C2410C"
            elif result["significant"] and result["risk"] == "neutral":
                icon, bg, border, tc = "\u26aa", "#F8FAFC", "#CBD5E1", "#475569"
            else:
                icon, bg, border, tc = "\u2014", "#F8FAFC", "#E2E8F0", "#64748B"

            st.markdown(
                f"<div style='background:{bg};border:1px solid {border};"
                f"border-left:3px solid {border};border-radius:6px;"
                f"padding:10px 14px;margin-bottom:8px'>"
                f"<div style='font-family:Fira Code,monospace;font-weight:700;"
                f"color:{tc};font-size:0.88rem;margin-bottom:4px'>"
                f"{icon}&nbsp; {region_name}</div>"
                f"<div style='font-size:0.82rem;color:#334155'>{result['statement']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.caption(
            f"\u26a0\ufe0f Se\u00f1al probabil\u00edstica \u2014 no certeza. "
            f"Solo regiones con p < {SIGNIFICANCE_THRESHOLD} muestran se\u00f1al direccional. "
            "Validar con pron\u00f3stico oficial NOAA/IRI antes de tomar decisiones."
        )
    else:
        st.info(
            f"Pronóstico estructurado IRI no disponible en este momento. "
            f"[Ver pronóstico oficial NOAA/IRI]({forecast.fallback_url})"
        )
        for region_name in REGIONS:
            region_data = corr_df[corr_df["region"] == region_name]
            sig = region_data[region_data["pearson_p"] < SIGNIFICANCE_THRESHOLD]
            risk_results[region_name] = {
                "significant": not sig.empty,
                "risk": "no_signal",
                "score": 0.0,
                "statement": "sin señal estadísticamente significativa",
            }

    # Footnote — shown regardless of forecast availability
    st.markdown(
        "<div style='background:#FFF7ED;border:1px solid #FED7AA;border-radius:6px;"
        "padding:8px 14px;font-size:0.78rem;color:#92400E;margin-top:8px'>"
        "\u26a0\ufe0f <strong>Nota metodol\u00f3gica:</strong> Las correlaciones son promedios "
        "espaciales sobre el bounding box regional \u2014 el comportamiento puede diferir "
        "significativamente entre provincias dentro de una misma regi\u00f3n. "
        "No usar para toma de decisiones a escala provincial sin validaci\u00f3n local."
        "</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Feature 3: Province bubble map ───────────────────────────────────────
    st.subheader("4b. Mapa de riesgo regional — Argentina")
    st.caption(
        "Un c\u00edrculo por provincia en su centroide geogr\u00e1fico. "
        "Gris = sin se\u00f1al estad\u00edsticamente significativa (p \u2265 0.05)."
    )
    render_risk_map(risk_results)

    st.divider()

    # ── Historical correlation detail (existing section) ──────────────────────
    st.subheader("4c. Correlación histórica por región (detalle)")
    pairs_df, _pairs_err = load_precip_pairs()

    for region_name in REGIONS:
        with st.expander(f"**{region_name}** — {REGIONS[region_name]['description']}"):
            text = _generate_risk_text(region_name, corr_df)
            st.markdown(text)

            region_data = corr_df[corr_df["region"] == region_name][
                ["lag", "pearson_r", "pearson_p", "spearman_r", "spearman_p", "n_obs"]
            ].copy()
            region_data["sig"] = region_data["pearson_p"].apply(_sig_marker)
            region_data.columns = ["Lag (m)", "r Pearson", "p Pearson", "r Spearman", "p Spearman", "N", "Sig."]
            st.dataframe(region_data.set_index("Lag (m)"), use_container_width=True)

            # ONI vs precipitation scatter chart (requires pairs cache)
            if pairs_df is not None:
                _render_oni_scatter(region_name, pairs_df, corr_df)


# ---------------------------------------------------------------------------
# Section 5: Metadata / Footer
# ---------------------------------------------------------------------------

def _check_data_staleness(snapshot) -> list[str]:
    """Return list of source names whose date lags the most recent source
    by more than DATA_STALENESS_THRESHOLD_DAYS.

    Args:
        snapshot: ENSOSnapshot with oni_date, nino34_date, soi_date as date objects.

    Returns:
        List of stale source labels (empty when all sources are fresh).
    """
    source_dates = {
        "ONI": snapshot.oni_date,
        "Niño 3.4": snapshot.nino34_date,
        "SOI": snapshot.soi_date,
    }
    latest = max(source_dates.values())
    return [
        name
        for name, d in source_dates.items()
        if (latest - d).days > DATA_STALENESS_THRESHOLD_DAYS
    ]


def render_footer() -> None:
    st.divider()

    st.markdown(
        "<div style='background:#1E3A8A;border-radius:10px;padding:20px 24px;margin-top:8px'>"
        "<div style='font-family:Fira Code,monospace;font-weight:700;color:#BFDBFE;"
        "font-size:0.85rem;letter-spacing:0.04em;margin-bottom:12px'>5. METADATA</div>",
        unsafe_allow_html=True,
    )

    snapshot, _ = load_enso_snapshot()
    corr_df, _ = load_correlations()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "<div style='color:#E2E8F0;font-size:0.82rem;font-weight:600;margin-bottom:6px'>"
            "Fuentes y actualizaciones</div>",
            unsafe_allow_html=True,
        )
        if snapshot:
            # Staleness check — warn when any source lags the freshest by >threshold
            stale_sources = _check_data_staleness(snapshot)

            def _date_html(name: str, d, url: str) -> str:
                stale_badge = (
                    " <span style='background:#FEF9C3;color:#92400E;font-size:0.68rem;"
                    "font-weight:700;padding:1px 5px;border-radius:3px;margin-left:4px'>"
                    "DESACTUALIZADO</span>"
                    if name in stale_sources else ""
                )
                return (
                    f"{name}: {d} · "
                    f"<a href='{url}' style='color:#93C5FD'>fuente</a>"
                    f"{stale_badge}"
                )

            src_html = "<br>".join([
                _date_html("ONI", snapshot.oni_date, NOAA_ONI_URL),
                _date_html("Niño 3.4", snapshot.nino34_date, NOAA_NINO34_URL),
                _date_html("SOI", snapshot.soi_date, NOAA_SOI_URL),
            ])

            st.markdown(
                f"<div style='color:#CBD5E1;font-size:0.78rem;line-height:1.9'>"
                f"{src_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

            if stale_sources:
                st.markdown(
                    f"<div style='background:#FEF9C3;border:1px solid #FDE047;border-radius:5px;"
                    f"padding:6px 10px;margin-top:6px;font-size:0.75rem;color:#78350F'>"
                    f"⚠️ <strong>{', '.join(stale_sources)}</strong> no se ha actualizado en más de "
                    f"{DATA_STALENESS_THRESHOLD_DAYS} días respecto a la fuente más reciente. "
                    f"Los datos pueden estar desactualizados."
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='color:#94A3B8;font-size:0.78rem'>Índices ENSO: no disponibles</div>",
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown(
            "<div style='color:#E2E8F0;font-size:0.82rem;font-weight:600;margin-bottom:6px'>"
            "Dataset correlaciones</div>",
            unsafe_allow_html=True,
        )
        if corr_df is not None and "version" in corr_df.columns:
            v = corr_df["version"].iloc[0]
            ca = str(corr_df.get("computed_at", pd.Series(["?"])).iloc[0])[:10]
            sy = int(corr_df.get("start_year", pd.Series([0])).iloc[0])
            ey = int(corr_df.get("end_year", pd.Series([0])).iloc[0])
            st.markdown(
                f"<div style='color:#CBD5E1;font-size:0.78rem;line-height:1.8'>"
                f"Versión: <code style='color:#93C5FD'>{v}</code><br>"
                f"Período: {sy}–{ey}<br>"
                f"Generado: {ca}<br>"
                f"Fuente precipitación: CHIRPS v2.0 · <em style='color:#FCD34D'>Fuente única</em> "
                f"(validación ERA5 pendiente)"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='color:#94A3B8;font-size:0.78rem'>Cache no disponible</div>",
                unsafe_allow_html=True,
            )

    github_url = os.getenv("GITHUB_REPO_URL", "#")
    contact = os.getenv("CONTACT_EMAIL", "contacto@example.com")
    st.markdown(
        f"<div style='margin-top:14px;padding-top:14px;border-top:1px solid #2D4FA0;"
        f"display:flex;gap:20px;align-items:center;flex-wrap:wrap'>"
        f"<a href='{github_url}' style='color:#93C5FD;font-size:0.8rem;font-weight:600;"
        f"text-decoration:none'>GitHub</a>"
        f"<span style='color:#94A3B8;font-size:0.78rem'>"
        f"Desarrollado por <strong style='color:#BFDBFE'>Ing. Ammar Mahfoud</strong>"
        f"</span>"
        f"<span style='color:#64748B;font-size:0.78rem'>"
        f"Demostración técnica · No constituye asesoría profesional · "
        f"<a href='mailto:{contact}' style='color:#93C5FD'>{contact}</a>"
        f"</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    render_sidebar()

    st.markdown(
        "<div style='padding:8px 0 4px'>"
        "<div style='font-family:Fira Code,monospace;font-size:2rem;font-weight:700;"
        "color:#1E3A8A;line-height:1.2'>Argentina ENSO<br>Impact Tracker</div>"
        "<div style='font-size:0.9rem;color:#64748B;margin-top:8px;max-width:640px'>"
        "Estado del ENSO y correlación histórica con precipitación en 5 regiones argentinas. "
        "Todos los datos provienen de fuentes públicas verificables (NOAA CPC, CHIRPS v2.0)."
        "</div>"
        "<div style='font-size:0.75rem;color:#94A3B8;margin-top:6px'>"
        "por <strong style='color:#64748B'>Ing. Ammar Mahfoud</strong>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin:16px 0 8px'>", unsafe_allow_html=True)

    render_anomaly_banner()
    render_enso_status()
    st.divider()
    render_forecast()
    st.divider()
    render_correlations()
    st.divider()
    render_risk_implications()
    render_footer()

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
