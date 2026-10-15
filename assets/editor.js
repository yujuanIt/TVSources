const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const pretty = value => JSON.stringify(value, null, 2) + '\n';
const draftKey = 'juan-source-draft:' + location.pathname.replace(/index\.html$/, '');
const labels = { playlists: '直播列表', channels: '频道', sites: '点播接口', movies: '影片', warehouses: '多仓配置' };
let data, online, hosting, undo = [], editing = null, toastTimer;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, action, className = 'quiet') {
  const node = element('button', text, className); node.type = 'button'; node.onclick = action; return node;
}
function notice(text) {
  $('toast').textContent = text; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5200);
}
function check(condition, message) { if (!condition) throw new Error(message); }
function m3uLinkMode() { return hosting?.channelFile === 'data/live.m3u'; }
function editableConfig(value) {
  const next = clone(value);
  if (next.live.channelFile || m3uLinkMode()) next.live.channels = [];
  if (m3uLinkMode()) delete next.live.channelFile;
  return next;
}
function channelsM3u(channels) {
  const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const lines = ['#EXTM3U'];
  for (const item of channels) {
    const attrs = Object.entries({ 'tvg-id': item.tvgId || '', 'tvg-name': item.name, 'tvg-logo': item.logo || '', 'group-title': item.group || '未分组', 'x-enabled': item.enabled === false ? 'false' : 'true' }).map(([key, value]) => key + '="' + escape(value) + '"').join(' ');
    for (const address of item.urls) {
      lines.push('#EXTINF:-1 ' + attrs + ',' + item.name);
      for (const directive of item.directives || []) {
        check(typeof directive === 'string' && !/[\r\n\u0000-\u001f\u007f]/.test(directive) && /^(#KODIPROP:|#EXTVLCOPT:)/.test(directive), '播放选项需要使用单行 KODIPROP / EXTVLCOPT');
        lines.push(directive);
      }
      for (const [name, value] of Object.entries(item.headers || {})) {
        check(typeof value === 'string' && !/[\r\n\u0000]/.test(value), '请求头需要不含换行的文字');
        if (name.toLowerCase() === 'user-agent') lines.push('#EXTVLCOPT:http-user-agent=' + value);
        if (name.toLowerCase() === 'referer') lines.push('#EXTVLCOPT:http-referrer=' + value);
      }
      if (Object.keys(item.headers || {}).length) lines.push('#EXTHTTP:' + JSON.stringify(item.headers));
      lines.push(address);
    }
  }
  return lines.join('\n') + '\n';
}
function validate(value) {
  check(value && value.version === 1 && typeof value.name === 'string' && value.name.trim(), '需要有效的 version: 1 与源站名称');
  check(value.live && value.vod && value.live.name && value.vod.name, '请填写直播与点播片库名称');
  check(value.live.channelFile === undefined || ['live.m3u', 'data/live.m3u'].includes(value.live.channelFile), 'channelFile 需要使用本站 M3U 文件');
  const movies = value.vod.movies === undefined ? [] : value.vod.movies;
  for (const [name, list] of Object.entries({ playlists: value.live.playlists, channels: value.live.channels, sites: value.vod.sites, movies, categories: value.vod.categories, warehouses: value.warehouses })) {
    check(Array.isArray(list), name + ' 必须是数组');
    list.forEach(row => { check(row && typeof row === 'object' && !Array.isArray(row), name + ' 的每项必须是对象'); check(row.enabled === undefined || typeof row.enabled === 'boolean', 'enabled 需要填写 true / false'); });
  }
  const safeUrl = (url, live = false) => { try { const u = new URL(url); return (live ? ['http:', 'https:', 'rtsp:', 'rtmp:', 'udp:', 'rtp:'] : ['http:', 'https:']).includes(u.protocol) && !!u.hostname && !u.username && !u.password && !/[\s\u0000-\u001f]/.test(url); } catch { return false; } };
  value.live.playlists.forEach(row => check(row.name && safeUrl(row.url), '直播列表需要名称和完整的 HTTP(S) 地址'));
  value.live.channels.forEach(row => { check(row.name && Array.isArray(row.urls) && row.urls.length && row.urls.every(url => safeUrl(url, true)), '频道需要名称和至少一条有效线路'); check(!row.logo || safeUrl(row.logo), '频道图标需要 HTTP(S) 地址'); });
  const ids = new Set(), categories = new Set(value.vod.categories.map(c => c.id));
  movies.forEach(row => {
    check(row.name && /^[\w-]+$/.test(row.id) && !ids.has(row.id), '影片需要名称和唯一 ID'); ids.add(row.id);
    check(categories.has(row.category), '影片分类不存在');
    check(Array.isArray(row.routes) && row.routes.length, '影片至少需要一条线路');
    row.routes.forEach(route => { check(route.name && Array.isArray(route.episodes) && route.episodes.length, '线路需要名称和剧集'); route.episodes.forEach(ep => check(ep.name && !/[#$]/.test(ep.name) && safeUrl(ep.url), '剧集需要名称和完整 HTTP(S) 视频地址，集名不能包含 # 或 $')); });
  });
  const keys = new Set(['juan_personal']);
  value.vod.sites.forEach(row => { check(row.name && /^[\w-]+$/.test(row.key) && !keys.has(row.key), '接口需要名称与唯一 key'); keys.add(row.key); check([0, 1, 3, 4].includes(row.type), '接口类型无效'); check(safeUrl(row.api) || row.api?.startsWith('csp_'), '接口地址无效'); });
  value.warehouses.forEach(row => check(row.name && safeUrl(row.url), '多仓配置需要名称和完整 HTTP(S) 地址'));
  return value;
}
function list(kind) { return kind === 'warehouses' ? data.warehouses : ['playlists', 'channels'].includes(kind) ? data.live[kind] : data.vod[kind]; }
function save(next) {
  validate(next); undo.push(clone(data)); if (undo.length > 30) undo.shift(); data = next;
  persist(); render();
}
function persist() {
  try { localStorage.setItem(draftKey, pretty(data)); } catch { notice('浏览器无法保存草稿，请导出 JSON 备份。'); }
}
function setTab(id) {
  if (!['overview', 'live', 'vod', 'movies', 'advanced'].includes(id)) id = 'overview';
  if (id === 'movies' && data.vod.movies === undefined) id = 'vod';
  document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === id));
  document.querySelectorAll('.nav-item').forEach(node => { node.classList.toggle('active', node.dataset.tab === id); node.setAttribute('aria-current', node.dataset.tab === id ? 'page' : 'false'); });
  $('breadcrumb').textContent = '我的源站 / ' + { overview: '总览', live: '直播电视', vod: '点播接口', movies: '自有影片', advanced: '配置与发布' }[id];
  history.replaceState(null, '', '#' + id);
}
function render() {
  const dirty = JSON.stringify(data) !== JSON.stringify(online);
  $('draft-state').textContent = dirty ? '● 本机草稿 · 尚未发布' : '● 与线上版本一致'; $('undo').disabled = !undo.length;
  $('source-name').value = data.name; $('live-name').value = data.live.name; $('vod-name').value = data.vod.name; $('raw-json').value = pretty(editableConfig(data));
  $('m3u-maintenance').hidden = !data.live.channelFile && !m3uLinkMode();
  $('channel-editor').hidden = m3uLinkMode();
  $('copy-m3u').textContent = m3uLinkMode() ? '复制 M3U 链接' : '复制频道 M3U';
  $('copy-json').textContent = data.live.channelFile ? '复制接口与订阅配置' : '复制完整配置';
  const hasMovies = data.vod.movies !== undefined;
  document.querySelector('[data-tab="movies"]').hidden = !hasMovies; $('movies').hidden = !hasMovies;
  const stats = [['自建频道', m3uLinkMode() ? hosting.channelCount : data.live.channels.length], ['直播列表', data.live.playlists.length], ...(hasMovies ? [['点播来源', data.vod.sites.length + data.warehouses.length], ['自有影片', data.vod.movies.length]] : [['点播接口', data.vod.sites.length], ['多仓配置', data.warehouses.length]])];
  $('stats').replaceChildren(...stats.map(([label, count]) => { const card = element('div', undefined, 'stat'); card.append(element('b', String(count)), element('span', label)); return card; }));
  for (const kind of ['playlists', 'channels', 'sites', ...(hasMovies ? ['movies'] : []), 'warehouses']) renderList(kind);
  renderSubscriptions();
}
function renderList(kind) {
  const target = $('list-' + kind), records = list(kind);
  if (!records.length) {
    const empty = element('div', undefined, 'empty'); empty.append(element('b', '还没有' + labels[kind]), element('p', '添加自己的内容，保存到 GitHub 后发布。')); target.replaceChildren(empty); return;
  }
  target.replaceChildren(...records.map((record, index) => {
    const row = element('article', undefined, 'item' + (record.enabled === false ? ' off' : ''));
    const copy = element('div', undefined, 'item-copy');
    const subtitle = kind === 'channels' ? (record.group || '未分组') + ' · ' + record.urls.length + ' 条线路' : kind === 'movies' ? (data.vod.categories.find(c => c.id === record.category)?.name || '') + ' · ' + record.routes.reduce((n, route) => n + route.episodes.length, 0) + ' 集' : record.url || record.api;
    copy.append(element('strong', record.name), element('p', (record.enabled === false ? '已停用 · ' : '') + subtitle));
    const actions = element('div', undefined, 'item-actions');
    actions.append(button('编辑', () => openEditor(kind, index)), button(record.enabled === false ? '启用' : '停用', () => { const next = clone(data); const rows = kind === 'warehouses' ? next.warehouses : ['playlists', 'channels'].includes(kind) ? next.live[kind] : next.vod[kind]; rows[index].enabled = record.enabled === false; save(next); }), button('删除', () => { const next = clone(data); const rows = kind === 'warehouses' ? next.warehouses : ['playlists', 'channels'].includes(kind) ? next.live[kind] : next.vod[kind]; rows.splice(index, 1); save(next); notice('已从草稿删除，可点击撤销。'); }, 'danger'));
    row.append(element('div', { channels: '▣', playlists: '▤', sites: '⌘', movies: '▷', warehouses: '◈' }[kind], 'item-icon'), copy, actions); return row;
  }));
}
function renderSubscriptions() {
  if (!hosting) return;
  const base = hosting.endpoints[Number($('endpoint').value) || 0].base;
  const groups = hosting.warehouseGroups || [];
  const warehouses = groups.length ? groups.map((group, index) => ['多仓分组 ' + (index + 1) + ' / ' + groups.length + ' · ' + group.count + ' 份配置', group.path]) : [['多仓订阅 · 包含外部配置', 'warehouse.json']];
  $('subscriptions').replaceChildren(...[['综合源 · 直播 + 点播', 'box.json'], ['点播专用配置', 'vod.json'], ...warehouses, ['自建频道 · TXT', 'live.txt'], ['自建频道 · M3U', hosting.channelFile || 'live.m3u'], ['自建频道 · JSON / 完整请求头', 'live.json']].map(([title, path]) => {
    const address = base + path, card = element('article', undefined, 'subscription'), head = element('div', undefined, 'subscription-head');
    head.append(element('h3', title), button('复制地址', () => copyText(address).then(() => notice('订阅地址已复制')).catch(error => notice(error.message))));
    const code = element('code', address); code.title = address; card.append(head, code);
    if (groups.some(group => group.path === path)) card.append(element('p', '依次添加所有分组即可完整接入；每组最多 6 份，兼容现有 App。', 'hint'));
    return card;
  }));
}
function field(label, name, value = '', options = {}) {
  const wrapper = element('label', label, options.wide ? 'wide' : ''); let input;
  if (options.type === 'select') {
    input = element('select'); for (const [id, title] of options.choices) { const option = element('option', title); option.value = id; input.append(option); }
  } else input = element(options.type === 'textarea' ? 'textarea' : 'input');
  if (options.type === 'checkbox') { input.type = 'checkbox'; input.checked = !!value; } else input.value = value;
  input.name = name; if (options.required) input.required = true;
  if (options.placeholder) input.placeholder = options.placeholder;
  wrapper.append(input); if (options.hint) wrapper.append(element('small', options.hint)); $('form-fields').append(wrapper); return input;
}
function openEditor(kind, index = -1) {
  editing = { kind, index }; const item = index >= 0 ? clone(list(kind)[index]) : {};
  $('dialog-title').textContent = (index >= 0 ? '编辑' : '添加') + labels[kind]; $('form-fields').replaceChildren(); $('form-error').textContent = '';
  field('名称', 'name', item.name || '', { required: true, wide: true, placeholder: { channels: '例如：我的电影频道', playlists: '例如：家里的直播列表', sites: '例如：我的 JSON 片库', movies: '影片名称', warehouses: '例如：我的 TVBox 配置' }[kind] });
  if (kind === 'channels') {
    field('分组', 'group', item.group || '未分组'); field('EPG 标识（可选）', 'tvgId', item.tvgId || '');
    field('图标地址（可选）', 'logo', item.logo || '', { wide: true, placeholder: 'https://…/logo.png' });
    field('播放线路', 'urls', (item.urls || []).join('\n'), { type: 'textarea', wide: true, required: true, hint: '每行一个真实视频地址，多行作为同一频道的备用线路。' });
  } else if (['playlists', 'warehouses'].includes(kind)) {
    field(kind === 'playlists' ? 'M3U / TXT / 直播 JSON 地址' : 'TVBox 配置 / 多仓 JSON 地址', 'url', item.url || '', { required: true, wide: true, placeholder: 'https://…' });
  } else if (kind === 'sites') {
    field('接口类型', 'type', String(item.type ?? 1), { type: 'select', choices: [['1', 'JSON 采集接口'], ['0', 'XML 采集接口'], ['4', 'HTTP 接口'], ['3', 'JavaScript / CSP 插件']] });
    field('唯一 key', 'key', item.key || uid('site'), { required: true, hint: '修改名称时保留 key，避免影响收藏和历史。' });
    field('API 或脚本地址', 'api', item.api || '', { wide: true, required: true, placeholder: 'https://…/api.php/provide/vod/' });
    field('解析地址（可选）', 'playUrl', item.playUrl || '', { wide: true });
    field('JAR 地址（CSP 插件需要，可选）', 'jar', item.jar || '', { wide: true });
    field('扩展参数 ext（可选）', 'ext', typeof item.ext === 'object' ? JSON.stringify(item.ext) : item.ext || '', { type: 'textarea', wide: true, hint: '可以填写文本、地址或 JSON 对象。' });
  } else if (kind === 'movies') {
    field('分类', 'category', item.category || data.vod.categories[0]?.id || '', { type: 'select', choices: data.vod.categories.map(c => [c.id, c.name]) });
    field('年份（可选）', 'year', item.year || ''); field('海报地址（可选）', 'poster', item.poster || '', { wide: true });
    field('简介（可选）', 'description', item.description || '', { type: 'textarea', wide: true });
    field('第一条线路名称', 'routeName', item.routes?.[0]?.name || '默认线路', { required: true, wide: true, hint: '更多线路可以在完整 JSON 中编辑，表单会保留已有的其他线路。' });
    field('剧集 / 视频地址', 'episodes', (item.routes?.[0]?.episodes || []).map(ep => ep.name + '$' + ep.url).join('\n'), { type: 'textarea', wide: true, required: true, hint: '每行“第01集$https://…”。电影也可只填一行视频地址。' });
    field('这些视频地址是需要嗅探的网页', 'sniff', item.sniff || false, { type: 'checkbox', wide: true });
  }
  if (kind !== 'warehouses') field('请求头（可选 JSON）', 'headers', JSON.stringify(item.headers || {}, null, 2), { type: 'textarea', wide: true, hint: '按源的实际要求填写；公开发布前确认其中没有私密凭据。' });
  $('editor-dialog').showModal(); $('entry-form').elements.namedItem('name').focus();
}
function uid(prefix) { return prefix + '-' + (globalThis.crypto?.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2, 9)); }
function submitEntry(event) {
  event.preventDefault();
  try {
    const form = new FormData($('entry-form')), get = name => String(form.get(name) || '').trim(); const { kind, index } = editing;
    const item = index >= 0 ? clone(list(kind)[index]) : { enabled: true }; item.name = get('name');
    if (kind !== 'warehouses') { item.headers = JSON.parse(get('headers') || '{}'); check(item.headers && typeof item.headers === 'object' && !Array.isArray(item.headers), '请求头必须是 JSON 对象'); }
    if (kind === 'channels') { item.group = get('group') || '未分组'; item.logo = get('logo'); item.tvgId = get('tvgId'); item.urls = get('urls').split(/\r?\n/).map(s => s.trim()).filter(Boolean); }
    else if (['playlists', 'warehouses'].includes(kind)) item.url = get('url');
    else if (kind === 'sites') {
      Object.assign(item, { key: get('key'), type: Number(get('type')), api: get('api'), playUrl: get('playUrl') });
      if (get('jar')) item.jar = get('jar'); else delete item.jar;
      const ext = get('ext'); item.ext = /^[\[{]/.test(ext) ? JSON.parse(ext) : ext;
    } else if (kind === 'movies') {
      item.id = item.id || uid('movie'); Object.assign(item, { category: get('category'), year: get('year'), poster: get('poster'), description: get('description'), sniff: form.has('sniff') });
      const old = item.routes?.[0] || {}; const oldEpisodes = old.episodes || [];
      const episodes = get('episodes').split(/\r?\n/).map(s => s.trim()).filter(Boolean).map((line, index) => { const split = line.indexOf('$'), name = split < 0 ? (index === 0 ? '正片' : '第' + (index + 1) + '集') : line.slice(0, split).trim(), url = split < 0 ? line : line.slice(split + 1).trim(); const original = oldEpisodes.find(ep => ep.name === name); return { ...(original || {}), name, url }; });
      item.routes = [{ ...old, name: get('routeName'), episodes }, ...(item.routes || []).slice(1)];
    }
    const next = clone(data), records = kind === 'warehouses' ? next.warehouses : ['playlists', 'channels'].includes(kind) ? next.live[kind] : next.vod[kind];
    if (index < 0) records.push(item); else records[index] = item;
    save(next); $('editor-dialog').close(); notice(kind === 'channels' && data.live.channelFile ? '频道已保存到草稿，请复制频道 M3U 并提交至 live.m3u。' : '已保存到本机草稿，提交 GitHub 后发布。');
  } catch (error) { $('form-error').textContent = error.message; }
}
async function copyText(value) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
  const area = element('textarea'); area.value = value; area.style.position = 'fixed'; area.style.opacity = '0'; document.body.append(area); area.select(); const result = document.execCommand('copy'); area.remove(); check(result, '复制失败，请导出配置文件。');
}
async function copyConfig() {
  validate(data); await copyText(pretty(editableConfig(data))); notice(data.live.channelFile ? '配置已复制。直播频道请在「直播电视」中另行复制 M3U 并提交。' : '配置已复制。打开 GitHub 文件，粘贴替换内容后提交。');
}
function importConfig(value) {
  validate(value);
  if (value.live.channelFile && !value.live.channels.length) value.live.channels = clone(data.live.channels);
  save(value);
}
async function fetchJson(path) {
  const response = await fetch(path, { cache: 'no-store', credentials: 'omit' });
  check(response.ok, '读取失败：' + path + '（HTTP ' + response.status + '）'); return response.json();
}
function safeAction(action) { return (...args) => Promise.resolve().then(() => action(...args)).catch(error => notice(error.message)); }
async function start() {
  try {
    [online, hosting] = await Promise.all([fetchJson('data/library.json'), fetchJson('hosting.json')]); validate(online); data = clone(online);
    try { const draft = localStorage.getItem(draftKey); if (draft) { data = validate(JSON.parse(draft)); if (m3uLinkMode() && data.live.channelFile) { delete data.live.channelFile; const own = online.live.playlists.find(item => item.url === hosting.channelUrl); if (own && !data.live.playlists.some(item => item.url === own.url)) data.live.playlists.unshift(clone(own)); } if (online.live.channelFile && !data.live.channelFile) { data.live.channelFile = online.live.channelFile; data.live.channels = clone(online.live.channels); } if (online.vod.movies === undefined && Array.isArray(data.vod.movies) && !data.vod.movies.length) delete data.vod.movies; if (JSON.stringify(data) !== JSON.stringify(online)) notice('已恢复本机草稿。线上版本可在配置与发布中重新读取。'); } } catch { notice('本机旧草稿无法读取，已加载线上版本。'); }
    $('github-edit').href = hosting.editUrl;
    $('github-live-edit').href = hosting.channelEditUrl || hosting.editUrl;
    $('copy-m3u').onclick = safeAction(async () => { validate(data); await copyText(m3uLinkMode() ? hosting.channelUrl : channelsM3u(data.live.channels)); notice(m3uLinkMode() ? 'M3U 订阅链接已复制；频道内容在 data/live.m3u 维护。' : '频道 M3U 已复制，打开 M3U 文件全选替换并提交。'); });
    hosting.endpoints.forEach((endpoint, index) => { const option = element('option', endpoint.name); option.value = String(index); $('endpoint').append(option); });
    document.querySelectorAll('[data-tab]').forEach(node => { node.onclick = () => setTab(node.dataset.tab); });
    window.addEventListener('hashchange', () => setTab(location.hash.slice(1)));
    document.querySelectorAll('[data-open-tab]').forEach(node => { node.onclick = () => setTab(node.dataset.openTab); });
    document.querySelectorAll('[data-add]').forEach(node => { node.onclick = () => openEditor(node.dataset.add); });
    $('endpoint').onchange = renderSubscriptions; $('entry-form').onsubmit = submitEntry;
    $('dialog-close').onclick = $('dialog-cancel').onclick = () => $('editor-dialog').close();
    $('undo').onclick = () => { if (undo.length) { data = undo.pop(); persist(); render(); notice('已撤销上一步草稿修改。'); } };
    $('save-names').onclick = safeAction(() => { const next = clone(data); next.name = $('source-name').value.trim(); next.live.name = $('live-name').value.trim(); next.vod.name = $('vod-name').value.trim(); save(next); notice('名称已保存到草稿。'); });
    $('copy-json').onclick = safeAction(copyConfig); $('publish-top').onclick = () => { setTab('advanced'); notice(data.live.channelFile ? '直播频道在「直播电视」复制 M3U；其他配置在这里复制 JSON。' : '先复制完整配置，再打开 GitHub 文件粘贴并提交。'); };
    $('apply-json').onclick = safeAction(() => { importConfig(JSON.parse($('raw-json').value)); notice('JSON 已检查并应用到草稿。'); });
    $('download').onclick = safeAction(() => { validate(data); const url = URL.createObjectURL(new Blob([pretty(data)], { type: 'application/json;charset=utf-8' })); const link = element('a'); link.href = url; link.download = 'library.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
    $('import-file').onchange = safeAction(async () => { const file = $('import-file').files[0]; if (!file) return; check(file.size <= 5 * 1024 * 1024, '配置文件上限为 5 MB'); importConfig(JSON.parse(await file.text())); $('import-file').value = ''; notice('配置已导入本机草稿，提交后发布。'); });
    $('reload').onclick = safeAction(async () => { if (JSON.stringify(data) !== JSON.stringify(online) && !confirm('用线上版本替换当前本机草稿？可以先导出备份。')) return; const fresh = validate(await fetchJson('data/library.json')); save(fresh); online = clone(fresh); render(); notice('已重新读取线上版本，之前的草稿可以撤销恢复。'); });
    render(); setTab(location.hash.slice(1) || 'overview');
  } catch (error) { $('fatal').textContent = error.message + '。请刷新页面重试，或直接在 GitHub 维护 library.json。'; $('fatal').hidden = false; $('draft-state').textContent = '读取失败'; $('publish-top').disabled = true; }
}
start();
