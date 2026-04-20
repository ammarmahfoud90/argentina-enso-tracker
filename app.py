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
    NOAA_CPC_ADVISORY_URL,
    NOAA_NINO34_URL,
    NOAA_ONI_URL,
    NOAA_SOI_URL,
    REGIONS,
    SIGNIFICANCE_THRESHOLD,
)
from src.fetch_enso import ENSOSnapshot, fetch_enso_snapshot

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
# Helpers
# ---------------------------------------------------------------------------

PHASE_COLORS = {
    "El Niño": "#d62728",
    "La Niña": "#1f77b4",
    "Neutral": "#2ca02c",
}

PHASE_ICONS = {
    "El Niño": "🔴",
    "La Niña": "🔵",
    "Neutral": "🟢",
}


def _phase_badge(phase: str) -> str:
    icon = PHASE_ICONS.get(phase, "⚪")
    return f"{icon} <strong>{phase}</strong>"


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


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Fuentes de datos")
        st.markdown(
            f"- [ONI (NOAA CPC)]({NOAA_ONI_URL})\n"
            f"- [Niño 3.4 (NOAA)]({NOAA_NINO34_URL})\n"
            f"- [SOI (NOAA CPC)]({NOAA_SOI_URL})\n"
            f"- [CHIRPS v2.0 (CHG/UCSB)](https://www.chc.ucsb.edu/data/chirps)\n"
            f"- [IRI ENSO Forecast]({NOAA_CPC_ADVISORY_URL})"
        )
        st.divider()

        github_url = os.getenv("GITHUB_REPO_URL", "#")
        st.markdown(f"[📂 Repositorio GitHub]({github_url})")

        st.divider()
        contact = os.getenv("CONTACT_EMAIL", "contacto@example.com")
        st.caption(
            "⚠️ **Disclaimer:** Este tracker es una demostración técnica. "
            "No constituye asesoría profesional. Para análisis de riesgo "
            f"operacional contactar [{contact}](mailto:{contact})."
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

    # Phase banner
    phase_color = PHASE_COLORS.get(snapshot.phase, "#666")
    st.markdown(
        f"<div style='background:{phase_color}22; border-left: 4px solid {phase_color}; "
        f"padding:12px; border-radius:4px; margin-bottom:16px'>"
        f"<span style='font-size:1.3em'>{_phase_badge(snapshot.phase)}</span><br/>"
        f"<small>Clasificación según criterio NOAA CPC: ONI ≥ +0.5 / ≤ −0.5 "
        f"por {5} meses consecutivos · Fuente: {snapshot.phase_source}</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label=f"ONI ({snapshot.oni_season})",
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

    # Colour area by phase
    fig.add_hrect(y0=0.5, y1=oni_df["oni"].max() + 0.1, fillcolor="#d62728", opacity=0.07, line_width=0)
    fig.add_hrect(y0=oni_df["oni"].min() - 0.1, y1=-0.5, fillcolor="#1f77b4", opacity=0.07, line_width=0)

    fig.add_trace(go.Scatter(
        x=oni_df["date"],
        y=oni_df["oni"],
        mode="lines",
        name="ONI",
        line=dict(color="#555", width=1.2),
        hovertemplate="<b>%{x|%Y %b}</b><br>ONI: %{y:+.2f} °C<extra></extra>",
    ))

    fig.add_hline(y=0.5, line_dash="dash", line_color="#d62728", annotation_text="El Niño +0.5")
    fig.add_hline(y=-0.5, line_dash="dash", line_color="#1f77b4", annotation_text="La Niña −0.5")
    fig.add_hline(y=0, line_color="#aaa", line_width=0.8)

    fig.update_layout(
        height=300,
        margin=dict(t=20, b=30, l=40, r=20),
        yaxis_title="ONI (°C)",
        xaxis_title=None,
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Section 2: Pronóstico ENSO oficial (curated links)
# ---------------------------------------------------------------------------

_FORECAST_RESOURCES = [
    {
        "title": "NOAA ENSO Advisory (mensual)",
        "description": (
            "Diagnóstico y pronóstico oficial de NOAA Climate Prediction Center. "
            "Actualización mensual con probabilidades por fase para los próximos trimestres."
        ),
        "button_label": "Ver advisory →",
        "url": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/",
    },
    {
        "title": "IRI ENSO Forecast",
        "description": (
            "Pronóstico probabilístico del International Research Institute for Climate "
            "and Society (Columbia University). Incluye gráfico plume de probabilidades "
            "por trimestre."
        ),
        "button_label": "Ver pronóstico IRI →",
        "url": "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/",
    },
    {
        "title": "NOAA ONI — series y pronóstico",
        "description": (
            "Serie histórica del Oceanic Niño Index y valores proyectados "
            "publicados por NOAA CPC."
        ),
        "button_label": "Ver ONI →",
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
                st.markdown(f"**{resource['title']}**")
                st.caption(resource["description"])
                st.link_button(resource["button_label"], resource["url"], use_container_width=True)


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
        st.caption(
            f"Cache v{version} · CHIRPS {start_year}–{end_year} · "
            f"Generado: {str(computed_at)[:10]} · "
            f"Fuente precipitación: [CHIRPS v2.0](https://www.chc.ucsb.edu/data/chirps)"
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
        "Lag = meses que ONI lidera la precipitación. "
        "\\* p<0.05 · \\*\\* p<0.01 · \\*\\*\\* p<0.001"
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
    with st.expander("Ver tabla completa (Pearson + Spearman + p-values)"):
        detail = table_df.drop(columns=["sig", "pearson_r_display"]).rename(columns={
            "region": "Región",
            "lag": "Lag (meses)",
            "pearson_r": "r (Pearson)",
            "pearson_p": "p (Pearson)",
            "spearman_r": "r (Spearman)",
            "spearman_p": "p (Spearman)",
            "n_obs": "N obs",
        })
        # Highlight significant rows
        def highlight_sig(row: pd.Series) -> list[str]:
            styles = []
            p_col = "p (Pearson)"
            if p_col in row.index and row[p_col] < SIGNIFICANCE_THRESHOLD:
                styles = ["background-color: #e8f5e9"] * len(row)
            else:
                styles = [""] * len(row)
            return styles

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
        colorscale="RdBu_r",
        zmid=0,
        zmin=-0.6,
        zmax=0.6,
        colorbar=dict(title="r (Pearson)"),
        hovertemplate="<b>%{y}</b><br>%{x}<br>r = %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title="Correlación ONI–Precipitación por región y lag",
        height=350,
        margin=dict(t=50, b=40, l=140, r=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
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

    for region_name in REGIONS:
        with st.expander(f"**{region_name}** — {REGIONS[region_name]['description']}"):
            text = _generate_risk_text(region_name, corr_df)
            st.markdown(text)

            # Show miniature correlation table for this region
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
    st.subheader("5. Metadata")

    snapshot, _ = load_enso_snapshot()
    corr_df, _ = load_correlations()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Fuentes y actualizaciones:**")
        if snapshot:
            st.markdown(
                f"- ONI: {snapshot.oni_date} · [NOAA CPC]({NOAA_ONI_URL})\n"
                f"- Niño 3.4: {snapshot.nino34_date} · [NOAA]({NOAA_NINO34_URL})\n"
                f"- SOI: {snapshot.soi_date} · [NOAA CPC]({NOAA_SOI_URL})\n"
            )
        else:
            st.markdown("- Índices ENSO: no disponibles")

    with col2:
        st.markdown("**Dataset correlaciones:**")
        if corr_df is not None and "version" in corr_df.columns:
            v = corr_df["version"].iloc[0]
            ca = str(corr_df.get("computed_at", pd.Series(["?"])).iloc[0])[:10]
            sy = int(corr_df.get("start_year", pd.Series([0])).iloc[0])
            ey = int(corr_df.get("end_year", pd.Series([0])).iloc[0])
            st.markdown(
                f"- Versión: `{v}`\n"
                f"- Período: {sy}–{ey}\n"
                f"- Generado: {ca}\n"
                f"- Fuente precipitación: CHIRPS v2.0 · ⚠️ *Fuente única* (validación ERA5 pendiente)\n"
            )
        else:
            st.markdown("- Cache no disponible")

    github_url = os.getenv("GITHUB_REPO_URL", "#")
    contact = os.getenv("CONTACT_EMAIL", "contacto@example.com")
    st.markdown(
        f"[📂 GitHub]({github_url}) · "
        f"**Disclaimer:** Este tracker es una demostración técnica. "
        f"No constituye asesoría profesional. "
        f"Para análisis de riesgo operacional contactar [{contact}](mailto:{contact})."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    render_sidebar()

    st.title("Argentina ENSO Impact Tracker")
    st.caption(
        "Estado del ENSO y su correlación histórica con precipitación en 5 regiones argentinas. "
        "Todos los datos provienen de fuentes públicas verificables (NOAA CPC, CHIRPS v2.0)."
    )

    render_enso_status()
    st.divider()
    render_forecast()
    st.divider()
    render_correlations()
    st.divider()
    render_risk_implications()
    render_footer()


if __name__ == "__main__":
    main()
