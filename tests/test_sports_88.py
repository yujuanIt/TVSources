import base64
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sports_88 as sports

spec = importlib.util.spec_from_file_location('sports_sync', ROOT / 'scripts/sync-live.py')
sync = importlib.util.module_from_spec(spec); spec.loader.exec_module(sync)
NOW = datetime(2026, 10, 16, 20, 0, tzinfo=sports.ZONE)
MEDIA = 'https://cdn.example.com/live.m3u8?sign=a%2Bb%2F&expires=1'


def response(links):
    body = json.dumps({'shareStatus': 0, 'shareStatusCheck': 0, 'links': links}, ensure_ascii=False).encode()
    return json.dumps({'data': 'abcdef' + base64.b64encode(body).decode() + 'YZ'}).encode()


def wrapper(address):
    encoded = base64.b64encode(base64.b64encode(address[::-1].encode())[::-1]).decode()
    from urllib.parse import quote
    return sports.WRAPPER + '?id=' + quote(encoded, safe='')


def listing(*entries):
    return ('<ul class="list-group">' + ''.join(entries) + '</ul>').encode()


def date(day):
    return '<li class="live-list-group-time">' + day + '</li>'


def game(key='123', label='NBA常规赛', at='19:35', team1='甲队', team2='乙队', status='直播中'):
    return f'''<li class="list-group-item group-game-item"><span class="game-type">{label}</span>
        <div class="category-game-time">{at}</div><span class="team-name">{team1}</span>
        <img data-src="https://images.example.com/logo.png"><span class="team-name">{team2}</span>
        <a href='/live/{key}/play'>{status}</a></li>'''


def source(kind='NBA'):
    return {'id': 'sports-' + kind.lower(), 'name': kind, 'url': sports.PAGES[kind], 'kind': kind,
            'format': '88zhibo', 'enabled': True, **({'retireMissing': True} if kind != 'channels' else {})}


def config():
    return {'version': 1, 'playlist': 'data/live.m3u', 'automaticSyncEnabled': True,
            'sources': [source(), {'id': 'other', 'name': '手工上游', 'url': 'https://example.com/list', 'format': 'm3u'}],
            'mergePolicy': {'sourceOrder': ['sports-nba', 'other']},
            'normalization': {'groupOrder': ['体育', 'NBA赛事', 'CBA赛事', '综合频道']}}


