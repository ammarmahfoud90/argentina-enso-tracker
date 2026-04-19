# Argentina ENSO Impact Tracker

Primer entregable de **FRIS (FloodRisk Intelligence System)**.
Dashboard público que muestra el estado actual del ENSO (El Niño / La Niña)
y su correlación histórica con precipitación en 5 regiones de Argentina.

**Demo:** *(URL Render disponible tras deploy)*

---

## Descripción

El tracker combina tres fuentes de datos en tiempo real y un análisis
histórico pre-computado:

| Componente | Fuente | Actualización |
|---|---|---|
| ONI (Oceanic Niño Index) | NOAA CPC | Mensual |
| Niño 3.4 SST anomalía | NOAA ERSSTv5 | Mensual |
| SOI (Índice Oscilación Sur) | NOAA CPC | Mensual |
| Pronóstico ENSO 6m | IRI Columbia / NOAA CPC | Mensual |
| Precipitación histórica | CHIRPS v2.0 (CHG/UCSB) | Anual |

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
5. **Validación cruzada**: ERA5 (Copernicus CDS) disponible para
   verificación de la serie CHIRPS.  El MVP corre sólo con CHIRPS;
   la validación ERA5 es un paso de QA externo.

---

## Fuentes de datos y citas

- **ONI**: NOAA Climate Prediction Center.
  `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`

- **Niño 3.4 SST**: NOAA ERSSTv5.
  `https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii`

- **SOI**: NOAA Climate Prediction Center.
  `https://www.cpc.ncep.noaa.gov/data/indices/soi`

- **CHIRPS v2.0**: Funk, C. et al. (2015). *The climate hazards infrared
  precipitation with stations — a new environmental record for monitoring
  extremes.* Scientific Data, 2, 150066.
  DOI: [10.1038/sdata.2015.66](https://doi.org/10.1038/sdata.2015.66)
  Descarga: `https://data.chc.ucsb.edu/products/CHIRPS-2.0/`

- **ERA5** (validación): Hersbach, H. et al. (2020). *The ERA5 global
  reanalysis.* Quarterly Journal of the Royal Meteorological Society,
  146(730), 1999–2049.
  DOI: [10.1002/qj.3803](https://doi.org/10.1002/qj.3803)

- **Pronóstico ENSO**: IRI / NOAA CPC.
  `https://iri.columbia.edu/our-expertise/climate/enso/`

---

## Limitaciones conocidas

1. **Pronóstico**: IRI no expone probabilidades como API estructurada.
   El dashboard muestra el link al plume oficial si el JSON no es
   parseeable.
2. **CHIRPS fuente única**: La validación cruzada con ERA5 no está
   incluida en el pipeline de producción (requiere registro en
   Copernicus CDS). Los datos CHIRPS están marcados como "fuente única"
   en el UI.
3. **Causalidad**: Las correlaciones reportadas son estadísticas, no
   implican causalidad directa.
4. **Latencia ONI**: El índice tiene un rezago de ~2 meses en
   publicación.
5. **Resolución espacial**: Los bounding boxes promedian sobre
   unidades administrativas heterogéneas; regiones con gradientes
   fuertes (NOA, Patagonia) pueden tener alta varianza interna.

---

## Setup local

### Requisitos
- Python 3.11+
- `pip install -r requirements.txt`

### Configuración
```bash
cp .env.example .env
# Editar .env con valores reales
```

### Generar cache de correlaciones (una sola vez)
```bash
python -m src.compute_correlations
```
Esto descarga ~45 años × ~130 MB/año de CHIRPS (primera vez).
Los archivos NetCDF van a `data/raw/chirps/` (gitignored).
El resultado se guarda en `data/processed/correlations.parquet` (~50 KB).

### Ejecutar dashboard
```bash
streamlit run app.py
```

### Tests
```bash
# Unit tests (sin red)
pytest -m "not integration"

# Con tests de red
pytest
```

---

## Deploy en Render

1. Fork / push este repo a GitHub.
2. En Render: *New → Web Service → conectar repo*.
3. Variables de entorno en Render:
   - `CONTACT_EMAIL`
   - `GITHUB_REPO_URL`
4. El `correlations.parquet` **debe estar commiteado** en
   `data/processed/` para que el deploy funcione sin regenerar.
5. Render free tier duerme tras 15 min de inactividad; el primer
   request puede tardar ~30s.

---

## Estructura del repo

```
argentina-enso-tracker/
├── app.py                    # Streamlit entry point
├── render.yaml               # Render deploy config
├── requirements.txt
├── pyproject.toml            # ruff + black + pytest config
├── .env.example
├── data/
│   ├── raw/                  # gitignored (CHIRPS NetCDF)
│   └── processed/
│       └── correlations.parquet  # versionado
├── src/
│   ├── config.py             # regiones, URLs, umbrales
│   ├── fetch_enso.py         # ONI, Niño 3.4, SOI
│   ├── fetch_forecast.py     # pronóstico IRI/NOAA
│   ├── fetch_chirps.py       # descarga y procesamiento CHIRPS
│   ├── compute_correlations.py  # script one-shot
│   └── utils.py              # HTTP retry, logging
└── tests/
    ├── test_fetch_enso.py
    └── test_correlations.py
```

---

## Disclaimer

Este tracker es una **demostración técnica** desarrollada como parte del
portfolio de FRIS (FloodRisk Intelligence System). **No constituye
asesoría profesional de ningún tipo.** Para análisis de riesgo
operacional contactar al equipo de FRIS.

Los datos mostrados provienen de fuentes públicas y se reproducen con
fines informativos. FRIS no garantiza la exactitud, completitud o
actualidad de los datos de terceros.
