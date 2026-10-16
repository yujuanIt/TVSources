#!/usr/bin/env python3
"""Refresh registered M3U inputs without discarding local channel edits or failed inputs."""
import argparse
import copy
import hashlib
from html import unescape
from http.client import HTTPException
import importlib.util
import json
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live_builder', ROOT / 'scripts/build-source-site.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
ATTR = re.compile(r'''([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')''')
CHANNEL_ID = re.compile(r'c_[a-f0-9]{24}')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def metadata(row):
    a = row['attrs']
    return dict(name=row['name'], group=a.get('group-title', '未分组'), tvgId=a.get('tvg-id', ''),
                logo=a.get('tvg-logo', ''), enabled=a.get('x-enabled', 'true'))


def route_key(row):
    return (row['url'], tuple(sorted((key.lower(), value) for key, value in row['headers'].items())), tuple(row['directives']))


def parse(content):
    # Use the publishing validator too, so an HTML error or half a playlist is never accepted.
    builder.parse_m3u(content)
    header, *blocks = re.split(r'(?m)(?=^#EXTINF:)', content.lstrip('\ufeff'))
    rows = []
    for block in blocks:
        channel = builder.parse_m3u('#EXTM3U\n' + block)[0]
        line = block.splitlines()[0]
        quote, separator = None, None
        for index, char in enumerate(line):
            if char in {'"', "'"}:
                if quote == char: quote = None
                elif quote is None: quote = char
            elif char == ',' and quote is None:
                separator = index; break
        attrs = {m[0]: unescape(m[1] or m[2]) for m in ATTR.findall(line[:separator])}
        attrs['group-title'] = channel['group']
        options = [line.strip() for line in block.splitlines()[1:] if line.strip().startswith(('#KODIPROP:', '#EXTVLCOPT:', '#EXTHTTP:'))]
        rows.append(dict(attrs=attrs, name=channel['name'], url=channel['urls'][0], options=options,
                         headers=channel['headers'], directives=channel.get('directives', []),
                         origins=channel.get('origins', {}).get(channel['urls'][0], [])))
    return header, rows


def normalized(value, hans):
    return re.sub(r'[\W_]+', '', hans(value).casefold())


def inherit_headers(row, defaults):
    present = {key.lower() for key in row['headers']}
    missing = {key: value for key, value in defaults.items() if key.lower() not in present}
    if missing:
        row['headers'].update(missing)
        row['options'].append('#EXTHTTP:' + json.dumps(missing, ensure_ascii=False, separators=(',', ':')))


def classify(row, hans):
    group, name = hans(row['attrs'].get('group-title', '')), hans(row['name'])
    path = urlsplit(row['url']).path.casefold()
    if any(word in group for word in ['更新时间', '提示', '公告']): return '公告'
    for label, aliases, segment in [('抖音', ['抖音'], '/douyin/'), ('虎牙', ['虎牙'], '/huya/'),
                                   ('B站', ['哔哩', 'B站'], '/bilibili/'), ('斗鱼', ['斗鱼'], '/douyu/'),
                                   ('Twitch', ['twitch'], '/twitch/'), ('SOOP', ['soop'], '/soop/'), ('YY', ['歪歪', 'YY'], '/yy/')]:
        if any(alias.casefold() in group.casefold() for alias in aliases) or segment in path: return label
    if '央视' in group or re.match(r'(?i)^(CCTV|CGTN)', name): return '央视'
    if any(word in group for word in ['香港', '台湾', '港澳台', '港·澳·台', 'myTV']) or re.search(r'香港|澳门|凤凰|翡翠|明珠|无线|TVBS|纬来|东森|靖天|天映|龙祥|中天', name): return '港澳台'
    if re.search(r'电影频道|经典剧场', group): return '影视'
    if '体育' in group or re.search(r'体育|竞技|篮球|足球|网球|钓鱼|围棋|(?i:sports?|SPOTV|Eurosport|NBA|NFL)', name): return '体育'
    if '动画频道' in group or re.search(r'少儿|幼儿|青少|卡通|动画|动漫', name): return '少儿'
    if '音乐频道' in group or re.search(r'音乐|广场舞', name): return '音乐'
    if re.search(r'电影|影院|影视|剧场|电视剧|星影|光影|重温经典|(?i:HBO|CHC)', name): return '影视'
    if '游戏频道' in group or re.search(r'游戏|电竞', name): return '游戏'
    if '咪视' in group: return '体育'
    if '☘' in group or '卫视' in group or '中国' in group or '卫视' in name: return '地方卫视'
    return '综合频道'


