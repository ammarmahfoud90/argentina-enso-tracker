"""Lightweight pipeline monitoring for the ENSO daily build.

Tracks timing, status, data freshness, and quality metrics per build.
Outputs pipeline_health.json for the site and emits GitHub Actions annotations.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

import pandas as pd

from src.config import PIPELINE_HEALTH_PATH


@dataclass
class SourceMetrics:
    """Metrics for a single data source fetch."""

    source_name: str
    status: str = "pending"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    latency_ms: Optional[float] = None
    data_freshness_days: Optional[int] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    cache_hit: bool = False


@dataclass
class QualityMetrics:
    """Data quality metrics for a dataset."""

    dataset_name: str
    null_rate: Optional[float] = None
    value_count: Optional[int] = None
    range_violations: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class BuildMetrics:
    """Aggregate metrics for a complete build run."""

    build_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = "running"
    sources: list[SourceMetrics] = field(default_factory=list)
    quality: list[QualityMetrics] = field(default_factory=list)
    output_files: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PipelineMonitor:
    """Instrument and track a build pipeline execution."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._build = BuildMetrics(build_id=now, start_time=now)
        self._wall_start = time.perf_counter()

    @contextmanager
    def track_source(self, source_name: str) -> Generator[SourceMetrics, None, None]:
        """Context manager to track a data source fetch.

        Usage::

            with monitor.track_source("NOAA ONI") as src:
                data = fetch_something()
                src.row_count = len(data)
                src.data_freshness_days = 5
        """
        metrics = SourceMetrics(source_name=source_name)
        metrics.start_time = datetime.now(timezone.utc).isoformat()
        start = time.perf_counter()
        try:
            yield metrics
            if metrics.status == "pending":
                metrics.status = "success"
        except Exception as exc:
            metrics.status = "failed"
            metrics.error_message = str(exc)[:200]
            raise
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            metrics.latency_ms = round(elapsed, 1)
            metrics.end_time = datetime.now(timezone.utc).isoformat()
            self._build.sources.append(metrics)

    def track_quality(
        self,
        dataset_name: str,
        df: pd.DataFrame,
        expected_range: dict[str, tuple[float, float]] | None = None,
    ) -> QualityMetrics:
        """Compute and record quality metrics for a DataFrame."""
        total_cells = df.shape[0] * df.shape[1]
        null_count = int(df.isnull().sum().sum())
        qm = QualityMetrics(
            dataset_name=dataset_name,
            null_rate=round(null_count / total_cells, 4) if total_cells > 0 else 0.0,
            value_count=df.shape[0],
        )
        if expected_range:
            for col, (lo, hi) in expected_range.items():
                if col in df.columns:
                    violations = int(((df[col] < lo) | (df[col] > hi)).sum())
                    if violations > 0:
                        qm.range_violations += violations
                        qm.notes.append(f"{col}: {violations} values outside [{lo}, {hi}]")
        self._build.quality.append(qm)
        return qm

    def record_output(self, path: str, size_bytes: int) -> None:
        """Record an output artifact."""
        self._build.output_files[path] = size_bytes

    def add_warning(self, msg: str) -> None:
        self._build.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self._build.errors.append(msg)

    def finalize(self, status: str = "success") -> BuildMetrics:
        """Mark build complete and compute final metrics."""
        self._build.end_time = datetime.now(timezone.utc).isoformat()
        self._build.duration_seconds = round(
            time.perf_counter() - self._wall_start, 2
        )
        if self._build.errors:
            self._build.status = "failure"
        elif self._build.warnings:
            self._build.status = "partial"
        else:
            self._build.status = status
        return self._build

    def write_health_json(self, output_path: str = PIPELINE_HEALTH_PATH) -> None:
        """Write pipeline health summary for the site frontend."""
        health: dict[str, Any] = {
            "build_id": self._build.build_id,
            "status": self._build.status,
            "duration_seconds": self._build.duration_seconds,
            "last_updated": self._build.end_time or self._build.start_time,
            "sources": [
                {
                    "name": s.source_name,
                    "status": s.status,
                    "latency_ms": s.latency_ms,
                    "freshness_days": s.data_freshness_days,
                }
                for s in self._build.sources
            ],
            "data_quality": {
                q.dataset_name: {
                    "rows": q.value_count,
                    "null_rate": q.null_rate,
                    "range_violations": q.range_violations,
                }
                for q in self._build.quality
            },
            "output_sizes_kb": {
                k: round(v / 1024, 1) for k, v in self._build.output_files.items()
            },
            "warnings": self._build.warnings,
            "errors": self._build.errors,
        }
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(health, f, ensure_ascii=False, indent=2)

    def emit_github_annotations(self) -> None:
        """Print GitHub Actions annotations for warnings and errors."""
        for w in self._build.warnings:
            print(f"::warning file=build.py::{w}")
        for e in self._build.errors:
            print(f"::error file=build.py::{e}")

    def write_job_summary(self) -> None:
        """Write a GitHub Actions job summary markdown table."""
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return
        lines = [
            "## Pipeline Build Summary\n",
            f"**Status:** {self._build.status} | "
            f"**Duration:** {self._build.duration_seconds}s\n",
            "### Data Sources\n",
            "| Source | Status | Latency | Freshness |",
            "|--------|--------|---------|-----------|",
        ]
        for s in self._build.sources:
            fresh = f"{s.data_freshness_days}d" if s.data_freshness_days is not None else "—"
            latency = f"{s.latency_ms:.0f}ms" if s.latency_ms is not None else "—"
            lines.append(f"| {s.source_name} | {s.status} | {latency} | {fresh} |")

        if self._build.output_files:
            lines.append("\n### Output Files\n")
            lines.append("| File | Size |")
            lines.append("|------|------|")
            for path, size in self._build.output_files.items():
                lines.append(f"| {path} | {size / 1024:.1f} KB |")

        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def to_dict(self) -> dict:
        """Serialize full build metrics to dict."""
        return asdict(self._build)
