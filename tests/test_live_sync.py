import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opencc import OpenCC

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live_sync', ROOT / 'scripts/sync-live.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
HANS = OpenCC('t2s').convert


def registry():
    return {'version': 1, 'playlist': 'data/live.m3u', 'automaticSyncEnabled': True,
            'sources': [{'id': key, 'name': '来源' + key, 'url': 'https://example.com/' + key, 'format': 'm3u', 'enabled': True, 'headers': {}} for key in ['a', 'b']],
            'mergePolicy': {'sourceOrder': ['a', 'b']},
            'normalization': {'groupOrder': ['央视', '地方卫视', '抖音', '虎牙', 'B站', '斗鱼', '港澳台', '体育', '影视', '少儿', '音乐', '游戏', '综合频道', 'Twitch', 'SOOP', 'YY', '公告']}}


def row(name='台湾新闻', url='https://example.com/video?sign=old%2B%2F', group='港澳台', epg='stable-id', origin='a', extra='', options=''):
    attrs = 'tvg-id="' + epg + '" tvg-name="' + name + '" tvg-logo="https://example.com/logo.png" group-title="' + group + '"'
    if origin: attrs += ' x-source-id="' + origin + '"'
    return '#EXTINF:-1 ' + attrs + (' ' + extra if extra else '') + ',' + name + '\n' + options + url + '\n'


def m3u(*rows): return '#EXTM3U\n' + ''.join(rows)


def run_merge(content, payloads, previous=None, config=None):
    return sync.merge(content, config or registry(), previous, {key: value.encode() for key, value in payloads.items()}, HANS)


