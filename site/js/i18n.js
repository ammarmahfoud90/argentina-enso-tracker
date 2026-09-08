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
    /* ── Navigation ── */
    skip_link:        { es: 'Saltar al contenido principal', en: 'Skip to main content' },
    nav_aria:         { es: 'Navegaci\u00f3n por secci\u00f3n', en: 'Section navigation' },
    nav_status:       { es: '\u00bfQu\u00e9 pasa ahora?', en: "What's happening now?" },
    nav_oni:          { es: '\u00bfC\u00f3mo evolucion\u00f3?', en: 'How did it evolve?' },
    nav_soi:          { es: '\u00bfHay alerta temprana?', en: 'Early warning signs?' },
    nav_sam:          { es: 'SAM', en: 'SAM' },
    nav_ocean:        { es: '\u00bfQu\u00e9 pasa en el oc\u00e9ano?', en: "What's under the surface?" },
    nav_heat:         { es: '\u00bfD\u00f3nde est\u00e1 el calor?', en: 'Where is the heat?' },
    nav_forecast:     { es: '\u00bfQu\u00e9 se espera?', en: "What's expected?" },
    nav_compare:      { es: '\u00bfSe parece a otro episodio?', en: 'Similar to a past episode?' },
    nav_timeline:     { es: 'L\u00ednea de tiempo', en: 'Timeline' },
    nav_rain:         { es: '\u00bfC\u00f3mo afecta la lluvia?', en: 'How does it affect rainfall?' },
    nav_temp:         { es: '\u00bfY la temperatura?', en: 'And temperature?' },
    nav_intensity:    { es: '\u00bfImporta la intensidad?', en: 'Does intensity matter?' },
    nav_drought:      { es: '\u00bfHay sequ\u00eda?', en: 'Is there drought?' },
    nav_region:       { es: '\u00bfQu\u00e9 significa para mi regi\u00f3n?', en: 'What does it mean for my region?' },
    nav_parana:       { es: 'R\u00edo Paran\u00e1', en: 'Paran\u00e1 River' },
    nav_sources:      { es: 'Fuentes y m\u00e9todo', en: 'Sources & methodology' },

    /* ── Loading ── */
    loading_text:     { es: 'Conectando con NOAA CPC...', en: 'Connecting to NOAA CPC...' },

    /* ── Masthead ── */
    masthead_kicker:  { es: 'Bolet\u00edn clim\u00e1tico \u00b7 NOAA CPC \u00b7 CHIRPS v2.0', en: 'Climate bulletin \u00b7 NOAA CPC \u00b7 CHIRPS v2.0' },
    updated_label:    { es: 'Actualizado', en: 'Updated' },
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
    legend_no_signal: { es: 'Sin se\u00f1al significativa', en: 'No significant signal' },

    /* ── ONI Section ── */
    oni_title:        { es: '\u00bfC\u00f3mo evolucion\u00f3 el ENSO?', en: 'How did ENSO evolve?' },
    oni_desc:         { es: 'El <span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span> resume cu\u00e1nto se desv\u00eda la temperatura del Pac\u00edfico central respecto de lo normal. Es el \u00edndice principal para determinar si estamos en <span class="glossary" data-i18n-tip="tip_el_nino" data-tip="">El Ni\u00f1o</span>, <span class="glossary" data-i18n-tip="tip_la_nina" data-tip="">La Ni\u00f1a</span> o fase Neutral. Fuente: NOAA CPC.', en: 'The <span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span> measures how much the central Pacific temperature deviates from normal. It is the primary index for determining whether we are in <span class="glossary" data-i18n-tip="tip_el_nino" data-tip="">El Ni\u00f1o</span>, <span class="glossary" data-i18n-tip="tip_la_nina" data-tip="">La Ni\u00f1a</span>, or Neutral phase. Source: NOAA CPC.' },
    oni_range_1970:   { es: '1970\u2013hoy', en: '1970\u2013today' },
    oni_range_2000:   { es: '2000\u2013hoy', en: '2000\u2013today' },
    oni_range_2010:   { es: '2010\u2013hoy', en: '2010\u2013today' },
    oni_inset_label:  { es: '\u00daltimos 24 meses', en: 'Last 24 months' },
    oni_aria:         { es: 'Serie hist\u00f3rica del \u00cdndice ONI (Oceanic Ni\u00f1o Index) desde el a\u00f1o seleccionado hasta la fecha m\u00e1s reciente disponible', en: 'Historical ONI (Oceanic Ni\u00f1o Index) time series from the selected year to the most recent available date' },
    oni_inset_aria:   { es: 'Detalle de los \u00faltimos 24 meses del \u00cdndice ONI', en: 'Detail of the last 24 months of the ONI Index' },

    /* ── SOI Section ── */
    soi_title:        { es: '\u00bfHay se\u00f1ales tempranas de cambio?', en: 'Are there early signs of change?' },
    soi_desc:         { es: 'La presi\u00f3n atmosf\u00e9rica entre Tah\u00edt\u00ed y Darwin anticipa los cambios en la temperatura del Pac\u00edfico. El <span class="glossary" data-i18n-tip="tip_soi" data-tip="">SOI</span> suele adelantarse 2 a 4 semanas al ONI. Valores negativos sostenidos acompa\u00f1an El Ni\u00f1o; valores positivos sostenidos, La Ni\u00f1a.', en: 'Atmospheric pressure between Tahiti and Darwin anticipates changes in Pacific temperature. The <span class="glossary" data-i18n-tip="tip_soi" data-tip="">SOI</span> typically leads the ONI by 2 to 4 weeks. Sustained negative values accompany El Ni\u00f1o; sustained positive values, La Ni\u00f1a.' },
    soi_current:      { es: 'SOI actual', en: 'Current SOI' },
    soi_aria:         { es: 'Serie temporal del SOI con media m\u00f3vil de 3 meses', en: 'SOI time series with 3-month moving average' },
    soi_monthly:      { es: 'SOI mensual', en: 'Monthly SOI' },
    soi_ma3:          { es: 'Media móvil 3m', en: '3-month moving avg' },

    /* ── SAM Section ── */
    sam_title:        { es: '\u00bfQu\u00e9 dice el Modo Anular del Sur?', en: 'What does the Southern Annular Mode say?' },
    sam_desc:         { es: 'El <span class="glossary" data-i18n-tip="tip_sam" data-tip="">SAM</span> (Modo Anular del Sur) es el patr\u00f3n de circulaci\u00f3n dominante en latitudes medias y altas del hemisferio sur. Compite con el ENSO como forzante de precipitaci\u00f3n en Patagonia y el sur argentino. Fuente: NOAA CPC.', en: 'The <span class="glossary" data-i18n-tip="tip_sam" data-tip="">SAM</span> (Southern Annular Mode) is the dominant circulation pattern in the middle and high latitudes of the Southern Hemisphere. It competes with ENSO as a precipitation driver in Patagonia and southern Argentina. Source: NOAA CPC.' },
    sam_current:      { es: 'SAM actual', en: 'Current SAM' },
    sam_aria:         { es: 'Serie temporal del SAM/AAO', en: 'SAM/AAO time series' },
    sam_note:         { es: 'SAM positivo \u2192 vientos del oeste se contraen hacia la Ant\u00e1rtida \u2192 menos precipitaci\u00f3n en Patagonia. SAM negativo \u2192 vientos se expanden hacia el norte \u2192 m\u00e1s lluvia en la zona. Este efecto puede reforzar o contrarrestar la se\u00f1al ENSO en el sur argentino.', en: 'Positive SAM \u2192 westerly winds contract toward Antarctica \u2192 less precipitation in Patagonia. Negative SAM \u2192 winds expand northward \u2192 more rainfall in the area. This effect can reinforce or counteract the ENSO signal in southern Argentina.' },
    sam_stale:        { es: 'Dato desactualizado: ultimo valor de {month} {year} ({days} dias). La fuente NOAA CPC puede estar temporalmente sin actualizar.', en: 'Stale data: last value from {month} {year} ({days} days ago). The NOAA CPC source may be temporarily not updated.' },

    /* ── Subsurface Section ── */
    subsurface_title: { es: '\u00bfQu\u00e9 pasa debajo de la superficie?', en: "What's happening below the surface?" },
    subsurface_desc:  { es: 'El calor acumulado bajo la superficie anticipa lo que pasar\u00e1 en la temperatura de superficie meses despu\u00e9s. Durante El Ni\u00f1o, el agua c\u00e1lida se desplaza hacia el Pac\u00edfico oriental. Durante La Ni\u00f1a, asciende agua fr\u00eda en esa zona. Este perfil muestra temperatura absoluta (\u00b0C) hasta 300 m de profundidad, medida por <span class="glossary" data-i18n-tip="tip_tao" data-tip="">boyas TAO/TRITON</span> (NOAA PMEL).', en: 'Subsurface heat buildup anticipates what will happen at the surface months later. During El Ni\u00f1o, warm water shifts toward the eastern Pacific. During La Ni\u00f1a, cold water rises in that area. This profile shows absolute temperature (\u00b0C) down to 300 m depth, measured by <span class="glossary" data-i18n-tip="tip_tao" data-tip="">TAO/TRITON buoys</span> (NOAA PMEL).' },
    subsurface_aria:  { es: 'Heatmap de temperatura subsuperficial del Pac\u00edfico ecuatorial, profundidad vs longitud', en: 'Subsurface temperature heatmap of the equatorial Pacific, depth vs longitude' },

    /* ── SST Map Section ── */
    sst_title:        { es: '\u00bfD\u00f3nde se concentra el calor?', en: 'Where is the heat concentrated?' },
    sst_desc:         { es: 'La <span class="glossary" data-i18n-tip="tip_sst" data-tip="">TSM</span> en el Pac\u00edfico ecuatorial, comparada con el promedio 1991\u20132020. Los recuadros marcan las regiones Ni\u00f1o que se usan para monitoreo. Fuente: NOAA OISST v2.1.', en: '<span class="glossary" data-i18n-tip="tip_sst" data-tip="">SST</span> in the equatorial Pacific, compared to the 1991\u20132020 average. Boxes mark the Ni\u00f1o regions used for monitoring. Source: NOAA OISST v2.1.' },
    sst_play:         { es: '\u25b6 Reproducir', en: '\u25b6 Play' },
    sst_pause:        { es: '\u23f8 Pausar', en: '\u23f8 Pause' },
    sst_play_aria:    { es: 'Reproducir animaci\u00f3n del mapa', en: 'Play map animation' },
    sst_aria:         { es: 'Mapa interactivo de anomal\u00eda de temperatura superficial del mar en el Pac\u00edfico ecuatorial', en: 'Interactive sea surface temperature anomaly map of the equatorial Pacific' },
    sst_fallback:     { es: 'No se pudo cargar el mapa satelital de TSM. Mostrando datos de ONI en su lugar.', en: 'Could not load the SST satellite map. Showing ONI data instead.' },
    sst_fallback2:    { es: 'Consulte la secci\u00f3n de Serie hist\u00f3rica ONI arriba para el estado actual del ENSO.', en: 'See the ONI Historical Series section above for the current ENSO status.' },

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
    compare_desc:     { es: 'El episodio actual superpuesto a las trayectorias de episodios ENSO hist\u00f3ricos notables. Cada curva arranca desde el mes en que el ONI cruz\u00f3 el umbral \u00b10.5. Permite comparar ritmo e intensidad, no predecir que se repetir\u00e1 un patr\u00f3n.', en: 'The current episode overlaid on notable historical ENSO episode trajectories. Each curve starts from the month when the ONI crossed the \u00b10.5 threshold. Allows comparing pace and intensity, not predicting a pattern will repeat.' },
    compare_nino:     { es: 'El Ni\u00f1o hist\u00f3ricos', en: 'Historical El Ni\u00f1o' },
    compare_nina:     { es: 'La Ni\u00f1a hist\u00f3ricos', en: 'Historical La Ni\u00f1a' },
    compare_aria:     { es: 'Comparaci\u00f3n del episodio ENSO actual con eventos hist\u00f3ricos', en: 'Comparison of the current ENSO episode with historical events' },

    /* ── Timeline Section ── */
    timeline_title:   { es: '\u00bfCu\u00e1ndo ocurrieron El Ni\u00f1o y La Ni\u00f1a?', en: 'When did El Ni\u00f1o and La Ni\u00f1a occur?' },
    timeline_desc:    { es: 'Cada barra es un episodio ENSO formal (criterio NOAA CPC: ONI sobre el umbral \u00b10.5 durante al menos 5 trimestres consecutivos). El ancho refleja la duraci\u00f3n.', en: 'Each bar is a formal ENSO episode (NOAA CPC criteria: ONI above the \u00b10.5 threshold for at least 5 consecutive overlapping seasons). Width reflects duration.' },
    timeline_today:   { es: 'hoy', en: 'today' },
    notable_title:    { es: 'Eventos ENSO notables y su impacto en Argentina', en: 'Notable ENSO events and their impact on Argentina' },

    /* ── Correlation Section ── */
    corr_title:       { es: '\u00bfC\u00f3mo se relaciona el ENSO con la lluvia?', en: 'How is ENSO related to rainfall?' },
    corr_desc:        { es: 'Qu\u00e9 tan asociados est\u00e1n el estado del Pac\u00edfico (<span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span>) y la precipitaci\u00f3n en cada regi\u00f3n argentina, usando datos de <span class="glossary" data-i18n-tip="tip_chirps" data-tip="">CHIRPS</span> v2.0 (1981\u20132025). Las barras m\u00e1s altas indican regiones donde el ENSO tiene m\u00e1s influencia sobre la lluvia. Use el selector de estaci\u00f3n para ver cu\u00e1ndo es m\u00e1s fuerte la se\u00f1al.', en: 'How closely associated are the Pacific state (<span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span>) and precipitation in each Argentine region, using <span class="glossary" data-i18n-tip="tip_chirps" data-tip="">CHIRPS</span> v2.0 data (1981\u20132025). Taller bars indicate regions where ENSO has more influence on rainfall. Use the season selector to see when the signal is strongest.' },
    corr_season_label:{ es: 'Estaci\u00f3n:', en: 'Season:' },
    corr_bar_aria:    { es: 'Gr\u00e1fico de barras de correlaci\u00f3n ENSO-precipitaci\u00f3n por regi\u00f3n', en: 'ENSO-precipitation correlation bar chart by region' },
    corr_detail_toggle:{ es: 'Tabla detallada por lag \u25b8', en: 'Detailed table by lag \u25b8' },
    corr_legend_label:{ es: 'correlaci\u00f3n', en: 'correlation' },
    corr_note:        { es: 'NEA y Pampa H\u00fameda tienen la se\u00f1al m\u00e1s clara: a\u00f1os El Ni\u00f1o tienden a ser m\u00e1s lluviosos, con 0 a 2 meses de retardo. NOA, Cuyo y Patagonia no muestran se\u00f1al en el agregado anual, pero s\u00ed por estaci\u00f3n. Cuyo en invierno y Patagonia en primavera responden al ENSO cuando se miran por separado.', en: 'NEA and Pampa H\u00fameda have the clearest signal: El Ni\u00f1o years tend to be wetter, with a 0 to 2 month lag. NOA, Cuyo, and Patagonia show no signal in the annual aggregate, but they do seasonally. Cuyo in winter and Patagonia in spring respond to ENSO when examined separately.' },
    corr_stat_toggle: { es: 'Detalle estad\u00edstico \u25b8', en: 'Statistical detail \u25b8' },
    corr_stat_detail: { es: 'Correlaci\u00f3n de Pearson ONI vs precipitaci\u00f3n regional (CHIRPS v2.0, 1981\u20132025). Significancia: * p<0.05, ** p<0.01, *** p<0.001 con <span class="glossary" data-i18n-tip="tip_neff" data-tip="">n<sub>eff</sub></span> (Bretherton 1999). Se\u00f1al estacional: NEA SON r=+0.32***, Pampa H\u00fameda DEF r=+0.39***, Cuyo JJA r=+0.25**, Patagonia SON r=+0.18*. El <span class="glossary" data-i18n-tip="tip_sam_inline" data-tip="">SAM</span> compite con el ENSO como forzante dominante en el sur.', en: 'Pearson correlation ONI vs regional precipitation (CHIRPS v2.0, 1981\u20132025). Significance: * p<0.05, ** p<0.01, *** p<0.001 with <span class="glossary" data-i18n-tip="tip_neff" data-tip="">n<sub>eff</sub></span> (Bretherton 1999). Seasonal signal: NEA SON r=+0.32***, Pampa H\u00fameda DEF r=+0.39***, Cuyo JJA r=+0.25**, Patagonia SON r=+0.18*. The <span class="glossary" data-i18n-tip="tip_sam_inline" data-tip="">SAM</span> competes with ENSO as the dominant driver in the south.' },
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
    temp_desc:        { es: 'Correlaci\u00f3n entre el <span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span> y la temperatura media regional (CPC Global Temperature, 0.5\u00b0). Misma metodolog\u00eda que las correlaciones de precipitaci\u00f3n: Pearson con correcci\u00f3n <span class="glossary" data-i18n-tip="tip_neff" data-tip="">n<sub>eff</sub></span> (Bretherton 1999). Barras positivas = El Ni\u00f1o tiende a estar asociado con temperaturas m\u00e1s altas.', en: 'Correlation between <span class="glossary" data-i18n-tip="tip_oni" data-tip="">ONI</span> and regional mean temperature (CPC Global Temperature, 0.5\u00b0). Same methodology as precipitation correlations: Pearson with <span class="glossary" data-i18n-tip="tip_neff" data-tip="">n<sub>eff</sub></span> correction (Bretherton 1999). Positive bars = El Ni\u00f1o tends to be associated with higher temperatures.' },
    temp_bar_aria:    { es: 'Gr\u00e1fico de barras de correlaci\u00f3n ENSO-temperatura por regi\u00f3n', en: 'ENSO-temperature correlation bar chart by region' },

    /* ── Composite Section ── */
    composite_title:  { es: '\u00bfImporta la intensidad del ENSO?', en: 'Does ENSO intensity matter?' },
    composite_desc:   { es: 'Precipitaci\u00f3n acumulada estacional promedio seg\u00fan la intensidad del evento ENSO: d\u00e9bil (|ONI| 0.5\u20131.0), moderado (1.0\u20131.5), fuerte (1.5\u20132.0), muy fuerte (>2.0). Colores rojos = El Ni\u00f1o, azules = La Ni\u00f1a. N = n\u00famero de estaciones en cada categor\u00eda.', en: 'Average seasonal cumulative precipitation by ENSO event intensity: weak (|ONI| 0.5\u20131.0), moderate (1.0\u20131.5), strong (1.5\u20132.0), very strong (>2.0). Red = El Ni\u00f1o, blue = La Ni\u00f1a. N = number of seasons in each category.' },
    composite_aria:   { es: 'Gr\u00e1fico de anomal\u00eda de precipitaci\u00f3n por intensidad ENSO', en: 'Precipitation anomaly chart by ENSO intensity' },
    anomaly_pct:      { es: 'Anomal\u00eda (%)', en: 'Anomaly (%)' },
    intensity_weak:   { es: 'D\u00e9bil', en: 'Weak' },
    intensity_moderate:{ es: 'Moderado', en: 'Moderate' },
    intensity_strong: { es: 'Fuerte', en: 'Strong' },
    intensity_vstrong:{ es: 'Muy fuerte', en: 'Very strong' },

    /* ── SPI Section ── */
    spi_title:        { es: '\u00bfHay sequ\u00eda o exceso de lluvia?', en: 'Is there drought or excess rainfall?' },
    spi_desc:         { es: 'El <span class="glossary" data-i18n-tip="tip_spi" data-tip="">SPI-3</span> mide el d\u00e9ficit o exceso de precipitaci\u00f3n acumulada en 3 meses respecto de la climatolog\u00eda (1981\u20132025). Valores bajo \u22121.0 indican sequ\u00eda; sobre +1.0, humedad anormal.', en: 'The <span class="glossary" data-i18n-tip="tip_spi" data-tip="">SPI-3</span> measures the deficit or excess of 3-month cumulative precipitation relative to climatology (1981\u20132025). Values below \u22121.0 indicate drought; above +1.0, abnormal wetness.' },
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
    data_fresh:       { es: 'Datos actualizados (< 3 días)', en: 'Data up to date (< 3 days)' },
    data_aging:       { es: 'Datos de hace {days} días', en: 'Data from {days} days ago' },
    data_stale:       { es: 'Datos desactualizados ({days} días)', en: 'Data outdated ({days} days)' },
    stale_banner:     { es: 'ATENCIÓN: Datos desactualizados (última actualización hace {days} días). Verifique el estado del pipeline.', en: 'WARNING: Outdated data (last update {days} days ago). Check the pipeline status.' },
    footer_generated: { es: 'Datos generados el {date}.', en: 'Data generated on {date}.' },
    footer_generated_stale: { es: 'Datos generados el {date} (hace {days} dias. Revise el pipeline).', en: 'Data generated on {date} ({days} days ago. Check the pipeline).' },

    /* ── Parana Section ── */
    parana_title:     { es: '\u00bfC\u00f3mo afecta el ENSO al R\u00edo Paran\u00e1?', en: 'How does ENSO affect the Paran\u00e1 River?' },
    parana_desc:      { es: 'El nivel del Paran\u00e1 en Rosario es un indicador clave del impacto hidrol\u00f3gico del ENSO en Argentina. Los eventos El Ni\u00f1o fuertes producen crecidas con 3\u20136 meses de retardo; las La Ni\u00f1a prolongadas causan bajantes. Los datos hist\u00f3ricos muestran la relaci\u00f3n entre la fase ENSO y los niveles del r\u00edo.', en: 'The Paran\u00e1 level at Rosario is a key indicator of ENSO\u2019s hydrological impact in Argentina. Strong El Ni\u00f1o events produce floods with a 3\u20136 month lag; prolonged La Ni\u00f1a events cause low water levels. Historical data shows the relationship between the ENSO phase and river levels.' },
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
    method_corr: { es: '<strong>Metodolog\u00eda de correlaci\u00f3n.</strong> Correlaci\u00f3n de Pearson y Spearman entre ONI y precipitaci\u00f3n mensual regional, lags 0 a 3 meses. Significancia: test bilateral con n<sub>eff</sub> (Bretherton et al. 1999), umbral p &lt; 0.05. Datos de precipitaci\u00f3n: promedio espacial CHIRPS v2.0 (resoluci\u00f3n 0.05\u00b0) sobre 5 cajas rectangulares lat/lon en Argentina (1981\u20132025). Las regiones son aproximaciones rectangulares, no pol\u00edgonos administrativos ni de cuenca. Existe solapamiento menor entre Pampa H\u00fameda y Patagonia (~10% de celdas) y entre NOA y Cuyo (~9%). NEA y Pampa H\u00fameda no comparten dominio espacial; sus correlaciones son independientes en ese sentido, aunque la autocorrelaci\u00f3n espacial de la precipitaci\u00f3n limita la independencia estricta. Correlaciones calculadas sobre todos los meses del a\u00f1o y por trimestre (SON, DEF, MAM, JJA).', en: '<strong>Correlation methodology.</strong> Pearson and Spearman correlation between ONI and regional monthly precipitation, lags 0 to 3 months. Significance: two-tailed test with n<sub>eff</sub> (Bretherton et al. 1999), threshold p &lt; 0.05. Precipitation data: CHIRPS v2.0 spatial average (0.05\u00b0 resolution) over 5 rectangular lat/lon boxes in Argentina (1981\u20132025). Regions are rectangular approximations, not administrative or watershed polygons. Minor overlap exists between Pampa H\u00fameda and Patagonia (~10% of cells) and between NOA and Cuyo (~9%). NEA and Pampa H\u00fameda share no spatial domain; their correlations are independent in that sense, although spatial precipitation autocorrelation limits strict independence. Correlations computed over all months and by quarter (SON, DJF, MAM, JJA).' },
    method_oni:    { es: '<strong>Base del ONI.</strong> Media m\u00f3vil de 3 meses de la anomal\u00eda SST en la regi\u00f3n Ni\u00f1o 3.4, usando ERSSTv5 con per\u00edodos base de 30 a\u00f1os centrados (NOAA CPC). Base vigente: 1991\u20132020. Otros proveedores (IRI) pueden usar bases distintas, lo que produce valores ligeramente distintos para la misma temporada.', en: '<strong>ONI baseline.</strong> 3-month running mean of SST anomaly in the Ni\u00f1o 3.4 region, using ERSSTv5 with centered 30-year base periods (NOAA CPC). Current baseline: 1991\u20132020. Other providers (IRI) may use different baselines, producing slightly different values for the same season.' },
    method_chirps:      { es: '<strong>Limitaci\u00f3n CHIRPS en precipitaci\u00f3n nival.</strong> CHIRPS v2.0 se basa en estimaciones infrarrojas satelitales calibradas con estaciones, y subrepresenta la precipitaci\u00f3n s\u00f3lida (nieve) en alta monta\u00f1a. La se\u00f1al ENSO en Cuyo y Patagonia cordillerana puede estar subestimada por esta limitaci\u00f3n, no por ausencia f\u00edsica del fen\u00f3meno.', en: '<strong>CHIRPS snowfall limitation.</strong> CHIRPS v2.0 is based on satellite infrared estimates calibrated with stations and underrepresents solid precipitation (snow) at high elevations. The ENSO signal in Cuyo and Andean Patagonia may be underestimated due to this limitation, not because of a physical absence of the phenomenon.' },
    method_neff:        { es: '<strong>Grados de libertad efectivos.</strong> El ONI est\u00e1 fuertemente autocorrelacionado por ser media m\u00f3vil de 3 meses. Los p-values usan n<sub>eff</sub> (Bretherton et al. 1999), no n bruto, para evitar sobreestimar la significancia. Se reportan ambos valores en el detalle de cada correlaci\u00f3n.', en: '<strong>Effective degrees of freedom.</strong> The ONI is strongly autocorrelated because it is a 3-month moving average. P-values use n<sub>eff</sub> (Bretherton et al. 1999), not raw n, to avoid overestimating significance. Both values are reported in each correlation detail.' },
    method_episodes:    { es: '<strong>Detecci\u00f3n de episodios.</strong> Criterio NOAA CPC: ONI \u2265 +0.5 (El Ni\u00f1o) o \u2264 \u22120.5 (La Ni\u00f1a) durante al menos 5 temporadas consecutivas superpuestas de 3 meses.', en: '<strong>Episode detection.</strong> NOAA CPC criteria: ONI \u2265 +0.5 (El Ni\u00f1o) or \u2264 \u22120.5 (La Ni\u00f1a) for at least 5 consecutive overlapping 3-month seasons.' },
    method_pipeline:    { es: 'Pipeline: Python (build.py), JSON, HTML/JS est\u00e1tico. Actualizaci\u00f3n diaria v\u00eda GitHub Actions.', en: 'Pipeline: Python (build.py), JSON, static HTML/JS. Daily update via GitHub Actions.' },

    /* ── Footer ── */
    footer_sources:   { es: 'Fuentes: NOAA CPC \u00b7 IRI Columbia \u00b7 CHIRPS v2.0 (UCSB) \u00b7 TAO/TRITON (NOAA PMEL)', en: 'Sources: NOAA CPC \u00b7 IRI Columbia \u00b7 CHIRPS v2.0 (UCSB) \u00b7 TAO/TRITON (NOAA PMEL)' },
    footer_disclaimer:{ es: 'El ENSO explica solo una parte de la variabilidad de precipitaci\u00f3n en Argentina. El SAM (Modo Anular del Sur), la variabilidad interna atmosf\u00e9rica y factores regionales tambi\u00e9n influyen significativamente.', en: 'ENSO explains only a fraction of precipitation variability in Argentina. The SAM (Southern Annular Mode), internal atmospheric variability, and regional factors also have significant influence.' },
    footer_latency:   { es: 'Latencia de datos: ONI ~2 meses (publicaci\u00f3n CPC); Ni\u00f1o 3.4 SST ~1 semana (ERDDAP/OISST, composites semanales); SOI ~1 mes (CPC / ERDDAP fallback); temperatura subsuperficial ~1 mes (TAO/TRITON). Estas latencias son est\u00e1ndar para monitoreo clim\u00e1tico operacional.', en: 'Data latency: ONI ~2 months (CPC publication); Ni\u00f1o 3.4 SST ~1 week (ERDDAP/OISST, weekly composites); SOI ~1 month (CPC / ERDDAP fallback); subsurface temperature ~1 month (TAO/TRITON). These latencies are standard for operational climate monitoring.' },
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
    summary_neutral_l1:    { es: 'El Pac\u00edfico ecuatorial est\u00e1 en su rango normal. El ONI marca {oni} \u00b0C.', en: 'The equatorial Pacific is in its normal range. The ONI is at {oni} \u00b0C.' },
    summary_active_l1:     { es: 'El Pac\u00edfico ecuatorial est\u00e1 {tempWord} de lo normal. El ONI marca {oni} \u00b0C{intStr}.', en: 'The equatorial Pacific is {tempWord} than normal. The ONI is at {oni} \u00b0C{intStr}.' },
    warmer:                { es: 'm\u00e1s c\u00e1lido', en: 'warmer' },
    cooler:                { es: 'm\u00e1s fr\u00edo', en: 'cooler' },
    summary_neutral_l2:    { es: 'Sin fase ENSO activa, la se\u00f1al hist\u00f3rica no apunta a una direcci\u00f3n de lluvia. Planificar con climatolog\u00eda estacional.', en: 'With no active ENSO phase, the historical signal does not point to a rainfall direction. Plan using seasonal climatology.' },
    summary_active_l2:     { es: 'De los {N} {seasonName} con {phase} desde 1981, {M} fueron m\u00e1s lluviosos que lo normal en {region}.', en: 'Of the {N} {seasonName} with {phase} since 1981, {M} were wetter than normal in {region}.' },
    summary_active_l2_other:{ es: ' Con {otherPhase}, {onlyStr}{ocM} de {ocN}.', en: ' With {otherPhase}, {onlyStr}{ocM} of {ocN}.' },
    summary_only:          { es: 'solo ', en: 'only ' },
    summary_active_l2_dev: { es: ' En promedio, llovió un {s}{dev}% en esos {seasonName}.', en: ' On average, it rained {s}{dev}% in those {seasonName}.' },
    summary_no_signal:     { es: 'No se detecta se\u00f1al estad\u00edstica clara del ENSO sobre la lluvia en {region} (1981\u20132025).', en: 'No clear ENSO statistical signal detected for rainfall in {region} (1981\u20132025).' },
    summary_l3:            { es: 'Esto no es un pron\u00f3stico. El ENSO explica solo una parte de la variabilidad de precipitaci\u00f3n.', en: 'This is not a forecast. ENSO explains only a fraction of precipitation variability.' },
    only:                  { es: 'solo ', en: 'only ' },

    /* ── Season names for summary ── */
    season_name_springs:   { es: 'primaveras', en: 'springs' },
    season_name_summers:   { es: 'veranos', en: 'summers' },
    season_name_autumns:   { es: 'oto\u00f1os', en: 'autumns' },
    season_name_winters:   { es: 'inviernos', en: 'winters' },

    /* ── Hero / Status ── */
    status_neutral:   { es: 'Condiciones Neutrales \u00b7 NOAA CPC', en: 'Neutral Conditions \u00b7 NOAA CPC' },
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
    risk_nino:        { es: 'Hist\u00f3ricamente, los a\u00f1os El Ni\u00f1o tienden a ser m\u00e1s lluviosos en NEA y Pampa H\u00fameda: oportunidad para la campa\u00f1a agr\u00edcola, pero riesgo de anegamiento para infraestructura y cuencas urbanas.', en: 'Historically, El Ni\u00f1o years tend to be wetter in NEA and Pampa H\u00fameda: opportunity for the agricultural season, but flooding risk for infrastructure and urban basins.' },
    risk_nina:        { es: 'Hist\u00f3ricamente, los a\u00f1os La Ni\u00f1a tienden a ser m\u00e1s secos en NEA y Pampa H\u00fameda: riesgo de d\u00e9ficit para la campa\u00f1a agr\u00edcola, menor presi\u00f3n sobre infraestructura de drenaje.', en: 'Historically, La Ni\u00f1a years tend to be drier in NEA and Pampa H\u00fameda: deficit risk for the agricultural season, less pressure on drainage infrastructure.' },
    risk_pampa_detail:{ es: ' Pampa H\u00fameda en verano (DEF) es el caso m\u00e1s fuerte: {enM}/{enN} veranos El Ni\u00f1o sobre la mediana (p={enP}) contra {lnM}/{lnN} en La Ni\u00f1a (p={lnP}). Correlaci\u00f3n y frecuencia coinciden (r=+0.39***).', en: ' Pampa H\u00fameda in summer (DJF) is the strongest case: {enM}/{enN} El Ni\u00f1o summers above median (p={enP}) vs {lnM}/{lnN} in La Ni\u00f1a (p={lnP}). Correlation and frequency agree (r=+0.39***).' },
    risk_no_signal:   { es: ' NOA, Cuyo y Patagonia no muestran se\u00f1al clara en el agregado anual, pero s\u00ed por estaci\u00f3n.', en: ' NOA, Cuyo, and Patagonia show no clear signal in the annual aggregate, but they do seasonally.' },

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
    freq_p_note:      { es: '* p < 0.05 (binomial bilateral). Desv\u00edo % = respecto de la media climatol\u00f3gica estacional. Rango = [min, max] de desv\u00edos estacionales individuales.', en: '* p < 0.05 (two-tailed binomial). Deviation % = relative to seasonal climatological mean. Range = [min, max] of individual seasonal deviations.' },
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
    freq_both_agree:  { es: ' (frecuencia: {M}/{N}, p={p} \u2014 ambos m\u00e9todos coinciden)', en: ' (frequency: {M}/{N}, p={p} \u2014 both methods agree)' },
    freq_disagree:    { es: ' (frecuencia: {M}/{N}, p={p} \u2014 los m\u00e9todos discrepan: correlaci\u00f3n significativa pero frecuencia no)', en: ' (frequency: {M}/{N}, p={p} \u2014 methods disagree: correlation significant but frequency not)' },

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
    adv_precip_summary:{ es: 'Los \u00faltimos 3 meses, la precipitaci\u00f3n estuvo {dir} de lo normal ({val} mm de anomal\u00eda media).', en: 'Over the last 3 months, precipitation was {dir} normal ({val} mm average anomaly).' },
    adv_soi_strong_nino:  { es: 'El SOI fuertemente negativo refuerza la se\u00f1al El Ni\u00f1o.', en: 'Strongly negative SOI reinforces the El Ni\u00f1o signal.' },
    adv_soi_mod_nino:     { es: 'El SOI moderadamente negativo es consistente con El Ni\u00f1o.', en: 'Moderately negative SOI is consistent with El Ni\u00f1o.' },
    adv_soi_strong_nina:  { es: 'El SOI fuertemente positivo refuerza la se\u00f1al La Ni\u00f1a.', en: 'Strongly positive SOI reinforces the La Ni\u00f1a signal.' },
    adv_soi_mod_nina:     { es: 'El SOI moderadamente positivo es consistente con La Ni\u00f1a.', en: 'Moderately positive SOI is consistent with La Ni\u00f1a.' },
    adv_no_data:      { es: 'No hay datos de correlaci\u00f3n disponibles para <strong>{region}</strong>.', en: 'No correlation data available for <strong>{region}</strong>.' },
    adv_no_relation:  { es: '<strong>{region}</strong>: no se detecta relaci\u00f3n estad\u00edstica clara entre el ENSO y la lluvia en esta regi\u00f3n (agregaci\u00f3n anual).', en: '<strong>{region}</strong>: no clear statistical relationship detected between ENSO and rainfall in this region (annual aggregation).' },
    adv_chirps_caveat:{ es: ' CHIRPS subrepresenta precipitaci\u00f3n nival en alta monta\u00f1a; la se\u00f1al ENSO cordillerana puede estar subestimada.', en: ' CHIRPS underrepresents snowfall at high elevations; the Andean ENSO signal may be underestimated.' },
    adv_neutral_text: { es: '<strong>{region}</strong>: condiciones ENSO Neutral (ONI {oni}). Existe correlaci\u00f3n hist\u00f3rica significativa, pero sin fase activa no se proyecta direcci\u00f3n de anomal\u00eda.', en: '<strong>{region}</strong>: ENSO Neutral conditions (ONI {oni}). Historical correlation exists, but without an active phase no anomaly direction is projected.' },
    adv_excess:       { es: 'precipitaci\u00f3n sobre lo normal', en: 'above-normal precipitation' },
    adv_deficit:      { es: 'precipitaci\u00f3n bajo lo normal', en: 'below-normal precipitation' },
    adv_excess_impl:  { es: 'm\u00e1s lluvia: oportunidad para la campa\u00f1a agr\u00edcola, riesgo de anegamiento para infraestructura', en: 'more rainfall: opportunity for the agricultural season, flooding risk for infrastructure' },
    adv_deficit_impl: { es: 'menos lluvia: riesgo de d\u00e9ficit para la campa\u00f1a agr\u00edcola', en: 'less rainfall: deficit risk for the agricultural season' },
    adv_active_text:  { es: '<strong>{region}</strong>: fase activa <strong>{phaseStr}</strong>{oniStr}. Histor\u00edcamente, {dirText} en esta regi\u00f3n. <strong>{implication}</strong>.', en: '<strong>{region}</strong>: active phase <strong>{phaseStr}</strong>{oniStr}. Historically, {dirText} in this region. <strong>{implication}</strong>.' },
    adv_validate:     { es: ' Se\u00f1al estad\u00edstica. Validar con pron\u00f3stico NOAA/IRI.', en: ' Statistical signal. Validate with NOAA/IRI forecast.' },

    /* ── Glossary tooltips ── */
    tip_enso:         { es: 'El Ni\u00f1o\u2013Oscilaci\u00f3n del Sur: ciclo clim\u00e1tico del Pac\u00edfico ecuatorial que influye en la precipitaci\u00f3n de Argentina.', en: 'El Ni\u00f1o\u2013Southern Oscillation: equatorial Pacific climate cycle that influences precipitation in Argentina.' },
    tip_oni:          { es: 'Oceanic Ni\u00f1o Index: media m\u00f3vil de 3 meses de la anomal\u00eda de temperatura en la regi\u00f3n Ni\u00f1o 3.4 del Pac\u00edfico. Fuente: NOAA CPC.', en: 'Oceanic Ni\u00f1o Index: 3-month running mean of the SST anomaly in the Pacific Ni\u00f1o 3.4 region. Source: NOAA CPC.' },
    tip_el_nino:      { es: 'Calentamiento an\u00f3malo del Pac\u00edfico ecuatorial. Se declara cuando el ONI supera +0.5 \u00b0C durante 5 trimestres consecutivos.', en: 'Anomalous warming of the equatorial Pacific. Declared when the ONI exceeds +0.5 \u00b0C for 5 consecutive overlapping seasons.' },
    tip_la_nina:      { es: 'Enfriamiento an\u00f3malo del Pac\u00edfico ecuatorial. Se declara cuando el ONI baja de \u22120.5 \u00b0C durante 5 trimestres consecutivos.', en: 'Anomalous cooling of the equatorial Pacific. Declared when the ONI drops below \u22120.5 \u00b0C for 5 consecutive overlapping seasons.' },
    tip_soi:          { es: 'Southern Oscillation Index: diferencia estandarizada de presi\u00f3n entre Tah\u00edt\u00ed y Darwin. Indicador atmosf\u00e9rico complementario del ONI.', en: 'Southern Oscillation Index: standardized pressure difference between Tahiti and Darwin. Atmospheric indicator complementary to the ONI.' },
    tip_sam:          { es: 'Southern Annular Mode / Antarctic Oscillation. Patr\u00f3n de circulaci\u00f3n dominante en el hemisferio sur. SAM positivo: vientos del oeste se contraen hacia la Ant\u00e1rtida, menos lluvia en Patagonia. SAM negativo: vientos se expanden hacia el norte, m\u00e1s lluvia en Patagonia.', en: 'Southern Annular Mode / Antarctic Oscillation. Dominant circulation pattern in the Southern Hemisphere. Positive SAM: westerlies contract toward Antarctica, less rain in Patagonia. Negative SAM: westerlies expand northward, more rain in Patagonia.' },
    tip_sam_inline:   { es: 'Modo Anular del Sur. Patr\u00f3n de circulaci\u00f3n atmosf\u00e9rica que influye en la precipitaci\u00f3n del sur de Sudam\u00e9rica, independiente del ENSO.', en: 'Southern Annular Mode. Atmospheric circulation pattern that influences precipitation in southern South America, independent of ENSO.' },
    tip_chirps:       { es: 'Climate Hazards group Infrared Precipitation with Stations. Producto satelital de precipitaci\u00f3n calibrado con estaciones, resoluci\u00f3n 0.05\u00b0.', en: 'Climate Hazards group Infrared Precipitation with Stations. Satellite precipitation product calibrated with stations, 0.05\u00b0 resolution.' },
    tip_neff:         { es: 'Grados de libertad efectivos. Corrige la autocorrelaci\u00f3n del ONI para no sobreestimar la significancia.', en: 'Effective degrees of freedom. Corrects for ONI autocorrelation to avoid overestimating significance.' },
    tip_tao:          { es: 'Red de boyas ancladas en el Pac\u00edfico ecuatorial que miden temperatura, corrientes y vientos en tiempo casi real.', en: 'Network of moored buoys in the equatorial Pacific measuring temperature, currents, and winds in near real-time.' },
    tip_sst:          { es: 'Temperatura Superficial del Mar. El mapa muestra la anomal\u00eda: diferencia respecto del promedio 1991\u20132020.', en: 'Sea Surface Temperature. The map shows the anomaly: difference from the 1991\u20132020 average.' },
    tip_spi:          { es: 'Standardized Precipitation Index: \u00edndice estandarizado de precipitaci\u00f3n acumulada en 3 meses. Valores negativos indican d\u00e9ficit; positivos, exceso.', en: 'Standardized Precipitation Index: standardized index of 3-month cumulative precipitation. Negative values indicate deficit; positive, excess.' },

    /* ── Language toggle ── */
    lang_toggle:      { es: 'EN', en: 'ES' },
    lang_toggle_aria: { es: 'Switch to English', en: 'Cambiar a espa\u00f1ol' },

    /* ── SOI data source table row ── */
    soi_source_desc:  { es: 'Primario: CPC estandarizado (NOAA). Fallback: ERDDAP erdlasNoix (estandarizaci\u00f3n distinta; diverge >0.5 del CPC en ~54% de meses). El r\u00f3tulo del indicador refleja la fuente efectiva de cada build. Escala estandarizada (rango \u2248 \u22123 a +3); \u00d710 \u2248 escala Troup (BOM). Los umbrales \u00b10.5 y \u00b11.0 son adimensionales y aplican a ambas series estandarizadas.', en: 'Primary: CPC standardized (NOAA). Fallback: ERDDAP erdlasNoix (different standardization; diverges >0.5 from CPC in ~54% of months). The indicator label reflects the effective source of each build. Standardized scale (range \u2248 \u22123 to +3); \u00d710 \u2248 Troup scale (BOM). The \u00b10.5 and \u00b11.0 thresholds are dimensionless and apply to both standardized series.' },
    nino34_source_desc:{ es: 'ERDDAP ncepNinoSSTwk (OISST v2, composites semanales promediados a mensual). Difiere del Ni\u00f1o 3.4 mensual de ERSSTv5 que usan NOAA CPC e IRI.', en: 'ERDDAP ncepNinoSSTwk (OISST v2, weekly composites averaged to monthly). Differs from the monthly Ni\u00f1o 3.4 from ERSSTv5 used by NOAA CPC and IRI.' },
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