def serialize(header, rows, registry):
    names = {source['id']: source['name'] for source in registry['sources']}
    source_order = registry['mergePolicy']['sourceOrder']
    rank = {key: index for index, key in enumerate(source_order + [key for key in names if key not in source_order])}
    result = [line for line in header.rstrip().splitlines() if not line.startswith('#SOURCE:')]
    result.extend('#SOURCE:' + json.dumps({key: source[key] for key in ['id', 'name', 'url']}, ensure_ascii=False, separators=(',', ':')) for source in registry['sources'])
    seen = {}
    for original in rows:
        row = copy.deepcopy(original)
        signature = (row['attrs']['x-sync-id'], digest({k: v for k, v in row['attrs'].items() if k not in ['x-source-id', 'x-source-name']}), route_key(row))
        if signature in seen:
            seen[signature]['origins'].extend(key for key in row['origins'] if key not in seen[signature]['origins'])
        else:
            seen[signature] = row
    groups = registry['normalization']['groupOrder']
    def order(row):
        group, name = row['attrs']['group-title'], row['name']
        kind = groups.index(group) if group in groups else len(groups)
        cctv = re.match(r'(?i)^CCTV[\s-]*(\d+)(\+)?(?=[^0-9kK]|$)', name)
        detail = (0, int(cctv[1]), bool(cctv[2])) if cctv else (1 if re.match(r'(?i)^CCTV[\s-]*[48]K', name) else 2 if name.upper().startswith('CGTN') else 3, 0, False)
        return kind, group if kind == len(groups) else '', detail if group == '央视' else (0 if '卫视' in name else 1, 0, False) if group == '地方卫视' else (0, 0, False)
    for row in sorted(seen.values(), key=order):
        attrs = row['attrs']; ids = sorted(set(row['origins']), key=lambda key: rank[key])
        attrs.pop('x-source-id', None); attrs.pop('x-source-name', None)
        if ids:
            attrs['x-source-id'] = ','.join(ids); attrs['x-source-name'] = ' / '.join(names[key] for key in ids)
        result.append('#EXTINF:-1 ' + ' '.join(key + '="' + builder.m3u_escape(value) + '"' for key, value in attrs.items()) + ',' + row['name'])
        result.extend(row['options']); result.append(row['url'])
    return '\n'.join(result) + '\n'


def bootstrap(rows, state):
    known = {}
    for row in rows:
        local = metadata(row); key = row['attrs'].get('x-sync-id', '')
        if not CHANNEL_ID.fullmatch(key): key = 'c_' + digest(local)[:24]
        if key in known and known[key] != local: key = 'c_' + digest(local)[:24]
        row['attrs']['x-sync-id'] = key; known[key] = local
    state.setdefault('channels', {}).update(known)
    return known


