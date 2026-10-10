"""Official hydrology links; no manually entered, untraceable river levels.

Quantitative levels must have station, datum, timestamp and a retrievable
observation source before being included in a future analysis. ENSO phase
alone is not a river-level forecast.
"""

PARANA_LIVE_LINK = "https://www.ina.gob.ar/alerta/"
PARANA_BDHI_LINK = "https://bdhi.hidricosargentina.gob.ar/"


def get_parana_data() -> dict:
    return {
        "events": [],
        "verification_status": "Quantitative series omitted: no traceable per-observation source",
        "source_url": PARANA_LIVE_LINK,
        "live_link": PARANA_LIVE_LINK,
        "bdhi_link": PARANA_BDHI_LINK,
    }
