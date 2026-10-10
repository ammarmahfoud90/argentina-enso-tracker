"""Fixed reference used when the monthly observations are extended.

1981–2025 retains the previous dashboard's reference years. The full
CHIRPS v3 migration recalculates the rainfall reference values; subsequent
monthly extensions do not refit it. This is a project calibration period,
not a WMO normal. Product or domain changes require explicit recalibration.
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