def merge(content, registry, previous, payloads, hans):
    """Pure merge; missing payloads mean failure/disabled and must leave their routes intact."""
    builder.validate_live_sources(registry)
    state = copy.deepcopy(previous or {'version': 1, 'channels': {}, 'sources': {}})
    builder.require(state.get('version') == 1 and isinstance(state.get('channels'), dict) and isinstance(state.get('sources'), dict), '同步状态格式无效')
    header, rows = parse(content)
    known_ids = {source['id'] for source in registry['sources']}
    builder.require(all(key in known_ids for row in rows for key in row['origins']), '本地列表含未登记的来源')
    current = bootstrap(rows, state)
    report = {'sources': [], 'addedChannels': 0, 'updatedChannels': 0, 'ambiguousChannels': 0, 'suppressedChannels': 0, 'retainedMissingChannels': 0}
    sources = {source['id']: source for source in registry['sources']}
    for source_id in registry['mergePolicy']['sourceOrder']:
        source = sources[source_id]
        source_id = source['id']
        if not source.get('enabled', True):
            report['sources'].append({'id': source_id, 'status': 'disabled', 'reason': '未抓取，保留现有线路'}); continue
        if source_id not in payloads:
            report['sources'].append({'id': source_id, 'status': 'kept', 'reason': '未取得有效上游，保留现有线路'}); continue
        payload = payloads[source_id]
        _, incoming = parse(payload.decode('utf-8-sig'))
        builder.require(incoming, source_id + ' 是空列表')
        selection = source.get('selection', {})
        if selection.get('mode') == 'keep-selected':
            names = {normalized(name, hans) for name in selection['names']}
            incoming = [row for row in incoming if normalized(row['name'], hans) in names]
            builder.require(incoming, source_id + ' 中找不到选取的频道')
        for row in incoming: inherit_headers(row, source.get('headers', {}))
        groups = {}
        for row in incoming:
            meta = metadata(row); identity = digest([meta['name'], meta['group'], meta['tvgId'], meta['logo'], classify(row, hans)])
            groups.setdefault(identity, []).append(row)
        old = state['sources'].get(source_id, {}).get('bindings', {})
        bindings = copy.deepcopy(old)
        updates, matched, blocked = {}, set(), set()
        source_rows = [row for row in rows if source_id in row['origins']]
        by_route, by_name, by_alias, by_epg = {}, {}, {}, {}
        for row in source_rows:
            channel = row['attrs']['x-sync-id']
            by_route.setdefault(route_key(row), set()).add(channel)
            by_name.setdefault((normalized(row['name'], hans), row['attrs'].get('tvg-id', '')), set()).add(channel)
        for item in old.values():
            by_alias.setdefault((normalized(item['name'], hans), item['tvgId']), set()).add(item['channel'])
            if item['tvgId']: by_epg.setdefault(item['tvgId'], set()).add(item['channel'])
        details = {'id': source_id, 'status': 'updated', 'channels': len(groups), 'routes': len(incoming), 'ambiguous': 0, 'suppressed': 0}
        for identity, remote_rows in groups.items():
            first = remote_rows[0]; remote = metadata(first); candidate = None
            if identity in old:
                candidate = old[identity]['channel']
            else:
                # Exact playback is strong bootstrap evidence, followed by source-scoped names/EPG.
                exact = set().union(*(by_route.get(route_key(row), set()) for row in remote_rows))
                same = by_name.get((normalized(remote['name'], hans), remote['tvgId']), set())
                same_group = {key for key in same if current[key]['group'] == classify(first, hans)}
                alias = by_alias.get((normalized(remote['name'], hans), remote['tvgId']), set())
                epg = by_epg.get(remote['tvgId'], set())
                for possibilities in [exact & same_group, exact & same, exact, same_group, same, alias, epg]:
                    if len(possibilities) == 1: candidate = next(iter(possibilities)); break
                if candidate is None and any([exact, same, alias, epg]):
                    blocked.update(exact | same | alias | epg)
                    details['ambiguous'] += 1; continue
            if candidate is not None and candidate not in current:
                details['suppressed'] += 1; continue  # A channel deleted by the owner is a tombstone.
            if candidate is None:
                a = {key: value for key, value in first['attrs'].items() if not key.startswith(('x-source-', 'x-sync-'))}
                a.update({'group-title': classify(first, hans), 'tvg-name': hans(first['attrs'].get('tvg-name', first['name']))})
                if 'tvg-logo' in a: a['tvg-logo'] = a['tvg-logo'].replace(' ', '%20')
                template = dict(attrs=a, name=hans(first['name']))
                local = metadata(template); deleted = [key for key, value in state['channels'].items() if key not in current and normalized(value['name'], hans) == normalized(local['name'], hans) and value['tvgId'] == local['tvgId']]
                if deleted: details['suppressed'] += 1; continue
                candidate = 'c_' + digest(local)[:24]
                if candidate not in current:
                    a['x-sync-id'] = candidate; current[candidate] = local; state['channels'][candidate] = local
                    # Reserve a template without introducing a dummy playable address.
                    updates.setdefault(candidate, {'template': template, 'rows': []})
                    report['addedChannels'] += 1
            if candidate not in updates:
                template = next(row for row in rows if row['attrs']['x-sync-id'] == candidate)
                updates[candidate] = {'template': template, 'rows': []}
            target = updates[candidate]
            for row in remote_rows:
                replacement = copy.deepcopy(row)
                replacement.update(name=target['template']['name'], attrs=copy.deepcopy(target['template']['attrs']), origins=[source_id])
                replacement['attrs']['x-sync-id'] = candidate
                target['rows'].append(replacement)
            bindings[identity] = {'channel': candidate, 'name': remote['name'], 'tvgId': remote['tvgId'], 'group': remote['group']}
            matched.add(candidate)
        for key in blocked:
            updates.pop(key, None); matched.discard(key)
        missing = {row['attrs']['x-sync-id'] for row in source_rows} - matched
        report['retainedMissingChannels'] += len(missing)
        report['updatedChannels'] += len(matched)
        report['ambiguousChannels'] += details['ambiguous']; report['suppressedChannels'] += details['suppressed']
        # Detach only this successful source from matched channels. Shared/failed sources stay attached.
        retained = []
        for row in rows:
            if row['attrs']['x-sync-id'] in updates and source_id in row['origins']:
                row = copy.deepcopy(row); row['origins'].remove(source_id)
                if not row['origins']: continue
            retained.append(row)
        for update in updates.values(): retained.extend(update['rows'])
        rows = retained
        state['sources'][source_id] = {'sha256': hashlib.sha256(payload).hexdigest(), 'routes': len(incoming), 'bindings': bindings}
        report['sources'].append(details)
    output = serialize(header, rows, registry)
    builder.parse_m3u(output)
    report.update(routes=output.count('#EXTINF:'), channels=len(builder.parse_m3u(output)), groups=list(dict.fromkeys(channel['group'] for channel in builder.parse_m3u(output))))
    return output, state, report


