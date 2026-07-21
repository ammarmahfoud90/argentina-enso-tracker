/**
 * advice.js — Regional risk advice strings for the Argentina ENSO Tracker.
 *
 * AUDIT NOTE: All text in this file is conditioned on:
 *   1. The current ENSO phase (derived from real ONI via build.py)
 *   2. The best-lag Pearson correlation for the selected region (from correlations.parquet)
 *
 * No data values are hardcoded. All r-values and phase labels are injected
 * at runtime from data/enso.json. Review each template branch carefully.
 *
 * Exported function: getRegionAdvice(regionName, phase, bestCorr)
 *   - regionName: string  e.g. "Pampa Húmeda"
 *   - phase:      string  "El Niño" | "La Niña" | "Neutral"
 *   - bestCorr:   object  { pearson_r, pearson_p, pearson_stars, lag, n_obs }
 *                         or null if no correlation data for region
 *
 * Returns: { signal: "excess"|"deficit"|"neutral"|"none", text: string }
 */

/* ── Significance threshold (must match pipeline: p < 0.05) ── */
const SIG_THRESHOLD = 0.05;
const ONI_NINO  = 0.5;   // NOAA El Niño threshold
const ONI_NINA  = -0.5;  // NOAA La Niña threshold

/**
 * Direction of expected precipitation change given ONI phase + correlation sign.
 *
 * El Niño → high positive ONI.
 *   r > 0 → historically more precip with higher ONI → excess risk.
 *   r < 0 → historically less precip with higher ONI → deficit risk.
 *
 * La Niña → low negative ONI.
 *   r > 0 → historically less precip with lower ONI → deficit risk.
 *   r < 0 → historically more precip with lower ONI → excess risk.
 *
 * @param {string} phase  "El Niño" | "La Niña"
 * @param {number} r      Pearson correlation coefficient
 * @returns {"excess"|"deficit"}
 */
function _precipDirection(phase, r) {
  if (phase === 'El Niño') {
    return r > 0 ? 'excess' : 'deficit';
  }
  // La Niña
  return r > 0 ? 'deficit' : 'excess';
}

/**
 * Human-readable lag string.
 * @param {number} lag
 * @returns {string}
 */
function _lagStr(lag) {
  if (lag === 0) return 'sin retardo (simultáneo)';
  if (lag === 1) return 'con 1 mes de retardo (ONI lidera)';
  return `con ${lag} meses de retardo (ONI lidera)`;
}

/**
 * Returns a qualitative signal label from |r|.
 * @param {number} absR
 * @returns {string}
 */
function _rLabel(absR) {
  if (absR >= 0.35) return 'fuerte';
  if (absR >= 0.20) return 'moderada';
  return 'débil';
}

/**
 * Build the advice object for a region given current phase and correlation data.
 *
 * @param {string} regionName
 * @param {string} phase         "El Niño" | "La Niña" | "Neutral"
 * @param {object|null} bestCorr Correlation record with highest |pearson_r|
 *                               among significant rows, or best non-sig row.
 *                               Fields: pearson_r, pearson_p, pearson_stars, lag, n_obs
 * @returns {{ signal: string, text: string }}
 */
function getRegionAdvice(regionName, phase, bestCorr) {

  /* ── No correlation data available ──────────────────────────────────── */
  if (!bestCorr) {
    return {
      signal: 'none',
      text: `No hay datos de correlación disponibles para <strong>${regionName}</strong>.`,
    };
  }

  const r    = bestCorr.pearson_r;
  const p    = bestCorr.pearson_p;
  const lag  = bestCorr.lag;
  const n    = bestCorr.n_obs;
  const stars = bestCorr.pearson_stars;
  const isSig = p < SIG_THRESHOLD;
  const absR  = Math.abs(r);
  const rSign = r > 0 ? 'positiva' : 'negativa';

  /* ── Correlation not statistically significant ───────────────────────── */
  if (!isSig) {
    return {
      signal: 'none',
      text:
        `<strong>${regionName}</strong>: la correlación ONI–precipitación no es ` +
        `estadísticamente significativa en ningún retardo analizado ` +
        `(mejor r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}, p&nbsp;=&nbsp;${p.toFixed(3)}, ` +
        `n&nbsp;=&nbsp;${n}). ` +
        `No se emite señal direccional — consultar pronóstico oficial NOAA/IRI.`,
    };
  }

  /* ── ENSO Neutral ────────────────────────────────────────────────────── */
  if (phase === 'Neutral') {
    return {
      signal: 'neutral',
      text:
        `<strong>${regionName}</strong>: condiciones ENSO Neutral según ONI (NOAA CPC). ` +
        `La correlación histórica ONI–precipitación es ${rSign} y significativa ` +
        `(r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, ` +
        `p&nbsp;=&nbsp;${p.toFixed(3)}, n&nbsp;=&nbsp;${n}, ${_lagStr(lag)}), ` +
        `pero sin señal de fase activa no se proyecta dirección de anomalía. ` +
        `Consultar fuentes oficiales para pronóstico estacional.`,
    };
  }

  /* ── Active phase (El Niño / La Niña) ───────────────────────────────── */
  const direction = _precipDirection(phase, r);
  const intensity = _rLabel(absR);

  let dirText, implication;
  if (direction === 'excess') {
    dirText     = 'precipitación históricamente sobre lo normal';
    implication = 'riesgo de exceso hídrico';
  } else {
    dirText     = 'precipitación históricamente bajo lo normal';
    implication = 'riesgo de déficit hídrico';
  }

  /* Disclaimer severity: mention that r²→variance-explained */
  const r2pct = Math.round(r * r * 100);

  const text =
    `<strong>${regionName}</strong> · Fase activa: <strong>${phase}</strong>. ` +
    `Correlación histórica ${rSign} ${intensity} ONI–precipitación ` +
    `(r&nbsp;=&nbsp;${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, ` +
    `p&nbsp;=&nbsp;${p.toFixed(3)}, n&nbsp;=&nbsp;${n}, ${_lagStr(lag)}). ` +
    `Históricamente, condiciones ${phase} se asocian con ${dirText} en esta región ` +
    `→ <strong>${implication}</strong>. ` +
    `El ONI explica ~${r2pct}% de la varianza de precipitación regional (r²). ` +
    `Señal estadística — no certeza operacional. Validar con pronóstico NOAA/IRI.`;

  return { signal: direction, text };
}

/* Export for use in index.html inline script */
if (typeof window !== 'undefined') {
  window.getRegionAdvice = getRegionAdvice;
}
