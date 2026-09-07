"""Tests for the DuckDB analytical warehouse."""

import tempfile
from pathlib import Path

import pytest


class TestENSOWarehouse:
    """Tests for src.warehouse.ENSOWarehouse."""

    @pytest.fixture
    def warehouse(self):
        from src.warehouse import ENSOWarehouse
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.duckdb"
            wh = ENSOWarehouse(db_path=db_path)
            wh.initialize()
            yield wh
            wh.close()

    def test_initialize_creates_tables(self, warehouse):
        tables = warehouse.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "dim_region" in table_names
        assert "dim_season" in table_names
        assert "dim_enso_episode" in table_names
        assert "fact_observations" in table_names
        assert "fact_correlations" in table_names

    def test_dim_region_populated(self, warehouse):
        rows = warehouse.con.execute("SELECT COUNT(*) FROM dim_region").fetchone()
        assert rows[0] == 5

    def test_dim_region_names(self, warehouse):
        names = warehouse.con.execute(
            "SELECT name FROM dim_region ORDER BY region_id"
        ).fetchall()
        expected = ["Pampa H\u00fameda", "NEA", "NOA", "Cuyo", "Patagonia"]
        assert [r[0] for r in names] == expected

    def test_dim_season_populated(self, warehouse):
        rows = warehouse.con.execute("SELECT COUNT(*) FROM dim_season").fetchone()
        assert rows[0] == 5  # ANN + SON + DEF + MAM + JJA

    def test_dim_season_codes(self, warehouse):
        codes = warehouse.con.execute(
            "SELECT code FROM dim_season ORDER BY season_id"
        ).fetchall()
        assert [r[0] for r in codes] == ["ANN", "SON", "DEF", "MAM", "JJA"]

    def test_load_episodes(self, warehouse):
        episodes = [
            {"type": "El Ni\u00f1o", "start": "1997-05-15", "end": "1998-05-15",
             "peak_oni": 2.4, "peak_season": "NDJ 1998", "category": "muy fuerte"},
            {"type": "La Ni\u00f1a", "start": "2010-06-15", "end": "2012-03-15",
             "peak_oni": -1.7, "peak_season": "DJF 2011", "category": "fuerte"},
        ]
        n = warehouse.load_episodes(episodes)
        assert n == 2
        summary = warehouse.episode_summary()
        assert len(summary) == 2
        assert summary[0]["type"] == "El Ni\u00f1o"
        assert summary[0]["peak_oni"] == 2.4

    def test_observation_coverage_empty(self, warehouse):
        coverage = warehouse.observation_coverage()
        assert coverage == {}

    def test_strongest_signal_empty(self, warehouse):
        result = warehouse.strongest_enso_signal()
        assert result == []

    def test_region_correlations_unknown_region(self, warehouse):
        result = warehouse.region_correlations("Antartida")
        assert result == []

    def test_idempotent_initialize(self, warehouse):
        """Calling initialize() twice should not error."""
        warehouse.initialize()
        rows = warehouse.con.execute("SELECT COUNT(*) FROM dim_region").fetchone()
        assert rows[0] == 5

    def test_context_manager(self):
        from src.warehouse import ENSOWarehouse
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_ctx.duckdb"
            with ENSOWarehouse(db_path=db_path) as wh:
                wh.initialize()
                assert wh.con.execute("SELECT 1").fetchone()[0] == 1
