"""Tests for src/fetch_iri_forecast.py — IRI forecast SVG parsing."""

from __future__ import annotations

import re

import pytest

from src.fetch_iri_forecast import _parse_probs_svg, fetch_iri_forecast


class TestParseIRISvg:
    """Test _parse_probs_svg against a minimal synthetic SVG."""

    # Synthetic SVG: 3 trimesters, patches 1-4 are background/axes,
    # patches 5-7 = La Niña, 8-10 = Neutral, 11-13 = El Niño.
    # Plot area: bottom=400 (0%), top=50 (100%), total height=350px.
    # Bar heights encode percentages: (y_bot - y_top) / 350 * 100.
    MINIMAL_SVG = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500">
<!-- ASO -->
<!-- SON -->
<!-- OND -->
<g id="patch_1"><path d="M 0 0 L 800 0 L 800 500 L 0 500 z"/></g>
<g id="patch_2">
    <path d="M 50 400
L 50 400
L 750 50
L 750 50 z"/>
</g>
<g id="patch_3"><path d="M 50 400 L 750 400 L 750 50 L 50 50 z"/></g>
<g id="patch_4"><path d="M 50 400 L 750 400 L 750 50 L 50 50 z"/></g>
<g id="patch_5"><path d="M 100 330 L 130 330 L 130 400 L 100 400 z"/></g>
<g id="patch_6"><path d="M 200 295 L 230 295 L 230 400 L 200 400 z"/></g>
<g id="patch_7"><path d="M 300 365 L 330 365 L 330 400 L 300 400 z"/></g>
<g id="patch_8"><path d="M 140 260 L 170 260 L 170 400 L 140 400 z"/></g>
<g id="patch_9"><path d="M 240 225 L 270 225 L 270 400 L 240 400 z"/></g>
<g id="patch_10"><path d="M 340 330 L 370 330 L 370 400 L 340 400 z"/></g>
<g id="patch_11"><path d="M 180 330 L 210 330 L 210 400 L 180 400 z"/></g>
<g id="patch_12"><path d="M 280 330 L 310 330 L 310 400 L 280 400 z"/></g>
<g id="patch_13"><path d="M 380 295 L 410 295 L 410 400 L 380 400 z"/></g>
<g id="patch_14"><path d="M 500 400 L 530 400 L 530 400 L 500 400 z"/></g>
</svg>"""

    def test_returns_list(self):
        result = _parse_probs_svg(self.MINIMAL_SVG)
        assert isinstance(result, list)

    def test_trimester_count(self):
        result = _parse_probs_svg(self.MINIMAL_SVG)
        assert len(result) == 3

    def test_trimesters_names(self):
        result = _parse_probs_svg(self.MINIMAL_SVG)
        names = [r["trimester"] for r in result]
        assert names == ["ASO", "SON", "OND"]

    def test_probabilities_sum_to_100(self):
        result = _parse_probs_svg(self.MINIMAL_SVG)
        for entry in result:
            total = entry["la_nina"] + entry["neutral"] + entry["el_nino"]
            assert total == 100, f"{entry['trimester']}: sum={total}"

    def test_returns_none_for_empty_svg(self):
        assert _parse_probs_svg("<svg></svg>") is None

    def test_returns_none_for_no_trimesters(self):
        svg = '<svg><g id="patch_2"><path d="M 50 400\nL 50 400\nL 750 50"/></g></svg>'
        assert _parse_probs_svg(svg) is None


class TestFetchIRIForecast:
    """Integration test: fetch_iri_forecast returns valid data from live IRI."""

    @pytest.mark.network
    def test_returns_dict_or_none(self):
        result = fetch_iri_forecast()
        if result is not None:
            assert isinstance(result, dict)
            assert "probs_svg" in result
            assert "plume_svg" in result
            assert "month" in result
            assert "year" in result

    @pytest.mark.network
    def test_probabilities_not_none(self):
        """IRI forecast should return parseable probabilities (not just URLs)."""
        result = fetch_iri_forecast()
        assert result is not None, "fetch_iri_forecast() returned None — IRI server unreachable?"
        assert result["probabilities"] is not None, "Probabilities parse returned None"
        assert len(result["probabilities"]) > 0, "Probabilities list is empty"