def fetch(source, timeout=20, max_bytes=8 * 1024 * 1024):
    request = Request(source['url'], headers={'User-Agent': 'JuAn-Live-Sync/1.0', 'Accept-Encoding': 'identity', **source.get('headers', {})})
    began = time.monotonic()
    with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
        builder.require(urlsplit(response.geturl()).scheme in {'http', 'https'}, '不支持的重定向')
        length = response.headers.get('Content-Length')
        if length is not None: builder.require(0 <= int(length) <= max_bytes, '上游列表超过大小上限')
        chunks, size = [], 0
        while True:
            builder.require(time.monotonic() - began < timeout * 2, '下载超时')
            chunk = response.read1(min(65536, max_bytes + 1 - size))
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            builder.require(size <= max_bytes, '上游列表超过大小上限')
        result = b''.join(chunks)
        if length is not None: builder.require(size == int(length), '上游响应未完整传输')
        _, rows = parse(result.decode('utf-8-sig'))
        builder.require(rows, '上游返回空列表')
        if source.get('selection', {}).get('mode') == 'keep-selected':
            from opencc import OpenCC
            converter = OpenCC('t2s').convert
            allowed = {normalized(name, converter) for name in source['selection']['names']}
            builder.require(any(normalized(row['name'], converter) in allowed for row in rows), '上游缺少选取的频道')
        return result


