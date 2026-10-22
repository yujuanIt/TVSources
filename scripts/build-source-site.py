#!/usr/bin/env python3
"""Validate editable source files and build only the public GitHub Pages source files."""
import argparse
import copy
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vod_config
import live_channels

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT
ID = re.compile(r'^[A-Za-z0-9_-]+$')
BAD_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
LIVE_SCHEMES = {'http', 'https', 'rtsp', 'rtmp', 'udp', 'rtp'}
MODULE_NAMES = {'television': '简视直播', 'entertainment': '简视娱乐', 'vod': '简视点播', 'sports': '简视体育'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, field, empty=False):
    require(isinstance(value, str), field + ' 必须是文字')
    require(empty or bool(value.strip()), field + ' 不能为空')
    require(not BAD_CONTROL.search(value), field + ' 不能包含换行或控制字符')
    return value


def url(value, field, live=False, empty=False):
    text(value, field, empty)
    if not value and empty:
        return value
    parsed = urlsplit(value)
    require(parsed.scheme.lower() in (LIVE_SCHEMES if live else {'http', 'https'}) and bool(parsed.hostname), field + ' 需要完整的有效地址')
    try:
        parsed.port
    except ValueError:
        raise ValueError(field + ' 的端口无效') from None
    require(not parsed.username and not parsed.password, field + ' 请勿使用包含登录密码的地址')
    require(' ' not in value, field + ' 中的空格需要编码为 %20')
    return value


def headers(value, field):
    require(isinstance(value, dict), field + ' 必须是对象')
    for key, item in value.items():
        require(bool(re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key)), field + ' 的请求头名称无效')
        text(item, field + '.' + key, True)


def rows(value, field):
    require(isinstance(value, list), field + ' 必须是数组')
    require(len(value) <= 10000, field + ' 最多 10000 项')
    for row in value:
        require(isinstance(row, dict), field + ' 的每项必须是对象')
        require(isinstance(row.get('enabled', True), bool), field + '.enabled 必须是 true 或 false')
    return value


def validate(data):
    require(isinstance(data, dict) and data.get('version') == 1, '需要 version: 1 的配置对象')
    text(data.get('name'), 'name')
    live, vod = data.get('live'), data.get('vod')
    require(isinstance(live, dict) and isinstance(vod, dict), 'live 和 vod 必须是对象')
    text(live.get('name'), 'live.name'); text(vod.get('name'), 'vod.name')
    require(set(live) <= {'name', 'playlists'}, 'live 仅支持 name 和 playlists，频道请在 M3U 维护')
    require(set(vod) <= {'name', 'url', 'sites', 'spider', 'contexts'}, 'vod 仅支持 name、url、sites、spider 和 contexts，影片及分类由点播接口提供')
    if 'url' in vod: url(vod['url'], 'vod.url')
    contexts = vod_config.contexts(vod)
    for context in contexts.values():
        url(context['url'], '依赖配置 URL')
        if context.get('spider'):
            url(vod_config.absolute(context['url'], context['spider']).split(';md5;', 1)[0], '依赖配置 spider')
    for entry in rows(live.get('playlists'), 'live.playlists'):
        text(entry.get('name'), '直播列表名称'); url(entry.get('url'), '直播列表地址')
        headers(entry.get('headers', {}), '直播列表请求头')
    site_keys = set()
    for site in rows(vod.get('sites'), 'vod.sites'):
        text(site.get('key'), '接口 key'); text(site.get('name'), '接口名称')
        require(isinstance(site.get('context', ''), str), '接口 context 必须是依赖配置 ID')
        require(vod_config.site_key(site['key']) and vod_config.site_identity(site) not in site_keys, '接口 key 需要在同一依赖配置内唯一')
        require(not site.get('context') or site['context'] in contexts, '接口引用了不存在的依赖配置')
        site_keys.add(vod_config.site_identity(site)); require(type(site.get('type')) is int and site['type'] in {0, 1, 3, 4}, '接口 type 支持 0 / 1 / 3 / 4')
        api = text(site.get('api'), '接口 api')
        if api.startswith('csp_'):
            require(site['type'] == 3 and bool(site.get('jar') or contexts.get(site.get('context'), {}).get('spider') or vod.get('spider')), 'csp 插件需设置 type: 3 及 jar、依赖配置 spider 或 vod.spider')
        else:
            url(api, '接口 api')
        headers(site.get('headers', {}), '接口请求头')
        url(site.get('playUrl', ''), '解析地址', empty=True)
        if site.get('jar'):
            url(site['jar'].split(';md5;', 1)[0], '插件 jar')
    if vod.get('spider'):
        url(vod['spider'].split(';md5;', 1)[0], 'vod.spider')
    for entry in rows(data.get('warehouses'), 'warehouses'):
        text(entry.get('name'), '多仓名称'); url(entry.get('url'), '多仓地址')
    return data


