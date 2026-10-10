/* Validate the actual files deployed together, including observation hashes. */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';

const read = path => JSON.parse(fs.readFileSync(path, 'utf8'));
const digest = path => crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex');
const data = read('site/data/enso.json');
const history = read('site/data/enso-history.json');
const manifest = read('data/processed/observations_refresh.json');
const migration = read('data/processed/chirps_v3_migration.json');
const metadata = data.precipitation_metadata;
assert.equal(data.scientific_methodology.version, '3.0.0');
assert.deepEqual(data.scientific_methodology.calibration_period, [1981, 2025]);
assert.equal(metadata.source, 'CHIRPS v3.0');
assert.equal(metadata.dataset_id, 'CHIRPS-v3.0-final-monthly');
assert.equal(metadata.product_status, 'final');
assert.equal(metadata.units, 'mm/month');
assert.deepEqual(metadata.global_latitude_coverage, [-60, 60]);
assert.equal(metadata.regional_coverage.Patagonia.lat_min, -50);
assert.equal(metadata.regional_coverage.Patagonia.lat_max, -37);
assert.equal(manifest.sources.precipitation.dataset_id, metadata.dataset_id);
assert.deepEqual(data.observation_refresh, manifest);
assert.equal(manifest.sources.precipitation.sha256, digest('data/processed/oni_precip_pairs.parquet'));
assert.equal(manifest.sources.temperature.sha256, digest('data/processed/oni_temp_pairs.parquet'));
assert.equal(migration.v2_archive_sha256, digest('data/processed/oni_precip_pairs_v2.parquet'));
assert.equal(migration.dataset_id, metadata.dataset_id);
assert.equal(migration.monthly_sources.length, migration.months);
for (const region of data.region_order) {
  const current = data.spi_current[region];
  assert.equal(current.date.slice(0, 7), metadata.latest_complete_month);
  const tail = history.spi_series[region].at(-1);
  assert.equal(tail.date, current.date);
  assert.equal(tail.spi, current.spi);
  assert.equal(tail.classification, current.classification);
  assert.deepEqual(history.spi_series[region], data.spi_series[region]);
}
assert.ok(data.frequency_methodology.data_source.includes('CHIRPS v3.0'));
console.log(`Publication checks passed: coherent CHIRPS v3 data, archive, manifest and SPI through ${metadata.latest_complete_month}.`);
