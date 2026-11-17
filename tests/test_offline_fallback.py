"""Offline fallback: a momentary NOAA outage must not tumble the pipeline.

When a live download fails after all retries, the build reads the versioned
copy in ``data/raw/`` that the "Refresh NOAA ENSO Data" workflow maintains,
labels that index ``cached`` with the copy's write date, and keeps publishing
each index's own dates.  When the copy is missing the failure must be loud and
explicit — never an invented value, never one index standing in for another.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

import src.fetch_enso as fe
import src.utils as utils
from src.config import (
    ERDDAP_NINO34_URL,
    NOAA_NINO34_URL,
    NOAA_ONI_URL,
    NOAA_RONI_URL,
    NOAA_SOI_URL,
    RAW_FALLBACK_PATHS,
)
from src.pipeline_monitor import PipelineMonitor

REPO_ROOT = Path(__file__).resolve().parent.parent


def _dead_fetch(*args, **kwargs):
    """Stand-in for fetch_text that behaves like an endpoint that never answers."""
    label = kwargs.get("label") or (args[0] if args else "?")
    raise RuntimeError(f"No se pudo obtener datos de {label} tras 4 intentos.")


# ---------------------------------------------------------------------------
# The registry itself
# ---------------------------------------------------------------------------


class TestFallbackRegistry:
    """Every index the build depends on must have a registered offline copy."""

    @pytest.mark.parametrize(
        "url",
        [NOAA_ONI_URL, NOAA_RONI_URL, NOAA_NINO34_URL, NOAA_SOI_URL],
    )
    def test_url_is_registered(self, url):
        assert url in RAW_FALLBACK_PATHS, f"No offline copy registered for {url}"

    def test_registry_has_no_cross_index_aliasing(self):
        """A cached file may only stand in for its own index."""
        paths = list(RAW_FALLBACK_PATHS.values())
        assert len(paths) == len(set(paths)), (
            f"Two indices share one offline copy: {paths}"
        )


# ---------------------------------------------------------------------------
# fetch_text_or_cached
# ---------------------------------------------------------------------------


class TestFetchTextOrCached:
    """Live failure + a valid local file → cached text with its write date."""

    def test_live_success_is_labelled_live(self, monkeypatch):
        monkeypatch.setattr(
            utils, "fetch_text", lambda *a, **k: "SEAS YR TOTAL ANOM\n DJF 1950 25.01 -1.32\n"
        )
        result = utils.fetch_text_or_cached(NOAA_ONI_URL, label="NOAA ONI")
        assert result.status == "live"
        assert result.is_cached is False
        assert result.path is None
        assert result.as_of is None

    def test_live_failure_reads_the_versioned_copy(self, monkeypatch):
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        result = utils.fetch_text_or_cached(NOAA_ONI_URL, label="NOAA ONI")

        local = REPO_ROOT / RAW_FALLBACK_PATHS[NOAA_ONI_URL]
        assert result.status == "cached"
        assert result.is_cached is True
        assert result.path == RAW_FALLBACK_PATHS[NOAA_ONI_URL]
        assert result.text == local.read_text(encoding="utf-8", errors="replace")
        # The file's own date is reported, not today's data as if it were fresh.
        assert result.as_of and len(result.as_of) == 10
        assert "tras" in (result.live_error or ""), "the live error must be preserved"

    def test_missing_local_copy_raises_a_clear_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        missing = tmp_path / "does-not-exist.txt"
        monkeypatch.setitem(utils.RAW_FALLBACK_PATHS, NOAA_ONI_URL, str(missing))

        with pytest.raises(RuntimeError) as exc:
            utils.fetch_text_or_cached(NOAA_ONI_URL, label="NOAA ONI")

        message = str(exc.value)
        assert "NOAA ONI" in message
        assert str(missing) in message
        assert "Refresh NOAA ENSO Data" in message

    def test_unregistered_url_raises_instead_of_guessing(self, monkeypatch):
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        with pytest.raises(RuntimeError, match="no hay copia versionada"):
            utils.fetch_text_or_cached("https://example.invalid/whatever", label="X")

    def test_empty_local_copy_is_refused(self, monkeypatch, tmp_path):
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        empty = tmp_path / "empty.txt"
        empty.write_text("   \n\n", encoding="utf-8")
        monkeypatch.setitem(utils.RAW_FALLBACK_PATHS, NOAA_ONI_URL, str(empty))

        with pytest.raises(RuntimeError, match="vac"):
            utils.fetch_text_or_cached(NOAA_ONI_URL, label="NOAA ONI")


# ---------------------------------------------------------------------------
# fetch_text retry budget
# ---------------------------------------------------------------------------


class TestRetryBudget:
    """More waiting between attempts, but never more than ~3 minutes a source."""

    def test_waits_grow_and_stay_under_three_minutes(self, monkeypatch):
        slept: list[float] = []

        def timeout_get(*args, **kwargs):
            raise requests.exceptions.Timeout()

        monkeypatch.setattr(utils.requests, "get", timeout_get)
        monkeypatch.setattr(utils.time, "sleep", lambda s: slept.append(s))

        with pytest.raises(RuntimeError):
            utils.fetch_text(
                "https://example.invalid/slow",
                label="slow",
                use_cache=False,
            )

        assert len(slept) >= 2, "there must be more than one wait between attempts"
        assert slept == sorted(slept), f"waits must not shrink: {slept}"
        assert slept[1] > slept[0], f"waiting must grow between attempts: {slept}"

        from src.config import (
            REQUEST_MAX_RETRIES,
            REQUEST_MAX_TOTAL_SECONDS,
            REQUEST_TIMEOUT_SECONDS,
        )

        worst_case = sum(slept) + REQUEST_MAX_RETRIES * REQUEST_TIMEOUT_SECONDS
        assert worst_case <= 200, f"worst case {worst_case}s is over ~3 minutes"
        assert REQUEST_MAX_TOTAL_SECONDS <= 180

    def test_budget_cuts_the_retries_short(self, monkeypatch):
        """An exhausted budget stops the attempts instead of overrunning it."""
        attempts = {"n": 0}

        def timeout_get(*args, **kwargs):
            attempts["n"] += 1
            raise requests.exceptions.Timeout()

        monkeypatch.setattr(utils.requests, "get", timeout_get)
        monkeypatch.setattr(utils.time, "sleep", lambda s: None)
        # A clock that jumps past the budget after the first attempt.
        ticks = iter([0.0, 0.0, 500.0, 500.0, 500.0, 500.0, 500.0, 500.0])
        monkeypatch.setattr(utils.time, "monotonic", lambda: next(ticks))

        with pytest.raises(RuntimeError):
            utils.fetch_text(
                "https://example.invalid/slow",
                label="slow",
                use_cache=False,
                max_total_seconds=60,
            )

        assert attempts["n"] == 1, "the budget must stop further attempts"


# ---------------------------------------------------------------------------
# _fetch_with_fallback — two live sources, then the offline copy
# ---------------------------------------------------------------------------


class TestFetchWithFallbackOffline:
    def test_both_live_sources_down_uses_the_primary_copy(self, monkeypatch):
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        provenance: dict = {}

        df, source = fe._fetch_with_fallback(
            primary_url=NOAA_NINO34_URL,
            primary_label="CPC Niño 3.4",
            primary_parser=fe.parse_nino34,
            fallback_url=ERDDAP_NINO34_URL,
            fallback_label="ERDDAP Niño 3.4",
            fallback_parser=fe.parse_erddap_nino34,
            provenance=provenance,
        )

        assert len(df) > 0
        # The source tag still names the index's own source, not "cached".
        assert source == "CPC"
        assert provenance["status"] == "cached"
        assert provenance["path"] == RAW_FALLBACK_PATHS[NOAA_NINO34_URL]
        assert provenance["as_of"]
        # Dates come from the file that was read — nothing is invented.
        assert df.iloc[-1]["date"] is not None

    def test_live_success_records_live_provenance(self, monkeypatch):
        sample = (
            " YR   MON  TOTAL  ClimAdjust  ANOM\n"
            "2026   9   29.10   26.50   2.60\n"
            "2026  10   29.20   26.55   2.65\n"
        )
        monkeypatch.setattr(fe, "fetch_text", lambda *a, **k: sample)
        provenance: dict = {}

        df, source = fe._fetch_with_fallback(
            primary_url=NOAA_NINO34_URL,
            primary_label="CPC Niño 3.4",
            primary_parser=fe.parse_nino34,
            fallback_url=ERDDAP_NINO34_URL,
            fallback_label="ERDDAP Niño 3.4",
            fallback_parser=fe.parse_erddap_nino34,
            provenance=provenance,
        )

        assert source == "CPC"
        assert provenance == {"status": "live", "source": "CPC"}
        assert len(df) == 2

    def test_no_copy_available_raises_naming_every_source(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        missing = tmp_path / "nino34-gone.txt"
        monkeypatch.setitem(utils.RAW_FALLBACK_PATHS, NOAA_NINO34_URL, str(missing))

        with pytest.raises(RuntimeError) as exc:
            fe._fetch_with_fallback(
                primary_url=NOAA_NINO34_URL,
                primary_label="CPC Niño 3.4",
                primary_parser=fe.parse_nino34,
                fallback_url=ERDDAP_NINO34_URL,
                fallback_label="ERDDAP Niño 3.4",
                fallback_parser=fe.parse_erddap_nino34,
            )

        message = str(exc.value)
        assert "CPC Niño 3.4" in message
        assert "ERDDAP Niño 3.4" in message
        assert str(missing) in message


# ---------------------------------------------------------------------------
# End to end: the snapshot survives a total NOAA outage
# ---------------------------------------------------------------------------


class TestSnapshotUnderOutage:
    def test_outage_builds_from_the_versioned_copies(self, monkeypatch):
        """Live failure + valid local files → snapshot OK, every index "cached"."""
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)

        snapshot = fe.fetch_enso_snapshot()

        assert snapshot.source_status is not None
        for index_name in ("oni", "nino34", "soi"):
            status = snapshot.source_status[index_name]
            assert status["status"] == "cached", f"{index_name} should be cached"
            assert status["as_of"], f"{index_name} must report the file's date"
            assert status["path"] == RAW_FALLBACK_PATHS[
                {
                    "oni": NOAA_ONI_URL,
                    "nino34": NOAA_NINO34_URL,
                    "soi": NOAA_SOI_URL,
                }[index_name]
            ]

        # Source labels stay truthful: these files are CPC products.
        assert snapshot.data_sources["oni"] == "CPC"
        assert snapshot.data_sources["nino34"] == "CPC"
        assert snapshot.data_sources["soi"] == "CPC"

        # Real values with their own dates — nothing invented.
        assert snapshot.oni_date is not None
        assert snapshot.nino34_date is not None
        assert snapshot.soi_date is not None
        assert -5.0 < snapshot.oni_value < 5.0
        assert -5.0 < snapshot.nino34_value < 5.0

    def test_outage_without_local_copies_fails_clearly(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        monkeypatch.setitem(
            utils.RAW_FALLBACK_PATHS, NOAA_ONI_URL, str(tmp_path / "oni-gone.txt")
        )

        with pytest.raises(RuntimeError) as exc:
            fe.fetch_enso_snapshot()

        message = str(exc.value)
        assert "NOAA ONI" in message
        assert "oni-gone.txt" in message
        assert "Refresh NOAA ENSO Data" in message


# ---------------------------------------------------------------------------
# pipeline_health.json
# ---------------------------------------------------------------------------


class TestPipelineHealthCached:
    def test_cached_source_is_written_with_its_date(self, tmp_path):
        monitor = PipelineMonitor()
        monitor.record_source(
            "NOAA ONI (copia versionada)",
            status="cached",
            cached_from="data/raw/oni.ascii.txt",
            as_of="2026-11-10",
            error_message="Timeout al conectar con NOAA ONI",
        )
        monitor.add_warning("oni: descarga en vivo fallida; publicado desde data/raw/oni.ascii.txt")
        monitor.finalize("success")

        out = tmp_path / "pipeline_health.json"
        monitor.write_health_json(str(out))

        import json

        health = json.loads(out.read_text(encoding="utf-8"))
        entry = next(s for s in health["sources"] if s["status"] == "cached")
        assert entry["cached_from"] == "data/raw/oni.ascii.txt"
        assert entry["as_of"] == "2026-11-10"
        # A cached index is a degraded build, not a clean one.
        assert health["status"] == "partial"
        assert health["warnings"]

    def test_cached_is_not_counted_as_a_failure(self, tmp_path):
        monitor = PipelineMonitor()
        monitor.record_source("NOAA SOI (copia versionada)", status="cached", as_of="2026-11-10")
        monitor.finalize("success")
        out = tmp_path / "pipeline_health.json"
        monitor.write_health_json(str(out))

        import json

        health = json.loads(out.read_text(encoding="utf-8"))
        failed = [s["name"] for s in health["sources"] if s["status"] == "failed"]
        assert failed == []


# ---------------------------------------------------------------------------
# RONI — the operational reference keeps its own provenance
# ---------------------------------------------------------------------------


class TestOperationalReferenceFallback:
    def test_roni_cached_is_labelled_cached(self, monkeypatch, tmp_path):
        """RONI falls back to its own copy and says so."""
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        copy = tmp_path / "roni.ascii.txt"
        copy.write_text(
            "SEAS  YR   TOTAL   ANOM\n  JAS 2026  29.12  1.80\n  ASO 2026  29.23  1.95\n",
            encoding="utf-8",
        )
        monkeypatch.setitem(utils.RAW_FALLBACK_PATHS, NOAA_RONI_URL, str(copy))

        result = fe.fetch_operational_reference()

        assert result["roni"] is not None
        assert result["roni"]["status"] == "cached"
        assert result["roni"]["cached_path"] == str(copy)
        assert result["roni"]["cached_as_of"]
        assert result["roni"]["value"] == 1.95
        # The advisory has no offline copy, so it stays explicitly unavailable.
        assert result["advisory"] is None
        assert "NOAA advisory unavailable" in result["errors"]

    def test_roni_without_a_copy_stays_explicitly_unavailable(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fe, "fetch_text", _dead_fetch)
        monkeypatch.setattr(utils, "fetch_text", _dead_fetch)
        monkeypatch.setitem(
            utils.RAW_FALLBACK_PATHS, NOAA_RONI_URL, str(tmp_path / "no-roni.txt")
        )

        result = fe.fetch_operational_reference()

        # No ONI value is ever substituted for a missing RONI observation.
        assert result["roni"] is None
        assert "RONI unavailable" in result["errors"]
