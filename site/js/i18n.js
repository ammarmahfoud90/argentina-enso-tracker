/**
 * i18n.js — Internationalization for the Argentina ENSO Impact Tracker.
 *
 * Supports ES (Spanish, default) and EN (English).
 * On language toggle, saves preference to localStorage and reloads
 * so all dynamic JS text re-renders in the new language.
 */

window.I18N = {
  _lang: localStorage.getItem('enso-lang') || 'es',

  MONTHS_SHORT: {
    es: ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'],
    en: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
  },
  MONTHS_LONG: {
    es: ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'],
    en: ['January','February','March','April','May','June','July','August','September','October','November','December'],
  },

  month(idx) { return this.MONTHS_SHORT[this._lang][idx]; },
  monthLong(idx) { return this.MONTHS_LONG[this._lang][idx]; },
  getLang() { return this._lang; },

  translations: {
    legacy_oni_label: {"es": "clasificación por ONI histórico", "en": "historical ONI classification"},
    roni_reading: {"es": "RONI NOAA: {value} °C · {season} {year}", "en": "NOAA RONI: {value} °C · {season} {year}"},
    advisory_reading: {"es": "Aviso oficial: {status} · emitido {date}.", "en": "Official advisory: {status} · issued {date}."},
    roni_unavailable: {"es": "RONI: fuente no disponible en esta actualización.", "en": "RONI: source unavailable in this update."},
    advisory_unavailable: {"es": "Aviso oficial NOAA no disponible; el ONI no lo reemplaza.", "en": "Official NOAA advisory unavailable; ONI does not replace it."},
    advisory_stale: {"es": "El aviso tiene más de 45 días: consultá la fuente oficial.", "en": "Advisory older than 45 days: check the official source."},
    roni_note: {"es": "NOAA usa RONI para el monitoreo desde febrero de 2026. Los valores recientes pueden revisarse. Las asociaciones de lluvia de este tracker conservan el ONI histórico y no se recalibraron con RONI.", "en": "NOAA uses RONI for monitoring since February 2026. Recent values may be revised. Rainfall associations in this tracker retain historical ONI and have not been recalibrated with RONI."},
    observations_asof: {"es": "Lluvia y SPI disponibles: {start} a {end}. Son observaciones históricas, no un diagnóstico de lluvia o sequía de hoy. Patagonia: solo 37–50°S. La actualización diaria del sitio no implica nuevos datos de lluvia.", "en": "Rainfall and SPI available: {start} to {end}. These are historical observations, not a rainfall or drought diagnosis for today. Patagonia: only 37–50°S. Daily site updates do not imply new rainfall observations."},
    observations_unavailable: {"es": "No se pudo verificar el período de las observaciones de lluvia.", "en": "The rainfall observation period could not be verified."},
    spi_asof: {"es": "Último mes observado: {date}. El SPI describe los tres meses que terminan allí. Si el archivo está atrasado, no informa la sequía actual.", "en": "Last observed month: {date}. SPI describes the three months ending then. If the file is delayed, it does not describe current drought."},
    corr_legend_sig: {"es": "q < 0.05 (FDR)", "en": "q < 0.05 (FDR)"},
    corr_legend_ns: {"es": "q ≥ 0.05", "en": "q ≥ 0.05"},
    heatmap_legend: {"es": "Asteriscos según q ajustado por comparaciones múltiples.", "en": "Stars use q adjusted for multiple comparisons."},
    /* ── Navigation ── */
    skip_link:        { es: 'Saltar al contenido principal', en: 'Skip to main content' },
    nav_aria:         { es: 'Navegaci\u00f3n por secci\u00f3n', en: 'Section navigation' },
    nav_status:       { es: '\u00bfQu\u00e9 pasa ahora?', en: "What's happening now?" },
    nav_oni:          { es: '\u00bfC\u00f3mo evolucion\u00f3?', en: 'How did it evolve?' },
    nav_soi: {"es": "Indicador atmosférico (SOI)", "en": "Atmospheric indicator (SOI)"},
    nav_sam:          { es: 'SAM', en: 'SAM' },
    nav_ocean:        { es: '\u00bfQu\u00e9 pasa en el oc\u00e9ano?', en: "What's under the surface?" },
    nav_heat:         { es: '\u00bfD\u00f3nde est\u00e1 el calor?', en: 'Where is the heat?' },
    nav_forecast:     { es: '\u00bfQu\u00e9 se espera?', en: "What's expected?" },
    nav_compare:      { es: '\u00bfSe parece a otro episodio?', en: 'Similar to a past episode?' },
    nav_timeline:     { es: 'L\u00ednea de tiempo', en: 'Timeline' },
    nav_rain:         { es: '\u00bfC\u00f3mo afecta la lluvia?', en: 'How does it affect rainfall?' },
    nav_temp:         { es: '\u00bfY la temperatura?', en: 'And temperature?' },
    nav_intensity:    { es: '\u00bfImporta la intensidad?', en: 'Does intensity matter?' },
    nav_drought: {"es": "Sequía histórica (SPI)", "en": "Historical drought (SPI)"},
    nav_region:       { es: '\u00bfQu\u00e9 significa para mi regi\u00f3n?', en: 'What does it mean for my region?' },
    nav_parana: {"es": "Monitoreo del Paraná", "en": "Paraná monitoring"},
    nav_sources:      { es: 'Fuentes y m\u00e9todo', en: 'Sources & methodology' },

    /* ── Loading ── */
    loading_text:     { es: 'Conectando con NOAA CPC...', en: 'Connecting to NOAA CPC...' },

    /* ── Masthead ── */
    masthead_kicker:  { es: 'Bolet\u00edn clim\u00e1tico \u00b7 NOAA CPC \u00b7 CHIRPS v2.0', en: 'Climate bulletin \u00b7 NOAA CPC \u00b7 CHIRPS v2.0' },
    updated_label: {"es": "Sitio generado", "en": "Site generated"},
    freshness_title:  { es: 'Estado de los datos', en: 'Data status' },
    masthead_desc:    { es: 'Estado <span class="glossary" data-i18n-tip="tip_enso" data-tip="" style="color:inherit;">ENSO</span> y su relaci\u00f3n hist\u00f3rica con<br>la lluvia en 5 regiones argentinas', en: '<span class="glossary" data-i18n-tip="tip_enso" data-tip="" style="color:inherit;">ENSO</span> status and its historical relationship with<br>rainfall in 5 Argentine regions' },
    region_selector:  { es: 'Qu\u00e9 significa para mi regi\u00f3n', en: 'What this means for my region' },

    /* ── Gauge ── */
    gauge_unit:       { es: '\u00b0C ONI', en: '\u00b0C ONI' },
    gauge_season:     { es: 'Temporada', en: 'Season' },

    /* ── Gauge segments ── */
    gauge_nina_strong:   { es: 'Ni\u00f1a fuerte', en: 'Strong Ni\u00f1a' },
    gauge_la_nina:       { es: 'La Ni\u00f1a', en: 'La Ni\u00f1a' },
    gauge_neutral:       { es: 'Neutral', en: 'Neutral' },
    gauge_nino_weak:     { es: 'Ni\u00f1o d\u00e9bil', en: 'Weak Ni\u00f1o' },
    gauge_nino_moderate: { es: 'Ni\u00f1o moderado', en: 'Moderate Ni\u00f1o' },
    gauge_nino_strong:   { es: 'Ni\u00f1o fuerte', en: 'Strong Ni\u00f1o' },
    gauge_nino_vstrong:  { es: 'Ni\u00f1o muy fuerte', en: 'Very strong Ni\u00f1o' },

    /* ── Badge ── */
    badge_no_signal:  { es: 'Sin se\u00f1al', en: 'No signal' },
    badge_more_rain:  { es: 'M\u00e1s lluvia', en: 'More rainfall' },
    badge_less_rain:  { es: 'Menos lluvia', en: 'Less rainfall' },

    /* ── Map tooltip ── */
    significant:      { es: 'significativa', en: 'significant' },
    not_significant:  { es: 'no significativa', en: 'not significant' },
    historical_signal:{ es: 'Se\u00f1al hist\u00f3rica (1981\u20132025)', en: 'Historical signal (1981\u20132025)' },

    /* ── Map legend ── */
    legend_more_rain: { es: 'M\u00e1s lluvia (se\u00f1al hist\u00f3rica)', en: 'More rainfall (historical signal)' },
    legend_less_rain: { es: 'Menos lluvia (se\u00f1al hist\u00f3rica)', en: 'Less rainfall (historical signal)' },
    legend_no_signal: {"es": "Sin señal tras el ajuste q", "en": "No signal after q adjustment"},
    /* ── ONI Section ── */
    oni_title:        { es: '\u00bfC\u00f3mo evolucion\u00f3 el ENSO?', en: 'How did ENSO evolve?' },
    oni_desc: {"es": "ONI: media trimestral de anomalías del Niño 3.4, conservada aquí como referencia histórica. NOAA usa RONI para el monitoreo operativo desde febrero de 2026; el aviso oficial y RONI se muestran en el encabezado.", "en": "ONI: three-month mean Niño 3.4 anomalies, retained here as a historical reference. NOAA uses RONI for operational monitoring since February 2026; the official advisory and RONI appear at the top."},
    oni_range_1970:   { es: '1970\u2013hoy', en: '1970\u2013today' },
    oni_range_2000:   { es: '2000\u2013hoy', en: '2000\u2013today' },
    oni_range_2010:   { es: '2010\u2013hoy', en: '2010\u2013today' },
    oni_inset_label:  { es: '\u00daltimos 24 meses', en: 'Last 24 months' },
    oni_aria:         { es: 'Serie hist\u00f3rica del \u00cdndice ONI (Oceanic Ni\u00f1o Index) desde el a\u00f1o seleccionado hasta la fecha m\u00e1s reciente disponible', en: 'Historical ONI (Oceanic Ni\u00f1o Index) time series from the selected year to the most recent available date' },
    oni_inset_aria:   { es: 'Detalle de los \u00faltimos 24 meses del \u00cdndice ONI', en: 'Detail of the last 24 months of the ONI Index' },

    /* ── SOI Section ── */
    soi_title: {"es": "El componente atmosférico del ENSO", "en": "The atmospheric component of ENSO"},
    soi_desc: {"es": "El SOI resume diferencias de presión entre Tahití y Darwin. Valores negativos sostenidos suelen acompañar El Niño; positivos, La Niña. Es un indicador complementario, no una alerta temprana calibrada por este tracker.", "en": "SOI summarizes pressure differences between Tahiti and Darwin. Sustained negative values often accompany El Niño; positive values, La Niña. It is a complementary indicator, not an early warning calibrated by this tracker."},
    soi_current: {"es": "Último SOI observado", "en": "Last observed SOI"},
    soi_aria:         { es: 'Serie temporal del SOI con media m\u00f3vil de 3 meses', en: 'SOI time series with 3-month moving average' },
    soi_monthly:      { es: 'SOI mensual', en: 'Monthly SOI' },
    soi_ma3:          { es: 'Media móvil 3m', en: '3-month moving avg' },

    /* ── SAM Section ── */
    sam_title:        { es: '\u00bfQu\u00e9 dice el Modo Anular del Sur?', en: 'What does the Southern Annular Mode say?' },
    sam_desc: {"es": "El SAM (Modo Anular del Sur) resume cambios de circulación en latitudes medias y altas del hemisferio sur. Complementa otros indicadores climáticos. Fuente: NOAA CPC AAO.", "en": "SAM (Southern Annular Mode) summarizes circulation changes in the middle and high latitudes of the Southern Hemisphere. It complements other climate indicators. Source: NOAA CPC AAO."},
    sam_current: {"es": "Último SAM observado", "en": "Last observed SAM"},
    sam_aria:         { es: 'Serie temporal del SAM/AAO', en: 'SAM/AAO time series' },
    sam_note: {"es": "El SAM modifica la posición y la intensidad de los vientos del oeste. Su asociación con la lluvia depende de la estación y del lugar; un valor positivo o negativo no determina por sí solo la lluvia en toda Patagonia. Puede interactuar con ENSO.", "en": "SAM affects the position and strength of the westerlies. Its rainfall association depends on season and location; its sign alone does not determine rainfall throughout Patagonia. It can interact with ENSO."},
    sam_stale:        { es: 'Dato desactualizado: ultimo valor de {month} {year} ({days} dias). La fuente NOAA CPC puede estar temporalmente sin actualizar.', en: 'Stale data: last value from {month} {year} ({days} days ago). The NOAA CPC source may be temporarily not updated.' },

    /* ── Subsurface Section ── */
    subsurface_title: { es: '\u00bfQu\u00e9 pasa debajo de la superficie?', en: "What's happening below the surface?" },
    subsurface_desc: {"es": "Perfil de temperatura absoluta del Pacífico ecuatorial hasta 300 m, medido por boyas TAO/TRITON. El contenido de calor subsuperficial aporta contexto físico, pero este perfil no está calibrado como pronóstico ni muestra anomalías respecto de una climatología.", "en": "Absolute equatorial Pacific temperature profile down to 300 m, measured by TAO/TRITON buoys. Subsurface heat provides physical context, but this profile is not calibrated as a forecast and does not show climatological anomalies."},
    subsurface_aria:  { es: 'Heatmap de temperatura subsuperficial del Pac\u00edfico ecuatorial, profundidad vs longitud', en: 'Subsurface temperature heatmap of the equatorial Pacific, depth vs longitude' },

    /* ── SST Map Section ── */
    sst_title:        { es: '\u00bfD\u00f3nde se concentra el calor?', en: 'Where is the heat concentrated?' },
    sst_desc: {"es": "Anomalía diaria de temperatura superficial del Pacífico ecuatorial respecto de la climatología OI.v2 1971–2000. Son instantáneas cada 30 días, no promedios mensuales. Fuente: NOAA OISST v2.1, variable anom de ERDDAP.", "en": "Daily equatorial Pacific SST anomaly relative to the OI.v2 1971–2000 climatology. These are snapshots every 30 days, not monthly averages. Source: NOAA OISST v2.1, ERDDAP anom variable."},
    sst_play:         { es: '\u25b6 Reproducir', en: '\u25b6 Play' },
    sst_pause:        { es: '\u23f8 Pausar', en: '\u23f8 Pause' },
    sst_play_aria:    { es: 'Reproducir animaci\u00f3n del mapa', en: 'Play map animation' },
    sst_aria:         { es: 'Mapa interactivo de anomal\u00eda de temperatura superficial del mar en el Pac\u00edfico ecuatorial', en: 'Interactive sea surface temperature anomaly map of the equatorial Pacific' },
    sst_fallback:     { es: 'No se pudo cargar el mapa satelital de TSM. Mostrando datos de ONI en su lugar.', en: 'Could not load the SST satellite map. Showing ONI data instead.' },
    sst_fallback2: {"es": "Consultá el aviso oficial de NOAA en el encabezado para el diagnóstico operativo.", "en": "See the official NOAA advisory at the top for the operational diagnosis."},
    /* ── Forecast Section ── */
    forecast_title:   { es: '\u00bfQu\u00e9 se espera para los pr\u00f3ximos meses?', en: "What's expected in the coming months?" },
    forecast_desc:    { es: 'Cada mes, m\u00faltiples modelos clim\u00e1ticos proyectan hacia d\u00f3nde se mover\u00e1 el ENSO. El gr\u00e1fico muestra las chances asignadas a cada fase (El Ni\u00f1o, Neutral, La Ni\u00f1a) por trimestre. Fuente: IRI/CCSR, Columbia University.', en: 'Each month, multiple climate models project where ENSO will move. The chart shows the probabilities assigned to each phase (El Ni\u00f1o, Neutral, La Ni\u00f1a) per quarter. Source: IRI/CCSR, Columbia University.' },
    forecast_probs:   { es: 'Probabilidades por fase', en: 'Probabilities by phase' },
    forecast_plume:   { es: 'Pluma de modelos', en: 'Model plume' },
    forecast_probs_aria:{ es: 'Probabilidades ENSO por trimestre: El Ni\u00f1o, Neutral, La Ni\u00f1a', en: 'ENSO probabilities by quarter: El Ni\u00f1o, Neutral, La Ni\u00f1a' },
    forecast_plume_fallback:{ es: 'Pluma de modelos no disponible.', en: 'Model plume not available.' },
    forecast_plume_link:{ es: 'Consultar en IRI', en: 'View at IRI' },
    forecast_no_data: { es: 'Pron\u00f3stico IRI no disponible para este mes.', en: 'IRI forecast not available for this month.' },
    forecast_source:  { es: 'Fuente: IRI/CCSR, Columbia University.', en: 'Source: IRI/CCSR, Columbia University.' },
    forecast_stale:   { es: 'Pronostico IRI de {month} {year}. La actualizacion automatica fallo el {date}.', en: 'IRI forecast from {month} {year}. Automatic update failed on {date}.' },
    forecast_not_available: { es: 'Pron\u00f3stico no disponible.', en: 'Forecast not available.' },

    /* ── Forecast links ── */
    forecast_noaa_name:  { es: 'NOAA ENSO Advisory', en: 'NOAA ENSO Advisory' },
    forecast_noaa_tag:   { es: 'Mensual', en: 'Monthly' },
    forecast_noaa_desc:  { es: 'Diagn\u00f3stico y pron\u00f3stico oficial del NOAA Climate Prediction Center.', en: 'Official diagnosis and forecast from the NOAA Climate Prediction Center.' },
    forecast_cta:        { es: 'Consultar', en: 'View' },
    forecast_iri_name:   { es: 'IRI ENSO Forecast', en: 'IRI ENSO Forecast' },
    forecast_iri_tag:    { es: 'Probabil\u00edstico', en: 'Probabilistic' },
    forecast_iri_desc:   { es: 'Pron\u00f3stico completo del IRI: probabilidades, pluma de modelos, an\u00e1lisis.', en: 'Complete IRI forecast: probabilities, model plume, analysis.' },
    forecast_oni_name:   { es: 'NOAA ONI: serie hist\u00f3rica', en: 'NOAA ONI: historical series' },
    forecast_oni_tag:    { es: 'Hist\u00f3rico', en: 'Historical' },
    forecast_oni_desc:   { es: 'Serie hist\u00f3rica del Oceanic Ni\u00f1o Index y valores proyectados.', en: 'Historical series of the Oceanic Ni\u00f1o Index and projected values.' },
    forecast_smn_name:   { es: 'SMN Argentina: Perspectiva Clim\u00e1tica', en: 'SMN Argentina: Climate Outlook' },
    forecast_smn_tag:    { es: 'Estacional', en: 'Seasonal' },
    forecast_smn_desc:   { es: 'Pron\u00f3stico estacional oficial del Servicio Meteorol\u00f3gico Nacional de Argentina.', en: 'Official seasonal forecast from the Argentine National Weather Service.' },

    /* ── Comparison Section ── */
    compare_title:    { es: '\u00bfSe parece a alg\u00fan episodio anterior?', en: 'Does it resemble a past episode?' },
    compare_meta:     { es: 'Episodio actual vs hist\u00f3ricos', en: 'Current episode vs historical' },
    compare_desc: {"es": "Trayectorias históricas de ONI en ventanas definidas alrededor de eventos destacados. Permiten comparar valores, no predecir que se repetirá un patrón. Las fechas son los meses centrales de las medias trimestrales.", "en": "Historical ONI trajectories in defined windows around notable events. They allow value comparisons, not predictions of repeated patterns. Dates are the central months of three-month means."},
    compare_nino:     { es: 'El Ni\u00f1o hist\u00f3ricos', en: 'Historical El Ni\u00f1o' },
    compare_nina:     { es: 'La Ni\u00f1a hist\u00f3ricos', en: 'Historical La Ni\u00f1a' },
    compare_aria:     { es: 'Comparaci\u00f3n del episodio ENSO actual con eventos hist\u00f3ricos', en: 'Comparison of the current ENSO episode with historical events' },

    /* ── Timeline Section ── */
    timeline_title:   { es: '\u00bfCu\u00e1ndo ocurrieron El Ni\u00f1o y La Ni\u00f1a?', en: 'When did El Ni\u00f1o and La Ni\u00f1a occur?' },
    timeline_desc: {"es": "Cada barra es un episodio histórico detectado con ONI: cinco estaciones solapadas sobre ±0.5 °C. No reemplaza el aviso operativo de NOAA basado en RONI y otros indicadores.", "en": "Each bar is a historical episode detected with ONI: five overlapping seasons beyond ±0.5 °C. It does not replace NOAA operational advisories based on RONI and other indicators."},
    timeline_today:   { es: 'hoy', en: 'today' },
    notable_title:    { es: 'Eventos ENSO notables en la serie histórica', en: 'Notable ENSO events in the historical record' },

    /* ── Correlation Section ── */
    corr_title:       { es: '\u00bfC\u00f3mo se relaciona el ENSO con la lluvia?', en: 'How is ENSO related to rainfall?' },
    corr_desc: {"es": "Asociaciones históricas entre ONI y lluvia en cinco cajas rectangulares CHIRPS v2.0. La comparación anual usa anomalías por mes calendario; la estacional, acumulados de tres meses completos. La altura de una barra indica asociación, no causalidad ni capacidad de pronóstico.", "en": "Historical associations between ONI and rainfall in five CHIRPS v2.0 rectangular boxes. Annual comparisons use calendar-month anomalies; seasonal comparisons use complete three-month totals. Bar height indicates association, not causality or forecast skill."},
    corr_season_label:{ es: 'Estaci\u00f3n:', en: 'Season:' },
    corr_bar_aria:    { es: 'Gr\u00e1fico de barras de correlaci\u00f3n ENSO-precipitaci\u00f3n por regi\u00f3n', en: 'ENSO-precipitation correlation bar chart by region' },
    corr_detail_toggle:{ es: 'Tabla detallada por lag \u25b8', en: 'Detailed table by lag \u25b8' },
    corr_legend_label:{ es: 'correlaci\u00f3n', en: 'correlation' },
    corr_note: {"es": "Los colores y asteriscos requieren q < 0.05 después de corregir todas las comparaciones de la familia. Un resultado sin asterisco no demuestra ausencia de un vínculo físico. Las cajas no son promedios por provincia ni por cuenca; Patagonia solo cubre 37–50°S.", "en": "Colors and stars require q < 0.05 after adjusting all comparisons in the family. An unstarred result does not prove absence of a physical link. Boxes are not province or watershed means; Patagonia only covers 37–50°S."},
    corr_stat_toggle: { es: 'Detalle estad\u00edstico \u25b8', en: 'Statistical detail \u25b8' },
    corr_stat_detail: {"es": "Pearson y Spearman con p aproximado por autocorrelación y q ajustado por Benjamini–Yekutieli. Familia: regiones × lags 0–3 × anual y cuatro estaciones, separada por variable y coeficiente. Asteriscos: * q<0.05, ** q<0.01, *** q<0.001. Resultados exploratorios sin validación fuera de muestra.", "en": "Pearson and Spearman with approximate autocorrelation-adjusted p and Benjamini–Yekutieli adjusted q. Family: regions × lags 0–3 × annual and four seasons, separately by variable and coefficient. Stars: * q<0.05, ** q<0.01, *** q<0.001. Exploratory results without out-of-sample validation."},
    all_months:       { es: 'Todos los meses (1981\u20132025)', en: 'All months (1981\u20132025)' },
    all_months_temp:  { es: 'Todos los meses \u00b7 CPC Global Temperature', en: 'All months \u00b7 CPC Global Temperature' },

    /* ── Season selectors ── */
    season_annual:    { es: 'Anual', en: 'Annual' },
    season_spring:    { es: 'Primavera (SON)', en: 'Spring (SON)' },
    season_summer:    { es: 'Verano (DEF)', en: 'Summer (DJF)' },
    season_autumn:    { es: 'Oto\u00f1o (MAM)', en: 'Autumn (MAM)' },
    season_winter:    { es: 'Invierno (JJA)', en: 'Winter (JJA)' },
    season_labels:    { es: { SON: 'Sep\u2013Nov (primavera)', DEF: 'Dic\u2013Feb (verano)', MAM: 'Mar\u2013May (oto\u00f1o)', JJA: 'Jun\u2013Ago (invierno)' }, en: { SON: 'Sep\u2013Nov (spring)', DEF: 'Dec\u2013Feb (summer)', MAM: 'Mar\u2013May (autumn)', JJA: 'Jun\u2013Aug (winter)' } },

    /* ── Temperature Section ── */
    temp_title:       { es: '\u00bfEl ENSO afecta la temperatura?', en: 'Does ENSO affect temperature?' },
    temp_desc: {"es": "Asociaciones históricas entre ONI y anomalías de temperatura media (CPC Global Temperature). Se usa el mismo calendario y ajuste estadístico que para lluvia. Sin eliminación de tendencias: son asociaciones exploratorias, no atribución causal ni pronóstico.", "en": "Historical associations between ONI and mean temperature anomalies (CPC Global Temperature). The calendar and statistical adjustment match the rainfall analysis. Trends have not been removed: these are exploratory associations, not causal attribution or forecasts."},
    temp_bar_aria:    { es: 'Gr\u00e1fico de barras de correlaci\u00f3n ENSO-temperatura por regi\u00f3n', en: 'ENSO-temperature correlation bar chart by region' },

    /* ── Composite Section ── */
    composite_title:  { es: '\u00bfImporta la intensidad del ENSO?', en: 'Does ENSO intensity matter?' },
    composite_desc: {"es": "Promedios descriptivos de lluvia estacional según |ONI|: débil [0.5,1), moderado [1,1.5), fuerte [1.5,2), muy fuerte ≥2. N cuenta estaciones completas; con N<10 la muestra es pequeña. Estas medias no son pronósticos ni tienen intervalos predictivos.", "en": "Descriptive seasonal rainfall means by |ONI|: weak [0.5,1), moderate [1,1.5), strong [1.5,2), very strong ≥2. N counts complete seasons; N<10 is a small sample. These means are not forecasts and have no prediction intervals."},
    composite_aria:   { es: 'Gr\u00e1fico de anomal\u00eda de precipitaci\u00f3n por intensidad ENSO', en: 'Precipitation anomaly chart by ENSO intensity' },
    anomaly_pct:      { es: 'Anomal\u00eda (%)', en: 'Anomaly (%)' },
    intensity_weak:   { es: 'D\u00e9bil', en: 'Weak' },
    intensity_moderate:{ es: 'Moderado', en: 'Moderate' },
    intensity_strong: { es: 'Fuerte', en: 'Strong' },
    intensity_vstrong:{ es: 'Muy fuerte', en: 'Very strong' },

    /* ── SPI Section ── */
    spi_title: {"es": "Sequía y humedad en el período observado", "en": "Drought and wetness in the observed period"},
    spi_desc: {"es": "El SPI-3 estandariza lluvia acumulada de tres meses mediante una distribución gamma por mes calendario, ajustada al período histórico disponible. SPI ≤−1 indica sequía meteorológica; ≥+1, humedad anormal. No mide sequía hidrológica o agrícola por sí solo.", "en": "SPI-3 standardizes three-month rainfall totals using a gamma distribution for each calendar month, fitted to the available historical period. SPI ≤−1 indicates meteorological drought; ≥+1, unusual wetness. It does not measure hydrological or agricultural drought on its own."},
    spi_aria:         { es: 'Serie temporal del SPI-3 por regi\u00f3n', en: 'SPI-3 time series by region' },
    spi_seq:          { es: 'Seq.', en: 'Dry' },
    spi_hum:          { es: 'H\u00fam.', en: 'Wet' },

    /* ── Risk Section ── */
    risk_title:       { es: '\u00bfQu\u00e9 significa para cada regi\u00f3n?', en: 'What does it mean for each region?' },
    risk_desc:        { es: 'Los colores reflejan la direcci\u00f3n de lluvia que se observ\u00f3 hist\u00f3ricamente durante fases similares a la actual (1981\u20132025). Son promedios regionales basados en datos de <span class="glossary" data-i18n-tip="tip_chirps" data-tip="">CHIRPS</span>. No reemplazan un pron\u00f3stico ni aplican a escala provincial sin validaci\u00f3n local.', en: 'Colors reflect the rainfall direction historically observed during phases similar to the current one (1981\u20132025). These are regional averages based on <span class="glossary" data-i18n-tip="tip_chirps" data-tip="">CHIRPS</span> data. They do not replace a forecast nor apply at the provincial scale without local validation.' },
    risk_map_aria:    { es: 'Mapa de se\u00f1al ENSO por regi\u00f3n en Argentina', en: 'ENSO signal map by region in Argentina' },
    risk_accordion:   { es: 'Detalle hist\u00f3rico por regi\u00f3n', en: 'Historical detail by region' },
    map_malvinas:     { es: 'Islas Malvinas (Arg.)', en: 'Falkland Islands (Arg.)' },
    label_current:    { es: 'Actual', en: 'Current' },
    data_fresh: {"es": "El sitio se generó recientemente; cada serie tiene su propia fecha de observación.", "en": "The site was generated recently; each series has its own observation date."},
    data_aging: {"es": "El sitio se generó hace {days} días; revisá las fechas de cada indicador.", "en": "The site was generated {days} days ago; check each indicator date."},
    data_stale: {"es": "El sitio se generó hace {days} días; sus datos pueden estar atrasados.", "en": "The site was generated {days} days ago; its observations may be delayed."},
    stale_banner:     { es: 'ATENCIÓN: Datos desactualizados (última actualización hace {days} días). Verifique el estado del pipeline.', en: 'WARNING: Outdated data (last update {days} days ago). Check the pipeline status.' },
    footer_generated: { es: 'Datos generados el {date}.', en: 'Data generated on {date}.' },
    footer_generated_stale: { es: 'Datos generados el {date} (hace {days} dias. Revise el pipeline).', en: 'Data generated on {date} ({days} days ago. Check the pipeline).' },

    /* ── Parana Section ── */
    parana_title: {"es": "Monitoreo hidrológico del Paraná", "en": "Paraná hydrological monitoring"},
    parana_desc: {"es": "Para niveles fluviales y alertas consultá el INA. El ENSO es uno de varios factores de la cuenca y no determina por sí solo una crecida o bajante. La tabla manual de niveles se retiró porque no tenía fuentes verificables para cada observación; este tracker no ofrece un pronóstico de niveles.", "en": "Consult INA for river levels and alerts. ENSO is one of several basin factors and does not determine floods or low flows on its own. The manual level table was removed because individual observations lacked verifiable sources; this tracker does not forecast river levels."},
    parana_aria:      { es: 'Niveles del Paran\u00e1 durante eventos ENSO', en: 'Paran\u00e1 levels during ENSO events' },
    parana_normal:    { es: 'Normal', en: 'Normal' },
    parana_alert:     { es: 'Alerta', en: 'Alert' },
    parana_level:     { es: 'Nivel (m)', en: 'Level (m)' },
    parana_ina_name:  { es: 'INA Alerta Hidrol\u00f3gico', en: 'INA Hydrological Alert' },
    parana_ina_tag:   { es: 'Tiempo real', en: 'Real-time' },
    parana_ina_desc:  { es: 'Niveles actuales del Paran\u00e1 y alerta hidrol\u00f3gica del INA.', en: 'Current Paran\u00e1 levels and INA hydrological alert.' },
    parana_bdhi_name: { es: 'BDHI: Base de Datos Hidrol\u00f3gica', en: 'BDHI: Hydrological Database' },
    parana_bdhi_tag:  { es: 'Hist\u00f3rico', en: 'Historical' },
    parana_bdhi_desc: { es: 'Base de datos hidrol\u00f3gica integrada del INA \u2014 series hist\u00f3ricas de caudal y nivel.', en: 'INA integrated hydrological database \u2014 historical flow and level series.' },
    forecast_ina_name:  { es: 'INA Alerta Hidrol\u00f3gico', en: 'INA Hydrological Alert' },
    forecast_ina_tag:   { es: 'Tiempo real', en: 'Real-time' },
    forecast_ina_desc:  { es: 'Niveles actuales del Paran\u00e1 y alerta hidrol\u00f3gica del INA.', en: 'Current Paran\u00e1 levels and INA hydrological alert.' },
    forecast_bdhi_name: { es: 'BDHI: Base de Datos Hidrol\u00f3gica', en: 'BDHI: Hydrological Database' },
    forecast_bdhi_tag:  { es: 'Hist\u00f3rico', en: 'Historical' },
    forecast_bdhi_desc: { es: 'Base de datos hidrol\u00f3gica integrada del INA \u2014 series hist\u00f3ricas de caudal y nivel.', en: 'INA integrated hydrological database \u2014 historical flow and level series.' },
    forecast_iri_nodata:{ es: 'Pron\u00f3stico IRI no disponible para este mes. <a href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noopener">Consultar en IRI</a>', en: 'IRI forecast not available for this month. <a href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noopener">View at IRI</a>' },
    forecast_iri_credit:{ es: 'Fuente: IRI/CCSR, Columbia University. <a id="iri-forecast-link" href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noopener">Consultar en IRI</a>', en: 'Source: IRI/CCSR, Columbia University. <a id="iri-forecast-link" href="https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/" target="_blank" rel="noopener">View at IRI</a>' },

    /* ── Data Sources Section ── */
    sources_title:    { es: 'Fuentes de datos y metodolog\u00eda', en: 'Data sources and methodology' },
    th_index:         { es: '\u00cdndice', en: 'Index' },
    th_source:        { es: 'Fuente', en: 'Source' },
    th_frequency:     { es: 'Frecuencia', en: 'Frequency' },
    th_latency:       { es: 'Latencia', en: 'Latency' },
    freq_monthly:     { es: 'Mensual', en: 'Monthly' },
    freq_weekly:      { es: 'Semanal, promediada a mensual', en: 'Weekly, averaged to monthly' },
    latency_2m:       { es: '~2 meses', en: '~2 months' },
    latency_1w:       { es: '~1 semana', en: '~1 week' },
    latency_1m:       { es: '~1 mes', en: '~1 month' },
    latency_cache:    { es: 'Cache (no tiempo real)', en: 'Cache (not real-time)' },
    latency_2w:       { es: '~2 semanas', en: '~2 weeks' },
    src_precipitation:{ es: 'Precipitaci\u00f3n', en: 'Precipitation' },
    src_subsurface:   { es: 'Temperatura subsuperficial', en: 'Subsurface temperature' },
    src_forecast:     { es: 'Pron\u00f3stico ENSO', en: 'ENSO Forecast' },

    /* ── Methodology text ── */
    method_corr: {"es": "<strong>Correlaciones exploratorias.</strong> Anomalías mensuales respecto de la media de cada mes del período disponible. Para estaciones: una observación por trimestre completo (sumas de lluvia, medias de temperatura) y el ONI publicado para su mes central. Lags 0–3 meses; no equivalen a anticipación operativa porque el ONI incluye meses posteriores a su fecha central. p aproximado con n<sub>eff</sub> y q Benjamini–Yekutieli por familia de región × lag × anual/estación, separada por variable y coeficiente. Se resaltan q&lt;0.05. Sin validación fuera de muestra ni detrendado de temperatura.", "en": "<strong>Exploratory correlations.</strong> Monthly anomalies relative to each calendar month mean over the available period. Seasonal samples contain one observation per complete quarter (rainfall totals, temperature means) and published ONI for its central month. Lags 0–3 months are not operational lead times: ONI includes months after its central date. Approximate p with n<sub>eff</sub> and Benjamini–Yekutieli q per region × lag × annual/season family, separately by variable and coefficient. Highlighting uses q&lt;0.05. No out-of-sample validation or temperature detrending."},
    method_oni: {"es": "<strong>ONI y RONI.</strong> NOAA usa RONI para monitoreo desde el 1 de febrero de 2026. RONI resta la anomalía tropical al Niño 3.4 y reescala la varianza; la serie actual usa ERSSTv6 y base 1991–2020. El ONI histórico sigue disponible con bases de 30 años centradas. Las asociaciones del tracker usan ONI; su clasificación no sustituye el aviso operativo de NOAA, que también considera la atmósfera.", "en": "<strong>ONI and RONI.</strong> NOAA uses RONI for monitoring since February 1, 2026. RONI subtracts the tropical anomaly from Niño 3.4 and rescales variance; the current series uses ERSSTv6 and a 1991–2020 baseline. Historical ONI remains available with centered 30-year baselines. Tracker associations use ONI; its classification does not replace NOAA operational advisories, which also consider the atmosphere."},
    method_chirps: {"es": "<strong>Dominio y cobertura.</strong> CHIRPS v2.0 cubre 50°S–50°N. La caja de lluvia de Patagonia solo aporta datos entre 37 y 50°S: excluye Tierra del Fuego y el extremo sur de Santa Cruz. Son medias aritméticas de píxeles válidos en cajas, sin ponderación de área ni máscara nacional; incluyen terreno fuera de Argentina y dominios solapados. No equivalen a promedios administrativos. La nieve y el relieve limitan su precisión. El período disponible se muestra en el encabezado.", "en": "<strong>Domain and coverage.</strong> CHIRPS v2.0 spans 50°S–50°N. Patagonia rainfall only samples 37–50°S: Tierra del Fuego and southernmost Santa Cruz are excluded. These are arithmetic valid-pixel means in boxes, without area weighting or a national mask; foreign land and overlapping domains are included. They are not administrative means. Snow and terrain limit precision. The available period appears at the top."},
    method_neff: {"es": "<strong>Incertidumbre.</strong> n<sub>eff</sub> estima el efecto de la autocorrelación; los p son aproximados. La corrección FDR ajusta comparaciones dependientes, pero no prueba causalidad ni elimina toda incertidumbre. Las frecuencias usan un binomial aproximado, una única familia exploratoria y q corregido. Correlaciones y frecuencias proceden de los mismos datos: no constituyen validaciones independientes.", "en": "<strong>Uncertainty.</strong> n<sub>eff</sub> estimates autocorrelation effects; p values are approximate. FDR adjusts dependent comparisons but does not prove causality or eliminate uncertainty. Frequencies use an approximate binomial, one exploratory family and corrected q. Correlations and frequencies use the same data: they are not independent validation."},
    method_episodes: {"es": "<strong>Episodios históricos por ONI.</strong> Se requieren cinco estaciones solapadas consecutivas con ONI ≥+0.5 o ≤−0.5. Es la regla histórica del ONI, no una declaración operativa actual. El encabezado muestra por separado el RONI y el aviso oficial de NOAA.", "en": "<strong>Historical ONI episodes.</strong> Five consecutive overlapping seasons with ONI ≥+0.5 or ≤−0.5 are required. This is the historical ONI rule, not a current operational declaration. RONI and the official NOAA advisory are shown separately at the top."},
    method_pipeline: {"es": "Actualización diaria del sitio. Cada serie conserva su propia fecha de observación; el archivo de lluvia y SPI puede terminar antes que los índices ENSO.", "en": "Daily site updates. Each series retains its own observation date; rainfall and SPI files may end earlier than ENSO indices."},
    /* ── Footer ── */
    footer_sources:   { es: 'Fuentes: NOAA CPC \u00b7 IRI Columbia \u00b7 CHIRPS v2.0 (UCSB) \u00b7 TAO/TRITON (NOAA PMEL)', en: 'Sources: NOAA CPC \u00b7 IRI Columbia \u00b7 CHIRPS v2.0 (UCSB) \u00b7 TAO/TRITON (NOAA PMEL)' },
    footer_disclaimer:{ es: 'El ENSO explica solo una parte de la variabilidad de precipitaci\u00f3n en Argentina. El SAM (Modo Anular del Sur), la variabilidad interna atmosf\u00e9rica y factores regionales tambi\u00e9n influyen significativamente.', en: 'ENSO explains only a fraction of precipitation variability in Argentina. The SAM (Southern Annular Mode), internal atmospheric variability, and regional factors also have significant influence.' },
    footer_latency: {"es": "Cada indicador muestra su fecha. ONI y RONI son medias trimestrales fechadas en el mes central; no observaciones instantáneas. El mapa OISST usa instantáneas diarias con latencia propia. La lluvia y el SPI conservan el período del archivo histórico.", "en": "Each indicator displays its date. ONI and RONI are three-month means dated at the central month, not instantaneous observations. The OISST map uses daily snapshots with its own latency. Rainfall and SPI retain the historical file period."},
    footer_auto:      { es: '\u00cdndices autom\u00e1ticos. No constituyen declaraci\u00f3n oficial.', en: 'Automated indices. Not an official statement.' },
    footer_corr:      { es: 'Correlaciones anuales y estacionales (1981\u20132025) \u00b7 CHIRPS v2.0', en: 'Annual and seasonal correlations (1981\u20132025) \u00b7 CHIRPS v2.0' },

    /* ── CSV / Buttons ── */
    csv_download:     { es: 'Descargar series (CSV)', en: 'Download series (CSV)' },
    dark_mode_aria:   { es: 'Alternar modo oscuro', en: 'Toggle dark mode' },
    back_to_top_aria: { es: 'Volver arriba', en: 'Back to top' },

    /* ── Error messages ── */
    error_loading:    { es: 'Error cargando datos: ', en: 'Error loading data: ' },
    error_boot:       { es: 'Error: ', en: 'Error: ' },
    error_libs:       { es: 'Error: no se pudieron cargar las librer\u00edas. Recargue la p\u00e1gina.', en: 'Error: could not load libraries. Please reload the page.' },

    /* ── Executive summary (main.js) ── */
    summary_neutral_l1: {"es": "El ONI histórico más reciente está en rango neutral: {oni} °C. El aviso operativo de NOAA figura arriba.", "en": "The latest historical ONI is in the neutral range: {oni} °C. NOAA operational status appears above."},
    summary_active_l1: {"es": "El ONI histórico más reciente marca {oni} °C{intStr}. Para el diagnóstico operativo, ver RONI y aviso NOAA arriba.", "en": "The latest historical ONI is {oni} °C{intStr}. See RONI and the NOAA advisory above for operational diagnosis."},
    warmer:                { es: 'm\u00e1s c\u00e1lido', en: 'warmer' },
    cooler:                { es: 'm\u00e1s fr\u00edo', en: 'cooler' },
    summary_neutral_l2:    { es: 'Sin fase ENSO activa, la se\u00f1al hist\u00f3rica no apunta a una direcci\u00f3n de lluvia. Planificar con climatolog\u00eda estacional.', en: 'With no active ENSO phase, the historical signal does not point to a rainfall direction. Plan using seasonal climatology.' },
    summary_active_l2: {"es": "En el archivo histórico: {M} de {N} {seasonName} clasificados con {phase} por ONI superaron la mediana estacional en la caja de {region}.", "en": "In the historical file: {M} of {N} {seasonName} classified as {phase} by ONI exceeded the seasonal median in the {region} box."},
    summary_active_l2_other:{ es: ' Con {otherPhase}, {onlyStr}{ocM} de {ocN}.', en: ' With {otherPhase}, {onlyStr}{ocM} of {ocN}.' },
    summary_only:          { es: 'solo ', en: 'only ' },
    summary_active_l2_dev: {"es": " El promedio de lluvia fue {s}{dev}% respecto de la media climatológica de esos {seasonName}.", "en": " Mean rainfall was {s}{dev}% relative to the climatological mean for those {seasonName}."},
    summary_no_signal:     { es: 'La tabla de frecuencias estacionales de {region} no muestra resultados significativos para {phase} tras el ajuste (1981–2025).', en: 'The seasonal frequency table for {region} shows no significant results for {phase} after adjustment (1981–2025).' },
    summary_l3: {"es": "Asociaciones históricas exploratorias: no predicen lluvia local ni niveles de río. Consultá SMN e INA.", "en": "Exploratory historical associations: they do not predict local rainfall or river levels. Consult SMN and INA."},
    only:                  { es: 'solo ', en: 'only ' },

    /* ── Season names for summary ── */
    season_name_springs:   { es: 'primaveras', en: 'springs' },
    season_name_summers:   { es: 'veranos', en: 'summers' },
    season_name_autumns:   { es: 'oto\u00f1os', en: 'autumns' },
    season_name_winters:   { es: 'inviernos', en: 'winters' },

    /* ── Hero / Status ── */
    status_neutral: {"es": "Neutral según ONI", "en": "Neutral by ONI"},
    ongoing_since:    { es: '{phase} en curso desde {onsetMonth}.', en: '{phase} ongoing since {onsetMonth}.' },

    /* ── Trajectory notes ── */
    traj_nino_below:  { es: ' El Ni\u00f1o 3.4 mensual ({n34} \u00b0C) est\u00e1 por debajo del ONI ({oni}). La superficie se ha enfriado respecto del promedio trimestral.', en: ' Monthly Ni\u00f1o 3.4 ({n34} \u00b0C) is below the ONI ({oni}). The surface has cooled relative to the quarterly average.' },
    traj_nino_above:  { es: ' Ni\u00f1o 3.4 mensual ({n34} \u00b0C) por encima del ONI. Fortalecimiento en curso.', en: ' Monthly Ni\u00f1o 3.4 ({n34} \u00b0C) above the ONI. Strengthening in progress.' },
    traj_nino_converge:{ es: ' El ONI est\u00e1 alcanzando a la se\u00f1al de superficie (Ni\u00f1o 3.4 {n34} \u00b0C). La brecha se ha cerrado.', en: ' The ONI is catching up to the surface signal (Ni\u00f1o 3.4 {n34} \u00b0C). The gap has closed.' },
    traj_nino_decel:  { es: ' El ONI sigue positivo pero la tasa de aumento se est\u00e1 desacelerando.', en: ' The ONI remains positive but the rate of increase is decelerating.' },
    traj_nina_above:  { es: ' El Ni\u00f1o 3.4 mensual ({n34} \u00b0C) est\u00e1 por encima del ONI ({oni}). La superficie se ha calentado respecto del promedio trimestral.', en: ' Monthly Ni\u00f1o 3.4 ({n34} \u00b0C) is above the ONI ({oni}). The surface has warmed relative to the quarterly average.' },
    traj_nina_below:  { es: ' Ni\u00f1o 3.4 mensual ({n34} \u00b0C) por debajo del ONI. Fortalecimiento en curso.', en: ' Monthly Ni\u00f1o 3.4 ({n34} \u00b0C) below the ONI. Strengthening in progress.' },
    traj_nina_converge:{ es: ' El ONI est\u00e1 alcanzando a la se\u00f1al de superficie (Ni\u00f1o 3.4 {n34} \u00b0C). La brecha se ha cerrado.', en: ' The ONI is catching up to the surface signal (Ni\u00f1o 3.4 {n34} \u00b0C). The gap has closed.' },
    traj_nina_decel:  { es: ' El ONI sigue negativo pero la tasa de descenso se est\u00e1 desacelerando.', en: ' The ONI remains negative but the rate of decline is decelerating.' },

    /* ── Risk summary ── */
    risk_neutral:     { es: 'Con el ONI en fase Neutral, la se\u00f1al ENSO se debilita. Planificar con climatolog\u00eda local y pron\u00f3sticos de corto plazo.', en: 'With the ONI in Neutral phase, the ENSO signal weakens. Plan using local climatology and short-term forecasts.' },
    risk_nino: {"es": "El Niño se asocia históricamente con cambios de lluvia en partes de Sudamérica. Evaluá las señales del período y dominio mostrado; este análisis no calcula el riesgo de inundación o rendimiento agrícola.", "en": "El Niño is historically associated with rainfall changes in parts of South America. Assess signals for the displayed period and domain; this analysis does not calculate flood risk or agricultural yield."},
    risk_nina: {"es": "La Niña se asocia históricamente con cambios de lluvia en partes de Sudamérica. Evaluá las señales del período y dominio mostrado; este análisis no calcula el riesgo de sequía o rendimiento agrícola.", "en": "La Niña is historically associated with rainfall changes in parts of South America. Assess signals for the displayed period and domain; this analysis does not calculate drought risk or agricultural yield."},
    risk_pampa_detail: {"es": " Frecuencia histórica en Pampa Húmeda DEF: El Niño {enM}/{enN} sobre la mediana (q={enP}); La Niña {lnM}/{lnN} (q={lnP}). Ambos análisis usan el mismo archivo histórico.", "en": " Historical Pampa Húmeda DJF frequency: El Niño {enM}/{enN} above median (q={enP}); La Niña {lnM}/{lnN} (q={lnP}). Both analyses use the same historical file."},
    risk_no_signal: {"es": " Las señales destacadas deben superar la corrección por comparaciones múltiples. Consultá SMN e INA para decisiones operativas.", "en": " Highlighted signals must survive multiple-comparison adjustment. Consult SMN and INA for operational decisions."},
    /* ── Region detail text ── */
    detail_no_signal: { es: 'No se detecta una relaci\u00f3n estad\u00edstica clara entre el ENSO y la lluvia en esta regi\u00f3n (agregaci\u00f3n anual). La variabilidad local domina.', en: 'No clear statistical relationship detected between ENSO and rainfall in this region (annual aggregation). Local variability dominates.' },
    detail_chirps_caveat: { es: ' CHIRPS subrepresenta precipitaci\u00f3n nival en alta monta\u00f1a; la se\u00f1al ENSO cordillerana puede estar subestimada por limitaci\u00f3n de la fuente, no por ausencia del fen\u00f3meno.', en: ' CHIRPS underrepresents snowfall at high elevations; the Andean ENSO signal may be underestimated due to source limitations, not absence of the phenomenon.' },
    detail_wetter:    { es: 'm\u00e1s lluviosos', en: 'wetter' },
    detail_drier:     { es: 'm\u00e1s secos', en: 'drier' },
    detail_less_rain: { es: 'menos lluvia', en: 'less rainfall' },
    detail_more_rain_2:{ es: 'm\u00e1s lluvia', en: 'more rainfall' },
    detail_nino_years:{ es: 'A\u00f1os El Ni\u00f1o tienden a ser {signal} en esta regi\u00f3n; a\u00f1os La Ni\u00f1a se asocian con {ninaEffect}. Es una se\u00f1al estad\u00edstica, no certeza operacional.', en: 'El Ni\u00f1o years tend to be {signal} in this region; La Ni\u00f1a years are associated with {ninaEffect}. This is a statistical signal, not operational certainty.' },
    detail_stat_toggle:{ es: 'Detalle estad\u00edstico \u25b8', en: 'Statistical detail \u25b8' },
    detail_seasonal_toggle:{ es: 'Frecuencia estacional \u25b8', en: 'Seasonal frequency \u25b8' },

    /* ── Frequency table headers ── */
    freq_season:      { es: 'Estaci\u00f3n', en: 'Season' },
    freq_phase:       { es: 'Fase', en: 'Phase' },
    freq_above_median:{ es: 'Sobre mediana', en: 'Above median' },
    freq_deviation:   { es: 'Desv\u00edo %', en: 'Deviation %' },
    freq_mm_season:   { es: 'mm/est', en: 'mm/season' },
    freq_range:       { es: 'Rango', en: 'Range' },
    freq_p_note: {"es": "* q<0.05, ajuste Benjamini–Yekutieli de toda la tabla; p binomial aproximado. Frecuencias históricas, no probabilidades de pronóstico. Desvío % respecto de la media; clasificación respecto de la mediana. Rango: mínimo y máximo observado, no intervalo predictivo.", "en": "* q<0.05, Benjamini–Yekutieli adjustment across the whole table; approximate binomial p. Historical frequencies, not forecast probabilities. Deviation % relative to the mean; classification relative to the median. Range: observed minimum and maximum, not a prediction interval."},
    freq_preliminary: { es: 'preliminar', en: 'preliminary' },

    /* ── Frequency season labels ── */
    freq_summer:      { es: 'Verano (DEF)', en: 'Summer (DJF)' },
    freq_spring:      { es: 'Primavera (SON)', en: 'Spring (SON)' },
    freq_autumn:      { es: 'Oto\u00f1o (MAM)', en: 'Autumn (MAM)' },
    freq_winter:      { es: 'Invierno (JJA)', en: 'Winter (JJA)' },

    /* ── Seasonal signal detected ── */
    seasonal_detected:{ es: '<strong>Se\u00f1al estacional detectada:</strong> {hits}. Use el selector "Estaci\u00f3n" en la secci\u00f3n de correlaciones.', en: '<strong>Seasonal signal detected:</strong> {hits}. Use the "Season" selector in the correlations section.' },
    seasonal_spring:  { es: 'primavera (SON)', en: 'spring (SON)' },
    seasonal_summer:  { es: 'verano (DEF)', en: 'summer (DJF)' },
    seasonal_autumn:  { es: 'oto\u00f1o (MAM)', en: 'autumn (MAM)' },
    seasonal_winter:  { es: 'invierno (JJA)', en: 'winter (JJA)' },
    freq_both_agree: {"es": " (frecuencia histórica: {M}/{N}, q={p}; mismos datos, sin validación independiente)", "en": " (historical frequency: {M}/{N}, q={p}; same data, no independent validation)"},
    freq_disagree: {"es": " (frecuencia histórica: {M}/{N}, q={p}; no supera el ajuste de comparaciones)", "en": " (historical frequency: {M}/{N}, q={p}; does not survive comparison adjustment)"},
    /* ── Accordion bar note ── */
    bar_note:         { es: 'Anomal\u00eda de precipitaci\u00f3n mensual \u00b7 {start} \u2013 {end} \u00b7 azul = m\u00e1s h\u00famedo \u00b7 rojo = m\u00e1s seco \u00b7 fuente: CHIRPS v2.0', en: 'Monthly precipitation anomaly \u00b7 {start} \u2013 {end} \u00b7 blue = wetter \u00b7 red = drier \u00b7 source: CHIRPS v2.0' },

    /* ── advice.js ── */
    adv_very_strong:  { es: 'muy fuerte', en: 'very strong' },
    adv_strong:       { es: 'fuerte', en: 'strong' },
    adv_moderate:     { es: 'moderado', en: 'moderate' },
    adv_weak:         { es: 'd\u00e9bil', en: 'weak' },
    adv_neutral:      { es: 'neutral', en: 'neutral' },
    adv_no_lag:       { es: 'sin retardo', en: 'no lag' },
    adv_1m_lag:       { es: '1 mes de retardo', en: '1-month lag' },
    adv_nm_lag:       { es: '{n} meses de retardo', en: '{n}-month lag' },
    adv_above:        { es: 'por encima', en: 'above' },
    adv_below:        { es: 'por debajo', en: 'below' },
    adv_precip_summary: {"es": "Entre {start} y {end}, la anomalía mensual media de lluvia fue {val} mm ({dir} de la media climatológica). Es el último trimestre disponible en el archivo.", "en": "Between {start} and {end}, the mean monthly rainfall anomaly was {val} mm ({dir} the climatological mean). This is the last available quarter in the file."},
    adv_soi_strong_nino:  { es: 'El SOI fuertemente negativo refuerza la se\u00f1al El Ni\u00f1o.', en: 'Strongly negative SOI reinforces the El Ni\u00f1o signal.' },
    adv_soi_mod_nino:     { es: 'El SOI moderadamente negativo es consistente con El Ni\u00f1o.', en: 'Moderately negative SOI is consistent with El Ni\u00f1o.' },
    adv_soi_strong_nina:  { es: 'El SOI fuertemente positivo refuerza la se\u00f1al La Ni\u00f1a.', en: 'Strongly positive SOI reinforces the La Ni\u00f1a signal.' },
    adv_soi_mod_nina:     { es: 'El SOI moderadamente positivo es consistente con La Ni\u00f1a.', en: 'Moderately positive SOI is consistent with La Ni\u00f1a.' },
    adv_no_data:      { es: 'No hay datos de correlaci\u00f3n disponibles para <strong>{region}</strong>.', en: 'No correlation data available for <strong>{region}</strong>.' },
    adv_no_relation: {"es": "<strong>{region}</strong>: la asociación anual no supera el ajuste por comparaciones múltiples; esto no demuestra ausencia de un vínculo físico.", "en": "<strong>{region}</strong>: the annual association does not survive multiple-comparison adjustment; this does not prove absence of a physical link."},
    adv_chirps_caveat: {"es": " La nieve y el relieve limitan CHIRPS; en Patagonia la muestra solo llega a 50°S.", "en": " Snow and terrain limit CHIRPS; the Patagonia sample only extends to 50°S."},
    adv_neutral_text: { es: '<strong>{region}</strong>: condiciones ENSO Neutral (ONI {oni}). Existe correlaci\u00f3n hist\u00f3rica significativa, pero sin fase activa no se proyecta direcci\u00f3n de anomal\u00eda.', en: '<strong>{region}</strong>: ENSO Neutral conditions (ONI {oni}). Historical correlation exists, but without an active phase no anomaly direction is projected.' },
    adv_excess:       { es: 'precipitaci\u00f3n sobre lo normal', en: 'above-normal precipitation' },
    adv_deficit:      { es: 'precipitaci\u00f3n bajo lo normal', en: 'below-normal precipitation' },
    adv_excess_impl:  { es: 'm\u00e1s lluvia: oportunidad para la campa\u00f1a agr\u00edcola, riesgo de anegamiento para infraestructura', en: 'more rainfall: opportunity for the agricultural season, flooding risk for infrastructure' },
    adv_deficit_impl: { es: 'menos lluvia: riesgo de d\u00e9ficit para la campa\u00f1a agr\u00edcola', en: 'less rainfall: deficit risk for the agricultural season' },
    adv_active_text: {"es": "<strong>{region}</strong>: según ONI, <strong>{phaseStr}</strong> ({oniStr} °C). La asociación histórica de esta caja apunta a {dirText}. Es descriptiva y no predice la lluvia de los próximos meses.", "en": "<strong>{region}</strong>: by ONI, <strong>{phaseStr}</strong> ({oniStr} °C). This box’s historical association points to {dirText}. It is descriptive and does not predict rainfall in the coming months."},
    adv_validate: {"es": " Consultá el pronóstico regional del SMN para evaluar condiciones futuras.", "en": " Consult SMN regional forecasts to assess future conditions."},
    /* ── Glossary tooltips ── */
    tip_enso:         { es: 'El Ni\u00f1o\u2013Oscilaci\u00f3n del Sur: ciclo clim\u00e1tico del Pac\u00edfico ecuatorial que influye en la precipitaci\u00f3n de Argentina.', en: 'El Ni\u00f1o\u2013Southern Oscillation: equatorial Pacific climate cycle that influences precipitation in Argentina.' },
    tip_oni:          { es: 'Oceanic Ni\u00f1o Index: media m\u00f3vil de 3 meses de la anomal\u00eda de temperatura en la regi\u00f3n Ni\u00f1o 3.4 del Pac\u00edfico. Fuente: NOAA CPC.', en: 'Oceanic Ni\u00f1o Index: 3-month running mean of the SST anomaly in the Pacific Ni\u00f1o 3.4 region. Source: NOAA CPC.' },
    tip_el_nino: {"es": "Fase cálida del ENSO. La regla histórica ONI usa cinco estaciones sobre +0.5 °C; el diagnóstico operativo de NOAA considera RONI y acoplamiento atmosférico.", "en": "Warm ENSO phase. The historical ONI rule uses five seasons above +0.5 °C; NOAA operational diagnosis considers RONI and atmospheric coupling."},
    tip_la_nina: {"es": "Fase fría del ENSO. La regla histórica ONI usa cinco estaciones bajo −0.5 °C; el diagnóstico operativo de NOAA considera RONI y acoplamiento atmosférico.", "en": "Cold ENSO phase. The historical ONI rule uses five seasons below −0.5 °C; NOAA operational diagnosis considers RONI and atmospheric coupling."},
    tip_soi:          { es: 'Southern Oscillation Index: diferencia estandarizada de presi\u00f3n entre Tah\u00edt\u00ed y Darwin. Indicador atmosf\u00e9rico complementario del ONI.', en: 'Southern Oscillation Index: standardized pressure difference between Tahiti and Darwin. Atmospheric indicator complementary to the ONI.' },
    tip_sam: {"es": "SAM/AAO: índice de circulación del hemisferio sur. Su vínculo con lluvia depende de la estación y el lugar; puede interactuar con ENSO.", "en": "SAM/AAO: Southern Hemisphere circulation index. Its rainfall link depends on season and location; it can interact with ENSO."},
    tip_sam_inline: {"es": "Modo Anular del Sur: indicador complementario de circulación, no necesariamente independiente del ENSO.", "en": "Southern Annular Mode: complementary circulation indicator, not necessarily independent of ENSO."},
    tip_chirps:       { es: 'Climate Hazards group Infrared Precipitation with Stations. Producto satelital de precipitaci\u00f3n calibrado con estaciones, resoluci\u00f3n 0.05\u00b0.', en: 'Climate Hazards group Infrared Precipitation with Stations. Satellite precipitation product calibrated with stations, 0.05\u00b0 resolution.' },
    tip_neff:         { es: 'Grados de libertad efectivos. Corrige la autocorrelaci\u00f3n del ONI para no sobreestimar la significancia.', en: 'Effective degrees of freedom. Corrects for ONI autocorrelation to avoid overestimating significance.' },
    tip_tao:          { es: 'Red de boyas ancladas en el Pac\u00edfico ecuatorial que miden temperatura, corrientes y vientos en tiempo casi real.', en: 'Network of moored buoys in the equatorial Pacific measuring temperature, currents, and winds in near real-time.' },
    tip_sst: {"es": "Anomalía diaria OISST respecto de la climatología OI.v2 1971–2000; el mapa muestra instantáneas.", "en": "Daily OISST anomaly relative to the OI.v2 1971–2000 climatology; the map shows snapshots."},
    tip_spi:          { es: 'Standardized Precipitation Index: \u00edndice estandarizado de precipitaci\u00f3n acumulada en 3 meses. Valores negativos indican d\u00e9ficit; positivos, exceso.', en: 'Standardized Precipitation Index: standardized index of 3-month cumulative precipitation. Negative values indicate deficit; positive, excess.' },

    /* ── Language toggle ── */
    lang_toggle:      { es: 'EN', en: 'ES' },
    lang_toggle_aria: { es: 'Switch to English', en: 'Cambiar a espa\u00f1ol' },

    /* ── SOI data source table row ── */
    soi_source_desc: {"es": "Primario: SOI estandarizado NOAA CPC. Fallback ERDDAP usa otra estandarización y se identifica como tal. No se aplican automáticamente al fallback los umbrales de interpretación de CPC.", "en": "Primary: NOAA CPC standardized SOI. ERDDAP fallback uses a different standardization and is labeled accordingly. CPC interpretation thresholds are not automatically applied to the fallback."},
    nino34_source_desc: {"es": "OISST semanal promediado por mes; puede ser un mes parcial. Difiere de ERSST mensual en producto y climatología: su diferencia con ONI no se interpreta como una tendencia.", "en": "Weekly OISST averaged by month; the month may be partial. It differs from monthly ERSST in product and climatology: its gap from ONI is not interpreted as a trend."},
  },

  t(key, params) {
    const entry = this.translations[key];
    if (!entry) return key;
    let text = entry[this._lang] || entry['es'] || key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        text = text.replaceAll('{' + k + '}', v);
      }
    }
    return text;
  },

  /* Get a nested translation (for objects like season_labels) */
  tObj(key) {
    const entry = this.translations[key];
    if (!entry) return {};
    return entry[this._lang] || entry['es'] || {};
  },

  toggleLang() {
    this._lang = this._lang === 'es' ? 'en' : 'es';
    localStorage.setItem('enso-lang', this._lang);
    location.reload();
  },

  applyToDOM() {
    document.documentElement.lang = this._lang;
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.innerHTML = this.t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-text]').forEach(el => {
      el.textContent = this.t(el.dataset.i18nText);
    });
    document.querySelectorAll('[data-i18n-tip]').forEach(el => {
      el.setAttribute('data-tip', this.t(el.dataset.i18nTip));
    });
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      el.setAttribute('aria-label', this.t(el.dataset.i18nAria));
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      el.setAttribute('title', this.t(el.dataset.i18nTitle));
    });
  },
};

/* Global shorthand */
function t(key, params) { return window.I18N.t(key, params); }
function tObj(key) { return window.I18N.tObj(key); }
