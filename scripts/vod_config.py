"""Shared validation and standard TVBox output for the editable, scoped site list."""
import copy
import re
import json
from pathlib import Path
from urllib.parse import urljoin

CONTEXT_ID = re.compile(r'^[A-Za-z0-9_-]+$')
CONTROL = re.compile(r'[\x00-\x1f\x7f]')
PRIVATE_SITE_FIELDS = {'enabled', 'context', 'origin', '_syncId'}
PRIVATE_CONTEXT_FIELDS = {'name', 'url'}
SITE_FILE = 'data/vod-sites.json'
SITE_FIELDS = {'sites', 'spider', 'contexts'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def manifest(data):
    """The public subscription contains a link, never a second maintained site list."""
    result = copy.deepcopy(data)
    vod = result['vod']
    require(isinstance(vod.get('url'), str) and vod['url'].startswith(('http://', 'https://')), 'vod.url 需要站点清单完整地址')
    result['vod'] = {key: vod[key] for key in ('name', 'url')}
    return result


def site_list(data):
    return {'version': 1, **{key: copy.deepcopy(value) for key, value in data['vod'].items() if key in SITE_FIELDS}}


def materialize(library, sites):
    """Join the two current input documents for internal validation and TVBox generation."""
    require(isinstance(library, dict) and isinstance(library.get('vod'), dict), '需要源站配置与 vod 对象')
    require(set(library['vod']) == {'name', 'url'}, 'vod 仅支持 name 和 url；站点请在 data/vod-sites.json 维护')
    require(isinstance(sites, dict) and sites.get('version') == 1 and set(sites) <= SITE_FIELDS | {'version'}, '站点清单需要 version: 1、sites 与可选 contexts、spider')
    require(isinstance(sites.get('sites'), list), '站点清单 sites 必须是数组')
    result = copy.deepcopy(library)
    result['vod'].update({key: copy.deepcopy(value) for key, value in sites.items() if key != 'version'})
    return result


def read_site_list(root):
    root = Path(root).resolve(); path = root / SITE_FILE
    require(not path.is_symlink() and path.resolve().is_relative_to(root), '站点清单必须是仓库内的真实文件')
    require(path.stat().st_size <= 4 * 1024 * 1024, '站点清单超过 4 MiB 上限')
    return json.loads(path.read_text(encoding='utf-8'))


def site_identity(site):
    return (site.get('context', ''), site['key'])


def site_key(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 256 and not CONTROL.search(value) and '/' not in value and '\\' not in value


def contexts(vod):
    value = vod.get('contexts', {})
    require(isinstance(value, dict) and len(value) <= 96, 'vod.contexts 需要最多 96 项的对象')
    for key, item in value.items():
        require(bool(CONTEXT_ID.fullmatch(key)), '依赖配置 ID 只能包含字母、数字、下划线和连字符')
        require(isinstance(item, dict), '依赖配置必须是对象')
        require(not {'sites', 'lives', 'urls', 'storeHouse', 'storehouse', 'warehouses', 'configs'} & item.keys(), '依赖配置不能内嵌站点、直播或多仓列表')
        require(isinstance(item.get('name'), str) and bool(item['name'].strip()), '依赖配置需要名称')
        require(isinstance(item.get('url'), str) and item['url'].startswith(('http://', 'https://')), '依赖配置需要原配置 URL')
        for field in ('parses', 'rules', 'headers', 'flags', 'ads', 'hosts', 'doh', 'proxy'):
            if field in item:
                require(isinstance(item[field], list), '依赖配置 ' + field + ' 必须是数组')
    return value


def absolute(base, value):
    """Keep signed absolute URLs byte-for-byte; expand only relative locations."""
    if not isinstance(value, str) or not value or value.startswith(('csp_', 'proxy://', 'parse:')):
        return value
    if value.startswith('json:'):
        return 'json:' + absolute(base, value[5:])
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value):
        return value
    path, separator, checksum = value.partition(';md5;')
    return urljoin(base, path) + (separator + checksum if separator else '')


def normalize_relative(value, base):
    if isinstance(value, dict):
        return {key: normalize_relative(item, base) if key not in ('header', 'headers') else copy.deepcopy(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_relative(item, base) for item in value]
    if isinstance(value, str) and value.startswith(('./', '../')):
        return absolute(base, value)
    return copy.deepcopy(value)


def public_site(site, base):
    result = {key: copy.deepcopy(value) for key, value in site.items() if key not in PRIVATE_SITE_FIELDS}
    for key in ('api', 'jar', 'playUrl'):
        if result.get(key):
            result[key] = absolute(base, result[key])
    if 'ext' in result:
        result['ext'] = normalize_relative(result['ext'], base)
    return result


def public_context(context):
    base = context['url']
    result = normalize_relative({key: value for key, value in context.items() if key not in PRIVATE_CONTEXT_FIELDS}, base)
    if result.get('spider'):
        result['spider'] = absolute(base, result['spider'])
    for item in result.get('parses', []):
        if isinstance(item, dict) and item.get('url'):
            item['url'] = absolute(base, item['url'])
    return result


def bundles(vod):
    result = {}
    for key, context in contexts(vod).items():
        sites = [public_site(site, context['url']) for site in vod['sites']
                 if site.get('context') == key and site.get('enabled', True)]
        if sites:
            result[key] = {**public_context(context), 'sites': sites}
            if not result[key].get('spider') and vod.get('spider'):
                result[key]['spider'] = vod['spider']
    return result
