#!/usr/bin/env python3
"""Import TVBox sites and refresh upstream fields while preserving owner edits/deletions."""
import argparse
import base64
import concurrent.futures
from contextlib import contextmanager
import copy
import fcntl
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import json5

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vod_config as config

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 4 * 1024 * 1024
CONFIG_FIELDS = ('spider', 'parses', 'rules', 'headers', 'flags', 'ads', 'hosts', 'doh', 'proxy', 'm3u8ads', 'ijk')
WAREHOUSE_KEYS = ('urls', 'storeHouse', 'storehouse', 'warehouses', 'configs')
MISSING = object()


@lru_cache(maxsize=1)
def source_builder():
    spec = importlib.util.spec_from_file_location('vod_source_builder', ROOT / 'scripts/build-source-site.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    return builder


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def strict_object(pairs):
    output = {}
    for key, value in pairs:
        config.require(key not in output, 'JSON 字段重复：' + key)
        output[key] = value
    return output


def parse(payload):
    if len(payload) > MAX_BYTES:
        raise ValueError('配置超过 4 MiB')
    text = payload.decode('utf-8', errors='replace').lstrip('\ufeff').strip()
    if '**' in text:
        tail = text.rsplit('**', 1)[1].strip()
        if re.fullmatch(r'[A-Za-z0-9+/=\s]{16,}', tail):
            decoded = base64.b64decode(re.sub(r'\s', '', tail), validate=True).decode('utf-8-sig').strip()
            if decoded.startswith(('{', '[', '//', '/*')):
                text = decoded
    encoded = text[9:] if text.startswith('base64://') else text
    if re.fullmatch(r'[A-Za-z0-9+/=\s]{16,}', encoded):
        text = base64.b64decode(re.sub(r'\s', '', encoded), validate=True).decode('utf-8-sig')
    if not text.lstrip().startswith(('{', '[', '//', '/*')):
        raise ValueError('响应不是 TVBox JSON / JSON5 配置')
    try:
        value = json.loads(text, object_pairs_hook=strict_object)
    except ValueError:
        value = json5.loads(text, allow_duplicate_keys=False)
    if not isinstance(value, (dict, list)):
        raise ValueError('配置顶层必须是对象或数组')
    return value


def network_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('上游需要不含登录密码的 HTTP(S) URL')
    netloc = parsed.hostname.encode('idna').decode()
    if ':' in netloc:
        netloc = '[' + netloc + ']'
    if parsed.port:
        netloc += ':' + str(parsed.port)
    return urlunsplit((parsed.scheme, netloc, quote(parsed.path, safe='/%:@!$&\'()*+,;='), parsed.query, parsed.fragment))


def fetch(source):
    # The python.org macOS installation may not have run Install Certificates.command.
    # Use the OS CA bundle in that case; certificate verification remains enabled.
    cafile = '/etc/ssl/cert.pem' if sys.platform == 'darwin' and not os.environ.get('SSL_CERT_FILE') else None
    context = ssl.create_default_context(cafile=cafile)
    request = Request(network_url(source['url']), headers={'User-Agent': 'okhttp/3.12.13', 'Accept-Encoding': 'identity', **source.get('headers', {})})
    with urlopen(request, timeout=20, context=context) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('配置超过 4 MiB')
        return body, response.url


def validate_registry(value):
    config.require(isinstance(value, dict) and value.get('version') == 1, '点播来源清单需要 version: 1')
    config.require(isinstance(value.get('automaticSyncEnabled'), bool), 'automaticSyncEnabled 必须是布尔值')
    config.require(value.get('newSitesEnabled') is True or value.get('newSitesEnabled') is False, 'newSitesEnabled 必须是布尔值')
    sources = value.get('sources')
    config.require(isinstance(sources, list) and len(sources) <= 32, '点播上游 sources 需要最多 32 项的数组')
    ids = set()
    for source in sources:
        key = source.get('id') if isinstance(source, dict) else None
        config.require(isinstance(key, str) and bool(config.CONTEXT_ID.fullmatch(key)) and key not in ids, '点播上游 ID 无效或重复')
        ids.add(key)
        config.require(isinstance(source.get('name'), str) and bool(source['name'].strip()), '点播上游需要名称')
        network_url(source.get('url', ''))
        config.require(isinstance(source.get('enabled', True), bool), '上游 enabled 必须是布尔值')
        config.require(isinstance(source.get('headers', {}), dict), '上游 headers 必须是对象')
        config.require(isinstance(source.get('mirrors', []), list) and len(source.get('mirrors', [])) <= 4, 'mirrors 需要最多 4 个备用地址的数组')
        for mirror in source.get('mirrors', []):
            network_url(mirror)
    return value


def registry_from_library(library):
    return {'version': 1, 'automaticSyncEnabled': True, 'newSitesEnabled': True,
            'sync': {'intervalHours': 6, 'timeZone': 'Asia/Shanghai'},
            'sources': [{'id': 'box_' + digest(row['url'])[:12], **copy.deepcopy(row)}
                        for row in library['warehouses']]}


def expand(source, fetcher=fetch):
    """Fetch bounded nested warehouses; never execute the imported JAR/JS/Python."""
    pending = [(source['url'], source['name'], 0, source.get('mirrors', []))]
    seen, documents, failures, rejected = set(), [], [], []
    total = 0
    while pending:
        url, name, depth, mirrors = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if len(seen) > 32:
            failures.append({'url': url, 'reason': '单个上游超过 32 份配置'}); break
        try:
            last = None
            for address in [url, *mirrors]:
                try:
                    fetched = fetcher({**source, 'url': address})
                    payload, base = fetched if isinstance(fetched, tuple) else (fetched, address)
                    total += len(payload)
                    config.require(total <= 16 * 1024 * 1024, '单个上游超过 16 MiB')
                    data = parse(payload); break
                except Exception as error:
                    last = error
            else:
                raise ValueError('配置请求或解析失败：' + type(last).__name__) from last
            if isinstance(data, list) and data and all(isinstance(row, dict) and 'api' in row for row in data):
                data = {'sites': data}
            entries = data if isinstance(data, list) else next((data[key] for key in WAREHOUSE_KEYS if isinstance(data.get(key), list)), None)
            if isinstance(data, dict) and 'sites' in data:
                sites = data['sites']
                config.require(isinstance(sites, list) and 0 < len(sites) <= 2000, 'sites 需要 1–2000 个站点')
                clean, keys = [], set()
                for row in sites:
                    try:
                        config.require(isinstance(row, dict) and config.site_key(row.get('key')), '站点 key 无效')
                        config.require(row['key'] not in keys, '同一配置中的站点 key 重复')
                        site = config.normalize_relative(row, base)
                        site.setdefault('type', 0)
                        config.require(type(site['type']) is int and site['type'] in (0, 1, 3, 4), '站点类型不支持')
                        config.require(isinstance(site.get('name'), str) and bool(site['name'].strip()), '站点名称无效')
                        config.require(isinstance(site.get('api'), str) and bool(site['api'].strip()), '站点 API 无效')
                        for field in ('api', 'jar', 'playUrl'):
                            if site.get(field): site[field] = config.absolute(base, site[field])
                        if site['api'].startswith('csp_'):
                            config.require(bool(site.get('jar') or data.get('spider')), '缺少 JAR')
                        else:
                            network_url(site['api'])
                        site.setdefault('searchable', 1)
                        site.setdefault('enabled', True)
                        keys.add(site['key']); clean.append(site)
                    except (ValueError, TypeError) as error:
                        rejected.append({'url': url, 'key': row.get('key') if isinstance(row, dict) else None, 'reason': str(error)})
                config.require(bool(clean), '没有可导入的站点')
                # Use the subscribed leaf URL for stable identity, even when redirects change.
                context_id = source['id'] if depth == 0 else source['id'] + '_' + digest(url)[:10]
                context = {'name': name, 'url': base, **{key: copy.deepcopy(data[key]) for key in CONFIG_FIELDS if key in data}}
                context = {**context, **config.public_context(context)}
                source_builder().validate({'version': 1, 'name': name, 'live': {'name': '直播', 'playlists': []}, 'warehouses': [],
                                           'vod': {'name': name, 'contexts': {context_id: context},
                                                   'sites': [{**row, 'context': context_id} for row in clean]}})
                documents.append({'id': context_id, 'context': context, 'sites': clean, 'url': url})
            else:
                config.require(isinstance(entries, list) and bool(entries), '配置没有 sites 或有效的多仓列表')
                config.require(depth < 3 and len(entries) + len(pending) <= 64, '多仓层级或条目过多')
                for row in entries:
                    address = row if isinstance(row, str) else row.get('url', row.get('sourceUrl', row.get('sourceURL', ''))) if isinstance(row, dict) else ''
                    title = row.get('name', row.get('sourceName', name)) if isinstance(row, dict) else name
                    if address.startswith('tvbox://'):
                        address = address[8:]
                    address = config.absolute(base, address)
                    network_url(address)
                    pending.append((address, title, depth + 1, []))
        except Exception as error:
            failures.append({'url': url, 'reason': str(error)[:160]})
    return {'id': source['id'], 'name': source['name'], 'documents': documents, 'failed': failures, 'rejected': rejected}


def three_way(local, baseline, upstream):
    """Only replace fields that still equal the previous upstream baseline."""
    if local == baseline:
        return copy.deepcopy(upstream) if upstream is not MISSING else MISSING
    if isinstance(local, dict) and isinstance(baseline, dict) and isinstance(upstream, dict):
        result = {}
        for key in dict.fromkeys([*local, *upstream]):
            value = three_way(local.get(key, MISSING), baseline.get(key, MISSING), upstream.get(key, MISSING))
            if value is not MISSING:
                result[key] = value
        return result
    return copy.deepcopy(local) if local is not MISSING else MISSING


def merge(library, registry, state, results):
    output = copy.deepcopy(library)
    previous = copy.deepcopy(state) if state is not None else {'version': 1, 'sites': {}, 'contexts': {}, 'deleted': []}
    config.require(previous.get('version') == 1 and isinstance(previous.get('sites'), dict) and isinstance(previous.get('contexts'), dict) and isinstance(previous.get('deleted'), list), '点播同步状态无效，请保留有效状态文件')
    rows = output['vod']['sites']; dependencies = output['vod'].setdefault('contexts', {})
    indexed = {}
    for row in rows:
        if row.get('_syncId'):
            config.require(row['_syncId'] not in indexed, '站点 _syncId 重复')
            indexed[row['_syncId']] = row
    deleted = set(previous['deleted']) | (set(previous['sites']) - set(indexed))
    deleted -= set(indexed)
    report = {'added': 0, 'updated': 0, 'keptDeleted': 0, 'retainedMissing': 0, 'sources': [], 'complete': True}
    seen = set()
    for result in results:
        source_report = {key: copy.deepcopy(result[key]) for key in ('id', 'name', 'failed', 'rejected')}
        source_report['sites'] = sum(len(document['sites']) for document in result['documents'])
        report['sources'].append(source_report)
        report['complete'] &= not bool(result['failed'])
        for document in result['documents']:
            context_id = document['id']; context = document['context']
            dependencies[context_id] = three_way(dependencies.get(context_id, context), previous['contexts'].get(context_id, context), context)
            previous['contexts'][context_id] = copy.deepcopy(context)
            for raw in document['sites']:
                row = copy.deepcopy(raw)
                sync_id = digest([context_id, row['key']])[:32]
                row.update(context=context_id, origin={'source': result['id'], 'name': result['name'], 'url': document['url'], 'key': raw['key']}, _syncId=sync_id)
                if registry['newSitesEnabled'] is False:
                    row['enabled'] = False
                seen.add(sync_id)
                if sync_id in deleted:
                    report['keptDeleted'] += 1
                elif sync_id in indexed:
                    current = indexed[sync_id]
                    replacement = three_way(current, previous['sites'].get(sync_id, current), row)
                    if current != replacement:
                        current.clear(); current.update(replacement); report['updated'] += 1
                else:
                    # An owner-created entry with the same scoped key takes precedence.
                    if any(config.site_identity(existing) == config.site_identity(row) for existing in rows):
                        deleted.add(sync_id); report['keptDeleted'] += 1
                    else:
                        rows.append(row); indexed[sync_id] = row; report['added'] += 1
                previous['sites'][sync_id] = copy.deepcopy(row)
    report['retainedMissing'] = len(set(indexed) - seen)
    report['sites'] = len(rows)
    previous['deleted'] = sorted(deleted)
    return output, previous, report


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as temporary:
        temporary.write(content); name = temporary.name
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


@contextmanager
def sync_lock(root):
    path = root / '.tools/vod-sync.lock'; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('另一个点播同步正在运行，请等待完成') from None
        yield


def recover(root, dry_run=False):
    """Recover an interrupted two-file update only when neither file was owner-edited."""
    journal = root / '.tools/vod-sync-pending.json'
    if not journal.exists():
        return
    pending = read_json(journal)
    names = set(pending.get('files', {}))
    config.require(pending.get('version') == 1 and names in ({'vod-sites.json', 'vod-sync-state.json'}, {'library.json', 'vod-sites.json', 'vod-sync-state.json'}), '点播同步恢复记录无效')
    current = {name: read_json(root / 'data' / name) for name in pending['files']}
    for name, values in pending['files'].items():
        config.require(isinstance(values, dict) and {'before', 'after'} <= values.keys(), '点播同步恢复记录缺少快照')
        config.require(current[name] == values['before'] or current[name] == values['after'], '上次同步中断后文件被手动编辑，请先核对 .tools/vod-sync-pending.json：' + name)
    if dry_run:
        config.require(all(current[name] == values['after'] for name, values in pending['files'].items()), '存在未完成同步，请先正常运行脚本完成恢复，再预览')
        return
    for name, values in pending['files'].items():
        write_json(root / 'data' / name, values['after'])
    journal.unlink()


def save_pair(root, before, output, state, updated_state, library_before=None, library_after=None):
    if before == output and state == updated_state and library_before == library_after:
        return
    journal = root / '.tools/vod-sync-pending.json'
    files = {'vod-sites.json': {'before': before, 'after': output}, 'vod-sync-state.json': {'before': state, 'after': updated_state}}
    if library_before != library_after: files['library.json'] = {'before': library_before, 'after': library_after}
    write_json(journal, {'version': 1, 'files': files})
    for name, values in files.items(): write_json(root / 'data' / name, values['after'])
    journal.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bootstrap-from-warehouses', action='store_true', help='首次将现有 warehouses 登记为同步上游，导入后清空该列表')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--preview-dir', type=Path, default=ROOT / '.tools/vod-preview')
    parser.add_argument('--report', type=Path, default=ROOT / '.tools/vod-sync-report.json')
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args(argv)
    with sync_lock(args.root):
        return synchronize(args)


