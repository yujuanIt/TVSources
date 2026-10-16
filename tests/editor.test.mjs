import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const source = (await readFile(new URL('../assets/editor.js', import.meta.url), 'utf8')).replace(/\nstart\(\);\s*$/, '\n');
const manifest = JSON.parse(await readFile(new URL('../data/library.json', import.meta.url), 'utf8'));
const sites = JSON.parse(await readFile(new URL('../data/vod-sites.json', import.meta.url), 'utf8'));
const maintained = { ...manifest, vod: { ...manifest.vod, ...Object.fromEntries(Object.entries(sites).filter(([key]) => key !== 'version')) } };
function editor(input = maintained) {
  const context = vm.createContext({ location: { pathname: '/TVSources/' }, URL, input: structuredClone(input) });
  vm.runInContext(source, context);
  return context;
}

test('manifest and site file export separately with all owner decisions and dependencies intact', () => {
  const context = editor(); vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportConfig()', context)), manifest);
  assert.deepEqual(JSON.parse(vm.runInContext('exportSites()', context)), sites);
  context.library = structuredClone(manifest); context.sites = structuredClone(sites);
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(attachSites(library, sites))', context)), maintained);
  context.sites.sites[0].name = '自己改的名称'; context.sites.sites[0].enabled = false;
  vm.runInContext('data = attachSites(library, sites)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportConfig()', context)), manifest);
  assert.equal(JSON.parse(vm.runInContext('exportSites()', context)).sites[0].name, '自己改的名称');
  assert.equal(JSON.parse(vm.runInContext('exportSites()', context)).sites[0].enabled, false);
});

test('external document validation rejects inlined sites, missing arrays and unsupported lists', () => {
  for (const change of [(root, sites) => root.vod.sites = [], (root, sites) => delete sites.sites,
    (root, sites) => sites.warehouses = [], (root, sites) => sites.version = 2,
    (root, sites) => root.vod.url = 'file:///private']) {
    const context = editor(); context.library = structuredClone(manifest); context.sites = structuredClone(sites);
    change(context.library, context.sites);
    assert.throws(() => vm.runInContext('attachSites(library, sites)', context));
  }
});

test('configuration exports exactly the three maintained source lists without adding fields', () => {
  const context = editor(); const before = JSON.stringify(context.input);
  vm.runInContext('data = validate(input)', context);
  const output = JSON.parse(vm.runInContext('exportDraft()', context));
  assert.deepEqual(output, maintained); assert.equal(JSON.stringify(context.input), before);
  assert.deepEqual(Object.keys(output.live), ['name', 'playlists']);
  assert.deepEqual(Object.keys(output.vod), Object.keys(maintained.vod));
  context.input = output;
  vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportDraft()', context)), output);
});

test('removed channel and movie fields are rejected rather than preserved or converted', () => {
  for (const [owner, key] of [['live', 'channels'], ['live', 'channelFile'], ['vod', 'categories'], ['vod', 'movies']]) {
    for (const value of [[], [{ name: '不属于订阅配置' }], null, {}]) {
      const context = editor(); context.input[owner][key] = value;
      assert.throws(() => vm.runInContext('validate(input)', context), new RegExp(owner + ' 仅支持'));
    }
  }
});

test('required source lists cannot be missing or replaced with malformed values', () => {
  for (const [owner, key] of [['live', 'playlists'], ['vod', 'sites'], [null, 'warehouses']]) {
    for (const value of [null, {}, 'not-an-array']) {
      const context = editor(); const parent = owner ? context.input[owner] : context.input;
      parent[key] = value;
      assert.throws(() => vm.runInContext('validate(input)', context), new RegExp(key + '.*数组'));
      delete parent[key];
      assert.throws(() => vm.runInContext('validate(input)', context), new RegExp(key + '.*数组'));
    }
  }
});

test('exports preserve disabled sources, signed URLs, headers and all plugin parameters', () => {
  const input = structuredClone(maintained);
  input.live.playlists = [{ name: '我的直播', url: 'https://example.com/live.txt?sign=a+b%2F#keep', headers: { 'User-Agent': 'TV Player', Referer: 'https://example.com/' }, enabled: false }];
  input.vod.spider = 'https://example.com/spider.jar;md5;abc';
  input.vod.sites = [{ key: 'spider', name: '片库', type: 3, api: 'csp_Test', searchable: 1,
    headers: { Cookie: 'fixture=keep' }, ext: { value: 'literal$#', url: 'https://example.com/ext?sign=a%2Bb' } }];
  input.warehouses = [{ name: '完整配置', url: 'https://example.com/box.json?sign=a%2Bb%2F', enabled: false }];
  const context = editor(input); vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportDraft()', context)), input);
});

test('empty lists are valid and do not create personal movie or channel entries', () => {
  const input = { version: 1, name: '我的源', live: { name: '直播', playlists: [] }, vod: { name: '点播', url: 'https://example.com/data/vod-sites.json', sites: [] }, warehouses: [] };
  const context = editor(input); vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportDraft()', context)), input);
});

test('invalid source URLs, duplicate site keys and invalid switches are rejected', () => {
  for (const change of [input => input.live.playlists[0].url = 'file:///private',
    input => input.vod.sites[0].api = 'javascript:alert(1)',
    input => input.vod.sites.push(structuredClone(input.vod.sites[0])),
    input => input.warehouses.push({ name: '配置', url: 'https://example.com/box.json', enabled: 'true' })]) {
    const context = editor(); change(context.input);
    assert.throws(() => vm.runInContext('validate(input)', context));
  }
});

test('scoped keys preserve dependencies and manual metadata without exposing an expansion UI', () => {
  const input = { version: 1, name: '我的源', live: { name: '直播', playlists: [] },
    vod: { name: '点播', url: 'https://example.com/data/vod-sites.json', sites: [], contexts: {} }, warehouses: [] };
  for (const key of ['one', 'two']) {
    input.vod.contexts[key] = { name: key, url: 'https://example.com/' + key + '/box.json', spider: './engine.jar' };
    input.vod.sites.push({ context: key, key: '中文站点', name: '自己命名', type: 3, api: 'csp_Test', _syncId: key, origin: { source: key }, searchable: 0 });
  }
  const context = editor(input); vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportDraft()', context)), input);
  delete input.vod.contexts.one;
  assert.throws(() => vm.runInContext('validate(input)', editor(input)), /不存在/);
});
