import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const source = (await readFile(new URL('../assets/editor.js', import.meta.url), 'utf8')).replace(/\nstart\(\);\s*$/, '\n');
function editor() {
  const context = vm.createContext({ location: { pathname: '/TVSources/' }, URL });
  vm.runInContext(source, context);
  return context;
}

test('source-only configuration validates and exports without recreating vod.movies', async () => {
  const context = editor();
  const input = JSON.parse(await readFile(new URL('../data/library.json', import.meta.url), 'utf8'));
  delete input.vod.movies; context.input = input;
  const before = JSON.stringify(input);
  const out = JSON.parse(vm.runInContext('JSON.stringify(editableConfig(validate(input)))', context));
  assert.equal(Object.hasOwn(out.vod, 'movies'), false);
  assert.deepEqual(out.vod.sites, input.vod.sites);
  assert.equal(JSON.stringify(input), before);
  for (const bad of [null, {}, 'not-an-array']) {
    context.input = structuredClone(input); context.input.vod.movies = bad;
    assert.throws(() => vm.runInContext('validate(input)', context), /movies.*数组/);
  }
  context.input = structuredClone(input); context.input.vod.movies = [];
  assert.doesNotThrow(() => vm.runInContext('validate(input)', context));
});

test('copying project JSON keeps the M3U reference without a second editable copy of its channels', () => {
  const context = editor();
  const input = { live: { channelFile: 'live.m3u', channels: [{ name: '我的频道' }] }, vod: { sites: [{ name: '接口' }] } };
  context.input = input;
  const out = JSON.parse(vm.runInContext('JSON.stringify(editableConfig(input))', context));
  assert.deepEqual(out.live, { channelFile: 'live.m3u', channels: [] });
  assert.deepEqual(out.vod, input.vod);
  assert.equal(input.live.channels.length, 1);
  const legacy = { live: { channels: [{ name: 'JSON 频道' }] } }; context.input = legacy;
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(editableConfig(input))', context)), legacy);
});

test('channel edits exported as M3U round-trip names, groups, logos, disabled state, routes and headers', () => {
  const context = editor();
  const channels = [{ name: '频道,一', group: '游戏,直播 & "其他"', tvgId: 'one', logo: 'https://example.com/logo?a=1&b=2',
    urls: ['https://example.com/a?sign=a%2Fb#keep', 'https://example.com/backup?id=1,2'],
    headers: { 'User-Agent': 'Player', Referer: 'https://example.com/', 'X-Example': 'public=value' }, enabled: false }];
  context.channels = channels;
  const m3u = vm.runInContext('channelsM3u(channels)', context);
  const script = 'import importlib.util,json,sys; s=importlib.util.spec_from_file_location("builder", sys.argv[1]); b=importlib.util.module_from_spec(s); s.loader.exec_module(b); print(json.dumps(b.parse_m3u(sys.stdin.read()),ensure_ascii=False))';
  const result = execFileSync('python3', ['-c', script, fileURLToPath(new URL('../scripts/build-source-site.py', import.meta.url))], { input: m3u, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  assert.deepEqual(JSON.parse(result), channels);
});

test('M3U export rejects request headers that could introduce playlist lines', () => {
  const context = editor();
  context.channels = [{ name: '频道', urls: ['https://example.com/live'], headers: { 'User-Agent': 'Player\nhttps://other.example/' } }];
  assert.throws(() => vm.runInContext('channelsM3u(channels)', context), /请求头/);
});

test('M3U export keeps player options without accepting extra playlist lines', () => {
  const context = editor();
  context.channels = [{ name: '频道', urls: ['https://example.com/live.mpd'], directives: ['#KODIPROP:inputstream.adaptive.manifest_type=mpd', '#EXTVLCOPT:network-caching=1000'] }];
  const result = vm.runInContext('channelsM3u(channels)', context);
  assert.ok(result.includes('#KODIPROP:inputstream.adaptive.manifest_type=mpd\n#EXTVLCOPT:network-caching=1000\nhttps://example.com/live.mpd'));
  for (const directive of ['#KODIPROP:x=y\nhttps://other.example/', '#EXTHTTP:{}', 'https://other.example/']) {
    context.channels[0].directives = [directive];
    assert.throws(() => vm.runInContext('channelsM3u(channels)', context), /播放选项/);
  }
});

test('URL-based M3U stays a playlist link when copying configuration', () => {
  const context = editor();
  context.input = { live: { channelFile: 'live.m3u', channels: [{ name: '旧草稿频道' }], playlists: [{ name: '我的 M3U', url: 'https://example.com/data/live.m3u' }] } };
  vm.runInContext("hosting = { channelFile: 'data/live.m3u' }", context);
  const result = JSON.parse(vm.runInContext('JSON.stringify(editableConfig(input))', context));
  assert.equal(Object.hasOwn(result.live, 'channelFile'), false); assert.deepEqual(result.live.channels, []);
  assert.deepEqual(result.live.playlists, context.input.live.playlists); assert.equal(context.input.live.channels.length, 1);
});
