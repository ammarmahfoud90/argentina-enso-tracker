"""Fixed reference used when the monthly observations are extended.

1981–2025 reproduces the reference in the published dashboard before the
2026 extension. It is a project calibration period, not a WMO normal.
Changing the product or the spatial domain requires explicit recalibration.
"""
from __future__ import annotations

import pandas as pd

CALIBRATION_PERIOD = (1981, 2025)


def reference_frame(frame: pd.DataFrame, period: tuple[int, int] | None) -> pd.DataFrame:
    if period is None:
        return frame
    years = pd.to_datetime(frame["date"]).dt.year
    reference = frame.loc[years.between(*period)]
    if reference.empty:
        raise ValueError(f"No observations in calibration period {period}")
    return reference
