"""Data lineage tracking for the ENSO build pipeline.

Records which sources contributed to each build, what transformations
were applied, and what artifacts were produced.  Answers the question:
"For today's enso.json, where did each piece of data come from?"
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import LINEAGE_PATH


@dataclass
class SourceRecord:
    """A data source that contributed to the build."""

    name: str
    url: Optional[str] = None
    access_method: str = "live_fetch"  # live_fetch, cache, parquet, static
    status: str = "pending"  # success, failed, cached, skipped
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    row_count: Optional[int] = None
    feeds_sections: list[str] = field(default_factory=list)


@dataclass
class TransformRecord:
    """A transformation step in the pipeline."""

    name: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    row_count_in: Optional[int] = None
    row_count_out: Optional[int] = None
    note: Optional[str] = None


@dataclass
class ArtifactRecord:
    """An output file produced by the build."""

    path: str
    size_bytes: int
    format: str  # json, parquet
    key_count: Optional[int] = None
    row_count: Optional[int] = None


class LineageTracker:
    """Track data provenance through the build pipeline."""

    def __init__(self) -> None:
        self.build_id = datetime.now(timezone.utc).isoformat()
        self.sources: list[SourceRecord] = []
        self.transforms: list[TransformRecord] = []
        self.artifacts: list[ArtifactRecord] = []

    def register_source(self, name: str, **kwargs: Any) -> SourceRecord:
        """Register a data source."""
        src = SourceRecord(name=name, **kwargs)
        self.sources.append(src)
        return src

    def register_transform(
        self,
        name: str,
        inputs: list[str],
        outputs: list[str],
        **kwargs: Any,
    ) -> TransformRecord:
        """Register a transformation step."""
        tx = TransformRecord(name=name, inputs=inputs, outputs=outputs, **kwargs)
        self.transforms.append(tx)
        return tx

    def register_artifact(
        self, path: str, size_bytes: int, fmt: str = "json", **kwargs: Any
    ) -> None:
        """Register an output artifact."""
        self.artifacts.append(
            ArtifactRecord(path=path, size_bytes=size_bytes, format=fmt, **kwargs)
        )

    def build_dependency_graph(self) -> dict[str, list]:
        """Build a source -> transform -> output DAG.

        Returns a dict with ``nodes`` and ``edges`` lists suitable for
        frontend visualization.
        """
        nodes: list[dict] = []
        edges: list[dict] = []

        source_names = {s.name for s in self.sources}

        for src in self.sources:
            nodes.append(
                {
                    "id": f"src:{src.name}",
                    "type": "source",
                    "label": src.name,
                    "status": src.status,
                }
            )
        for tx in self.transforms:
            nodes.append(
                {
                    "id": f"tx:{tx.name}",
                    "type": "transform",
                    "label": tx.name,
                    "status": tx.status,
                }
            )
            for inp in tx.inputs:
                if inp in source_names:
                    edges.append({"from": f"src:{inp}", "to": f"tx:{tx.name}"})
            for out in tx.outputs:
                edges.append({"from": f"tx:{tx.name}", "to": f"out:{out}"})

        for art in self.artifacts:
            nodes.append(
                {"id": f"out:{art.path}", "type": "artifact", "label": art.path}
            )

        return {"nodes": nodes, "edges": edges}

    def to_dict(self) -> dict[str, Any]:
        """Serialize lineage to a JSON-compatible dict."""
        return {
            "build_id": self.build_id,
            "sources": [asdict(s) for s in self.sources],
            "transforms": [asdict(t) for t in self.transforms],
            "artifacts": [asdict(a) for a in self.artifacts],
            "dependency_graph": self.build_dependency_graph(),
        }

    def write_json(self, output_path: str = LINEAGE_PATH) -> None:
        """Write lineage to JSON file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def store_in_duckdb(self, warehouse: Any) -> None:
        """Persist lineage records in the DuckDB warehouse.

        Creates tables build_lineage, source_lineage, transform_lineage
        and inserts this build's records.
        """
        con = warehouse.con

        con.execute("""
            CREATE TABLE IF NOT EXISTS build_lineage (
                build_id     VARCHAR PRIMARY KEY,
                start_time   VARCHAR,
                status       VARCHAR,
                n_sources    INTEGER,
                n_transforms INTEGER,
                n_artifacts  INTEGER
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS source_lineage (
                build_id      VARCHAR,
                source_name   VARCHAR NOT NULL,
                url           VARCHAR,
                access_method VARCHAR,
                status        VARCHAR,
                row_count     INTEGER,
                date_range_start VARCHAR,
                date_range_end   VARCHAR,
                PRIMARY KEY (build_id, source_name)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS transform_lineage (
                build_id        VARCHAR,
                transform_name  VARCHAR NOT NULL,
                inputs          VARCHAR,
                outputs         VARCHAR,
                status          VARCHAR,
                row_count_in    INTEGER,
                row_count_out   INTEGER,
                PRIMARY KEY (build_id, transform_name)
            )
        """)

        con.execute(
            "INSERT INTO build_lineage VALUES (?, ?, ?, ?, ?, ?)",
            [
                self.build_id,
                self.build_id,
                "success",
                len(self.sources),
                len(self.transforms),
                len(self.artifacts),
            ],
        )
        for s in self.sources:
            con.execute(
                "INSERT INTO source_lineage VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    self.build_id,
                    s.name,
                    s.url,
                    s.access_method,
                    s.status,
                    s.row_count,
                    s.date_range_start,
                    s.date_range_end,
                ],
            )
        for t in self.transforms:
            con.execute(
                "INSERT INTO transform_lineage VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    self.build_id,
                    t.name,
                    json.dumps(t.inputs),
                    json.dumps(t.outputs),
                    t.status,
                    t.row_count_in,
                    t.row_count_out,
                ],
            )
