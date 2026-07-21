# Handoff: Argentina ENSO Tracker — Redesign

## Overview
Complete visual + UX redesign of the Argentina ENSO Impact Tracker (currently a Streamlit app at argentina-enso-tracker.onrender.com). The redesign turns the vertical Streamlit bulletin into an editorial, data-first climate dashboard: status hero with phase-transition scale, indicator strip, annotated 50-year ONI chart with 24-month inset, forecast probability plume, correlation heatmap, and a regional risk section with a real-geometry Argentina map.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. The task is to **recreate these designs in the target codebase's environment**. The current app is Streamlit; two viable paths:
1. **Stay in Streamlit**: recreate via custom CSS (st.markdown with unsafe_allow_html), Plotly/Altair charts themed to the tokens below, and st.components for the map. Some effects (load choreography) are not achievable — acceptable degradation.
2. **Recommended**: move the frontend to a small static/React page fed by the same data pipeline (the design is a read-only bulletin; it needs no server-side interactivity Streamlit provides).

## Fidelity
**High-fidelity** for layout, typography, color, and copy structure. **Data shown is partly illustrative**: the ONI historical series, forecast probabilities, and monthly precipitation-anomaly bars are synthesized placeholders — wire them to the app's real data sources (NOAA CPC ONI table, IRI forecast, CHIRPS aggregates). Correlation values and current indicator values were taken from the existing app.

## Screens / Views
Single page, max-width 1180px, centered, 32px side padding, background #FFFFFF.

