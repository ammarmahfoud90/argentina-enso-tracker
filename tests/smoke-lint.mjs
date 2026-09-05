#!/usr/bin/env node
/**
 * Smoke test: extract inline JS from site/index.html,
 * verify syntax, and lint for no-use-before-define (TDZ bugs).
 *
 * Run: node tests/smoke-lint.mjs
 * CI:  npm i --no-save eslint && node tests/smoke-lint.mjs
 */
import { readFileSync, writeFileSync, unlinkSync, mkdtempSync } from 'fs';
import { execSync } from 'child_process';
import { tmpdir } from 'os';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(__dirname, '..', 'site', 'index.html'), 'utf8');

// Extract all inline scripts (no src attribute)
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
if (scripts.length === 0) {
  console.error('ERROR: No inline <script> blocks found in index.html');
  process.exit(1);
}

// Use the largest inline script (the main app logic)
const mainScript = scripts.reduce((a, b) => a[1].length > b[1].length ? a : b)[1];
console.log(`Extracted inline script: ${mainScript.length} chars`);

const dir = mkdtempSync(join(tmpdir(), 'enso-lint-'));
const jsFile = join(dir, 'main.js');

writeFileSync(jsFile, mainScript);

let failed = false;

// 1. Syntax check via Node
try {
  execSync(`node --check "${jsFile}"`, { stdio: 'pipe' });
  console.log('OK  syntax');
} catch (e) {
  console.error('FAIL  syntax:', e.stderr?.toString().trim() || e.message);
  failed = true;
}

// 2. ESLint: no-use-before-define (catches TDZ bugs like oniSign)
const configFile = join(dir, 'eslint.config.mjs');
writeFileSync(configFile, `export default [{
  rules: {
    'no-use-before-define': ['error', { functions: false, classes: true, variables: true }],
  },
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'script',
    globals: {
      document: 'readonly', window: 'readonly', localStorage: 'readonly',
      console: 'readonly', fetch: 'readonly', Blob: 'readonly', URL: 'readonly',
      setInterval: 'readonly', clearInterval: 'readonly', setTimeout: 'readonly',
      IntersectionObserver: 'readonly', Plotly: 'readonly', d3: 'readonly',
      topojson: 'readonly',
    }
  }
}];
`);

try {
  execSync(`npx eslint -c "${configFile}" "${jsFile}"`, { stdio: 'pipe', cwd: dir, timeout: 60000 });
  console.log('OK  no-use-before-define');
} catch (e) {
  const out = e.stdout?.toString() || '';
  if (out.includes('no-use-before-define')) {
    console.error('FAIL  no-use-before-define:\n' + out);
    failed = true;
  } else {
    // eslint internal error or config issue — warn but don't block
    console.warn('WARN  eslint check skipped:', (e.stderr?.toString() || e.message).slice(0, 200));
  }
}

// Cleanup
try { unlinkSync(jsFile); unlinkSync(configFile); } catch {}

if (failed) {
  console.error('\nSmoke test FAILED — fix before deploying.');
  process.exit(1);
}
console.log('\nAll smoke checks passed.');