class LiveSyncTests(unittest.TestCase):
    def test_registered_official_file_is_local_bounded_and_merges_idempotently(self):
        config = registry(); official = {'id': 'official', 'name': '官方直播', 'url': 'https://www.yangshipin.cn/tv/home',
            'format': 'local-m3u', 'file': 'data/live-official.m3u', 'headers': {'User-Agent': 'qqlive'}}
        config['sources'].insert(0, official); config['mergePolicy']['sourceOrder'].insert(0, 'official')
        content = m3u(row(name='CCTV1高清', epg='cctv1', group='央视', url='https://backup.test/a'))
        public = m3u(row(name='CCTV-1 综合', epg='cctv1', origin='', group='央视', url='https://www.yangshipin.cn/tv/home?pid=600001859&cnlid=2024078201'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir(); path = root / 'data/live-official.m3u'; path.write_text(public)
            with patch.object(sync, 'urlopen', side_effect=AssertionError('Local import must not request the official API')):
                payload = sync.fetch(official, root=root)
            self.assertEqual(public.encode(), payload)
            with self.assertRaises(ValueError): sync.fetch(official, root=root, max_bytes=8)
            path.unlink(); path.symlink_to(ROOT / 'data/live.m3u')
            with self.assertRaises(ValueError): sync.fetch(official, root=root)
        first, state, report = sync.merge(content, config, None, {'official': payload}, HANS)
        self.assertEqual(1, report['addedChannels']); self.assertIn('https://backup.test/a', first)
        self.assertIn('x-source-name="官方直播"', first)
        official_row = next(row for row in sync.builder.parse_m3u(first) if 'www.yangshipin.cn' in row['urls'][0])
        self.assertEqual('qqlive', official_row['headers']['User-Agent'])
        second, state2, _ = sync.merge(first, config, state, {'official': payload}, HANS)
        self.assertEqual(first, second); self.assertEqual(state, state2)
    def test_signed_url_changes_and_local_edits_survive_multiple_runs(self):
        original = m3u(row(extra='x-enabled="false" custom-tag="keep"'))
        incoming = m3u(row(name='臺灣新聞', origin='', group='台湾频道', options='#EXTHTTP:{"Cookie":"signed=a%2Bb","Referer":"https://example.com/"}\n#KODIPROP:inputstream.adaptive.manifest_type=hls\n'))
        first, state, _ = run_merge(original, {'a': incoming})
        edited = first.replace('台湾新闻', '我的新闻').replace('group-title="港澳台"', 'group-title="常看"').replace('https://example.com/logo.png', 'https://example.com/custom.png').replace('tvg-id="stable-id"', 'tvg-id="my-epg"')
        fresh = incoming.replace('sign=old%2B%2F', 'sign=new%2B%2F&expires=123')
        updated, state, _ = run_merge(edited, {'a': fresh}, state)
        parsed = sync.builder.parse_m3u(updated)[0]
        self.assertEqual(('我的新闻', '常看', 'my-epg', 'https://example.com/custom.png', False), (parsed['name'], parsed['group'], parsed['tvgId'], parsed['logo'], parsed['enabled']))
        self.assertEqual(['https://example.com/video?sign=new%2B%2F&expires=123'], parsed['urls'])
        self.assertEqual('signed=a%2Bb', parsed['headers']['Cookie'])
        self.assertIn('custom-tag="keep"', updated)
        self.assertIn('#KODIPROP:inputstream.adaptive.manifest_type=hls', updated)
        same, same_state, _ = run_merge(updated, {'a': fresh}, state)
        self.assertEqual(updated, same); self.assertEqual(state, same_state)

    def test_new_channels_are_simplified_and_grouped_by_platform_before_genre(self):
        upstream = m3u(row('臺灣綜藝', origin='', group='台灣'), row('體育賽事', url='https://example.com/douyin/123', origin='', group='抖音體育', epg='other'), row('CCTV-12', origin='', group='央視頻道', epg='c12'), row('CCTV-2', origin='', group='央視頻道', epg='c2'))
        output, _, _ = run_merge('#EXTM3U\n', {'a': upstream})
        parsed = sync.builder.parse_m3u(output)
        self.assertEqual(['CCTV-2', 'CCTV-12', '体育赛事', '台湾综艺'], [ch['name'] for ch in parsed])
        self.assertEqual(['央视', '央视', '抖音', '港澳台'], [ch['group'] for ch in parsed])
        self.assertIn('tvg-name="台湾综艺"', output)

    def test_failed_and_disabled_sources_and_removed_channels_are_retained(self):
        original = m3u(row(origin='a,b'), row('上游暂时没有', epg='missing', url='https://example.com/old', origin='a'), row('手工频道', epg='manual', url='https://example.com/manual', origin=''))
        output, _, report = run_merge(original, {'a': m3u(row(origin='', url='https://example.com/new'))})
        channels = sync.builder.parse_m3u(output)
        all_urls = [url for channel in channels for url in channel['urls']]
        self.assertEqual(4, len(all_urls))
        self.assertIn('https://example.com/old', all_urls); self.assertIn('https://example.com/manual', all_urls)
        self.assertIn('https://example.com/video?sign=old%2B%2F', all_urls)
        self.assertIn('x-source-id="b"', output)
        self.assertEqual(1, report['retainedMissingChannels'])

    def test_shared_routes_union_origins_but_headers_and_ordered_options_do_not_mix(self):
        same_url = 'https://example.com/same'
        left = m3u(row(url=same_url, origin='', options='#EXTHTTP:{"Referer":"one"}\n#KODIPROP:a=1\n#KODIPROP:b=2\n'))
        right = m3u(row(url=same_url, origin='', options='#EXTHTTP:{"referer":"one"}\n#KODIPROP:a=1\n#KODIPROP:b=2\n'))
        output, state, _ = run_merge('#EXTM3U\n', {'a': left, 'b': right})
        self.assertEqual(1, output.count('#EXTINF:')); self.assertIn('x-source-id="a,b"', output)
        changed = right.replace('"one"', '"two"').replace('#KODIPROP:a=1\n#KODIPROP:b=2', '#KODIPROP:b=2\n#KODIPROP:a=1')
        output, _, _ = run_merge(output, {'a': left, 'b': changed}, state)
        self.assertEqual(2, output.count('#EXTINF:'))
        self.assertIn('"Referer":"one"', output); self.assertIn('"referer":"two"', output)

    def test_owner_deletion_is_not_resurrected_and_disabled_channel_stays_disabled(self):
        incoming = m3u(row(origin=''))
        first, state, _ = run_merge(m3u(row(extra='x-enabled="false"')), {'a': incoming})
        self.assertFalse(sync.builder.parse_m3u(first)[0]['enabled'])
        output, state, report = run_merge('#EXTM3U\n', {'a': incoming}, state)
        self.assertEqual(0, output.count('#EXTINF:')); self.assertEqual(1, report['suppressedChannels'])
        restored, _, _ = run_merge(first, {'a': incoming}, state)
        self.assertEqual(1, restored.count('#EXTINF:'))

    def test_selected_favorites_do_not_import_unselected_channels(self):
        config = registry(); config['sources'][0]['selection'] = {'mode': 'keep-selected', 'names': ['台湾新闻']}
        incoming = m3u(row(name='臺灣新聞', origin=''), row('别的节目', epg='other', origin=''))
        output, _, _ = run_merge('#EXTM3U\n', {'a': incoming}, config=config)
        self.assertNotIn('别的节目', output); self.assertIn('台湾新闻', output)

    def test_ambiguous_names_are_kept_for_review_instead_of_replacing_an_arbitrary_channel(self):
        original = m3u(row(extra='custom="one"'), row(extra='custom="two"', url='https://example.com/another'))
        # Different local logos are separate channels despite a reused EPG/name upstream.
        original = original.replace('custom="two"', 'custom="two"').replace('tvg-logo="https://example.com/logo.png" group-title="港澳台" x-source-id="a" custom="two"', 'tvg-logo="https://example.com/other.png" group-title="港澳台" x-source-id="a" custom="two"')
        output, _, report = run_merge(original, {'a': m3u(row(origin='', url='https://example.com/new'))})
        self.assertNotIn('https://example.com/new\n', output); self.assertEqual(1, report['ambiguousChannels'])
        self.assertEqual(2, output.count('#EXTINF:'))

    def test_source_order_and_repeated_runs_are_deterministic(self):
        config = registry(); config['mergePolicy']['sourceOrder'] = ['b', 'a']
        incoming = m3u(row(origin=''))
        first, state, _ = run_merge('#EXTM3U\n', {'a': incoming, 'b': incoming}, config=config)
        self.assertIn('x-source-id="b,a"', first)
        second, following, _ = run_merge(first, {'a': incoming, 'b': incoming}, state, config)
        self.assertEqual(first, second); self.assertEqual(state, following)

    def test_one_old_upstream_group_can_split_into_platform_and_tv_channels_without_losing_routes(self):
        original = m3u(row('七龙珠', group='虎牙', url='https://example.com/huya/one?sign=old'), row('七龙珠', group='少儿', url='https://example.com/cartoon?sign=old'))
        upstream = m3u(row('七龙珠', group='动画频道', origin='', url='https://example.com/huya/one?sign=old'), row('七龙珠', group='动画频道', origin='', url='https://example.com/cartoon?sign=old'))
        first, state, report = run_merge(original, {'a': upstream})
        self.assertEqual(2, first.count('#EXTINF:')); self.assertEqual(0, report['ambiguousChannels'])
        output, _, _ = run_merge(first, {'a': upstream.replace('sign=old', 'sign=new')}, state)
        parsed = sync.builder.parse_m3u(output)
        self.assertEqual(['虎牙', '少儿'], [ch['group'] for ch in parsed])
        self.assertTrue(all('sign=new' in url for ch in parsed for url in ch['urls']))

    def test_manifest_request_headers_are_playback_defaults_and_never_override_explicit_headers(self):
        config = registry(); config['sources'][0]['headers'] = {'User-Agent': 'Default', 'Referer': 'https://example.com/default'}
        incoming = m3u(row(origin='', options='#EXTVLCOPT:http-user-agent=Explicit\n'))
        output, _, _ = run_merge('#EXTM3U\n', {'a': incoming}, config=config)
        headers = sync.builder.parse_m3u(output)[0]['headers']
        self.assertEqual({'User-Agent': 'Explicit', 'Referer': 'https://example.com/default'}, headers)

    def test_suspiciously_short_responses_are_kept_for_review(self):
        config = registry(); config['sources'][1]['enabled'] = False
        previous = {'sources': {'a': {'routes': 20}}}
        with patch.object(sync.time, 'sleep'):
            payloads, failures = sync.download(config, lambda source: m3u(row(origin='')).encode(), previous)
        self.assertEqual({}, payloads); self.assertEqual({'a': 'ValueError'}, failures)

    def test_http_download_sends_registered_headers_and_rejects_html_empty_and_oversized_bodies(self):
        seen = []; content = m3u(row(name='臺灣新聞', origin='')).encode()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.headers.get('User-Agent'))
                body = b'<html>403</html>' if self.path == '/html' else b'#EXTM3U\n' if self.path == '/empty' else content
                self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        source = {'url': f'http://127.0.0.1:{server.server_port}/good', 'headers': {'User-Agent': 'Registered'}}
        try:
            self.assertEqual(content, sync.fetch(source))
            for path in ['/html', '/empty']:
                with self.subTest(path=path), self.assertRaises(ValueError): sync.fetch({**source, 'url': source['url'].replace('/good', path)})
            with self.assertRaises(ValueError): sync.fetch(source, max_bytes=10)
            self.assertEqual(['Registered'] * 4, seen)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_invalid_or_empty_upstream_is_not_a_success_and_network_retries_are_bounded(self):
        config = registry(); config['sources'][1]['enabled'] = False
        calls = []
        def broken(source):
            calls.append(source['id']); raise HTTPError(source['url'], 503, 'Unavailable', {}, None)
        with patch.object(sync.time, 'sleep'):
            payloads, failures = sync.download(config, broken)
        self.assertEqual(['a', 'a'], calls); self.assertEqual({}, payloads); self.assertEqual({'a': 'HTTP 503'}, failures)
        for content in ['<html>error</html>', '#EXTM3U\n#EXTINF:-1,截断', '#EXTM3U\n']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                run_merge(m3u(row()), {'a': content})

    def test_all_failures_do_not_modify_the_playlist_or_write_sync_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir()
            path = root / 'data/live.m3u'; original = m3u(row()); path.write_text(original)
            (root / 'data/live-sources.json').write_text(json.dumps(registry()))
            with patch.object(sync, 'download', return_value=({}, {'a': 'HTTP 503', 'b': 'HTTP 404'})), patch('sys.argv', ['sync-live', '--root', str(root), '--report', str(root / 'report.json')]), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): sync.main()
            self.assertEqual(original, path.read_text()); self.assertFalse((root / 'data/live-sync-state.json').exists())

    def test_manifest_disable_prevents_any_network_or_data_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir(); config = registry(); config['automaticSyncEnabled'] = False
            (root / 'data/live-sources.json').write_text(json.dumps(config))
            with patch.object(sync, 'download') as download, patch('sys.argv', ['sync-live', '--root', str(root)]): sync.main()
            download.assert_not_called(); self.assertFalse((root / 'data/live-sync-state.json').exists())

    def test_disabling_one_registered_source_keeps_its_data_without_requiring_an_order_edit(self):
        config = registry(); config['sources'][0]['enabled'] = False
        original = m3u(row(origin='a'))
        output, _, report = run_merge(original, {'a': m3u(row(origin='', url='https://example.com/unwanted'))}, config=config)
        self.assertNotIn('https://example.com/unwanted', output)
        self.assertIn('https://example.com/video?sign=old%2B%2F', output)
        self.assertEqual('disabled', report['sources'][0]['status'])

    def test_atomic_write_skips_identical_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            self.assertTrue(sync.write_if_changed(path, '{}\n')); stamp = path.stat().st_mtime_ns
            self.assertFalse(sync.write_if_changed(path, '{}\n')); self.assertEqual(stamp, path.stat().st_mtime_ns)


if __name__ == '__main__': unittest.main()