def validate_channels(channels):
    for entry in rows(channels, 'M3U 频道'):
        text(entry.get('name'), '频道名称'); text(entry.get('group', '未分组'), '频道分组')
        require(isinstance(entry.get('urls'), list) and len(entry['urls']) > 0, '频道至少需要一条线路')
        for address in entry['urls']:
            url(address, '频道线路', True)
        url(entry.get('logo', ''), '频道图标', empty=True)
        text(entry.get('tvgId', ''), '频道 EPG 标识', True)
        headers(entry.get('headers', {}), '频道请求头')
        require(isinstance(entry.get('directives', []), list), '频道播放选项必须是数组')
        for directive in entry.get('directives', []):
            text(directive, '频道播放选项')
            require(directive.startswith(('#KODIPROP:', '#EXTVLCOPT:')), '频道播放选项仅支持 KODIPROP / EXTVLCOPT')
        origins = entry.get('origins', {})
        require(isinstance(origins, dict), '频道 origins 必须是按播放地址索引的对象')
        for address, source_ids in origins.items():
            require(address in entry['urls'], '来源标记必须对应本频道已有线路')
            require(isinstance(source_ids, list) and len(source_ids) <= 64 and all(isinstance(key, str) for key in source_ids) and len(set(source_ids)) == len(source_ids), '线路来源需要不重复的 ID 数组')
            require(all(isinstance(key, str) and ID.fullmatch(key) for key in source_ids), '线路来源 ID 只能包含字母、数字、下划线和连字符')
    return channels


def active(items):
    return [item for item in items if item.get('enabled', True)]


