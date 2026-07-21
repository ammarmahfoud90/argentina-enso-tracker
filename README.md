# Argentina ENSO Impact Tracker

Primer entregable de **FRIS (FloodRisk Intelligence System)**.
Sitio editorial estático que muestra el estado actual del ENSO (El Niño / La Niña)
y su correlación histórica con precipitación en 5 regiones de Argentina.

**Demo:** *(URL Render disponible tras deploy — ver instrucciones abajo)*

---

## Arquitectura

El proyecto es un **sitio estático** generado por un pipeline Python.
No hay servidor de aplicación en producción.

```
build.py  →  site/data/enso.json  →  site/index.html  (vanilla JS)
                                  →  site/map.html     (D3 v7 + topojson)
```

| Componente | Descripción |
|---|---|
| `build.py` | Fetches live NOAA indices, lee el Parquet de correlaciones, detecta episodios ENSO, escribe `site/data/enso.json` |
| `site/data/enso.json` | Único origen de datos del frontend. Actualizado diariamente por GitHub Action |
| `site/index.html` | Página editorial: ONI hero + escala gradiente, cards, gráfico histórico SVG, heatmap de correlaciones, sección de riesgo por región, mapa |
| `site/map.html` | Mapa Argentina con D3 v7 + topojson; círculos proporcionales a \|r Pearson\| |
| `site/js/advice.js` | Textos de riesgo parametrizados — condicionales sobre fase ONI real + r real |
| `site/css/tokens.css` | Tokens de diseño v2 (paleta blanca editorial) |
| `.github/workflows/daily-build.yml` | Cron 07:00 UTC — corre `build.py`, valida JSON, commitea si hay cambios |

**Regla de datos:** todo número renderizado en el sitio proviene de `enso.json`
(generado desde NOAA CPC + Parquet CHIRPS). No hay datos inventados ni generadores sintéticos.

---

## Fuentes de datos

| Índice | Fuente | Actualización |
|---|---|---|
| ONI (Oceanic Niño Index) | NOAA CPC | Mensual |
| Niño 3.4 SST anomalía | NOAA ERSSTv5 | Mensual |
| SOI (Índice Oscilación Sur) | NOAA CPC | Mensual |
| Precipitación histórica | CHIRPS v2.0 (CHG/UCSB) | Anual |
| Pronóstico ENSO | IRI Columbia / NOAA CPC — solo links | Mensual |

---

## Regiones analizadas

| Región | Bounding Box (lat/lon) | Provincias |
|---|---|---|
| **Pampa Húmeda** | −40/−29°S · −65/−57°O | BA (centro-sur), Santa Fe (sur), Córdoba (sur) |
| **NEA** | −29/−22°S · −62/−53°O | Chaco, Formosa, Corrientes, Misiones |
| **NOA** | −29/−22°S · −69/−62°O | Salta, Jujuy, Tucumán, Catamarca, Stgo. del Estero |
| **Cuyo** | −36/−28°S · −70/−65°O | Mendoza, San Juan, La Rioja, San Luis |
| **Patagonia** | −55/−37°S · −73/−62°O | Neuquén, Río Negro, Chubut, Santa Cruz |

Los límites derivan de los datos vectoriales del IGN Argentina y fueron
ajustados +0.1° para cobertura completa de píxeles CHIRPS.

---

## Metodología de correlación

1. **Precipitación mensual** por región: promedio espacial de CHIRPS v2.0
   (resolución 0.05°, 1981–presente) dentro del bounding box.
2. **ONI mensual**: serie de anomalías Niño 3.4 con media móvil 3 meses
   (NOAA CPC, base 1991–2020).
3. **Correlación**: Pearson y Spearman entre ONI y precipitación, con lags
   0, 1, 2, 3 meses (ONI lidera). Período: 1981–2024.
4. **Significancia**: p-value de dos colas (umbral p < 0.05).
5. **Detección de episodios**: ONI ≥ +0.5 / ≤ −0.5 por ≥5 temporadas
   consecutivas solapadas (criterio NOAA CPC).

### Resultados (CHIRPS 1981–2024)

| Región | Mejor r Pearson | Lag | p-value |
|---|---|---|---|
| NEA | +0.223 | 0m | \*\*\* |
| Pampa Húmeda | +0.186 | 0m | \*\*\* |
| NOA | — | — | n.s. |
| Cuyo | — | — | n.s. |
| Patagonia | — | — | n.s. |

---

## Setup local

### Requisitos
```
Python 3.11+
pip install -r requirements-data.txt   # para build.py
pip install -r requirements.txt        # para todo (incl. legacy Streamlit)
```

### Generar cache de correlaciones (una sola vez, tarda ~20 min)
```bash
python -m src.compute_correlations
```
Accede a CHIRPS via IRI OPeNDAP — descarga sólo el subset Argentina (~486 MB, 1981–2024).
El resultado se guarda en `data/processed/correlations.parquet` (versionado en el repo).

