import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const listeners = {};
let offline = false;
let networkCalls = 0;
const saved = new Map();
const cache = {
  match: async request => saved.get(request.url)?.clone(),
  put: async (request, response) => saved.set(request.url, response.clone()),
};
const context = {
  URL, Request, Response, console,
  self: {
    location: {origin: 'https://example.test'},
    addEventListener: (name, callback) => { listeners[name] = callback; },
    skipWaiting: () => {},
    clients: {claim: () => {}},
  },
  caches: {open: async () => cache, match: cache.match},
  fetch: async () => {
    networkCalls++;
    if (offline) throw new Error('offline');
    return new Response('current publication');
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('site/sw.js', 'utf8'), context);
async function load(path) {
  const request = new Request('https://example.test' + path);
  let result;
  listeners.fetch({request, respondWith: promise => { result = promise; }});
  return (await result).text();
}
for (const path of ['/data/enso.json', '/js/main.js', '/js/i18n.js']) {
  saved.set('https://example.test' + path, new Response('outdated publication'));
  assert.equal(await load(path), 'current publication');
  offline = true;
  assert.equal(await load(path), 'current publication');
  offline = false;
}
assert.equal(networkCalls, 6);
console.log('Service-worker freshness checks passed: current data and code online, cached fallback offline.');
