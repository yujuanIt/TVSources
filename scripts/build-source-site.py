#!/usr/bin/env python3
"""Validate one editable document and build only the public GitHub Pages source files."""
import argparse
import copy
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT
ID = re.compile(r'^[A-Za-z0-9_-]+$')
BAD_CONTROL = re.compile(r'[\x00-\x1f\x7f]')
LIVE_SCHEMES = {'http', 'https', 'rtsp', 'rtmp', 'udp', 'rtp'}


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
    for entry in rows(live.get('playlists'), 'live.playlists'):
        text(entry.get('name'), '直播列表名称'); url(entry.get('url'), '直播列表地址')
        headers(entry.get('headers', {}), '直播列表请求头')
    for entry in rows(live.get('channels'), 'live.channels'):
        text(entry.get('name'), '频道名称'); text(entry.get('group', '未分组'), '频道分组')
        require(isinstance(entry.get('urls'), list) and len(entry['urls']) > 0, '频道至少需要一条线路')
        for address in entry['urls']:
            url(address, '频道线路', True)
        url(entry.get('logo', ''), '频道图标', empty=True)
        text(entry.get('tvgId', ''), '频道 EPG 标识', True)
        headers(entry.get('headers', {}), '频道请求头')
    categories = rows(vod.get('categories'), 'vod.categories')
    category_ids = set()
    for category in categories:
        key = text(category.get('id'), '分类 ID'); text(category.get('name'), '分类名称')
        require(bool(ID.fullmatch(key)) and key not in category_ids, '分类 ID 需要唯一的字母 / 数字 / 下划线 / 连字符')
        category_ids.add(key)
    movie_ids = set()
    for movie in rows(vod.get('movies'), 'vod.movies'):
        key = text(movie.get('id'), '影片 ID'); text(movie.get('name'), '影片名称')
        require(bool(ID.fullmatch(key)) and key not in movie_ids, '影片 ID 需要唯一的字母 / 数字 / 下划线 / 连字符')
        movie_ids.add(key); require(movie.get('category') in category_ids, '影片分类必须使用 categories 中已有的 ID')
        for field in ['year', 'remarks', 'actor', 'director', 'area']:
            text(movie.get(field, ''), '影片 ' + field, True)
        require(isinstance(movie.get('description', ''), str), '影片简介必须是文字')
        url(movie.get('poster', ''), '影片海报', empty=True)
        headers(movie.get('headers', {}), '影片请求头')
        require(isinstance(movie.get('sniff', False), bool), 'sniff 必须是 true 或 false')
        routes = rows(movie.get('routes'), '影片 routes'); require(bool(routes), '影片至少需要一条播放线路')
        for route in routes:
            text(route.get('name'), '线路名称'); require('$$$' not in route['name'], '线路名称不能包含 $$$')
            headers(route.get('headers', {}), '线路请求头')
            episodes = rows(route.get('episodes'), '线路 episodes'); require(bool(episodes), '每条线路至少需要一集')
            for episode in episodes:
                text(episode.get('name'), '集名'); require(not any(c in episode['name'] for c in '#$'), '集名不能包含 # 或 $')
                url(episode.get('url'), '影片视频地址'); headers(episode.get('headers', {}), '单集请求头')
    site_keys = {'juan_personal'}
    for site in rows(vod.get('sites'), 'vod.sites'):
        text(site.get('key'), '接口 key'); text(site.get('name'), '接口名称')
        require(bool(ID.fullmatch(site['key'])) and site['key'] not in site_keys, '接口 key 需要唯一，且不能使用 juan_personal')
        site_keys.add(site['key']); require(type(site.get('type')) is int and site['type'] in {0, 1, 3, 4}, '接口 type 支持 0 / 1 / 3 / 4')
        api = text(site.get('api'), '接口 api')
        if api.startswith('csp_'):
            require(site['type'] == 3 and bool(site.get('jar') or vod.get('spider')), 'csp 插件需设置 type: 3 及 jar 或 vod.spider')
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


def active(items):
    return [item for item in items if item.get('enabled', True)]


