/* Runs the actual translation, advice and UI selection code without a DOM.
   Regression protection for stale dates and nominal-p false highlights. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const context = {console, localStorage: {getItem: () => null},
  document: {readyState: 'loading', addEventListener: () => {}},
  navigator: {}, setInterval, clearInterval, setTimeout, Date, performance};
context.window = context;
vm.createContext(context);
for (const name of ['i18n', 'scientific', 'advice', 'main']) {
  vm.runInContext(fs.readFileSync(`site/js/${name}.js`, 'utf8'), context, {filename: name});
}
const rain = ['2025-10-15','2025-11-15','2025-12-15'].map(date => ({date, anomaly_mm: 34}));
const raw = {region:'NEA', lag:0, n_obs:540, n_eff:200, pearson_r:.4,
  pearson_p:.001, pearson_q:.2, pearson_stars:'***'};
for (const lang of ['es','en']) {
  context.I18N._lang = lang;
  const summary = context._precipSummary(rain);
  assert.ok(summary.includes('2025-10') && summary.includes('2025-12'));
  assert.ok(!summary.includes('last 3 months') && !summary.includes('últimos 3 meses'));
  assert.equal(context.getRegionAdvice('NEA','El Niño',raw,{precip_anomaly:rain}).signal,'none');
  assert.equal(context.correlationStars(raw),'');
  assert.ok(context.t('sst_desc').includes('1971–2000'));
  assert.ok(context.t('roni_note').includes('RONI'));
  assert.ok(context.t('observations_asof',{start:'1981-01',end:'2025-12'}).includes('2025-12'));
  assert.ok(context.t('observations_asof',{start:'1981-01',end:'2025-12'}).includes('CHIRPS v3.0'));
  assert.ok(context.t('method_chirps').includes('60°S–60°N'));
  assert.ok(context.t('method_chirps').includes('37–50°S') || context.t('method_chirps').includes('37 y 50°S'));
}
assert.equal(context._precipSummary([rain[0], {...rain[1], date:'2025-09-15'}, rain[2]]), null);
assert.equal(context.correlationQ({...raw, pearson_q:undefined}),1);
assert.equal(context.frequencyQ({p_binomial:.001}),1);
assert.equal(context.frequencySignificant({p_binomial:.001, significant:true}),false);
const corrected = {...raw, pearson_r:.3, pearson_q:.02, pearson_stars:'*'};
assert.equal(context.bestByRegion([raw,corrected],['NEA']).NEA.pearson_r,.3);
assert.equal(context.getRegionAdvice('NEA','El Niño',corrected,{}).signal,'excess');
assert.equal(context.correlationStars(corrected),'*');
console.log('Scientific UI checks passed (ES/EN, dates, missing months, FDR and legacy-cache fallback).');
