import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';

const source = await readFile(new URL('../assets/vod.js', import.meta.url), 'utf8');
const fixture = {
  categories: [{ id: 'movie', name: '电影' }, { id: 'series', name: '电视剧' }],
  movies: [
    { id: 'film-a', name: '我的电影', category: 'movie', typeName: '电影', year: '2026',
      headers: { 'User-Agent': 'Personal Player', Referer: 'https://origin.example/' },
      routes: [{ name: '高清', headers: { Referer: 'https://route.example/' }, episodes: [
        { name: '正片', url: 'https://video.example/film.m3u8?signature=a%2Bb#fragment$literal', headers: { Cookie: 'session=keep' } }
      ] }] },
    { id: 'series-b', name: '我的电视剧', category: 'series', typeName: '电视剧',
      routes: [{ name: '主线', episodes: [{ name: '第01集', url: 'https://video.example/1.m3u8' }, { name: '第02集', url: 'https://video.example/2.m3u8' }] },
               { name: '备用', episodes: [{ name: '第01集', url: 'https://video.example/backup.m3u8' }] }] },
    { id: 'hidden', name: '已停用的影片', category: 'movie', enabled: false, routes: [] }
  ]
};
async function adapter(data = fixture, responseCode = 200) {
  let calls = 0;
  const context = vm.createContext({ req: async () => { calls++; return { code: responseCode, content: JSON.stringify(data) }; } });
  const module = new vm.SourceTextModule(source, { context }); await module.link(() => { throw new Error('No external module expected'); }); await module.evaluate();
  return { spider: module.namespace.default, calls: () => calls };
}
test('home, category and search return the correct local content without repeating pages', async () => {
  const { spider } = await adapter(); await spider.init('https://example.com/catalog.json');
  assert.equal(JSON.parse(await spider.home()).class[1].type_id, 'series');
  assert.deepEqual(JSON.parse(await spider.category('series', '1')).list.map(x => x.vod_id), ['series-b']);
  assert.deepEqual(JSON.parse(await spider.search('我的电影', false, '1')).list.map(x => x.vod_id), ['film-a']);
  assert.deepEqual(JSON.parse(await spider.search('我的', false, '2')).list, []);
  assert.equal(JSON.parse(await spider.homeVod()).list.length, 2);
});
test('details match the requested film ID and never fall back to the first item', async () => {
  const { spider } = await adapter(); await spider.init('https://example.com/catalog.json');
  const details = JSON.parse(await spider.detail('series-b')).list;
  assert.equal(details.length, 1); assert.equal(details[0].vod_name, '我的电视剧');
  assert.equal(details[0].vod_play_from, '主线$$$备用');
  assert.equal(JSON.parse(await spider.detail('unknown')).list.length, 0);
  assert.equal(JSON.parse(await spider.detail('hidden')).list.length, 0);
});
test('opaque episode IDs preserve signed URLs and all request-header layers', async () => {
  const { spider } = await adapter(); await spider.init('https://example.com/catalog.json');
  const detail = JSON.parse(await spider.detail('film-a')).list[0];
  const token = detail.vod_play_url.split('$')[1]; const playback = JSON.parse(await spider.play('高清', token));
  assert.equal(playback.url, fixture.movies[0].routes[0].episodes[0].url);
  assert.deepEqual(playback.header, { 'User-Agent': 'Personal Player', Referer: 'https://route.example/', Cookie: 'session=keep' });
  assert.equal(playback.parse, 0);
});
test('alternate routes select the correct episode rather than an adjacent item', async () => {
  const { spider } = await adapter(); await spider.init('https://example.com/catalog.json');
  assert.equal(JSON.parse(await spider.play('主线', 'juan:series-b:0:1')).url, 'https://video.example/2.m3u8');
  assert.equal(JSON.parse(await spider.play('备用', 'juan:series-b:1:0')).url, 'https://video.example/backup.m3u8');
  await assert.rejects(spider.play('', 'juan:series-b:1:1'), /已从个人片库移除/);
});
test('unrecognized addresses and stale or hidden episode tokens are rejected', async () => {
  const { spider } = await adapter(); await spider.init('https://example.com/catalog.json');
  await assert.rejects(spider.play('', 'https://unlisted.example/movie.m3u8'), /标识无效/);
  await assert.rejects(spider.play('', 'juan:hidden:0:0'), /已从个人片库移除/);
});
test('the catalog is cached briefly and a failed init does not silently use stale data', async () => {
  const good = await adapter(); await good.spider.init('https://example.com/catalog.json');
  await good.spider.home(); await good.spider.search('电影', false); assert.equal(good.calls(), 1);
  const bad = await adapter(fixture, 403); await assert.rejects(bad.spider.init('https://example.com/catalog.json'), /暂时无法读取/);
  await good.spider.destroy(); await assert.rejects(good.spider.home(), /地址无效/);
});
test('explicit web-page sniffing is retained for personal movie entries', async () => {
  const data = structuredClone(fixture); data.movies[0].sniff = true;
  const { spider } = await adapter(data); await spider.init({ url: 'https://example.com/catalog.json' });
  assert.equal(JSON.parse(await spider.play('', 'juan:film-a:0:0')).parse, 1);
});
