const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const pretty = value => JSON.stringify(value, null, 2) + '\n';
const draftKey = 'juan-source-draft:v2:' + location.pathname.replace(/index\.html$/, '');
const labels = { playlists: '直播列表', sites: '点播接口', warehouses: '完整 TVBox 配置' };
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
function hasProjectM3u() { return hosting?.channelFile === 'data/live.m3u'; }
function exportDraft() { validate(data); return pretty(data); }
function exportConfig() { const value = clone(validate(data)); value.vod = { name: data.vod.name, url: data.vod.url }; return pretty(value); }
function exportSites() { validate(data); return pretty({ version: 1, ...Object.fromEntries(Object.entries(data.vod).filter(([key]) => ['sites', 'spider', 'contexts'].includes(key))) }); }
function attachSites(library, sites) {
  check(library?.vod && Object.keys(library.vod).every(key => ['name', 'url'].includes(key)), 'vod 仅支持 name 和 url；站点请在独立清单维护');
  check(sites?.version === 1 && Object.keys(sites).every(key => ['version', 'sites', 'contexts', 'spider'].includes(key)), '站点清单需要 version: 1、sites 与可选 contexts、spider');
  const value = clone(library); value.vod = { ...value.vod, ...Object.fromEntries(Object.entries(sites).filter(([key]) => key !== 'version')) }; return validate(value);
}
function selectedFile() { return $('config-file').value === 'sites' ? 'vod-sites.json' : 'library.json'; }
function selectedJson() { return selectedFile() === 'vod-sites.json' ? exportSites() : exportConfig(); }
function renderJson() { $('raw-json').value = selectedJson(); $('github-edit').href = selectedFile() === 'vod-sites.json' ? hosting.vodSiteEditUrl : hosting.editUrl; }
function validate(value) {
  const safeUrl = url => { try { const u = new URL(url); return ['http:', 'https:'].includes(u.protocol) && !!u.hostname && !u.username && !u.password && !/[\s\u0000-\u001f]/.test(url); } catch { return false; } };
  check(value && value.version === 1 && typeof value.name === 'string' && value.name.trim(), '需要有效的 version: 1 与源站名称');
  check(value.live && value.vod && value.live.name && value.vod.name, '请填写直播与点播片库名称');
  check(Object.keys(value.live).every(key => ['name', 'playlists'].includes(key)), 'live 仅支持 name 和 playlists，频道请在 M3U 维护');
  check(Object.keys(value.vod).every(key => ['name', 'url', 'sites', 'spider', 'contexts'].includes(key)), 'vod 仅支持 name、url 以及独立清单中的 sites、spider、contexts');
  check(safeUrl(value.vod.url), '点播清单需要完整 HTTP(S) 地址');
  const contexts = value.vod.contexts === undefined ? {} : value.vod.contexts;
  check(typeof contexts === 'object' && contexts !== null && !Array.isArray(contexts) && Object.keys(contexts).length <= 96, 'vod.contexts 需要最多 96 项的对象');
  for (const [key, item] of Object.entries(contexts)) {
    check(/^[\w-]+$/.test(key) && item && typeof item === 'object' && !Array.isArray(item) && item.name && safeUrl(item.url), '依赖配置需要 ID、名称与原配置 URL');
    check(!['sites', 'lives', 'urls', 'storeHouse', 'storehouse', 'warehouses', 'configs'].some(field => field in item), '依赖配置不能内嵌站点、直播或多仓列表');
    for (const field of ['parses', 'rules', 'headers', 'flags', 'ads', 'hosts', 'doh', 'proxy']) check(!(field in item) || Array.isArray(item[field]), '依赖配置 ' + field + ' 必须是数组');
  }
  for (const [name, list] of Object.entries({ playlists: value.live.playlists, sites: value.vod.sites, warehouses: value.warehouses })) {
    check(Array.isArray(list), name + ' 必须是数组');
    list.forEach(row => { check(row && typeof row === 'object' && !Array.isArray(row), name + ' 的每项必须是对象'); check(row.enabled === undefined || typeof row.enabled === 'boolean', 'enabled 需要填写 true / false'); });
  }
  value.live.playlists.forEach(row => check(row.name && safeUrl(row.url), '直播列表需要名称和完整的 HTTP(S) 地址'));
  const keys = new Set();
  value.vod.sites.forEach(row => {
    const identity = JSON.stringify([row.context || '', row.key]);
    check(row.name && typeof row.key === 'string' && row.key.trim() && row.key.length <= 256 && !/[\x00-\x1f\x7f/\\]/.test(row.key) && !keys.has(identity), '接口需要名称与同一依赖配置内唯一的 key');
    check(row.context === undefined || typeof row.context === 'string', '接口 context 必须是依赖配置 ID');
    check(!row.context || Object.hasOwn(contexts, row.context), '接口引用了不存在的依赖配置');
    keys.add(identity); check([0, 1, 3, 4].includes(row.type), '接口类型无效'); check(safeUrl(row.api) || row.api?.startsWith('csp_'), '接口地址无效');
  });
  value.warehouses.forEach(row => check(row.name && safeUrl(row.url), '多仓配置需要名称和完整 HTTP(S) 地址'));
  return value;
}
function list(kind, value = data) { return kind === 'warehouses' ? value.warehouses : kind === 'playlists' ? value.live.playlists : value.vod.sites; }
function save(next, file) {
  validate(next); undo.push(clone(data)); if (undo.length > 30) undo.shift(); data = next;
  if (file) $('config-file').value = file;
  persist(); render();
}
function persist() {
  try { localStorage.setItem(draftKey, pretty(data)); } catch { notice('浏览器无法保存草稿，请导出 JSON 备份。'); }
}
function setTab(id) {
  if (!['overview', 'live', 'vod', 'advanced'].includes(id)) id = 'overview';
  document.querySelectorAll('.page').forEach(node => node.classList.toggle('active', node.id === id));
  document.querySelectorAll('.nav-item').forEach(node => { node.classList.toggle('active', node.dataset.tab === id); node.setAttribute('aria-current', node.dataset.tab === id ? 'page' : 'false'); });
  $('breadcrumb').textContent = '我的源站 / ' + { overview: '总览', live: '直播电视', vod: '点播接口', advanced: '配置与发布' }[id];
  history.replaceState(null, '', '#' + id);
}
function render() {
  const dirty = JSON.stringify(data) !== JSON.stringify(online);
  $('draft-state').textContent = dirty ? '● 本机草稿 · 尚未发布' : '● 与线上版本一致'; $('undo').disabled = !undo.length;
  $('source-name').value = data.name; $('live-name').value = data.live.name; $('vod-name').value = data.vod.name; renderJson();
  $('m3u-maintenance').hidden = !hasProjectM3u();
  $('live-sources-link').hidden = hosting?.liveSources !== 'data/live-sources.json';
  $('github-vod-edit').href = hosting.vodSiteEditUrl;
  $('vod-sites-address').textContent = data.vod.url;
  const stats = [...(hasProjectM3u() ? [['自建频道', hosting.channelCount]] : []), ['直播列表', data.live.playlists.length], ['点播接口', data.vod.sites.length], ['完整配置', data.warehouses.length]];
  $('stats').replaceChildren(...stats.map(([label, count]) => { const card = element('div', undefined, 'stat'); card.append(element('b', String(count)), element('span', label)); return card; }));
  for (const kind of ['playlists', 'sites', 'warehouses']) renderList(kind);
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
    const subtitle = record.url || record.api;
    copy.append(element('strong', record.name), element('p', (record.enabled === false ? '已停用 · ' : '') + subtitle));
    const actions = element('div', undefined, 'item-actions');
    actions.append(button('编辑', () => openEditor(kind, index)), button(record.enabled === false ? '启用' : '停用', () => { const next = clone(data); list(kind, next)[index].enabled = record.enabled === false; save(next, kind === 'sites' ? 'sites' : 'library'); }), button('删除', () => { const next = clone(data); list(kind, next).splice(index, 1); save(next, kind === 'sites' ? 'sites' : 'library'); notice('已从草稿删除，可点击撤销。'); }, 'danger'));
    row.append(element('div', { playlists: '▤', sites: '⌘', warehouses: '◈' }[kind], 'item-icon'), copy, actions); return row;
  }));
}
function renderSubscriptions() {
  if (!hosting) return;
  const base = hosting.endpoints[Number($('endpoint').value) || 0].base;
  const groups = hosting.warehouseGroups || [];
  const warehouses = groups.length ? groups.map((group, index) => ['多仓分组 ' + (index + 1) + ' / ' + groups.length + ' · ' + group.count + ' 份配置', group.path]) : [['多仓订阅 · 包含外部配置', 'warehouse.json']];
  $('subscriptions').replaceChildren(...[['综合源 · 直播 + 点播', 'box.json'], ['点播站点维护清单 · 居安影院', 'data/vod-sites.json'], ['点播专用配置', 'vod.json'], ...warehouses, ['自建频道 · TXT', 'live.txt'], ['自建频道 · M3U', hosting.channelFile || 'live.m3u'], ['自建频道 · JSON / 完整请求头', 'live.json']].map(([title, path]) => {
    const address = base + path, card = element('article', undefined, 'subscription'), head = element('div', undefined, 'subscription-head');
    head.append(element('h3', title), button('复制地址', () => copyText(address).then(() => notice('订阅地址已复制')).catch(error => notice(error.message))));
    const code = element('code', address); code.title = address; card.append(head, code);
    if (groups.some(group => group.path === path)) card.append(element('p', '依次添加所有分组即可完整接入；每组最多 6 份。', 'hint'));
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
  field('名称', 'name', item.name || '', { required: true, wide: true, placeholder: { playlists: '例如：家里的直播列表', sites: '例如：我的 JSON 片库', warehouses: '例如：我的 TVBox 配置' }[kind] });
  if (['playlists', 'warehouses'].includes(kind)) {
    field(kind === 'playlists' ? 'M3U / TXT / 直播 JSON 地址' : 'TVBox 配置 / 多仓 JSON 地址', 'url', item.url || '', { required: true, wide: true, placeholder: 'https://…' });
  } else if (kind === 'sites') {
    field('接口类型', 'type', String(item.type ?? 1), { type: 'select', choices: [['1', 'JSON 采集接口'], ['0', 'XML 采集接口'], ['4', 'HTTP 接口'], ['3', 'JavaScript / CSP 插件']] });
    field('唯一 key', 'key', item.key || uid('site'), { required: true, hint: '同一依赖配置内唯一；修改名称时保留 key，避免影响收藏和历史。' });
    field('API 或脚本地址', 'api', item.api || '', { wide: true, required: true, placeholder: 'https://…/api.php/provide/vod/' });
    field('解析地址（可选）', 'playUrl', item.playUrl || '', { wide: true });
    field('JAR 地址（CSP 插件需要，可选）', 'jar', item.jar || '', { wide: true });
    field('扩展参数 ext（可选）', 'ext', typeof item.ext === 'object' ? JSON.stringify(item.ext) : item.ext || '', { type: 'textarea', wide: true, hint: '可以填写文本、地址或 JSON 对象。' });
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
    if (['playlists', 'warehouses'].includes(kind)) item.url = get('url');
    else if (kind === 'sites') {
      Object.assign(item, { key: get('key'), type: Number(get('type')), api: get('api'), playUrl: get('playUrl') });
      if (get('jar')) item.jar = get('jar'); else delete item.jar;
      const ext = get('ext'); item.ext = /^[\[{]/.test(ext) ? JSON.parse(ext) : ext;
    }
    const next = clone(data), records = list(kind, next);
    if (index < 0) records.push(item); else records[index] = item;
    save(next, kind === 'sites' ? 'sites' : 'library'); $('editor-dialog').close(); notice('已保存到本机草稿，提交 GitHub 后发布。');
  } catch (error) { $('form-error').textContent = error.message; }
}
async function copyText(value) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
  const area = element('textarea'); area.value = value; area.style.position = 'fixed'; area.style.opacity = '0'; document.body.append(area); area.select(); const result = document.execCommand('copy'); area.remove(); check(result, '复制失败，请导出配置文件。');
}
async function copyConfig() {
  await copyText(selectedJson()); notice(selectedFile() + ' 已复制。打开对应 GitHub 文件，粘贴替换内容后提交。');
}
function importConfig(value) {
  save(value?.live ? attachSites(value, JSON.parse(exportSites())) : attachSites(JSON.parse(exportConfig()), value), value?.live ? 'library' : 'sites');
}
async function fetchJson(path) {
  const response = await fetch(path, { cache: 'no-store', credentials: 'omit' });
  check(response.ok, '读取失败：' + path + '（HTTP ' + response.status + '）'); return response.json();
}
function safeAction(action) { return (...args) => Promise.resolve().then(() => action(...args)).catch(error => notice(error.message)); }
async function start() {
  try {
    const [library, sites, metadata] = await Promise.all([fetchJson('data/library.json'), fetchJson('data/vod-sites.json'), fetchJson('hosting.json')]);
    hosting = metadata; online = attachSites(library, sites); data = clone(online);
    try { const draft = localStorage.getItem(draftKey); if (draft) { data = validate(JSON.parse(draft)); if (JSON.stringify(data) !== JSON.stringify(online)) notice('已恢复本机草稿。线上版本可在配置与发布中重新读取。'); } } catch { notice('本机草稿无法读取，已加载线上版本。'); }
    $('github-edit').href = hosting.editUrl;
    $('github-live-edit').href = hosting.channelEditUrl || hosting.editUrl;
    $('copy-vod-sites').onclick = safeAction(async () => { await copyText(data.vod.url); notice('点播清单链接已复制；站点在 data/vod-sites.json 维护。'); });
    $('config-file').onchange = renderJson;
    $('copy-m3u').onclick = safeAction(async () => { validate(data); await copyText(hosting.channelUrl); notice('M3U 订阅链接已复制；频道内容在 data/live.m3u 维护。'); });
    hosting.endpoints.forEach((endpoint, index) => { const option = element('option', endpoint.name); option.value = String(index); $('endpoint').append(option); });
    document.querySelectorAll('[data-tab]').forEach(node => { node.onclick = () => setTab(node.dataset.tab); });
    window.addEventListener('hashchange', () => setTab(location.hash.slice(1)));
    document.querySelectorAll('[data-open-tab]').forEach(node => { node.onclick = () => setTab(node.dataset.openTab); });
    document.querySelectorAll('[data-add]').forEach(node => { node.onclick = () => openEditor(node.dataset.add); });
    $('endpoint').onchange = renderSubscriptions; $('entry-form').onsubmit = submitEntry;
    $('dialog-close').onclick = $('dialog-cancel').onclick = () => $('editor-dialog').close();
    $('undo').onclick = () => { if (undo.length) { data = undo.pop(); persist(); render(); notice('已撤销上一步草稿修改。'); } };
    $('save-names').onclick = safeAction(() => { const next = clone(data); next.name = $('source-name').value.trim(); next.live.name = $('live-name').value.trim(); next.vod.name = $('vod-name').value.trim(); save(next, 'library'); notice('名称已保存到草稿。'); });
    $('copy-json').onclick = safeAction(copyConfig); $('publish-top').onclick = () => { setTab('advanced'); notice('站点修改提交 vod-sites.json；直播订阅和完整 TVBox 地址修改提交 library.json。选择对应文件后复制并提交。'); };
    $('apply-json').onclick = safeAction(() => { importConfig(JSON.parse($('raw-json').value)); notice('JSON 已检查并应用到草稿。'); });
    $('download').onclick = safeAction(() => { const url = URL.createObjectURL(new Blob([selectedJson()], { type: 'application/json;charset=utf-8' })); const link = element('a'); link.href = url; link.download = selectedFile(); link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
    $('import-file').onchange = safeAction(async () => { const file = $('import-file').files[0]; if (!file) return; check(file.size <= 5 * 1024 * 1024, '配置文件上限为 5 MB'); importConfig(JSON.parse(await file.text())); $('import-file').value = ''; notice('配置已导入本机草稿，提交后发布。'); });
    $('reload').onclick = safeAction(async () => { if (JSON.stringify(data) !== JSON.stringify(online) && !confirm('用线上版本替换当前本机草稿？可以先分别导出备份。')) return; const [library, sites] = await Promise.all([fetchJson('data/library.json'), fetchJson('data/vod-sites.json')]); const fresh = attachSites(library, sites); save(fresh); online = clone(fresh); render(); notice('已重新读取线上配置与站点清单，之前的草稿可以撤销恢复。'); });
    render(); setTab(location.hash.slice(1) || 'overview');
  } catch (error) { $('fatal').textContent = error.message + '。请刷新页面重试，或直接在 GitHub 维护 library.json。'; $('fatal').hidden = false; $('draft-state').textContent = '读取失败'; $('publish-top').disabled = true; }
}
start();
