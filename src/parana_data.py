"""Curated Parana River level data during notable ENSO events.

Source: INA (Instituto Nacional del Agua) BDHI, manually compiled from
historical records and published reports.

This is a STATIC dataset -- not fetched live. The INA API is fragile and
requires scraping, so we provide curated historical data plus a direct link
to the INA real-time dashboard.
"""

from __future__ import annotations

PARANA_ENSO_SUMMARY = {
    "station": "Rosario (km 416)",
    "source": "INA BDHI / SIyAH (compilacion manual de registros historicos)",
    "normal_level_m": 3.5,
    "alert_level_m": 4.5,
    "evacuation_level_m": 5.5,
    "events": [
        {
            "year_range": "1982-83",
            "enso_type": "El Nino muy fuerte",
            "peak_level_m": 7.52,
            "peak_date": "1983-07",
            "anomaly_m": 4.02,
            "description": (
                "Crecida extraordinaria. El Parana en Rosario alcanzo 7.52 m, "
                "la segunda marca mas alta del siglo XX. Inundaciones masivas "
                "en Santa Fe, Entre Rios y norte de Buenos Aires."
            ),
        },
        {
            "year_range": "1997-98",
            "enso_type": "El Nino muy fuerte",
            "peak_level_m": 6.84,
            "peak_date": "1998-05",
            "anomaly_m": 3.34,
            "description": (
                "Crecida mayor asociada al El Nino mas intenso del siglo XX. "
                "Evacuaciones en Reconquista, Goya, y localidades riberenas. "
                "El caudal medio del Parana supero los 25.000 m3/s."
            ),
        },
        {
            "year_range": "2015-16",
            "enso_type": "El Nino muy fuerte",
            "peak_level_m": 6.21,
            "peak_date": "2016-01",
            "anomaly_m": 2.71,
            "description": (
                "Crecida significativa coincidiendo con el El Nino mas "
                "intenso registrado instrumentalmente (ONI +2.6). "
                "Inundaciones en Concordia, Concepcion del Uruguay."
            ),
        },
        {
            "year_range": "2020-21",
            "enso_type": "La Nina (triple, 2020-23)",
            "peak_level_m": 0.09,
            "peak_date": "2021-08",
            "anomaly_m": -3.41,
            "description": (
                "Bajante historica: el Parana en Rosario toco 0.09 m en agosto 2021, "
                "el nivel mas bajo en 77 anos. Triple La Nina + deficit "
                "de lluvias en la cuenca alta (Brasil). Afecto la navegacion "
                "fluvial, el abastecimiento de agua potable y la generacion "
                "hidroelectrica de Yacyreta."
            ),
        },
        {
            "year_range": "2023-24",
            "enso_type": "El Nino fuerte (2023-24)",
            "peak_level_m": 5.10,
            "peak_date": "2024-03",
            "anomaly_m": 1.60,
            "description": (
                "Recuperacion del caudal tras la triple La Nina. "
                "El Parana volvio a niveles normales-altos durante el "
                "verano 2023-24, aliviando la crisis hidrica de los anos previos."
            ),
        },
    ],
    "correlation_note": (
        "El nivel del Parana en Rosario muestra una relacion positiva con El Nino: "
        "los eventos El Nino fuertes tienden a producir crecidas significativas "
        "con un retardo de 3 a 6 meses (tiempo de transito de la cuenca alta). "
        "Las La Nina prolongadas, en cambio, se asocian con bajantes. "
        "La senal ENSO se transmite a traves de la precipitacion en la cuenca "
        "del Parana Superior en Brasil (estados de Parana, Sao Paulo, Minas Gerais)."
    ),
}

PARANA_LIVE_LINK = "https://www.ina.gob.ar/alerta/"
PARANA_BDHI_LINK = "https://bdhi.hidricosargentina.gob.ar/"


def get_parana_data() -> dict:
    """Return the curated Parana-ENSO dataset."""
    return {
        "summary": PARANA_ENSO_SUMMARY,
        "live_link": PARANA_LIVE_LINK,
        "bdhi_link": PARANA_BDHI_LINK,
    }
