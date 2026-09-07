"""Tests for the data lineage tracking module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.lineage import LineageTracker


class TestLineageTracker:
    """Tests for LineageTracker."""

    def test_register_source(self):
        lt = LineageTracker()
        src = lt.register_source("NOAA ONI", url="http://example.com",
                                 access_method="live_fetch", status="success",
                                 feeds_sections=["current", "oni_series"])
        assert len(lt.sources) == 1
        assert src.name == "NOAA ONI"
        assert src.feeds_sections == ["current", "oni_series"]

    def test_register_transform(self):
        lt = LineageTracker()
        tx = lt.register_transform("episode_detection",
                                    inputs=["NOAA ONI"],
                                    outputs=["episodes"],
                                    parameters={"threshold": 0.5},
                                    status="success",
                                    row_count_in=900, row_count_out=32)
        assert len(lt.transforms) == 1
        assert tx.row_count_out == 32

    def test_register_artifact(self):
        lt = LineageTracker()
        lt.register_artifact("enso.json", 700000, "json", key_count=24)
        assert len(lt.artifacts) == 1
        assert lt.artifacts[0].size_bytes == 700000

    def test_build_dependency_graph(self):
        lt = LineageTracker()
        lt.register_source("A", status="success")
        lt.register_source("B", status="success")
        lt.register_transform("T1", inputs=["A", "B"], outputs=["out1"],
                              status="success")
        graph = lt.build_dependency_graph()
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 3  # 2 sources + 1 transform
        assert len(graph["edges"]) == 3  # A->T1, B->T1, T1->out1

    def test_to_dict(self):
        lt = LineageTracker()
        lt.register_source("S1", status="success")
        lt.register_transform("T1", inputs=["S1"], outputs=["o1"], status="success")
        lt.register_artifact("out.json", 1024, "json")
        d = lt.to_dict()
        assert "build_id" in d
        assert len(d["sources"]) == 1
        assert len(d["transforms"]) == 1
        assert len(d["artifacts"]) == 1

    def test_write_json(self):
        lt = LineageTracker()
        lt.register_source("S1", status="success")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lineage.json"
            lt.write_json(str(path))
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["sources"][0]["name"] == "S1"

    def test_store_in_duckdb(self):
        """Test lineage persistence in DuckDB."""
        from src.warehouse import ENSOWarehouse
        lt = LineageTracker()
        lt.register_source("NOAA ONI", status="success", row_count=900)
        lt.register_transform("episodes", inputs=["NOAA ONI"],
                              outputs=["episodes"], status="success",
                              row_count_in=900, row_count_out=32)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_lin.duckdb"
            with ENSOWarehouse(db_path=db_path) as wh:
                wh.initialize()
                lt.store_in_duckdb(wh)
                # Verify data was inserted
                builds = wh.con.execute("SELECT * FROM build_lineage").fetchall()
                assert len(builds) == 1
                sources = wh.con.execute("SELECT * FROM source_lineage").fetchall()
                assert len(sources) == 1
                transforms = wh.con.execute("SELECT * FROM transform_lineage").fetchall()
                assert len(transforms) == 1

    def test_empty_tracker(self):
        lt = LineageTracker()
        d = lt.to_dict()
        assert d["sources"] == []
        assert d["transforms"] == []
        assert d["artifacts"] == []
        graph = d["dependency_graph"]
        assert graph["nodes"] == []
        assert graph["edges"] == []
