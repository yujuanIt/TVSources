import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const source = (await readFile(new URL('../assets/editor.js', import.meta.url), 'utf8')).replace(/\nstart\(\);\s*$/, '\n');
const maintained = JSON.parse(await readFile(new URL('../data/library.json', import.meta.url), 'utf8'));
function editor(input = maintained) {
  const context = vm.createContext({ location: { pathname: '/TVSources/' }, URL, input: structuredClone(input) });
  vm.runInContext(source, context);
  return context;
}

test('configuration exports exactly the three maintained source lists without adding fields', () => {
  const context = editor(); const before = JSON.stringify(context.input);
  vm.runInContext('data = validate(input)', context);
  const output = JSON.parse(vm.runInContext('exportConfig()', context));
  assert.deepEqual(output, maintained); assert.equal(JSON.stringify(context.input), before);
  assert.deepEqual(Object.keys(output.live), ['name', 'playlists']);
  assert.deepEqual(Object.keys(output.vod), ['name', 'sites']);
  context.input = output;
  vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportConfig()', context)), output);
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
  assert.deepEqual(JSON.parse(vm.runInContext('exportConfig()', context)), input);
});

test('empty lists are valid and do not create personal movie or channel entries', () => {
  const input = { version: 1, name: '我的源', live: { name: '直播', playlists: [] }, vod: { name: '点播', sites: [] }, warehouses: [] };
  const context = editor(input); vm.runInContext('data = validate(input)', context);
  assert.deepEqual(JSON.parse(vm.runInContext('exportConfig()', context)), input);
});

test('invalid source URLs, duplicate site keys and invalid switches are rejected', () => {
  for (const change of [input => input.live.playlists[0].url = 'file:///private',
    input => input.vod.sites[0].api = 'javascript:alert(1)',
    input => input.vod.sites.push(structuredClone(input.vod.sites[0])),
    input => input.warehouses[0].enabled = 'true']) {
    const context = editor(); change(context.input);
    assert.throws(() => vm.runInContext('validate(input)', context));
  }
});
