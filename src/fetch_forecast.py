"""Fetch ENSO 6-month probabilistic forecast.

Primary source: IRI ENSO forecast JSON embedded in the IRI forecast page.
The IRI exposes a semi-structured JSON object inside a <script> tag on
https://iri.columbia.edu/our-expertise/climate/enso/

If the JSON cannot be parsed (source format changed, page unavailable),
this module raises ``ForecastUnavailableError`` — the UI must handle this
gracefully by showing the official link, NOT by inventing probabilities.

Fallback link (display-only):
    https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from src.config import IRI_ENSO_FORECAST_URL, NOAA_CPC_ADVISORY_URL
from src.utils import fetch_text, get_logger

logger = get_logger(__name__)


class ForecastUnavailableError(Exception):
    """Raised when the ENSO forecast cannot be parsed from the source.

    The caller (Streamlit app) should display the official forecast link
    instead of any inferred or invented probabilities.
    """


@dataclass
class ForecastQuarter:
    """Probabilities for one forecast target season.

    Attributes:
        label: Human-readable label (e.g. "JJA 2025").
        el_nino_pct: Probability of El Niño (0–100).
        neutral_pct: Probability of Neutral (0–100).
        la_nina_pct: Probability of La Niña (0–100).
        source: Data source label.
    """

    label: str
    el_nino_pct: float
    neutral_pct: float
    la_nina_pct: float
    source: str = "IRI ENSO Forecast"

    def validate(self) -> None:
        """Assert probabilities sum to ~100 (within 2 pp rounding tolerance).

        Raises:
            ValueError: If the sum is not within [98, 102].
        """
        total = self.el_nino_pct + self.neutral_pct + self.la_nina_pct
        if not (98 <= total <= 102):
            raise ValueError(
                f"Probabilidades para {self.label} suman {total:.1f}%, "
                "se esperaba ~100%."
            )


@dataclass
class ENSOForecast:
    """Container for a multi-season ENSO forecast.

    Attributes:
        quarters: List of forecast seasons (up to 6).
        source_url: URL used to obtain the data.
        retrieved_at: ISO timestamp of fetch.
        is_structured: True if probabilities were parsed from structured data;
            False if only the fallback link is available.
        fallback_url: Always set to the NOAA advisory page.
    """

    quarters: list[ForecastQuarter] = field(default_factory=list)
    source_url: str = IRI_ENSO_FORECAST_URL
    retrieved_at: str = ""
    is_structured: bool = False
    fallback_url: str = NOAA_CPC_ADVISORY_URL


# ---------------------------------------------------------------------------
# IRI JSON extraction
# ---------------------------------------------------------------------------

# The IRI ENSO forecast page embeds forecast probabilities in a JavaScript
# object.  The structure has changed over the years; this regex targets the
# pattern observed in 2024-2025 where data appears as:
#   var forecastData = {...};
# or inside a JSON-like block labelled "plume" or "prob".

_IRI_JSON_PATTERNS = [
    # Pattern 1: var forecastData = { ... };
    r"var\s+forecastData\s*=\s*(\{.*?\});",
    # Pattern 2: window.__NEXT_DATA__ or similar
    r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>",
    # Pattern 3: JSON block containing "probabilities" key
    r'(\{"probabilities":\s*\[.*?\]\s*\})',
]


def _try_extract_iri_json(html: str) -> Optional[dict]:
    """Attempt to extract the forecast JSON from the IRI page HTML.

    Args:
        html: Full HTML content of the IRI ENSO forecast page.

    Returns:
        Parsed dictionary if extraction succeeds, else ``None``.
    """
    for pattern in _IRI_JSON_PATTERNS:
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                if "probabilities" in str(data) or "forecast" in str(data).lower():
                    logger.info("IRI JSON extraído con patrón: %r", pattern[:40])
                    return data
            except json.JSONDecodeError:
                continue
    return None


def _parse_iri_forecast(data: dict) -> list[ForecastQuarter]:
    """Parse IRI forecast JSON into a list of ForecastQuarter objects.

    Args:
        data: Parsed JSON dictionary from the IRI page.

    Returns:
        List of :class:`ForecastQuarter` (up to 6 entries).

    Raises:
        ForecastUnavailableError: If the structure cannot be navigated.
    """
    quarters = []

    # Navigate expected structure — adapt if IRI changes layout
    probs_list = None
    if "probabilities" in data:
        probs_list = data["probabilities"]
    elif "data" in data and isinstance(data["data"], list):
        probs_list = data["data"]

    if not probs_list:
        raise ForecastUnavailableError(
            "Estructura JSON de IRI no reconocida; la fuente pudo haber cambiado formato."
        )

    for item in probs_list[:6]:
        try:
            label = item.get("season") or item.get("label") or item.get("period", "?")
            el_nino = float(item.get("el_nino") or item.get("ElNino") or item.get("above") or 0)
            neutral = float(item.get("neutral") or item.get("Neutral") or item.get("normal") or 0)
            la_nina = float(item.get("la_nina") or item.get("LaNina") or item.get("below") or 0)
            q = ForecastQuarter(
                label=str(label),
                el_nino_pct=el_nino,
                neutral_pct=neutral,
                la_nina_pct=la_nina,
            )
            q.validate()
            quarters.append(q)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Skipping forecast item %r: %s", item, exc)
            continue

    if not quarters:
        raise ForecastUnavailableError(
            "No se pudieron extraer trimestres de pronóstico del JSON de IRI."
        )

    return quarters


# ---------------------------------------------------------------------------
# High-level fetch function
# ---------------------------------------------------------------------------


def fetch_enso_forecast() -> ENSOForecast:
    """Attempt to fetch structured ENSO forecast from IRI.

    If the structured forecast cannot be obtained (source format changed,
    network error, JSON not parseable), returns an :class:`ENSOForecast`
    with ``is_structured=False`` and an empty ``quarters`` list.  The
    ``fallback_url`` attribute always points to the NOAA advisory page.

    The dashboard must check ``forecast.is_structured`` before displaying
    probabilities.

    Returns:
        :class:`ENSOForecast` — always returns an object, never raises.
    """
    from datetime import datetime, timezone

    forecast = ENSOForecast()
    forecast.retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        html = fetch_text(IRI_ENSO_FORECAST_URL, label="IRI ENSO Forecast", timeout=30)
    except RuntimeError as exc:
        logger.warning("No se pudo obtener página IRI: %s", exc)
        logger.info(
            "AVISO: pronóstico estructurado no disponible. "
            "El dashboard mostrará el link oficial: %s",
            NOAA_CPC_ADVISORY_URL,
        )
        return forecast

    data = _try_extract_iri_json(html)
    if data is None:
        logger.info(
            "No se encontró JSON de pronóstico en la página IRI. "
            "Esto es esperado si IRI no expone datos estructurados. "
            "El dashboard mostrará el link oficial."
        )
        return forecast

    try:
        forecast.quarters = _parse_iri_forecast(data)
        forecast.is_structured = True
        logger.info("Pronóstico ENSO: %d trimestres parseados", len(forecast.quarters))
    except ForecastUnavailableError as exc:
        logger.warning("ForecastUnavailableError: %s", exc)

    return forecast