def m3u_escape(value):
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def validate_live_sources(data):
    require(isinstance(data, dict) and data.get('version') == 1, '直播来源清单需要 version: 1')
    require(data.get('playlist') == 'data/live.m3u', '直播来源清单只管理 data/live.m3u')
    require(isinstance(data.get('automaticSyncEnabled'), bool), 'automaticSyncEnabled 需要是布尔值')
    sources = rows(data.get('sources'), '直播来源 sources'); require(0 < len(sources) <= 64, '直播来源需要 1–64 项')
    known = {}
    for source in sources:
        key = text(source.get('id'), '上游 ID')
        require(bool(ID.fullmatch(key)) and key not in known, '上游 ID 无效或重复')
        known[key] = source
        text(source.get('name'), '上游名称'); url(source.get('url'), '上游地址'); headers(source.get('headers', {}), '上游请求头')
        require(source.get('format') in {'m3u', 'local-m3u', 'tvbox-lives', '88zhibo'}, '上游格式需要 m3u、local-m3u、tvbox-lives 或 88zhibo')
        if source.get('format') == '88zhibo':
            kind = source.get('kind')
            pages = {'channels': '21', 'NBA': '1', 'CBA': '2'}
            require(kind in pages and source['url'] == 'https://www.88zhibo.tv/match/' + pages[kind] + '/live', '88直播仅支持已登记的体育频道、NBA、CBA 页面')
        if 'retireMissing' in source:
            require(isinstance(source['retireMissing'], bool), 'retireMissing 需要是布尔值')
        if source.get('retireMissing', False):
            require(source.get('format') == '88zhibo' and source.get('kind') in {'NBA', 'CBA'}, '只有动态赛事允许自动移除过期条目')
        if source.get('format') == 'local-m3u':
            require(source.get('file') == 'data/live-official.m3u', '本地官方清单仅支持 data/live-official.m3u')
        if 'selection' in source:
            selection = source['selection']
            require(isinstance(selection, dict) and selection.get('mode') == 'keep-selected', 'selection 仅支持 keep-selected')
            selected_names = selection.get('names')
            require(isinstance(selected_names, list) and 0 < len(selected_names) <= 10000, 'selection.names 需要非空频道名称数组')
            for name in selected_names: text(name, '选取的频道名称')
        snapshot = source.get('lastImport', {})
        require(isinstance(snapshot, dict), 'lastImport 必须是对象')
        if 'sha256' in snapshot:
            require(isinstance(snapshot['sha256'], str) and bool(re.fullmatch(r'[0-9a-f]{64}', snapshot['sha256'])), '来源快照 SHA-256 无效')
    for source in sources:
        children = source.get('includes', [])
        require(isinstance(children, list) and all(isinstance(key, str) and key in known and key != source['id'] for key in children), '合集 includes 需要引用已知子源')
        require(not children or source['format'] == 'tvbox-lives', '只有合集可以声明 includes')
        require(all(known[key]['format'] == 'm3u' for key in children), '合集只引用已登记的 M3U，不递归展开')
    policy = data.get('mergePolicy', {})
    require(isinstance(policy, dict), 'mergePolicy 必须是对象')
    order = policy.get('sourceOrder', [])
    require(isinstance(order, list) and all(isinstance(key, str) and key in known for key in order) and len(set(order)) == len(order), '合并顺序需要已知且不重复的上游 ID')
    enabled = {source['id'] for source in sources if source.get('enabled', True)}
    require(enabled <= set(order) and all(known[key]['format'] in {'m3u', 'local-m3u', '88zhibo'} for key in order), '合并顺序需要包含所有启用的直播上游；已展开合集不重复抓取')
    if 'sync' in data:
        settings = data['sync']
        require(isinstance(settings, dict), 'sync 必须是对象')
        ratio = settings.get('minimumPreviousRouteRatio', .5)
        require(type(ratio) in {int, float} and 0 < ratio <= 1, '同步线路保护比例需要大于 0 且不超过 1')
    if data.get('automaticSyncEnabled') or 'normalization' in data:
        normalization = data.get('normalization', {})
        require(isinstance(normalization, dict) and normalization.get('displayLanguage', 'zh-Hans') == 'zh-Hans', '同步显示语言仅支持 zh-Hans')
        groups = normalization.get('groupOrder', [])
        require(isinstance(groups, list) and groups and all(isinstance(group, str) and group.strip() for group in groups) and len(set(groups)) == len(groups), '同步分组顺序需要不重复的名称数组')
        for group in groups: text(group, '同步分组名称')
    return data


