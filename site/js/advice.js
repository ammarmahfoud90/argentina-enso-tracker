/**
 * advice.js — Data-driven regional risk advice for the Argentina ENSO Tracker.
 *
 * All text is conditioned on:
 *   1. Current ENSO phase (from ONI via build.py)
 *   2. Current ONI magnitude (for intensity grading)
 *   3. Best-lag Pearson correlation for the selected region
 *   4. SOI trend (leading indicator)
 *   5. Recent precipitation anomaly (observed conditions)
 *
 * Exported function: getRegionAdvice(regionName, phase, bestCorr, extras)
 */

/* ── Thresholds ── */
const SIG_THRESHOLD = 0.05;

/* ONI intensity thresholds (NOAA CPC categories) */
const ONI_WEAK    = 0.5;
const ONI_MOD     = 1.0;
const ONI_STRONG  = 1.5;
const ONI_VSTRONG = 2.0;

function _oniIntensity(oni) {
  const a = Math.abs(oni);
  if (a >= ONI_VSTRONG) return 'muy fuerte';
  if (a >= ONI_STRONG)  return 'fuerte';
  if (a >= ONI_MOD)     return 'moderado';
  if (a >= ONI_WEAK)    return 'débil';
  return 'neutral';
}

function _precipDirection(phase, r) {
  if (phase === 'El Niño') return r > 0 ? 'excess' : 'deficit';
  return r > 0 ? 'deficit' : 'excess';
}

function _lagStr(lag) {
  if (lag === 0) return 'sin retardo';
  if (lag === 1) return '1 mes de retardo';
  return `${lag} meses de retardo`;
}

function _precipSummary(precipAnomaly) {
  if (!precipAnomaly || precipAnomaly.length < 3) return null;
  const recent = precipAnomaly.slice(-3);
  const avgAnomaly = recent.reduce((sum, d) => sum + d.anomaly_mm, 0) / recent.length;
  if (Math.abs(avgAnomaly) < 5) return null;
  const dir = avgAnomaly > 0 ? 'por encima' : 'por debajo';
  return `Los últimos 3 meses, la precipitación estuvo ${dir} de lo normal (${avgAnomaly > 0 ? '+' : ''}${avgAnomaly.toFixed(0)} mm de anomalía media).`;
}

function _soiContext(soiTrend, soiValue) {
  if (!soiTrend || !soiValue) return null;
  if (soiValue <= -1.5) return 'El SOI fuertemente negativo refuerza la señal El Niño.';
  if (soiValue <= -0.5) return 'El SOI moderadamente negativo es consistente con El Niño.';
  if (soiValue >= 1.5) return 'El SOI fuertemente positivo refuerza la señal La Niña.';
  if (soiValue >= 0.5) return 'El SOI moderadamente positivo es consistente con La Niña.';
  return null;
}

/**
 * Build the advice object for a region.
 */
function getRegionAdvice(regionName, phase, bestCorr, extras) {
  const ext = extras || {};

  if (!bestCorr) {
    return {
      signal: 'none',
      text: `No hay datos de correlación disponibles para <strong>${regionName}</strong>.`,
    };
  }

  const r     = bestCorr.pearson_r;
  const p     = bestCorr.pearson_p;
  const lag   = bestCorr.lag;
  const n     = bestCorr.n_obs;
  const nEff  = bestCorr.n_eff || n;
  const stars = bestCorr.pearson_stars;
  const isSig = p < SIG_THRESHOLD;
  const absR  = Math.abs(r);
  const oni   = ext.oni_value;

  /* CHIRPS snowfall limitation caveat for mountain regions */
  const _chirpsCaveat = (regionName === 'Cuyo' || regionName === 'Patagonia')
    ? ' CHIRPS subrepresenta precipitación nival en alta montaña; la señal ENSO cordillerana puede estar subestimada.'
    : '';

  /* Collapsible statistical detail */
  const statDetail =
    `<details style="margin-top:6px;"><summary style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#79818E;cursor:pointer;">Detalle estadístico ▸</summary>` +
    `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#79818E;">` +
    `r = ${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, p = ${p.toFixed(3)}, ` +
    `n = ${n}, n<sub>eff</sub> = ${nEff}, ${_lagStr(lag)}` +
    `</span></details>`;

  /* Not significant */
  if (!isSig) {
    let text =
      `<strong>${regionName}</strong>: no se detecta relación estadística clara entre el ENSO y la lluvia en esta región (agregación anual).${_chirpsCaveat}`;
    const precip = _precipSummary(ext.precip_anomaly);
    if (precip) text += ' ' + precip;
    text += statDetail;
    return { signal: 'none', text };
  }

  /* ENSO Neutral */
  if (phase === 'Neutral') {
    let text =
      `<strong>${regionName}</strong>: condiciones ENSO Neutral (ONI ${oni != null ? (oni >= 0 ? '+' : '') + oni.toFixed(2) : '?'}). ` +
      `Existe correlación histórica significativa, pero sin fase activa no se proyecta dirección de anomalía.`;
    const soi = _soiContext(ext.soi_trend, ext.soi_value);
    if (soi) text += ' ' + soi;
    const precip = _precipSummary(ext.precip_anomaly);
    if (precip) text += ' ' + precip;
    text += statDetail;
    return { signal: 'neutral', text };
  }

  /* Active phase (El Niño / La Niña) */
  const direction = _precipDirection(phase, r);
  const oniLabel = oni != null ? _oniIntensity(oni) : null;
  const phaseStr = oniLabel && oniLabel !== 'neutral'
    ? `${phase} ${oniLabel}`
    : phase;

  let dirText, implication;
  if (direction === 'excess') {
    dirText     = 'precipitación sobre lo normal';
    implication = 'más lluvia: oportunidad para la campaña agrícola, riesgo de anegamiento para infraestructura';
  } else {
    dirText     = 'precipitación bajo lo normal';
    implication = 'menos lluvia: riesgo de déficit para la campaña agrícola';
  }

  let text =
    `<strong>${regionName}</strong>: fase activa <strong>${phaseStr}</strong>` +
    (oni != null ? ` (ONI ${oni >= 0 ? '+' : ''}${oni.toFixed(2)})` : '') + `. ` +
    `Históricamente, ${dirText} en esta región. <strong>${implication}</strong>.`;

  const soi = _soiContext(ext.soi_trend, ext.soi_value);
  if (soi) text += ' ' + soi;

  const precip = _precipSummary(ext.precip_anomaly);
  if (precip) text += ' ' + precip;

  text += ' Señal estadística. Validar con pronóstico NOAA/IRI.';
  text += statDetail;

  return { signal: direction, text };
}

/* Export */
if (typeof window !== 'undefined') {
  window.getRegionAdvice = getRegionAdvice;
}