class Sports88Tests(unittest.TestCase):
    def test_public_payload_keeps_signed_url_and_wrapper_headers_and_skips_gated_ads(self):
        parsed = sports.decode_lines(response([
            {'url': wrapper(MEDIA), 'name': '高清', 'shareLock': 0},
            {'url': '/#'}, {'url': 'https://ads.example.com/install.apk'},
            {'url': 'https://another.example.com/a.m3u8', 'shareLock': 1},
            {'url': 'https://another.example.com/a.m3u8', 'shareLock': 'unlock-required'},
            {'url': 'http://127.0.0.1/private.m3u8'},
        ]))
        self.assertEqual(1, len(parsed)); self.assertEqual(MEDIA, parsed[0][0])
        self.assertEqual('https://cloud.yumixiu768.com/', parsed[0][1]['Referer'])
        self.assertEqual('https://cloud.yumixiu768.com', parsed[0][1]['Origin'])
        self.assertEqual([], sports.decode_lines(response(None)))
        for payload in [b'<html>error</html>', b'{}', b'{"data":"not-an-encoded-payload"}', response({})]:
            with self.assertRaises(ValueError): sports.decode_lines(payload)

    def test_schedule_keeps_league_time_logo_and_excludes_old_finished_and_other_leagues(self):
        body = listing(date('2026-10-15'), game('1'), date('2026-10-16'),
                       game('2', status='已结束'), game('3', label='WNBA常规赛'),
                       game('4', label='CBA常规赛'), game('5'), date('2026-10-18'), game('6'))
        rows = sports.schedule(body, 'NBA', NOW)
        self.assertEqual(['https://www.88zhibo.tv/live/5/play'], [row['url'] for row in rows])
        self.assertEqual('10-16 19:35 甲队 vs 乙队', rows[0]['name'])
        self.assertEqual('NBA赛事', rows[0]['group'])
        self.assertEqual('https://images.example.com/logo.png', rows[0]['logo'])
        self.assertEqual(1, len(sports.schedule(body, 'CBA', NOW)))
        with self.assertRaises(ValueError): sports.schedule(b'<html>maintenance</html>', 'NBA', NOW)

    def test_ingest_requires_video_evidence_and_publishes_stable_page_not_ticket(self):
        seen = []
        def fetch(url, headers, limit, prefix=False):
            seen.append((url, headers, prefix))
            if '/match/' in url: return listing(date('2026-10-16'), game())
            if url.endswith('/source'): return response([{'url': wrapper(MEDIA)}])
            if url == MEDIA: return b'#EXTM3U\n#EXTINF:6,\npart.ts?sign=one%2Btwo\n'
            if 'part.ts' in url: return bytes([0x47]) + bytes(187) + bytes([0x47]) + bytes(200)
            self.fail(url)
        payload = sports.fetch_playlist(source(), fetch, NOW)
        self.assertIn(b'/live/123/play', payload); self.assertNotIn(b'expires=', payload)
        self.assertIn('NBA赛事'.encode(), payload)
        self.assertTrue(any(prefix and url.endswith('part.ts?sign=one%2Btwo') for url, _, prefix in seen))
        self.assertIn(('https://www.88zhibo.tv/live/123/source', {'Referer': 'https://www.88zhibo.tv/live/123/play'}, False), seen)
        first, state, _ = sync.merge('#EXTM3U\n', config(), None, {'sports-nba': payload}, lambda s: s)
        self.assertIn('group-title="NBA赛事"', first)
        self.assertIn('x-source-name="NBA"', first)
        again, _, _ = sync.merge(first, config(), state, {'sports-nba': payload}, lambda s: s)
        self.assertEqual(first, again)

    def test_hls_rejects_html_replay_encrypted_private_and_invalid_segment(self):
        for manifest in [b'<html>denied</html>', b'#EXTM3U\n#EXT-X-ENDLIST\n',
                         b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"\n#EXTINF:6,\nsegment.ts',
                         b'#EXTM3U\n#EXTINF:6,\nhttp://192.168.1.2/private.ts',
                         b'#EXTM3U\n#EXTINF:6,\npart.ts']:
            def get(url, headers, limit, prefix=False): return b'<html>not video</html>' if prefix else manifest
            self.assertFalse(sports.playable(MEDIA, {}, get))

    def test_no_lines_is_valid_empty_event_snapshot_but_api_failure_is_not(self):
        def empty(url, headers, limit, prefix=False):
            return listing(date('2026-10-16'), game()) if '/match/' in url else response(None)
        self.assertEqual(b'#EXTM3U\n', sports.fetch_playlist(source(), empty, NOW))
        def broken(url, headers, limit, prefix=False):
            return listing(date('2026-10-16'), game()) if '/match/' in url else b'<html>403</html>'
        with self.assertRaises(ValueError): sports.fetch_playlist(source(), broken, NOW)
        with self.assertRaises(ValueError): sports.fetch_playlist(source('channels'), empty, NOW)

    def test_expired_events_retire_only_their_routes_and_can_return_without_losing_edits(self):
        def fake(url, headers, limit, prefix=False):
            return listing(date('2026-10-16'), game()) if '/match/' in url else response([{'url': MEDIA}])
        payload = sports.fetch_playlist(source(), fake, NOW, lambda *args: True)
        first, state, _ = sync.merge('#EXTM3U\n', config(), None, {'sports-nba': payload}, lambda s: s)
        first = first.replace('10-16 19:35 甲队 vs 乙队', '我的比赛').replace('group-title="NBA赛事"', 'group-title="自选"')
        retired, state, report = sync.merge(first, config(), state, {'sports-nba': b'#EXTM3U\n'}, lambda s: s)
        self.assertNotIn('#EXTINF:', retired); self.assertEqual(1, report['retiredEventChannels'])
        restored, state, _ = sync.merge(retired, config(), state, {'sports-nba': payload}, lambda s: s)
        self.assertIn('我的比赛', restored); self.assertIn('group-title="自选"', restored)
        # Manual deletion is different from automatic retirement and stays deleted.
        deleted, _, report = sync.merge('#EXTM3U\n', config(), state, {'sports-nba': payload}, lambda s: s)
        self.assertNotIn('#EXTINF:', deleted); self.assertEqual(1, report['suppressedChannels'])

    def test_failed_snapshot_keeps_old_events_and_sports_only_skips_other_networks(self):
        def fake(url, headers, limit, prefix=False):
            return listing(date('2026-10-16'), game()) if '/match/' in url else response([{'url': MEDIA}])
        payload = sports.fetch_playlist(source(), fake, NOW, lambda *args: True)
        first, state, _ = sync.merge('#EXTM3U\n', config(), None, {'sports-nba': payload}, lambda s: s)
        kept, _, _ = sync.merge(first, config(), state, {}, lambda s: s)
        self.assertEqual(first, kept)
        def fetcher(item):
            self.assertEqual('sports-nba', item['id']); return b'#EXTM3U\n'
        payloads, failures = sync.download(config(), fetcher, state, sports_only=True)
        self.assertEqual({'sports-nba': b'#EXTM3U\n'}, payloads); self.assertFalse(failures)

    def test_retirement_cannot_be_enabled_for_an_ordinary_source(self):
        unsafe = config(); unsafe['sources'][1]['retireMissing'] = True
        with self.assertRaises(ValueError): sync.builder.validate_live_sources(unsafe)
        unsafe = config(); unsafe['sources'][0]['retireMissing'] = 'false'
        with self.assertRaises(ValueError): sync.builder.validate_live_sources(unsafe)

    def test_event_retirement_leaves_a_shared_route_and_manual_metadata_intact(self):
        def fake(url, headers, limit, prefix=False):
            return listing(date('2026-10-16'), game()) if '/match/' in url else response([{'url': MEDIA}])
        payload = sports.fetch_playlist(source(), fake, NOW, lambda *args: True)
        first, state, _ = sync.merge('#EXTM3U\n', config(), None, {'sports-nba': payload}, lambda s: s)
        shared = first.replace('x-source-id="sports-nba"', 'x-source-id="sports-nba,other"')
        output, state, _ = sync.merge(shared, config(), state, {'sports-nba': b'#EXTM3U\n'}, lambda s: s)
        self.assertIn('/live/123/play', output); self.assertIn('x-source-id="other"', output)
        self.assertNotIn('x-source-id="sports-nba,other"', output)
        self.assertEqual([], state['sources']['sports-nba']['retired'])

    def test_disabling_all_sports_is_a_successful_noop_for_the_half_hour_workflow(self):
        data = config(); data['sources'][0]['enabled'] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir()
            (root / 'data/live-sources.json').write_text(json.dumps(data))
            with patch.object(sys, 'argv', ['sync-live.py', '--root', str(root), '--sports-only']), redirect_stdout(StringIO()) as output:
                with patch.object(sync, 'download', side_effect=AssertionError('Disabled sources must not be fetched')):
                    sync.main()
            self.assertIn('全部停用', output.getvalue())


if __name__ == '__main__':
    unittest.main()
