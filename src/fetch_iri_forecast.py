"""Fetch IRI/CCSR ENSO forecast probabilities by parsing the SVG chart.

The IRI forecast SVG at ensoforecast2.iri.columbia.edu/figure3_plot/{year}/{month}
is a matplotlib-generated grouped bar chart showing La Niña, Neutral, and El Niño
probabilities for 9 upcoming trimesters. This module parses the bar heights to
extract structured probability data.

The plume SVG (figure4_plot) is kept as an image URL — no data extraction needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.config import IRI_FORECAST_PLUME_SVG, IRI_FORECAST_PROBS_SVG
from src.utils import fetch_text, get_logger

logger = get_logger(__name__)


def _parse_probs_svg(svg: str) -> list[dict] | None:
    """Parse probability values from the IRI figure3_plot SVG.

    The SVG contains a grouped bar chart with 3 bars per trimester
    (La Niña, Neutral, El Niño). Each group of 9 patches corresponds
    to one category across all trimesters.

    Returns list of dicts: [{trimester, la_nina, neutral, el_nino}, ...]
    """
    # Extract trimester labels from SVG comments
    trimesters = re.findall(r'<!-- ([A-Z]{3}) -->', svg)
    if len(trimesters) < 3:
        logger.warning("Could not find trimester labels in SVG")
        return None

    # Extract plot area bounds from axes patch (patch_2)
    axes_match = re.search(
        r'id="patch_2">\s*<path d="M [0-9.]+ ([0-9.]+)\s*\nL [0-9.]+ [0-9.]+\s*\nL [0-9.]+ ([0-9.]+)',
        svg,
    )
    if not axes_match:
        logger.warning("Could not find axes bounds in SVG")
        return None

    bottom = float(axes_match.group(1))  # y at 0%
    top = float(axes_match.group(2))     # y at 100%
    total = bottom - top
    if total <= 0:
        logger.warning("Invalid axes bounds: bottom=%.1f, top=%.1f", bottom, top)
        return None

    # Extract all bar patches
    patches = re.findall(r'id="patch_(\d+)">\s*<path d="([^"]+)"', svg)

    n_tri = len(trimesters)

    # Bar patches start after the background patches (1=figure bg, 2=axes bg,
    # 3=axes border, 4=?) — find the first group by looking for patches with
    # consistent spacing. The 3 groups each have n_tri patches.
    # Patches: skip first few, then groups of n_tri for La Niña, Neutral, El Niño.
    bar_patches = []
    for idx_str, d in patches:
        idx = int(idx_str)
        coords = re.findall(r'[ML] ([0-9.]+) ([0-9.]+)', d)
        if len(coords) >= 4:
            ys = [float(c[1]) for c in coords[:4]]
            y_top = min(ys)
            y_bot = max(ys)
            bar_patches.append((idx, y_top, y_bot))

    # Filter to only bars within the plot area (not legend patches at far right)
    # Legend patches have x > the rightmost bar cluster
    plot_bars = [b for b in bar_patches if abs(b[2] - bottom) < 1.0 or abs(b[1] - bottom) < 1.0]

    # We need exactly 3 * n_tri bar patches (skip background/border patches)
    # Background patches have zero height (y_top == y_bot == bottom)
    # OR full-height patches that are background
    # Group by: first n_tri patches after background = group 1, etc.
    # Skip patch_1 (figure bg), patch_2 (axes bg), and look for first zero-or-real bars

    # Simple approach: take patches indexed 5 through 5+3*n_tri-1
    expected_start = 5  # patch_5 is typically the first bar
    expected_count = 3 * n_tri

    if len(patches) < expected_start + expected_count:
        logger.warning(
            "Not enough patches: found %d, expected %d+ for %d trimesters",
            len(patches), expected_start + expected_count, n_tri,
        )
        return None

    def _bar_pct(patch_data: tuple) -> int:
        """Convert bar patch coordinates to percentage (0-100)."""
        _, y_top, y_bot = patch_data
        height = y_bot - y_top
        return round(height / total * 100)

    # Extract the 3 groups
    group_start = expected_start - 1  # 0-indexed into bar_patches list
    # But bar_patches may not start at patch_5, so find by patch index
    bar_by_idx = {b[0]: b for b in bar_patches}

    la_nina_pcts = []
    neutral_pcts = []
    el_nino_pcts = []

    for i in range(n_tri):
        ln_idx = expected_start + i
        ne_idx = expected_start + n_tri + i
        en_idx = expected_start + 2 * n_tri + i

        ln = bar_by_idx.get(ln_idx, (ln_idx, bottom, bottom))
        ne = bar_by_idx.get(ne_idx, (ne_idx, bottom, bottom))
        en = bar_by_idx.get(en_idx, (en_idx, bottom, bottom))

        la_nina_pcts.append(_bar_pct(ln))
        neutral_pcts.append(_bar_pct(ne))
        el_nino_pcts.append(_bar_pct(en))

    # Build result
    result = []
    for i, tri in enumerate(trimesters):
        ln = la_nina_pcts[i] if i < len(la_nina_pcts) else 0
        ne = neutral_pcts[i] if i < len(neutral_pcts) else 0
        en = el_nino_pcts[i] if i < len(el_nino_pcts) else 0

        # Normalize to ensure sum = 100 (rounding may cause ±1)
        total_pct = ln + ne + en
        if total_pct > 0 and total_pct != 100:
            # Adjust the largest value
            diff = 100 - total_pct
            vals = [ln, ne, en]
            max_idx = vals.index(max(vals))
            vals[max_idx] += diff
            ln, ne, en = vals

        result.append({
            "trimester": tri,
            "la_nina": ln,
            "neutral": ne,
            "el_nino": en,
        })

    return result


def fetch_iri_forecast() -> dict | None:
    """Fetch IRI ENSO forecast data (probabilities + plume URL).

    Returns dict with keys:
        probabilities: list of {trimester, la_nina, neutral, el_nino}
        probs_svg:     URL to the probability SVG image
        plume_svg:     URL to the plume SVG image
        month:         forecast month
        year:          forecast year
        source:        attribution string
    Returns None if the forecast is unavailable.
    """
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    probs_url = IRI_FORECAST_PROBS_SVG.format(year=year, month=month)
    plume_url = IRI_FORECAST_PLUME_SVG.format(year=year, month=month)

    logger.info("Fetching IRI forecast SVG for %d/%d...", year, month)

    # Try current month, fall back to previous month
    svg = None
    for attempt_month, attempt_year in [(month, year), (month - 1 if month > 1 else 12, year if month > 1 else year - 1)]:
        url = IRI_FORECAST_PROBS_SVG.format(year=attempt_year, month=attempt_month)
        try:
            svg = fetch_text(url, label="IRI forecast SVG", timeout=30)
            if svg and '<svg' in svg:
                probs_url = url
                plume_url = IRI_FORECAST_PLUME_SVG.format(year=attempt_year, month=attempt_month)
                year, month = attempt_year, attempt_month
                break
            svg = None
        except Exception as exc:
            logger.warning("IRI forecast fetch failed for %d/%d: %s", attempt_year, attempt_month, exc)
            svg = None

    if not svg:
        logger.warning("IRI forecast SVG unavailable")
        return None

    probabilities = _parse_probs_svg(svg)
    if not probabilities:
        logger.warning("Could not parse probabilities from IRI SVG")
        # Return URLs only so frontend can still show the image
        return {
            "probabilities": None,
            "probs_svg": probs_url,
            "plume_svg": plume_url,
            "month": month,
            "year": year,
            "source": "IRI/CCSR (Columbia University)",
        }

    logger.info(
        "IRI forecast: %d trimesters, first=%s (EN=%d%% NE=%d%% LN=%d%%)",
        len(probabilities),
        probabilities[0]["trimester"],
        probabilities[0]["el_nino"],
        probabilities[0]["neutral"],
        probabilities[0]["la_nina"],
    )

    return {
        "probabilities": probabilities,
        "probs_svg": probs_url,
        "plume_svg": plume_url,
        "month": month,
        "year": year,
        "source": "IRI/CCSR (Columbia University)",
    }
