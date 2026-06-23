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
    ENSO_EL_NINO_THRESHOLD,
    ENSO_LA_NINA_THRESHOLD,
    NOAA_CPC_ADVISORY_URL,
    NOAA_NINO34_URL,
    NOAA_ONI_URL,
    NOAA_SOI_URL,
    ONI_ALERT_WINDOW,
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

    /* ── App background ── */
    .stApp {
        background-color: #F8FAFC;
    }

    /* ── Sidebar ── */
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
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
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
        color: #64748B !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Fira Code', monospace !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #1E3A8A !important;
    }

    /* ── Section headers ── */
    h2 {
        border-bottom: 2px solid #DBEAFE;
        padding-bottom: 8px;
        margin-top: 8px !important;
    }

    /* ── Containers with border ── */
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 10px !important;
        border: 1px solid #DBEAFE !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 4px rgba(30,64,175,0.06);
        transition: box-shadow 200ms ease, border-color 200ms ease;
    }
    [data-testid="stVerticalBlockBorderWrapper"] > div:hover {
        box-shadow: 0 4px 16px rgba(30,64,175,0.10);
        border-color: #93C5FD !important;
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
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        background: #FFFFFF !important;
        margin-bottom: 8px;
        transition: border-color 150ms ease;
    }
    [data-testid="stExpander"]:hover {
        border-color: #93C5FD !important;
    }
    [data-testid="stExpander"] summary {
        font-family: 'Fira Sans', sans-serif !important;
        font-weight: 600 !important;
        color: #1E3A8A !important;
        cursor: pointer;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        overflow: hidden;
    }

    /* ── Divider ── */
    hr {
        border-color: #E2E8F0 !important;
        margin: 24px 0 !important;
    }

    /* ── Caption ── */
    [data-testid="stCaptionContainer"] {
        color: #64748B !important;
        font-size: 0.78rem !important;
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
        color: #1E3A8A !important;
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


# ---------------------------------------------------------------------------
# Feature 3 helper — build GeoJSON from REGIONS bounding boxes
# ---------------------------------------------------------------------------

def _build_regions_geojson() -> dict:
    """Build a GeoJSON FeatureCollection from REGIONS bounding boxes (config.py)."""
    features = []
    for name, r in REGIONS.items():
        coords = [[
            [r["lon_min"], r["lat_min"]],
            [r["lon_max"], r["lat_min"]],
            [r["lon_max"], r["lat_max"]],
            [r["lon_min"], r["lat_max"]],
            [r["lon_min"], r["lat_min"]],
        ]]
        features.append({
            "type": "Feature",
            "id": name,
            "properties": {"name": name},
            "geometry": {"type": "Polygon", "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": features}


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
    """Render Plotly choropleth map of Argentina coloured by forecast risk level.

    Significant regions are coloured blue (excess) or orange (deficit).
    Non-significant regions are rendered in neutral gray.
    Uses carto-positron tile style — no Mapbox token required.
    """
    geojson = _build_regions_geojson()
    region_names = list(REGIONS.keys())

    scores = []
    hover_labels = []
    for r in region_names:
        res = risk_results.get(r, {})
        scores.append(res.get("score", 0.0))
        if not res.get("significant", False):
            hover_labels.append("Sin se\u00f1al estad\u00edsticamente significativa")
        elif res["risk"] == "excess":
            hover_labels.append("Exceso h\u00eddrico (pron\u00f3stico)")
        elif res["risk"] == "deficit":
            hover_labels.append("D\u00e9ficit h\u00eddrico (pron\u00f3stico)")
        else:
            hover_labels.append("Neutral")

    customdata = [[region_names[i], hover_labels[i]] for i in range(len(region_names))]

    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=region_names,
        featureidkey="id",
        z=scores,
        customdata=customdata,
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
        colorscale=[
            [0.0, "#F97316"],   # score -1 → orange = drought/deficit
            [0.5, "#94A3B8"],   # score  0 → gray  = no signal / neutral
            [1.0, "#1D4ED8"],   # score +1 → blue  = excess/flood
        ],
        zmin=-1,
        zmax=1,
        marker_opacity=0.72,
        marker_line_width=1.5,
        marker_line_color="#FFFFFF",
        showscale=False,
    ))

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=2.6,
        mapbox_center={"lat": -38.5, "lon": -63.5},
        margin=dict(t=0, b=0, l=0, r=0),
        height=480,
        paper_bgcolor="#FFFFFF",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Color legend
    legend_items = [
        ("#1D4ED8", "Exceso h\u00eddrico (pron\u00f3stico)"),
        ("#F97316", "D\u00e9ficit h\u00eddrico (pron\u00f3stico)"),
        ("#94A3B8", "Sin se\u00f1al estad\u00edsticamente significativa (p \u2265 0.05)"),
    ]
    parts = []
    for color, label in legend_items:
        parts.append(
            f"<div style='display:flex;align-items:center;gap:6px;"
            f"font-size:0.78rem;color:#475569'>"
            f"<span style='display:inline-block;width:14px;height:14px;"
            f"border-radius:3px;background:{color}'></span>{label}</div>"
        )
    st.markdown(
        "<div style='display:flex;gap:20px;flex-wrap:wrap;margin-top:4px'>"
        + "".join(parts)
        + "</div>",
        unsafe_allow_html=True,
    )


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
            f"- [IRI ENSO Forecast]({NOAA_CPC_ADVISORY_URL})"
        )
        st.divider()

        github_url = os.getenv("GITHUB_REPO_URL", "#")
        st.markdown(f"[Repositorio GitHub]({github_url})")

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

    # Phase banner — polished card
    colors = PHASE_COLORS.get(snapshot.phase, {"bg": "#F8FAFC", "border": "#94A3B8", "text": "#475569", "dot": "#94A3B8"})
    st.markdown(
        f"<div style='"
        f"background:{colors['bg']};"
        f"border:1px solid {colors['border']};"
        f"border-left:4px solid {colors['border']};"
        f"border-radius:8px;"
        f"padding:14px 18px;"
        f"margin-bottom:20px;"
        f"display:flex;align-items:center;gap:12px"
        f"'>"
        f"<div style='flex:1'>"
        f"<div style='font-family:Fira Code,monospace;font-size:1.15rem;font-weight:700'>"
        f"{_phase_badge(snapshot.phase)}"
        f"</div>"
        f"<div style='font-size:0.78rem;color:#64748B;margin-top:4px'>"
        f"Clasificación NOAA CPC: ONI &ge; +0.5 / &le; &minus;0.5 por 5 meses consecutivos"
        f" &middot; Fuente: {snapshot.phase_source}"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

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
        st.metric(
            label="SOI",
            value=f"{snapshot.soi_value:+.1f}",
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
        hovertemplate="<b>%{x|%Y %b}</b><br>ONI: %{y:+.2f} °C<extra></extra>",
    ))

    # Threshold lines
    fig.add_hline(
        y=0.5, line_dash="dot", line_color="#EF4444", line_width=1.2,
        annotation_text="El Niño +0.5", annotation_position="right",
        annotation=dict(font_size=10, font_color="#EF4444"),
    )
    fig.add_hline(
        y=-0.5, line_dash="dot", line_color="#3B82F6", line_width=1.2,
        annotation_text="La Niña −0.5", annotation_position="right",
        annotation=dict(font_size=10, font_color="#3B82F6"),
    )
    fig.add_hline(y=0, line_color="#CBD5E1", line_width=0.8)

    layout = dict(**_PLOTLY_BASE)
    layout.update(
        height=300,
        margin=dict(t=20, b=30, l=50, r=70),
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

    st.markdown(
        "El pronóstico ENSO operacional lo emiten centros especializados (NOAA, IRI). "
        "Este tracker no reproduce esos pronósticos: los enlaza directamente."
    )

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
                st.link_button(resource["button_label"] + " →", resource["url"], use_container_width=True)


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
                sig = _sig_marker(p)
                row_z.append(r)
                row_text.append(f"{r:+.3f}{sig}")
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
            f"\u26a0\ufe0f Señal probabilística — no certeza. "
            f"Solo regiones con p < {SIGNIFICANCE_THRESHOLD} muestran señal direccional. "
            "Validar con pronóstico oficial NOAA/IRI antes de tomar decisiones."
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

    st.divider()

    # ── Feature 3: Choropleth map ─────────────────────────────────────────────
    st.subheader("4b. Mapa de riesgo regional — Argentina")
    st.caption(
        "Regiones aproximadas por bounding box (IGN Argentina). "
        "Gris = sin señal estadísticamente significativa (p ≥ 0.05)."
    )
    render_risk_map(risk_results)

    st.divider()

    # ── Historical correlation detail (existing section) ──────────────────────
    st.subheader("4c. Correlación histórica por región (detalle)")
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


# ---------------------------------------------------------------------------
# Section 5: Metadata / Footer
# ---------------------------------------------------------------------------

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
            st.markdown(
                f"<div style='color:#CBD5E1;font-size:0.78rem;line-height:1.8'>"
                f"ONI: {snapshot.oni_date} · "
                f"<a href='{NOAA_ONI_URL}' style='color:#93C5FD'>NOAA CPC</a><br>"
                f"Niño 3.4: {snapshot.nino34_date} · "
                f"<a href='{NOAA_NINO34_URL}' style='color:#93C5FD'>NOAA</a><br>"
                f"SOI: {snapshot.soi_date} · "
                f"<a href='{NOAA_SOI_URL}' style='color:#93C5FD'>NOAA CPC</a>"
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
