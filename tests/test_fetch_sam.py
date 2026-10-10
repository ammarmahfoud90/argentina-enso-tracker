"""Regression tests for NOAA SAM rows with an incomplete current year."""

import pandas as pd
import pytest

from src.fetch_sam import parse_aao

COMPLETE_YEAR = (
    "2025 -0.080 -0.271 0.733 1.138 0.509 0.209 "
    "0.753 0.357 -0.709 -1.236 -1.324 -1.136\n"
)
PARTIAL_YEAR = "2026 0.848 0.489 0.492 -0.125 0.544 2.506 0.394 -0.624 0.263\n"


def test_current_year_supplies_latest_month_without_changing_history():
    history = parse_aao(COMPLETE_YEAR)
    result = parse_aao(COMPLETE_YEAR + PARTIAL_YEAR)

    pd.testing.assert_frame_equal(history, result.iloc[:12].reset_index(drop=True))
    assert len(result) == 21
    assert result.iloc[-1]["date"] == pd.Timestamp("2026-09-15")
    assert result.iloc[-1]["sam"] == 0.26
    assert not (result["date"] > pd.Timestamp("2026-09-15")).any()


@pytest.mark.parametrize("months", range(1, 13))
def test_accepts_available_months_from_january_through_december(months):
    row = "2026 " + " ".join(str(month / 10) for month in range(1, months + 1))
    result = parse_aao(row)

    assert len(result) == months
    assert result.iloc[-1]["date"] == pd.Timestamp(2026, months, 15)


def test_missing_values_preserve_the_month_positions():
    result = parse_aao("Jan Feb Mar Apr May Jun\n2026 0.1 -99.99 0.3 -999 bad 0.6")

    assert list(result["date"].dt.month) == [1, 3, 6]
    assert list(result["sam"]) == [0.1, 0.3, 0.6]


def test_rejects_input_without_valid_months():
    with pytest.raises(RuntimeError, match="No valid AAO/SAM data"):
        parse_aao("Jan Feb Mar\n2026\n2027 -999")
