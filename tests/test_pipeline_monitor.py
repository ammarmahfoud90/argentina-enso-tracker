"""Tests for the pipeline monitoring module."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline_monitor import PipelineMonitor, SourceMetrics


class TestPipelineMonitor:
    """Tests for PipelineMonitor."""

    def test_track_source_success(self):
        mon = PipelineMonitor()
        with mon.track_source("test_source") as src:
            src.row_count = 42
        assert len(mon._build.sources) == 1
        assert mon._build.sources[0].status == "success"
        assert mon._build.sources[0].row_count == 42
        assert mon._build.sources[0].latency_ms is not None

    def test_track_source_failure(self):
        mon = PipelineMonitor()
        with pytest.raises(ValueError, match="boom"):
            with mon.track_source("bad_source") as src:
                raise ValueError("boom")
        assert mon._build.sources[0].status == "failed"
        assert "boom" in mon._build.sources[0].error_message

    def test_track_quality(self):
        mon = PipelineMonitor()
        df = pd.DataFrame({"a": [1.0, 2.0, None], "b": [0.5, 0.3, 0.1]})
        qm = mon.track_quality("test_data", df,
                               expected_range={"a": (0.0, 1.5)})
        assert qm.null_rate > 0
        assert qm.range_violations == 1  # a=2.0 > 1.5
        assert len(qm.notes) == 1

    def test_finalize_success(self):
        mon = PipelineMonitor()
        with mon.track_source("src") as src:
            src.row_count = 10
        metrics = mon.finalize("success")
        assert metrics.status == "success"
        assert metrics.duration_seconds is not None
        assert metrics.duration_seconds >= 0

    def test_finalize_with_errors(self):
        mon = PipelineMonitor()
        mon.add_error("something broke")
        metrics = mon.finalize("success")
        assert metrics.status == "failure"  # errors override status

    def test_finalize_with_warnings(self):
        mon = PipelineMonitor()
        mon.add_warning("data is stale")
        metrics = mon.finalize("success")
        assert metrics.status == "partial"

    def test_write_health_json(self):
        mon = PipelineMonitor()
        with mon.track_source("test") as src:
            src.row_count = 5
            src.data_freshness_days = 3
        mon.record_output("test.json", 1024)
        mon.finalize("success")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health.json"
            mon.write_health_json(str(path))
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["status"] == "success"
            assert len(data["sources"]) == 1
            assert data["sources"][0]["name"] == "test"
            assert data["sources"][0]["freshness_days"] == 3
            assert "test.json" in data["output_sizes_kb"]

    def test_record_output(self):
        mon = PipelineMonitor()
        mon.record_output("out.json", 2048)
        assert mon._build.output_files["out.json"] == 2048

    def test_to_dict(self):
        mon = PipelineMonitor()
        mon.finalize("success")
        d = mon.to_dict()
        assert "build_id" in d
        assert "sources" in d
        assert "status" in d
