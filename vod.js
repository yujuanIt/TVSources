// Personal static catalog adapter for 居安影院's existing JavaScript spider interface.
// Pages hosts metadata; the player requests the original video with its original headers.
let address = '';
let catalog = null;
let loadedAt = 0;

async function load() {
  if (catalog && Date.now() - loadedAt < 60000) return catalog;
  if (!/^https?:\/\//i.test(address)) throw new Error('个人片库地址无效');
  const response = await req(address + (address.indexOf('?') < 0 ? '?' : '&') + '_t=' + Math.floor(Date.now() / 60000), { timeout: 15000 });
  if (Number(response.code) !== 200) throw new Error('个人片库暂时无法读取');
  const data = JSON.parse(response.content);
  if (!Array.isArray(data.movies) || !Array.isArray(data.categories)) throw new Error('个人片库格式无效');
  catalog = data; loadedAt = Date.now();
  return data;
}

function visible(data) { return data.movies.filter(movie => movie.enabled !== false); }
function movieItem(movie, full) {
  const item = {
    vod_id: movie.id, vod_name: movie.name, vod_pic: movie.poster || '',
    vod_year: movie.year || '', type_id: movie.category,
    type_name: movie.typeName || '', vod_remarks: movie.remarks || '',
    vod_content: movie.description || '', vod_actor: movie.actor || '',
    vod_director: movie.director || '', vod_area: movie.area || ''
  };
  if (full) {
    item.vod_play_from = movie.routes.map(route => route.name).join('$$$');
    item.vod_play_url = movie.routes.map((route, r) => route.episodes.map((episode, e) =>
      episode.name + '$juan:' + movie.id + ':' + r + ':' + e).join('#')).join('$$$');
  }
  return item;
}
function page(items, number) {
  return JSON.stringify({ page: Number(number) || 1, pagecount: 1, total: items.length, limit: items.length,
    list: Number(number || 1) === 1 ? items.map(movie => movieItem(movie, false)) : [] });
}

export default {
  async init(ext) {
    address = typeof ext === 'string' ? ext : ext.url || ext.ext || '';
    catalog = null; loadedAt = 0;
    await load();
  },
  async home() {
    const data = await load();
    return JSON.stringify({ class: data.categories.map(c => ({ type_id: c.id, type_name: c.name })),
      page: 1, pagecount: 1, list: visible(data).map(movie => movieItem(movie, false)) });
  },
  async homeVod() { return page(visible(await load()), 1); },
  async category(tid, pg) {
    return page(visible(await load()).filter(movie => tid === 'all' || movie.category === tid), pg);
  },
  async detail(id) {
    const ids = String(id).split(',');
    return JSON.stringify({ list: visible(await load()).filter(movie => ids.indexOf(movie.id) >= 0).map(movie => movieItem(movie, true)) });
  },
  async search(word, quick, pg) {
    const query = String(word || '').trim().toLowerCase();
    return page(visible(await load()).filter(movie => movie.name.toLowerCase().indexOf(query) >= 0), pg || 1);
  },
  async play(flag, id) {
    const parts = /^juan:([A-Za-z0-9_-]+):(\d+):(\d+)$/.exec(String(id));
    if (!parts) throw new Error('影片标识无效，请刷新片库');
    const movie = visible(await load()).find(item => item.id === parts[1]);
    const route = movie && movie.routes[Number(parts[2])];
    const episode = route && route.episodes[Number(parts[3])];
    if (!episode) throw new Error('这集已从个人片库移除，请刷新片库');
    return JSON.stringify({ parse: movie.sniff === true ? 1 : 0, url: episode.url,
      header: { ...(movie.headers || {}), ...(route.headers || {}), ...(episode.headers || {}) } });
  },
  sniffer() { return false; },
  isVideo() { return false; },
  destroy() { catalog = null; loadedAt = 0; address = ''; }
};