### 1. Masthead
- Kicker (IBM Plex Mono 11px, letter-spacing 0.14em, uppercase, #79818E): "BOLETÍN CLIMÁTICO · NOAA CPC · CHIRPS V2.0"
- H1 (Libre Franklin 800, 48px, letter-spacing -0.02em, line-height 1.02): "Argentina ENSO Impact Tracker" (two lines)
- Right column, right-aligned: "Actualizado" label + date (Plex Mono 14px/600) + 12px gray description
- Bottom border: 3px solid #14161A

### 2. Status hero (2-col grid, 48px gap, collapses <340px/col)
- Left: red status dot (10px) + mono uppercase red label "CAMBIO DE FASE EN CURSO"; phase title 40px/800 "Transición a Neutral"; explainer paragraph 15px #555C68; threshold note in mono 11px.
- Region selector: pill buttons (mono 12px, 6×13px padding, radius 3px, 1px border #C7CCD6; selected = ink bg #14161A, white text) for NEA / Pampa Húmeda / NOA / Cuyo / Patagonia. Selecting swaps a one-line plain-language advisory in a #F4F6F9 panel (radius 4px, 12×16px padding).
- Right: ONI scale strip — 22px tall bar, radius 4px, gradient La Niña→Neutral→El Niño (#2A55D0 → #8098E0 → #EDEFF3 42–58% → #DC8E80 → #C2382A), black 3px marker at value position ((oni+2.5)/5 of width) with ink tooltip badge "+0.98". Axis labels −2.5 / −0.5 / 0 / +0.5 / +2.5 (mono 11px).

### 3. Indicator strip (3 cells, 1px #E4E7EC dividers via grid gap on colored bg)
Each: mono uppercase label 11px #79818E; value Plex Mono 600 50px (ONI/SST in #C2382A, SOI in ink); unit 15px gray; 13px note. Values count up from 0 over ~1.1s on load (cubic ease-out).

### 4. Serie histórica ONI
- Header row: H2 27px/800 + right-aligned mono meta "1970–hoy · mensual · NOAA CPC"
- Main chart (SVG 1120×250): ink 1.4px line; dashed threshold lines ±0.5 (red/blue, 0.5 opacity); zero line #C7CCD6; vertical episode bands (rect, fill red/blue at 0.09 opacity) for runs of |ONI|≥0.5 lasting ≥5 months; year-span labels ('82–83 etc., mono 10.5px/600) above strong episodes (peak ≥1.5); terminal red dot + "+0.98" label.
- Inset "ÚLTIMOS 24 MESES" (300×230, #FAFBFC panel, 1px border, radius 4px) to the right; wraps under on narrow screens.
- Range switcher (1970/2000/2010–hoy) re-scales the x-axis.

### 5. Pronóstico ENSO oficial
- Probability plume (SVG 1120×300): three 2px lines — El Niño #C2382A, Neutral #79818E, La Niña #2A55D0 — over 7 trimesters (JJA 26 → DJF 27), gridlines at 0/25/50/75/100%, end labels "Neutral 47%" etc. (mono 11.5px/600).
- Source list: 3 rows (grid 180px/110px/1fr/auto), 1px top borders, hover bg #F4F6F9: NOAA ENSO Advisory / IRI ENSO Forecast / NOAA ONI series, each with outlined mono tag chip and "Ver →" link (#1E3FAE).

### 6. Correlación ENSO × Precipitación (heatmap)
- Grid: region column + 4 lag columns (Lag 0m–3m), 6px gaps, cells radius 3px, 16×14px padding.
- Cell bg encodes Pearson r: positive `oklch(0.56 C 30 / A)` with C = 0.14·|r|/0.25, A = 0.12+0.55·|r|/0.25; negative same with hue 262. Value text Plex Mono 14px + red significance stars.
- Data (region: lag0/1/2/3): Pampa Húmeda +0.182***/+0.160***/+0.165***/+0.147***; NEA +0.223***/+0.221***/+0.216***/+0.188***; NOA +0.017/+0.006/+0.003/−0.001; Cuyo +0.031/+0.022/+0.022/+0.020; Patagonia +0.071*/+0.066*/+0.014/−0.017.
- Legend: 180px gradient bar 0→+0.25; "Lectura" paragraph beneath.

### 7. Implicaciones de riesgo por región
- 2-col: left = ranked signal list (region name 15px/700, provinces 12px gray, r value mono, outlined severity chip Alta/Débil/Sin señal) + summary paragraph; right = Argentina map (see map2.html: d3-geo Mercator, Natural Earth countries-110m, neighbors in #F0F2F5, Argentina #FAFBFC with ink outline, region circles r = 9+|r|·90 colored by the heatmap scale, dashed outline when not significant, legend bottom-right).
- Below: 5 accordions (details/summary) per region with a 12-month precipitation-anomaly bar chart (blue #2A55D0 = wetter, red #C2382A = drier, zero line #C7CCD6) and interpretation paragraph.

### 8. Footer
3px ink top border; two mono 11px gray lines: sources + "Índices automáticos — no constituyen declaración oficial".

## Interactions & Behavior
- Region selector: click → swaps advisory text; button transition 250ms (background/color/border).
- Accordions: native details/summary.
- Forecast rows: whole row is a link, hover bg #F4F6F9.
- Load choreography (skip in Streamlit): sections fade+rise 550ms staggered 80ms; chart lines draw via stroke-dashoffset (main 1.5s, inset 1s, plume 1.1s staggered); episode bands/labels fade after line passes; scale marker slides from center 900ms cubic-bezier(.22,.7,.3,1); indicator values count up 1.1s; heatmap cells stagger 25ms each; map circles grow 650ms staggered 130ms. All wrapped in `@media (prefers-reduced-motion: reduce)` kill switch.

## State Management
- `region` (string, default 'NEA') — selector state.
- `rangoHistorico` ('1970–hoy' | '2000–hoy' | '2010–hoy') — chart range.
- Data inputs: current ONI/SST/SOI values + updated date; monthly ONI series; forecast probabilities per trimester; correlation matrix; per-region monthly precipitation anomalies.

## Design Tokens
- Background #FFFFFF; panel #F4F6F9; inset panel #FAFBFC
- Ink #14161A; body muted #555C68; secondary #79818E; disabled #A7AEBB
- Borders #E4E7EC (hairline), #C7CCD6 (axis), #EEF0F4 (faint grid)
- El Niño red #C2382A; La Niña cobalt #2A55D0; link blue #1E3FAE
- Heatmap scale: oklch(0.56 <0–0.14> 30 / <0.12–0.67>) positive, hue 262 negative
- Type: Libre Franklin (400/600/700/800) for UI/headers; IBM Plex Mono (400/500/600) for all numerals, labels, meta
- Scale: H1 48/800, H2 27/800, hero phase 40/800, indicator value 50 mono, body 14–15, meta/labels 11–13 mono
- Radius: 3–4px; hero advisory panel 4px. Spacing: sections 44px top padding; grid gaps 40–48px.

## Assets
- No raster assets. Map geometry: https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json (Natural Earth, public domain) rendered with d3-geo + topojson-client (pinned versions in map2.html).
- Fonts via Google Fonts: Libre Franklin, IBM Plex Mono.

## Files
- `ENSO Tracker v2.dc.html` — the full dashboard (final direction: cool technical). Markup inside `<x-dc>` uses inline styles; logic in the trailing script (data, chart path generation, heatmap colors, selector state, count-up).
- `map2.html` — standalone Argentina signal map (d3), embedded via iframe.
- `ENSO Tracker.dc.html` — earlier warm-paper variant, for reference only.
- `enso-scenes.jsx` + `ENSO Motion.dc.html` — companion 34s motion piece (six scenes), separate deliverable, not part of the app implementation.
