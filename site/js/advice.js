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
  if (a >= ONI_VSTRONG) return t('adv_very_strong');
  if (a >= ONI_STRONG)  return t('adv_strong');
  if (a >= ONI_MOD)     return t('adv_moderate');
  if (a >= ONI_WEAK)    return t('adv_weak');
  return t('adv_neutral');
}

function _precipDirection(phase, r) {
  if (phase === 'El Niño') return r > 0 ? 'excess' : 'deficit';
  return r > 0 ? 'deficit' : 'excess';
}

function _lagStr(lag) {
  if (lag === 0) return t('adv_no_lag');
  if (lag === 1) return t('adv_1m_lag');
  return t('adv_nm_lag', {n: lag});
}

function _precipSummary(precipAnomaly) {
  if (!precipAnomaly || precipAnomaly.length < 3) return null;
  const recent = precipAnomaly.slice(-3);
  const avgAnomaly = recent.reduce((sum, d) => sum + d.anomaly_mm, 0) / recent.length;
  if (Math.abs(avgAnomaly) < 5) return null;
  const dir = avgAnomaly > 0 ? t('adv_above') : t('adv_below');
  return t('adv_precip_summary', {dir, val: (avgAnomaly > 0 ? '+' : '') + avgAnomaly.toFixed(0)});
}

function _soiContext(soiTrend, soiValue) {
  if (!soiTrend || !soiValue) return null;
  if (soiValue <= -1.5) return t('adv_soi_strong_nino');
  if (soiValue <= -0.5) return t('adv_soi_mod_nino');
  if (soiValue >= 1.5) return t('adv_soi_strong_nina');
  if (soiValue >= 0.5) return t('adv_soi_mod_nina');
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
      text: t('adv_no_data', {region: regionName}),
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
    ? t('adv_chirps_caveat')
    : '';

  /* Collapsible statistical detail */
  const statDetail =
    `<details style="margin-top:6px;"><summary style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#79818E;cursor:pointer;">${t('detail_stat_toggle')}</summary>` +
    `<span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#79818E;">` +
    `r = ${r > 0 ? '+' : ''}${r.toFixed(3)}${stars}, p = ${p.toFixed(3)}, ` +
    `n = ${n}, n<sub>eff</sub> = ${nEff}, ${_lagStr(lag)}` +
    `</span></details>`;

  /* Not significant */
  if (!isSig) {
    let text = t('adv_no_relation', {region: regionName}) + _chirpsCaveat;
    const precip = _precipSummary(ext.precip_anomaly);
    if (precip) text += ' ' + precip;
    text += statDetail;
    return { signal: 'none', text };
  }

  /* ENSO Neutral */
  if (phase === 'Neutral') {
    let text = t('adv_neutral_text', {region: regionName, oni: oni != null ? (oni >= 0 ? '+' : '') + oni.toFixed(2) : '?'});
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
    dirText     = t('adv_excess');
    implication = t('adv_excess_impl');
  } else {
    dirText     = t('adv_deficit');
    implication = t('adv_deficit_impl');
  }

  const oniStr = oni != null ? (oni >= 0 ? '+' : '') + oni.toFixed(2) : null;
  let text = t('adv_active_text', {region: regionName, phaseStr, oniStr, dirText, implication});

  const soi = _soiContext(ext.soi_trend, ext.soi_value);
  if (soi) text += ' ' + soi;

  const precip = _precipSummary(ext.precip_anomaly);
  if (precip) text += ' ' + precip;

  text += t('adv_validate');
  text += statDetail;

  return { signal: direction, text };
}

/* Export */
if (typeof window !== 'undefined') {
  window.getRegionAdvice = getRegionAdvice;
}