def m3u_escape(value):
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def build(data, base_url, repository='yujuanIt/TVSources'):
    validate(data); url(base_url, '站点地址'); base_url = base_url.rstrip('/') + '/'
    require(not urlsplit(base_url).query and not urlsplit(base_url).fragment, '站点地址不能包含查询参数或片段')
    live, vod = data['live'], data['vod']
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*', repository)), '仓库名称格式需要 owner/repo')
    # Relative links keep Pages, Raw, and accelerator endpoints on the selected route.
    sites = [{'key': 'juan_personal', 'name': vod['name'], 'type': 3, 'api': './vod.js',
              'ext': './catalog.json', 'searchable': 1, 'quickSearch': 1, 'filterable': 0}]
    for item in active(vod['sites']):
        site = copy.deepcopy(item); site.pop('enabled', None); sites.append(site)
    lives = [{'name': live['name'], 'type': 0, 'url': './live.json'}]
    lives.extend({'name': item['name'], 'type': 0, 'url': item['url'], 'headers': item.get('headers', {})} for item in active(live['playlists']))
    box = {'sites': sites, 'lives': lives, 'parses': []}
    if vod.get('spider'):
        box['spider'] = vod['spider']
    class_names = {item['id']: item['name'] for item in vod['categories']}
    movies = copy.deepcopy(active(vod['movies']))
    for movie in movies:
        movie['typeName'] = class_names[movie['category']]
    catalog = {'name': vod['name'], 'categories': vod['categories'], 'movies': movies}
    groups = {}; m3u = ['#EXTM3U']
    for channel in active(live['channels']):
        group = channel.get('group', '未分组')
        groups.setdefault(group, []).append({'name': channel['name'], 'logo': channel.get('logo', ''),
            'urls': channel['urls'], 'headers': channel.get('headers', {})})
        attrs = 'tvg-id="{}" tvg-name="{}" tvg-logo="{}" group-title="{}"'.format(*(m3u_escape(v) for v in [channel.get('tvgId', ''), channel['name'], channel.get('logo', ''), group]))
        # Repeat EXTINF for fallback URLs; compatible clients group equal names into routes.
        for address in channel['urls']:
            m3u.append('#EXTINF:-1 ' + attrs + ',' + channel['name'])
            for name, value in channel.get('headers', {}).items():
                if name.lower() == 'user-agent': m3u.append('#EXTVLCOPT:http-user-agent=' + value)
                if name.lower() == 'referer': m3u.append('#EXTVLCOPT:http-referrer=' + value)
            m3u.append(address)
    live_json = {'name': live['name'], 'groups': [{'name': group, 'channels': channels} for group, channels in groups.items()]}
    warehouse = {'urls': [{'name': data['name'], 'url': './box.json'}] +
                 [{'name': item['name'], 'url': item['url']} for item in active(data['warehouses'])]}
    # Existing APKs import at most six configurations per warehouse. Publish complete
    # batches too, so no source silently disappears behind that client-side limit.
    warehouse_groups = {}
    group_links = []
    if len(warehouse['urls']) > 6:
        for start in range(0, len(warehouse['urls']), 6):
            path = 'warehouse-' + str(start // 6 + 1) + '.json'
            entries = warehouse['urls'][start:start + 6]
            warehouse_groups[path] = {'urls': entries}
            group_links.append({'name': '多仓分组 ' + str(start // 6 + 1), 'path': path, 'count': len(entries)})
    stamp = {'name': data['name'], 'generatedAt': datetime.now(timezone.utc).isoformat(),
             'channels': len(active(live['channels'])), 'livePlaylists': len(active(live['playlists'])),
             'movies': len(movies), 'sites': len(active(vod['sites'])), 'warehouses': len(active(data['warehouses']))}
    raw_base = 'https://raw.githubusercontent.com/' + repository + '/source-data/'
    hosting = {'repository': repository, 'editUrl': 'https://github.com/' + repository + '/edit/main/data/library.json',
               'endpoints': [{'name': '免费加速 · GH-Proxy', 'base': 'https://gh-proxy.com/' + raw_base},
                             {'name': '备用加速 · GHFast', 'base': 'https://ghfast.top/' + raw_base},
                             {'name': 'GitHub Pages 原址', 'base': base_url},
                             {'name': 'GitHub Raw 原址', 'base': raw_base}],
               'warehouseGroups': group_links}
    vod_config = {key: value for key, value in box.items() if key != 'lives'}
    return {'box.json': box, 'vod.json': vod_config, 'catalog.json': catalog, 'live.json': live_json,
            'warehouse.json': warehouse, 'manifest.json': stamp, 'hosting.json': hosting, 'live.m3u': '\n'.join(m3u) + '\n',
            **warehouse_groups}


def publish_files(data, base_url, output, repository='yujuanIt/TVSources'):
    generated = build(data, base_url, repository)
    output = Path(output).resolve()
    require(output != SOURCE.resolve(), '输出目录必须与源文件目录分开')
    require((output != ROOT and ROOT not in output.parents) or output.is_relative_to(ROOT / '.tools'), '仓库内的输出请放在 .tools 下')
    expected = {'index.html', 'assets/style.css', 'assets/editor.js', 'data/library.json', 'vod.js', '.nojekyll'} | set(generated)
    if output.exists():
        require(not any(p.is_symlink() for p in output.rglob('*')), '输出中不允许符号链接')
        old_groups = [p for p in output.iterdir() if p.is_file() and re.fullmatch(r'warehouse-[1-9][0-9]*\.json', p.name) and p.name not in expected]
        unexpected = [p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.relative_to(output).as_posix() not in expected and p not in old_groups]
        require(not unexpected, '输出目录存在非发布文件，拒绝继续：' + ', '.join(unexpected))
        for path in old_groups:
            path.unlink()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / 'index.html', output / 'index.html')
    (output / 'assets').mkdir(exist_ok=True); (output / 'data').mkdir(exist_ok=True)
    for name in ['style.css', 'editor.js']:
        shutil.copy2(SOURCE / 'assets' / name, output / 'assets' / name)
    shutil.copy2(SOURCE / 'assets' / 'vod.js', output / 'vod.js')
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_json(output / 'data' / 'library.json', data)
    for name, value in generated.items():
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
        data = json.loads(args.input.read_text(encoding='utf-8'))
        print(json.dumps(publish_files(data, args.base_url, args.output, args.repository), ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.exit(1, '配置检查失败：' + str(error) + '\n')


if __name__ == '__main__':
    main()