def synchronize(args):
    recover(args.root, args.dry_run)
    path = args.root / 'data/library.json'; registry_path = args.root / 'data/vod-sources.json'; state_path = args.root / 'data/vod-sync-state.json'
    manifest = json.loads(path.read_text(encoding='utf-8')); sites_before = config.read_site_list(args.root)
    library = config.materialize(manifest, sites_before)
    registry_before = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else None
    registry = registry_before if registry_before is not None else registry_from_library(library) if args.bootstrap_from_warehouses else None
    validate_registry(registry)
    if not registry['automaticSyncEnabled']:
        print('点播自动同步已停用'); return 0
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    config.require(state is not None or not any(row.get('_syncId') for row in library['vod']['sites']), '已有托管站点但缺少同步状态，拒绝重建以免丢失删除记录')
    enabled = [source for source in registry['sources'] if source.get('enabled', True)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(expand, enabled))
    if enabled and not any(result['documents'] for result in results):
        write_json(args.report, {'success': False, 'sources': results})
        print('全部点播上游失败，站点列表和状态保持原样', file=sys.stderr); return 1
    output, updated_state, report = merge(library, registry, state, results)
    if args.bootstrap_from_warehouses:
        output['warehouses'] = []
    source_builder().validate(output)
    config.require(len(json.dumps(output, ensure_ascii=False).encode()) <= MAX_BYTES, '生成清单超过 App 的 4 MiB 上限')
    # Do not replace a file the owner edited while network requests were running.
    config.require(json.loads(path.read_text(encoding='utf-8')) == manifest and config.read_site_list(args.root) == sites_before, '抓取期间清单被修改，本次结果未写入，请重新运行')
    config.require((json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None) == state, '抓取期间同步状态被修改，请重新运行')
    config.require((json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else None) == registry_before, '抓取期间上游清单被修改，请重新运行')
    if args.dry_run:
        write_json(args.preview_dir / 'library.json', config.manifest(output))
        write_json(args.preview_dir / 'vod-sites.json', config.site_list(output))
        write_json(args.preview_dir / 'vod-sync-state.json', updated_state)
        write_json(args.preview_dir / 'vod-sources.json', registry)
    else:
        if registry_before is None:
            write_json(registry_path, registry)
        save_pair(args.root, sites_before, config.site_list(output), state, updated_state, manifest, config.manifest(output))
    write_json(args.report, report)
    if args.summary:
        with args.summary.open('a', encoding='utf-8') as summary:
            summary.write('\n### 点播站点同步\n\n' + f"站点 {report['sites']}，新增 {report['added']}，更新 {report['updated']}，保留手动删除 {report['keptDeleted']}。\n\n")
            for source in report['sources']:
                summary.write(f"- {source['name']}：导入 {source['sites']} 项，失败 {len(source['failed'])}，跳过非法项 {len(source['rejected'])}\n")
    print(json.dumps({key: value for key, value in report.items() if key != 'sources'}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
