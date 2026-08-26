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

/**
 * Classify ONI magnitude into intensity label.
 * @param {number} oni  Absolute ONI value
 * @returns {string}
 */
function _oniIntensity(oni) {
  const a = Math.abs(oni);
  if (a >= ONI_VSTRONG) return 'muy fuerte';
  if (a >= ONI_STRONG)  return 'fuerte';
  if (a >= ONI_MOD)     return 'moderado';
  if (a >= ONI_WEAK)    return 'débil';
  return 'neutral';
}

/**
 * Direction of expected precipitation change given phase + correlation sign.
 */
function _precipDirection(phase, r) {
  if (phase === 'El Niño') return r > 0 ? 'excess' : 'deficit';
  return r > 0 ? 'deficit' : 'excess';
}

function _lagStr(lag) {
  if (lag === 0) return 'sin retardo (simultáneo)';
  if (lag === 1) return 'con 1 mes de retardo';
  return `con ${lag} meses de retardo`;
}

function _rLabel(absR) {
  if (absR >= 0.35) return 'fuerte';
  if (absR >= 0.20) return 'moderada';
  return 'débil';
}

/**
 * Summarize recent precipitation anomaly for a region.
 * @param {Array} precipAnomaly  Array of {date, month, anomaly_mm}
 * @returns {string|null}  Summary text or null if no data
 */
function _precipSummary(precipAnomaly) {
  if (!precipAnomaly || precipAnomaly.length < 3) return null;
  const recent = precipAnomaly.slice(-3);
  const avgAnomaly = recent.reduce((sum, d) => sum + d.anomaly_mm, 0) / recent.length;
  if (Math.abs(avgAnomaly) < 5) return null; // negligible
  const dir = avgAnomaly > 0 ? 'por encima' : 'por debajo';
  return `Los últimos 3 meses muestran precipitación ${dir} de lo normal (anomalía media: ${avgAnomaly > 0 ? '+' : ''}${avgAnomaly.toFixed(0)} mm).`;
}

/**
 * SOI trend context for the advice.
 * @param {object} soiTrend  {label, color} from soiTrend()
 * @param {number} soiValue  Current SOI value
 * @returns {string|null}
 */
function _soiContext(soiTrend, soiValue) {
  if (!soiTrend || !soiValue) return null;
  if (soiValue <= -1.5) return 'El SOI fuertemente negativo refuerza la señal El Niño.';
  if (soiValue <= -0.5) return 'El SOI moderadamente negativo es consistente con tendencia El Niño.';
  if (soiValue >= 1.5) return 'El SOI fuertemente positivo refuerza la señal La Niña.';
  if (soiValue >= 0.5) return 'El SOI moderadamente positivo es consistente con tendencia La Niña.';
  return null;
}

/**
 * Build the advice object for a region.
 *
 * @param {string} regionName
 * @param {string} phase         "El Niño" | "La Niña" | "Neutral"
 * @param {object|null} bestCorr {pearson_r, pearson_p, pearson_stars, lag, n_obs}
 * @param {object} extras        Optional: {oni_value, soi_value, soi_trend, precip_anomaly}
 * @returns {{ signal: string, text: string }}
 */
function getRegionAdvice(regionName, phase, bestCorr, extras) {
  const ext = extras || {};

  /* ── No correlation data ── */
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
  const stars = bestCorr.pearson_stars;
  const isSig = p < SIG_THRESHOLD;
  const absR  = Math.abs(r);
  const rSign = r > 0 ? 'positiva' : 'negativa';
  const oni   = ext.oni_value;

  /* ── Correlation not significant ── */
  if (!isSig) {
    let text =
      `<strong>${regionName}</strong>: la correlación ONI–precipitación no es ` +
      `estadísticamente significativa ` +
      `(mejor r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}, p&nbsp;=&nbsp;${p.toFixed(3)}, ` +
      `n&nbsp;=&nbsp;${n}). No se emite señal direccional.`;
    const precip = _precipSummary(ext.precip_anomaly);
    if (precip) text += ' ' + precip;
    return { signal: 'none', text };
  }

  /* ── ENSO Neutral ── */
  if (phase === 'Neutral') {
    let text =
      `<strong>${regionName}</strong>: condiciones ENSO Neutral (ONI ${oni != null ? (oni >= 0 ? '+' : '') + oni.toFixed(2) : '—'}). ` +
      `Correlación histórica ${rSign} significativa ` +
      `(r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, ${_lagStr(lag)}), ` +
      `pero sin fase activa no se proyecta dirección de anomalía.`;
    const soi = _soiContext(ext.soi_trend, ext.soi_value);
    if (soi) text += ' ' + soi;
    const precip = _precipSummary(ext.precip_anomaly);
    if (precip) text += ' ' + precip;
    return { signal: 'neutral', text };
  }

  /* ── Active phase (El Niño / La Niña) ── */
  const direction = _precipDirection(phase, r);
  const intensity = _rLabel(absR);
  const r2pct = Math.round(r * r * 100);

  /* ONI intensity grading */
  const oniLabel = oni != null ? _oniIntensity(oni) : null;
  const phaseStr = oniLabel && oniLabel !== 'neutral'
    ? `${phase} ${oniLabel}`
    : phase;

  let dirText, implication;
  if (direction === 'excess') {
    dirText     = 'precipitación históricamente sobre lo normal';
    implication = 'riesgo de exceso hídrico';
  } else {
    dirText     = 'precipitación históricamente bajo lo normal';
    implication = 'riesgo de déficit hídrico';
  }

  let text =
    `<strong>${regionName}</strong> · Fase activa: <strong>${phaseStr}</strong>` +
    (oni != null ? ` (ONI ${oni >= 0 ? '+' : ''}${oni.toFixed(2)})` : '') + `. ` +
    `Correlación ${rSign} ${intensity} ` +
    `(r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, ` +
    `n&nbsp;=&nbsp;${n}, ${_lagStr(lag)}). ` +
    `Históricamente: ${dirText} → <strong>${implication}</strong>. ` +
    `R² = ${r2pct}% de la varianza explicada.`;

  /* Append SOI context */
  const soi = _soiContext(ext.soi_trend, ext.soi_value);
  if (soi) text += ' ' + soi;

  /* Append precipitation obs */
  const precip = _precipSummary(ext.precip_anomaly);
  if (precip) text += ' ' + precip;

  text += ' Señal estadística — validar con pronóstico NOAA/IRI.';

  return { signal: direction, text };
}

/* Export */
if (typeof window !== 'undefined') {
  window.getRegionAdvice = getRegionAdvice;
}