def parse_m3u(content):
    lines = content.lstrip('\ufeff').splitlines()
    require(bool(lines) and lines[0].strip().startswith('#EXTM3U'), 'live.m3u 第一行需要是 #EXTM3U')
    channels, merged, pending = [], {}, None
    for number, raw in enumerate(lines[1:], 2):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#EXTINF:'):
            require(pending is None, f'live.m3u 第 {number} 行：上一频道缺少播放地址')
            quote, separator = None, None
            for index, char in enumerate(line):
                if char in {'"', "'"}:
                    if quote == char: quote = None
                    elif quote is None: quote = char
                elif char == ',' and quote is None:
                    separator = index; break
            require(separator is not None, f'live.m3u 第 {number} 行：EXTINF 缺少频道名称分隔符')
            attrs = {match[0]: unescape(match[1] or match[2]) for match in
                     re.findall(r'''([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')''', line[:separator])}
            require(attrs.get('x-enabled', 'true') in {'true', 'false'}, f'live.m3u 第 {number} 行：x-enabled 需要是 true 或 false')
            pending = {'name': line[separator + 1:].strip() or attrs.get('tvg-name', ''),
                       'group': attrs.get('group-title', '') or '未分组', 'logo': attrs.get('tvg-logo', ''),
                       'tvgId': attrs.get('tvg-id', ''), 'urls': [], 'headers': {}, 'enabled': attrs.get('x-enabled') != 'false'}
            if attrs.get('x-source-id'):
                source_ids = attrs['x-source-id'].split(',')
                require(len(source_ids) <= 64 and all(ID.fullmatch(key) for key in source_ids), f'live.m3u 第 {number} 行：来源 ID 无效')
                pending['_sourceIds'] = list(dict.fromkeys(source_ids))
        elif line.startswith('#EXTGRP:'):
            require(pending is not None, f'live.m3u 第 {number} 行：分组需要放在 EXTINF 后')
            pending['group'] = line.split(':', 1)[1].strip() or '未分组'
        elif line.startswith('#EXTVLCOPT:'):
            require(pending is not None, f'live.m3u 第 {number} 行：请求头需要放在 EXTINF 后')
            option, separator, value = line.split(':', 1)[1].partition('=')
            key = {'http-user-agent': 'User-Agent', 'http-referrer': 'Referer', 'http-referer': 'Referer',
                   'http-cookie': 'Cookie', 'http-origin': 'Origin'}.get(option.lower())
            if key and separator: pending['headers'][key] = value
            else: pending.setdefault('directives', []).append(line)
        elif line.startswith('#KODIPROP:'):
            require(pending is not None, f'live.m3u 第 {number} 行：播放选项需要放在 EXTINF 后')
            pending.setdefault('directives', []).append(line)
        elif line.startswith('#EXTHTTP:'):
            require(pending is not None, f'live.m3u 第 {number} 行：请求头需要放在 EXTINF 后')
            try:
                extra = json.loads(line.split(':', 1)[1]); headers(extra, 'M3U 请求头')
            except (ValueError, TypeError) as error:
                raise ValueError(f'live.m3u 第 {number} 行：请求头 JSON 无效') from error
            pending['headers'].update(extra)
        elif not line.startswith('#'):
            require(pending is not None, f'live.m3u 第 {number} 行：播放地址缺少 EXTINF')
            url(line, f'live.m3u 第 {number} 行播放地址', True)
            source_ids = pending.pop('_sourceIds', [])
            key = (pending['group'], pending['name'], pending['logo'], pending['tvgId'], pending['enabled'],
                   json.dumps(pending['headers'], sort_keys=True), tuple(pending.get('directives', [])))
            if key not in merged:
                merged[key] = pending; channels.append(pending)
            merged[key]['urls'].append(line)
            if source_ids:
                origins = merged[key].setdefault('origins', {}).setdefault(line, [])
                origins.extend(source_id for source_id in source_ids if source_id not in origins)
            pending = None
    require(pending is None, 'live.m3u 最后一个频道缺少播放地址')
    return channels


def source_endpoints(base_url, repository):
    raw_base = 'https://raw.githubusercontent.com/' + repository + '/source-data/'
    return [{'name': '免费加速 · GH-Proxy', 'base': 'https://gh-proxy.com/' + raw_base},
            {'name': '备用加速 · GHFast', 'base': 'https://ghfast.top/' + raw_base},
            {'name': 'GitHub Pages 原址', 'base': base_url.rstrip('/') + '/'},
            {'name': 'GitHub Raw 原址', 'base': raw_base}]


def project_m3u_urls(base_url, repository):
    return {entry['base'] + 'data/live.m3u' for entry in source_endpoints(base_url, repository)}


def read_project_channels(data, base_url, repository):
    validate(data)
    own_urls = project_m3u_urls(base_url, repository)
    address = next((item['url'] for item in data['live']['playlists'] if item['url'] in own_urls), None)
    if address is None:
        return None, []
    path = SOURCE / 'data/live.m3u'
    require(not path.is_symlink() and not path.parent.is_symlink(), 'M3U 不允许使用符号链接')
    return address, validate_channels(parse_m3u(path.read_text(encoding='utf-8-sig')))