### Generar el JSON del sitio
```bash
python build.py
# → site/data/enso.json
```
Requiere internet para fetchar NOAA CPC. Lee el Parquet en caché, no re-corre CHIRPS.

### Ver el sitio localmente
```bash
# Cualquier servidor HTTP estático sirve:
python -m http.server 8080 --directory site
# → http://localhost:8080
```

### Tests
```bash
pytest -m "not integration"   # unit tests (sin red)
pytest                        # incluye tests de integración NOAA live
```

---

## Deploy en Render (sitio estático)

1. Push este repo a GitHub.
2. En Render: **New → Static Site → conectar repo**.
3. Configurar:
   - **Publish directory:** `site`
   - **Build command:** *(vacío — el JSON se commitea por el GitHub Action)*
4. El GitHub Action (`.github/workflows/daily-build.yml`) corre `build.py` diariamente
   a las 07:00 UTC y commitea `site/data/enso.json` si hubo cambios.
   Render detecta el nuevo commit y redeploya automáticamente.

> **Nota:** Si el repo venía configurado como Web Service en Render, cambiar
> el tipo a Static Site requiere crear un nuevo servicio o editar manualmente
> en Settings → Environment.

---

## Estructura del repo

```
argentina-enso-tracker/
├── build.py                      # Pipeline → site/data/enso.json
├── render.yaml                   # Render static site config
├── requirements.txt              # Todas las dependencias
├── requirements-data.txt         # Solo las necesarias para build.py
├── pyproject.toml                # ruff + black + pytest config
├── .env.example
├── .github/
│   └── workflows/
│       └── daily-build.yml       # Cron diario: fetch → JSON → commit
├── site/                         # Sitio estático (servido en producción)
│   ├── index.html                # Página principal (vanilla JS)
│   ├── map.html                  # Mapa D3 + topojson
│   ├── css/
│   │   └── tokens.css            # Design tokens v2
│   ├── js/
│   │   └── advice.js             # Textos de riesgo (auditables)
│   └── data/
│       └── enso.json             # Generado por build.py (versionado)
├── src/                          # Pipeline de datos (usado por build.py)
│   ├── config.py                 # Regiones, URLs, umbrales ENSO
│   ├── fetch_enso.py             # ONI, Niño 3.4, SOI desde NOAA
│   ├── fetch_chirps.py           # Descarga y procesamiento CHIRPS
│   ├── compute_correlations.py   # Script one-shot (Pearson + Spearman)
│   └── utils.py                  # HTTP retry, logging
├── data/
│   ├── raw/                      # gitignored (CHIRPS NetCDF)
│   └── processed/
│       └── correlations.parquet  # Versionado — no re-corre CHIRPS en prod
├── legacy/
│   └── app.py                    # Dashboard Streamlit original (archivado)
└── tests/
    └── test_correlations.py
```

---

## Limitaciones conocidas

1. **Pronóstico**: IRI/NOAA no exponen probabilidades como API estructurada.
   El sitio muestra links oficiales (NOAA Advisory, IRI Forecast) sin gráfico de plume.
   El parseo IRI está en [BACKLOG.md](BACKLOG.md).
2. **CHIRPS fuente única**: validación cruzada con ERA5 no está en el pipeline de producción.
   Los datos CHIRPS están marcados como "fuente única" en el UI.
3. **Causalidad**: las correlaciones son estadísticas, no implican causalidad directa.
4. **Resolución espacial**: los bounding boxes promedian sobre unidades administrativas
   heterogéneas; NOA y Patagonia pueden tener alta varianza interna.
5. **Latencia ONI**: el índice tiene un rezago de ~2 meses en publicación.

---

## Fuentes y citas

- **ONI / SOI**: NOAA Climate Prediction Center — `https://www.cpc.ncep.noaa.gov/`
- **Niño 3.4 SST**: NOAA ERSSTv5 — `https://www.cpc.ncep.noaa.gov/data/indices/`
- **CHIRPS v2.0**: Funk, C. et al. (2015). *The climate hazards infrared precipitation
  with stations.* Scientific Data, 2, 150066.
  DOI: [10.1038/sdata.2015.66](https://doi.org/10.1038/sdata.2015.66)
- **Pronóstico ENSO**: IRI Columbia University — `https://iri.columbia.edu/`

---

## Disclaimer

Este tracker es una **demostración técnica** desarrollada como parte del
portfolio de FRIS (FloodRisk Intelligence System). **No constituye
asesoría profesional de ningún tipo.** Para análisis de riesgo
operacional contactar al equipo de FRIS.

Los índices se calculan automáticamente a partir de fuentes públicas —
no constituyen declaración oficial de NOAA.
