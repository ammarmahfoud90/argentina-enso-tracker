"""The NOAA refresh must read the real CPC SOI layout, and fail when it can't.

`data/raw/soi.txt` sat frozen at May 2026 because the generic row scanner in
``src.utils._parse_last_period`` cannot read the SOI file: each row carries
twelve monthly values, and the year runs into the first value when that value
is wide (``2030-999.9-999.9...``).  The freshness check raised `ValueError`,
the script printed `[FAIL]` and moved on, and the workflow still ended green —
so the file silently stopped being refreshed for five months.

These tests pin both halves of the fix: the check reads the real format by
reusing ``src.fetch_enso.parse_soi``, and a parse error on any index makes the
script exit non-zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.refresh_noaa_data as refresh
from src.config import NOAA_SOI_URL
from src.utils import _parse_last_period, check_noaa_data_freshness

REPO_ROOT = Path(__file__).resolve().parent.parent

# A real excerpt of https://www.cpc.ncep.noaa.gov/data/indices/soi, kept
# verbatim (column positions included): the two sections, the year that runs
# into a wide first value, and the all-placeholder future rows.
REAL_CPC_SOI = """(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS
                        ANOMALY

YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
1951   2.5   1.5  -0.2  -0.5  -1.1   0.3  -1.7  -0.4  -1.8  -1.6  -1.3  -1.2
2025   0.3   0.9   2.8   0.9   0.7   0.5   1.0   0.7   0.1   1.9   1.8  -0.0
2026   2.8   3.4   3.0  -1.6  -2.5  -1.9  -2.2  -1.3  -0.7  -1.8-999.9-999.9
2027-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9

(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS
                    STANDARDIZED    DATA

YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
1951   1.5   0.9  -0.1  -0.3  -0.7   0.2  -1.1  -0.3  -1.2  -1.1  -0.9  -0.8
2025   0.2   0.5   1.7   0.5   0.4   0.3   0.6   0.4   0.0   1.1   1.1  -0.0
2026   1.1   1.4   1.2  -0.6  -0.9  -0.8  -0.9  -0.5  -0.3  -1.1-999.9-999.9
2027-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9
2030-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9
"""


# ---------------------------------------------------------------------------
# Reading the real format
# ---------------------------------------------------------------------------


class TestSoiLastPeriod:
    def test_reads_the_last_real_month_of_a_cpc_sample(self):
        """October is the last month with an observation; the rest are -999.9."""
        assert refresh._soi_last_period(REAL_CPC_SOI) == (2026, 10)

    def test_ignores_the_placeholder_years(self):
        """2027 and 2030 are all -999.9 and must not be read as the latest."""
        year, month = refresh._soi_last_period(REAL_CPC_SOI)
        assert year == 2026, "a row of -999.9 is not an observation"
        assert month == 10

    def test_reads_the_copy_committed_in_the_repo(self):
        """Regression against the file the pipeline actually falls back to."""
        local = REPO_ROOT / "data" / "raw" / "soi.txt"
        year, month = refresh._soi_last_period(local.read_text(encoding="utf-8"))
        assert 1950 <= year <= 2100
        assert 1 <= month <= 12

    def test_reuses_parse_soi_rather_than_a_second_parser(self):
        """The period must come from the build's own parser, not a copy of it."""
        from src.fetch_enso import parse_soi

        expected = parse_soi(REAL_CPC_SOI)["date"].iloc[-1]
        assert refresh._soi_last_period(REAL_CPC_SOI) == (
            int(expected.year), int(expected.month),
        )

    def test_the_generic_scanner_still_cannot_read_this_format(self):
        """Why the override exists: the default parser fails on the SOI file."""
        with pytest.raises(ValueError):
            _parse_last_period(REAL_CPC_SOI)

    def test_empty_payload_raises(self):
        with pytest.raises(ValueError):
            refresh._soi_last_period("YEAR   JAN   FEB\n")


class TestSoiFreshnessCheck:
    def test_a_stale_copy_is_reported_as_stale(self, tmp_path):
        """A copy ending in May against a live file ending in October."""
        stale = tmp_path / "soi.txt"
        stale.write_text(
            REAL_CPC_SOI.replace(
                "2026   1.1   1.4   1.2  -0.6  -0.9  -0.8  -0.9  -0.5  -0.3  -1.1-999.9-999.9",
                "2026   1.1   1.4   1.2  -0.6  -0.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9",
            ),
            encoding="utf-8",
        )

        report = check_noaa_data_freshness(
            stale, REAL_CPC_SOI, period_parser=refresh._soi_last_period
        )

        assert report.local_last_period == (2026, 5)
        assert report.remote_last_period == (2026, 10)
        assert report.period_delta_months == 5
        assert report.status == "STALE"

    def test_a_current_copy_is_reported_as_current(self, tmp_path):
        current = tmp_path / "soi.txt"
        current.write_text(REAL_CPC_SOI, encoding="utf-8")

        report = check_noaa_data_freshness(
            current, REAL_CPC_SOI, period_parser=refresh._soi_last_period
        )

        assert report.is_current is True
        assert report.period_delta_months == 0

    def test_the_soi_source_is_registered_with_its_parser(self):
        soi = next(s for s in refresh.SOURCES if s["url"] == NOAA_SOI_URL)
        assert soi["period_parser"] is refresh._soi_last_period

    def test_default_parser_is_unchanged_for_the_other_sources(self):
        """ONI, Niño 3.4 and RONI keep the generic scanner."""
        for source in refresh.SOURCES:
            if source["url"] == NOAA_SOI_URL:
                continue
            assert source.get("period_parser") is None


# ---------------------------------------------------------------------------
# A parse error must fail the run
# ---------------------------------------------------------------------------


def _one_source(tmp_path, label="SOI", parser=None, text="data"):
    local = tmp_path / "copy.txt"
    local.write_text(text, encoding="utf-8")
    return [{
        "label": label,
        "url": "https://example.invalid/index",
        "local_path": local,
        "description": "test source",
        "period_parser": parser,
    }]


class TestExitCode:
    def test_a_parse_error_fails_the_run(self, monkeypatch, tmp_path, capsys):
        """The old behaviour printed [FAIL] and still exited 0."""
        def boom(_text):
            raise ValueError("no valid rows")

        monkeypatch.setattr(refresh, "SOURCES", _one_source(tmp_path, parser=boom))
        monkeypatch.setattr(refresh, "fetch_text", lambda *a, **k: "live payload")
        monkeypatch.setattr(refresh, "_write_github_output", lambda *a, **k: None)

        with pytest.raises(SystemExit) as exc:
            refresh.main()

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "Parser error during freshness check" in out
        assert "FAILED  : SOI" in out
        assert "::error::Refresh failed for SOI" in out

    def test_a_fetch_error_fails_the_run(self, monkeypatch, tmp_path, capsys):
        def dead(*args, **kwargs):
            raise RuntimeError("timeout")

        monkeypatch.setattr(refresh, "SOURCES", _one_source(tmp_path, label="ONI"))
        monkeypatch.setattr(refresh, "fetch_text", dead)
        monkeypatch.setattr(refresh, "_write_github_output", lambda *a, **k: None)

        with pytest.raises(SystemExit) as exc:
            refresh.main()

        assert exc.value.code == 1
        assert "FAILED  : ONI" in capsys.readouterr().out

    def test_a_clean_run_exits_zero(self, monkeypatch, tmp_path):
        """Nothing to update is still a success."""
        monkeypatch.setattr(
            refresh, "SOURCES",
            _one_source(tmp_path, parser=lambda _t: (2026, 10), text=REAL_CPC_SOI),
        )
        monkeypatch.setattr(refresh, "fetch_text", lambda *a, **k: REAL_CPC_SOI)
        monkeypatch.setattr(refresh, "_write_github_output", lambda *a, **k: None)

        with pytest.raises(SystemExit) as exc:
            refresh.main()

        assert exc.value.code == 0

    def test_failed_sources_are_reported_to_the_workflow(self, monkeypatch, tmp_path):
        """The run writes failed_sources so the job can be read without the log."""
        outputs: dict[str, str] = {}

        def boom(_text):
            raise ValueError("no valid rows")

        monkeypatch.setattr(refresh, "SOURCES", _one_source(tmp_path, parser=boom))
        monkeypatch.setattr(refresh, "fetch_text", lambda *a, **k: "live payload")
        monkeypatch.setattr(
            refresh, "_write_github_output", lambda k, v: outputs.__setitem__(k, v)
        )

        with pytest.raises(SystemExit):
            refresh.main()

        assert outputs["failed_sources"] == "SOI"
        assert outputs["changed_sources"] == ""


class TestWorkflowDependencies:
    def test_the_workflow_installs_pandas(self):
        """parse_soi needs pandas, so `pip install requests` alone would break."""
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "refresh-noaa-data.yml"
        ).read_text(encoding="utf-8")
        install = next(
            line for line in workflow.splitlines() if "pip install" in line
        )
        assert "pandas" in install, install
        assert "requests" in install, install