def live_outputs(channel_rows, live_name, base_url, source_registry=None):
    """Serialize rows once, preserving per-route playback metadata for every subscription."""
    source_names = {}
    groups = {}; m3u = ['#EXTM3U']
    if source_registry is not None:
        validate_live_sources(source_registry)
        source_names = {source['id']: source['name'] for source in source_registry['sources']}
        m3u.append('#SOURCE-MANIFEST:' + base_url + 'data/live-sources.json')
        for source in source_registry['sources']:
            m3u.append('#SOURCE:' + json.dumps({key: source[key] for key in ['id', 'name', 'url']}, ensure_ascii=False, separators=(',', ':')))
    for channel in active(channel_rows):
        group = channel.get('group', '未分组')
        public_channel = {'name': channel['name'], 'logo': channel.get('logo', ''), 'urls': channel['urls'], 'headers': channel.get('headers', {})}
        if channel.get('origins'):
            public_channel['origins'] = copy.deepcopy(channel['origins'])
            if source_registry is not None:
                require(all(key in source_names for ids in channel['origins'].values() for key in ids), 'M3U 线路引用了未登记的上游来源')
        groups.setdefault(group, []).append(public_channel)
        attrs = 'tvg-id="{}" tvg-name="{}" tvg-logo="{}" group-title="{}"'.format(*(m3u_escape(v) for v in [channel.get('tvgId', ''), channel['name'], channel.get('logo', ''), group]))
        # Repeat EXTINF for fallback URLs; compatible clients group equal names into routes.
        for address in channel['urls']:
            source_ids = channel.get('origins', {}).get(address, [])
            source_attrs = ' x-source-id="' + ','.join(source_ids) + '"' if source_ids else ''
            if source_ids and source_names:
                source_attrs += ' x-source-name="' + m3u_escape(' / '.join(source_names[key] for key in source_ids)) + '"'
            m3u.append('#EXTINF:-1 ' + attrs + source_attrs + ',' + channel['name'])
            m3u.extend(channel.get('directives', []))
            for name, value in channel.get('headers', {}).items():
                if name.lower() == 'user-agent': m3u.append('#EXTVLCOPT:http-user-agent=' + value)
                if name.lower() == 'referer': m3u.append('#EXTVLCOPT:http-referrer=' + value)
            if channel.get('headers'):
                m3u.append('#EXTHTTP:' + json.dumps(channel['headers'], ensure_ascii=False, separators=(',', ':')))
            m3u.append(address)
    live_json = {'name': live_name, 'groups': [{'name': group, 'channels': channels} for group, channels in groups.items()]}
    txt = []
    for group, channels in groups.items():
        txt.append(group + ',#genre#')
        for channel in channels:
            # Repeated names in the same group become fallback routes in TVBox.
            txt.extend(channel['name'] + ',' + address for address in channel['urls'])
    return {'json': live_json, 'm3u': '\n'.join(m3u) + '\n', 'txt': '\n'.join(txt) + ('\n' if txt else '')}