def download(registry, fetcher=fetch, previous=None):
    payloads, failures = {}, {}
    sources = {source['id']: source for source in registry['sources']}
    for source in [sources[key] for key in registry['mergePolicy']['sourceOrder']]:
        if not source.get('enabled', True): continue
        for attempt in range(2):
            try:
                payload = fetcher(source)
                _, fetched_rows = parse(payload.decode('utf-8-sig'))
                if source.get('selection', {}).get('mode') == 'keep-selected':
                    from opencc import OpenCC
                    converter = OpenCC('t2s').convert
                    allowed = {normalized(name, converter) for name in source['selection']['names']}
                    fetched_rows = [row for row in fetched_rows if normalized(row['name'], converter) in allowed]
                builder.require(fetched_rows, '上游没有可选频道')
                last_routes = (previous or {}).get('sources', {}).get(source['id'], {}).get('routes', source.get('lastImport', {}).get('routes', 0))
                builder.require(len(fetched_rows) >= last_routes * registry.get('sync', {}).get('minimumPreviousRouteRatio', .5), '上游线路异常减少，保留待核对')
                payloads[source['id']] = payload; break
            except (OSError, ValueError, UnicodeError, HTTPException, HTTPError, URLError) as error:
                failures[source['id']] = 'HTTP ' + str(error.code) if isinstance(error, HTTPError) else type(error).__name__
                if attempt == 0: time.sleep(1)
        if source['id'] in payloads: failures.pop(source['id'], None)
    return payloads, failures


def write_if_changed(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == value: return False
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(value, encoding='utf-8'); temporary.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--preview-dir', type=Path)
    parser.add_argument('--report', type=Path, default=ROOT / '.tools/live-sync-report.json')
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    registry = builder.validate_live_sources(json.loads((args.root / 'data/live-sources.json').read_text(encoding='utf-8')))
    if not registry['automaticSyncEnabled']:
        print('自动同步已在来源清单中关闭。'); return
    from opencc import OpenCC
    hans = OpenCC('t2s').convert
    path, state_path = args.root / registry['playlist'], args.root / 'data/live-sync-state.json'
    builder.require(not path.is_symlink() and not path.parent.is_symlink() and not state_path.is_symlink(), '同步数据文件不能使用符号链接')
    original = path.read_text(encoding='utf-8')
    previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    payloads, failures = download(registry, previous=previous)
    if payloads:
        result, state, report = merge(original, registry, previous, payloads, hans)
        output = args.preview_dir if args.preview_dir else args.root / 'data'
        if not args.dry_run or args.preview_dir:
            write_if_changed(output / 'live.m3u', result)
            write_if_changed(output / 'live-sync-state.json', json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        report['playlistChanged'] = original != result
    else:
        report = {'sources': [], 'playlistChanged': False}
    report['failures'] = failures
    write_if_changed(args.report, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if args.summary:
        lines = ['## 直播上游同步', '', f'成功 {len(payloads)} 个来源，失败保留 {len(failures)} 个来源。', '',
                 f"频道 {report.get('channels', '保持原样')}，线路 {report.get('routes', '保持原样')}；新增频道 {report.get('addedChannels', 0)}，待核对旧频道 {report.get('retainedMissingChannels', 0)}，匹配不明确 {report.get('ambiguousChannels', 0)}。", '']
        lines.extend('- `' + key + '`：' + reason + '，保留上次线路。' for key, reason in failures.items())
        with args.summary.open('a', encoding='utf-8') as summary: summary.write('\n'.join(lines) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'sources'}, ensure_ascii=False))
    for key, reason in failures.items(): print('::warning::' + key + ': ' + reason + '，保留上次有效内容')
    if not payloads: parser.exit(1, '全部上游均未取得有效列表，未修改直播文件或同步状态。\n')


if __name__ == '__main__':
    main()