def module_outputs(data, base_url, repository, channel_rows, source_registry=None):
    """Derive module subscriptions from the same maintained library and original M3U rows."""
    files, links = {}, []
    own_urls = project_m3u_urls(base_url, repository)
    for module, name in MODULE_NAMES.items():
        path = 'data/modules/' + module + '.json'
        manifest = {'version': 1, 'name': name, 'module': module}
        if module in {'television', 'entertainment'}:
            playlist_path = 'data/modules/' + module + '.m3u'
            playlists = copy.deepcopy(data['live']['playlists'])
            for playlist in playlists:
                if playlist['url'] in own_urls:
                    playlist['url'] = playlist['url'][:-len('data/live.m3u')] + playlist_path
            manifest['live'] = {'name': data['live']['name'], 'playlists': playlists}
            # Filter before display normalization. Platform rooms named after a TV channel
            # retain their original group, title, metadata and per-route playback options.
            selected = [row for row in channel_rows if live_channels.is_platform_group(row.get('group')) == (module == 'entertainment')]
            if module == 'television':
                selected = live_channels.public_channels(selected, source_registry)
            files[playlist_path] = live_outputs(selected, data['live']['name'], base_url, source_registry)['m3u']
        elif module == 'vod':
            manifest['vod'] = {'name': data['vod']['name'], 'url': data['vod']['url']}
            manifest['warehouses'] = copy.deepcopy(data['warehouses'])
        # Sports rooms and schedules use the client's independent public-page backend.
        # This manifest intentionally adds no dependency on VOD or the general M3U.
        files[path] = manifest
        links.append({'module': module, 'name': name, 'path': path})
    return files, links


def build(data, base_url, repository='yujuanIt/TVSources', source_registry=None, channel_rows=None, channel_url=None):
    validate(data); url(base_url, '站点地址'); base_url = base_url.rstrip('/') + '/'
    require(not urlsplit(base_url).query and not urlsplit(base_url).fragment, '站点地址不能包含查询参数或片段')
    live, vod = data['live'], data['vod']
    original_rows = validate_channels([] if channel_rows is None else channel_rows)
    channel_rows = live_channels.public_channels(original_rows, source_registry)
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*', repository)), '仓库名称格式需要 owner/repo')
    module_files, module_links = module_outputs(data, base_url, repository, original_rows, source_registry)
    # Relative links keep Pages, Raw, and accelerator endpoints on the selected route.
    sites = []
    for item in active(vod['sites']):
        if not item.get('context'):
            sites.append(vod_config.public_site(item, base_url))
    vod_bundles = vod_config.bundles(vod)
    bundled_files = {'vod/' + key + '.json': value for key, value in vod_bundles.items()}
    lives = [{'name': item['name'], 'type': 0, 'url': item['url'], 'headers': item.get('headers', {})} for item in active(live['playlists'])]
    box = {'sites': sites, 'lives': lives, 'parses': []}
    if vod.get('spider'):
        box['spider'] = vod['spider']
    live_files = live_outputs(channel_rows, live['name'], base_url, source_registry)
    warehouse = {'urls': [{'name': data['name'], 'url': './box.json'}] +
                 [{'name': vod['contexts'][key]['name'], 'url': './vod/' + key + '.json'} for key in vod_bundles] +
                 [{'name': item['name'], 'url': item['url']} for item in active(data['warehouses'])]}
    # Keep each warehouse group bounded while publishing every configured source.
    warehouse_groups = {}
    group_links = []
    if len(warehouse['urls']) > 6:
        for start in range(0, len(warehouse['urls']), 6):
            path = 'warehouse-' + str(start // 6 + 1) + '.json'
            entries = warehouse['urls'][start:start + 6]
            warehouse_groups[path] = {'urls': entries}
            group_links.append({'name': '多仓分组 ' + str(start // 6 + 1), 'path': path, 'count': len(entries)})
    stamp = {'name': data['name'], 'generatedAt': datetime.now(timezone.utc).isoformat(),
             'channels': len({(row['group'], row['name']) for row in channel_rows}), 'livePlaylists': len(active(live['playlists'])),
             'sites': len(active(vod['sites'])), 'warehouses': len(active(data['warehouses']))}
    hosting = {'repository': repository, 'editUrl': 'https://github.com/' + repository + '/edit/main/data/library.json',
               'endpoints': source_endpoints(base_url, repository),
               'warehouseGroups': group_links, 'modules': module_links}
    hosting.update(vodSiteFile=vod_config.SITE_FILE, vodSiteUrl=vod['url'],
                   vodSiteEditUrl='https://github.com/' + repository + '/edit/main/' + vod_config.SITE_FILE)
    if channel_url is not None:
        hosting.update(channelFile='data/live.m3u', channelUrl=channel_url, channelCount=stamp['channels'],
                       channelEditUrl='https://github.com/' + repository + '/edit/main/data/live.m3u')
    if source_registry is not None:
        hosting['liveSources'] = 'data/live-sources.json'
    hosting['vodContexts'] = [{'name': vod['contexts'][key]['name'], 'path': 'vod/' + key + '.json', 'count': len(value['sites'])}
                              for key, value in vod_bundles.items()]
    vod_output = {key: value for key, value in box.items() if key != 'lives'}
    return {'box.json': box, 'vod.json': vod_output, 'live.json': live_files['json'],
            'warehouse.json': warehouse, 'manifest.json': stamp, 'hosting.json': hosting, 'live.m3u': live_files['m3u'],
            'data/live.m3u': live_files['m3u'], 'live.txt': live_files['txt'],
            vod_config.SITE_FILE: vod_config.site_list(data),
            **module_files, **warehouse_groups, **bundled_files, **({'data/live-sources.json': source_registry} if source_registry is not None else {})}


def publish_files(data, base_url, output, repository='yujuanIt/TVSources'):
    channel_url, channel_rows = read_project_channels(data, base_url, repository)
    registry_path = SOURCE / 'data/live-sources.json'
    if registry_path.is_file():
        require(not registry_path.is_symlink() and registry_path.resolve().is_relative_to(SOURCE.resolve()), '直播来源清单必须是仓库内的真实文件')
    source_registry = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.is_file() else None
    generated = build(data, base_url, repository, source_registry, channel_rows, channel_url)
    output = Path(output).resolve()
    require(output != SOURCE.resolve(), '输出目录必须与源文件目录分开')
    require((output != ROOT and ROOT not in output.parents) or output.is_relative_to(ROOT / '.tools'), '仓库内的输出请放在 .tools 下')
    expected = {'index.html', 'assets/style.css', 'assets/editor.js', 'data/library.json', '.nojekyll'} | set(generated)
    if output.exists():
        require(not any(p.is_symlink() for p in output.rglob('*')), '输出中不允许符号链接')
        obsolete = [p for p in output.iterdir() if p.is_file() and re.fullmatch(r'warehouse-[1-9][0-9]*\.json', p.name) and p.name not in expected]
        obsolete.extend(p for p in (output / 'vod').glob('*.json') if p.relative_to(output).as_posix() not in expected)
        registry_output = output / 'data/live-sources.json'
        if registry_output.is_file() and 'data/live-sources.json' not in expected:
            obsolete.append(registry_output)
        unexpected = [p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.relative_to(output).as_posix() not in expected and p not in obsolete]
        require(not unexpected, '输出目录存在非发布文件，拒绝继续：' + ', '.join(unexpected))
        for path in obsolete:
            path.unlink()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / 'index.html', output / 'index.html')
    (output / 'assets').mkdir(exist_ok=True); (output / 'data').mkdir(exist_ok=True)
    for name in ['style.css', 'editor.js']:
        shutil.copy2(SOURCE / 'assets' / name, output / 'assets' / name)
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_json(output / 'data' / 'library.json', vod_config.manifest(data))
    for name, value in generated.items():
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str): (output / name).write_text(value, encoding='utf-8')
        else: write_json(output / name, value)
    (output / '.nojekyll').write_text('', encoding='utf-8')
    return generated['manifest.json']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=SOURCE / 'data' / 'library.json')
    parser.add_argument('--output', type=Path, default=ROOT / '.tools' / 'site')
    parser.add_argument('--base-url', default='https://yujuanit.github.io/TVSources/')
    parser.add_argument('--repository', default='yujuanIt/TVSources')
    args = parser.parse_args()
    try:
        library = json.loads(args.input.read_text(encoding='utf-8'))
        data = vod_config.materialize(library, vod_config.read_site_list(args.input.parent.parent))
        print(json.dumps(publish_files(data, args.base_url, args.output, args.repository), ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.exit(1, '配置检查失败：' + str(error) + '\n')


if __name__ == '__main__':
    main()
