import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_builder', ROOT / 'scripts/build-source-site.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sample():
    data = json.loads((ROOT / 'data/library.json').read_text())
    data['live'].pop('channelFile', None)
    data['live']['channels'] = [{'name': '居安频道', 'group': '我的频道', 'logo': 'https://example.com/logo.png',
        'urls': ['https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc', 'http://example.com/backup.m3u8'],
        'headers': {'User-Agent': 'My Player', 'Referer': 'https://example.com/'}}]
    data['live']['playlists'] = [{'name': '直播列表', 'url': 'https://example.com/channels.m3u'}]
    data['vod']['sites'] = [{'key': 'my_api', 'name': '我的 API', 'type': 1, 'api': 'https://example.com/api.php',
        'headers': {'Referer': 'https://example.com/'}, 'ext': {'value': 'keep'}}]
    data['vod']['movies'] = [{'id': 'movie-1', 'name': '我的影片', 'category': 'movie', 'year': '2026',
        'routes': [{'name': '默认线路', 'episodes': [{'name': '第01集', 'url': 'https://example.com/video.m3u8?sign=x%2Fy#keep$literal'}]}]}]
    data['warehouses'] = [{'name': '另一个配置', 'url': 'https://example.com/box.json'}]
    return data


class BuilderTests(unittest.TestCase):
    def test_source_only_library_omits_movies_without_creating_an_empty_personal_site(self):
        data = sample(); data['vod'].pop('movies')
        before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            builder.publish_files(data, 'https://example.com/', output)
            published = json.loads((output / 'data/library.json').read_text())
            self.assertNotIn('movies', published['vod'])
            self.assertEqual(before, data)
            for name in ['box.json', 'vod.json']:
                sites = json.loads((output / name).read_text())['sites']
                self.assertEqual(['my_api'], [site['key'] for site in sites])
                self.assertEqual(data['vod']['sites'][0]['headers'], sites[0]['headers'])
            self.assertEqual([], json.loads((output / 'catalog.json').read_text())['movies'])
            self.assertEqual(0, json.loads((output / 'manifest.json').read_text())['movies'])
            self.assertEqual(data['live']['playlists'][0]['url'], json.loads((output / 'box.json').read_text())['lives'][1]['url'])

    def test_movies_may_be_absent_but_a_present_value_must_still_be_an_array(self):
        for bad in [None, {}, 'not-an-array']:
            data = sample(); data['vod']['movies'] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_m3u_roundtrip_keeps_logos_epg_multiple_routes_and_all_headers(self):
        data = sample(); channel = data['live']['channels'][0]
        channel.update(group='组名,含 & "引号"', tvgId='channel-1')
        channel['headers']['X-Playback-Token'] = 'public-example=a%2Fb'
        out = builder.build(data, 'https://example.com/')
        parsed = builder.parse_m3u(out['live.m3u'])
        self.assertEqual([{**channel, 'enabled': True}], parsed)

    def test_m3u_accepts_bom_crlf_single_quotes_and_resets_headers_between_channels(self):
        content = '\ufeff#EXTM3U\r\n#EXTINF:-1 tvg-logo=\'https://example.com/logo.png?a=1&amp;b=2\' group-title=\'游戏,直播\',名称,含逗号\r\n#EXTVLCOPT:http-user-agent=Test Player\r\nhttps://example.com/1?id=1,2#keep\r\n#EXTINF:-1,另一频道\r\n#EXTGRP:其他\r\n#EXTHTTP:{"Referer":"https://example.com/"}\r\nhttps://example.com/2\r\n#EXTINF:-1 x-enabled="false",已停用\r\nhttps://example.com/off\r\n'
        channels = builder.parse_m3u(content)
        self.assertEqual('游戏,直播', channels[0]['group'])
        self.assertEqual('名称,含逗号', channels[0]['name'])
        self.assertEqual('https://example.com/logo.png?a=1&b=2', channels[0]['logo'])
        self.assertEqual(['https://example.com/1?id=1,2#keep'], channels[0]['urls'])
        self.assertEqual({'User-Agent': 'Test Player'}, channels[0]['headers'])
        self.assertEqual({'Referer': 'https://example.com/'}, channels[1]['headers'])
        self.assertFalse(channels[2]['enabled'])
        data = sample(); data['live']['channels'] = channels
        out = builder.build(data, 'https://example.com/')
        self.assertNotIn('https://example.com/off', out['live.m3u'])
        self.assertNotIn('https://example.com/off', out['live.txt'])

    def test_invalid_m3u_fails_instead_of_silently_losing_channels(self):
        for content in ['<html>error</html>', '#EXTM3U\nhttps://example.com/live',
                        '#EXTM3U\n#EXTINF:-1,没有地址',
                        '#EXTM3U\n#EXTINF:-1,一\n#EXTINF:-1,二\nhttps://example.com/live',
                        '#EXTM3U\n#EXTINF:-1,一\n#EXTHTTP:[]\nhttps://example.com/live',
                        '#EXTM3U\n#EXTINF:-1,一\nfile:///private',
                        '#EXTM3U\n#EXTINF:-1 x-enabled="yes",一\nhttps://example.com/live']:
            with self.subTest(content=content), self.assertRaises(ValueError): builder.parse_m3u(content)

    def test_editing_project_m3u_updates_published_app_data_json_txt_and_m3u_together(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; source.mkdir()
            shutil.copy2(ROOT / 'index.html', source / 'index.html')
            shutil.copytree(ROOT / 'assets', source / 'assets')
            channel_file = source / 'live.m3u'
            channel_file.write_text('#EXTM3U\n#EXTINF:-1 group-title="直播",我的频道\n#EXTVLCOPT:http-user-agent=Player\nhttps://example.com/original?sign=a%2Fb\n', encoding='utf-8')
            data = sample(); data['live'].update(channelFile='live.m3u', channels=[])
            before = copy.deepcopy(data); output = root / 'site'
            with patch.object(builder, 'SOURCE', source):
                builder.publish_files(data, 'https://example.com/', output)
                published = json.loads((output / 'data/library.json').read_text())
                self.assertEqual('我的频道', published['live']['channels'][0]['name'])
                self.assertEqual({'User-Agent': 'Player'}, published['live']['channels'][0]['headers'])
                self.assertIn('https://example.com/original?sign=a%2Fb', (output / 'live.txt').read_text())
                channel_file.write_text('#EXTM3U\n#EXTINF:-1 group-title="新分组",改名频道\nhttps://example.com/new\n', encoding='utf-8')
                builder.publish_files(data, 'https://example.com/', output)
                published = json.loads((output / 'data/library.json').read_text())
                self.assertEqual('改名频道', published['live']['channels'][0]['name'])
                self.assertEqual(['https://example.com/new'], published['live']['channels'][0]['urls'])
                live = json.loads((output / 'live.json').read_text())
                self.assertEqual('新分组', live['groups'][0]['name'])
                self.assertEqual('改名频道', live['groups'][0]['channels'][0]['name'])
                self.assertNotIn('original', (output / 'live.m3u').read_text())
                self.assertIn('改名频道,https://example.com/new', (output / 'live.txt').read_text())
                hosting = json.loads((output / 'hosting.json').read_text())
                self.assertEqual('https://github.com/yujuanIt/TVSources/edit/main/live.m3u', hosting['channelEditUrl'])
                channel_file.write_text('#EXTM3U\n#EXTINF:-1,没有地址', encoding='utf-8')
                with self.assertRaises(ValueError): builder.publish_files(data, 'https://example.com/', output)
                self.assertEqual(published, json.loads((output / 'data/library.json').read_text()))
            self.assertEqual(before, data)

    def test_m3u_reference_cannot_read_arbitrary_files(self):
        for path in ['../secret.m3u', '/tmp/secret', 'data/library.json', 'https://example.com/live.m3u']:
            data = sample(); data['live']['channelFile'] = path
            with self.subTest(path=path), self.assertRaises(ValueError): builder.resolve_channel_file(data)

    def test_empty_library_does_not_expand_remote_playlists_or_invent_movies(self):
        data = sample()
        data['live']['channels'] = []
        data['vod']['movies'] = []
        out = builder.build(data, 'https://example.com/project/')
        self.assertEqual([], out['catalog.json']['movies'])
        self.assertEqual([], out['live.json']['groups'])
        self.assertEqual('#EXTM3U\n', out['live.m3u'])
        self.assertEqual('', out['live.txt'])

    def test_large_warehouses_split_into_complete_six_config_batches(self):
        for count in [5, 6, 12]:
            data = sample()
            data['warehouses'] = [{'name': '配置 ' + str(i), 'url': 'https://example.com/' + str(i) + '.json?signature=a%2Fb'} for i in range(count)]
            data['warehouses'].append({'name': '停用配置', 'url': 'https://example.com/off.json', 'enabled': False})
            out = builder.build(data, 'https://example.com/')
            groups = out['hosting.json']['warehouseGroups']
            if count == 5:
                self.assertEqual([], groups)
            else:
                combined = []
                for index, group in enumerate(groups):
                    self.assertEqual('warehouse-' + str(index + 1) + '.json', group['path'])
                    urls = out[group['path']]['urls']
                    self.assertLessEqual(len(urls), 6)
                    self.assertEqual(len(urls), group['count'])
                    combined.extend(urls)
                self.assertEqual(out['warehouse.json']['urls'], combined)
                self.assertEqual(len(combined), len({item['url'] for item in combined}))

    def test_removing_warehouses_removes_old_batch_files_without_removing_other_files(self):
        data = sample(); data['warehouses'] *= 7
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            builder.publish_files(data, 'https://example.com/', output)
            self.assertTrue((output / 'warehouse-2.json').exists())
            data['warehouses'] = []
            (output / 'private.txt').write_text('keep')
            with self.assertRaises(ValueError): builder.publish_files(data, 'https://example.com/', output)
            self.assertEqual('keep', (output / 'private.txt').read_text())
            self.assertTrue((output / 'warehouse-2.json').exists())
            (output / 'private.txt').unlink()
            builder.publish_files(data, 'https://example.com/', output)
            self.assertFalse(list(output.glob('warehouse-*.json')))

    def test_relative_links_keep_all_internal_requests_on_the_selected_accelerator(self):
        out = builder.build(sample(), 'https://example.com/project/')
        own = out['box.json']['sites'][0]
        self.assertEqual('./vod.js', own['api'])
        self.assertEqual('./catalog.json', own['ext'])
        self.assertEqual('./live.json', out['box.json']['lives'][0]['url'])
        self.assertEqual('./box.json', out['warehouse.json']['urls'][0]['url'])
        self.assertTrue(out['hosting.json']['endpoints'][0]['base'].startswith('https://gh-proxy.com/'))

    def test_multi_route_live_preserves_groups_logos_headers_and_signed_urls(self):
        data = sample(); out = builder.build(data, 'https://example.com/project/')
        channel = out['live.json']['groups'][0]['channels'][0]
        self.assertEqual('我的频道', out['live.json']['groups'][0]['name'])
        self.assertEqual(data['live']['channels'][0]['urls'], channel['urls'])
        self.assertEqual(data['live']['channels'][0]['headers'], channel['headers'])
        self.assertEqual('https://example.com/logo.png', channel['logo'])
        self.assertEqual(2, out['live.m3u'].count('#EXTINF:'))
        self.assertIn('#EXTVLCOPT:http-referrer=https://example.com/', out['live.m3u'])

    def test_txt_groups_interleaved_channels_and_preserves_every_route_and_signed_url(self):
        data = sample()
        data['live']['channels'] += [
            {'name': '另一频道', 'group': '其他分组', 'urls': ['https://example.com/live?id=1,2&sign=a%2Fb#keep']},
            {'name': '同组频道', 'group': '我的频道', 'urls': ['https://example.com/third']},
            {'name': '停用频道', 'group': '不显示', 'urls': ['https://example.com/off'], 'enabled': False},
        ]
        out = builder.build(data, 'https://example.com/')
        self.assertEqual([
            '我的频道,#genre#',
            '居安频道,https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc',
            '居安频道,http://example.com/backup.m3u8',
            '同组频道,https://example.com/third',
            '其他分组,#genre#',
            '另一频道,https://example.com/live?id=1,2&sign=a%2Fb#keep',
        ], out['live.txt'].splitlines())

    def test_disabled_items_stay_in_input_and_do_not_enter_public_subscriptions(self):
        data = sample()
        for rows in [data['live']['channels'], data['live']['playlists'], data['vod']['movies'], data['vod']['sites'], data['warehouses']]:
            rows[0]['enabled'] = False
        before = copy.deepcopy(data); out = builder.build(data, 'https://example.com/')
        self.assertEqual(before, data)
        self.assertEqual([], out['catalog.json']['movies'])
        self.assertEqual([], out['live.json']['groups'])
        self.assertEqual('', out['live.txt'])
        self.assertEqual(0, len(out['box.json']['sites']))
        self.assertEqual(1, len(out['warehouse.json']['urls']))

    def test_movies_keep_signed_urls_and_receive_the_category_display_name(self):
        data = sample(); out = builder.build(data, 'https://example.com/')
        self.assertEqual('电影', out['catalog.json']['movies'][0]['typeName'])
        self.assertEqual(data['vod']['movies'][0]['routes'], out['catalog.json']['movies'][0]['routes'])

    def test_missing_or_duplicate_ids_and_missing_movie_categories_are_rejected(self):
        for change in [lambda d: d['vod']['movies'].append(copy.deepcopy(d['vod']['movies'][0])),
                       lambda d: d['vod']['movies'][0].update(category='unknown'),
                       lambda d: d['vod']['sites'][0].update(key='juan_personal')]:
            data = sample(); change(data)
            with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_header_injection_or_active_url_schemes_never_reach_output(self):
        for change in [lambda d: d['live']['channels'][0]['headers'].update(Referer='good\r\nInjected: bad'),
                       lambda d: d['live']['channels'][0].update(logo='javascript:alert(1)'),
                       lambda d: d['vod']['sites'][0].update(api='file:///etc/passwd')]:
            data = sample(); change(data)
            with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_csp_requires_an_explicit_jar_but_js_does_not(self):
        data = sample(); data['vod']['sites'][0].update(type=3, api='csp_MySpider')
        with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')
        data['vod']['sites'][0]['jar'] = 'https://example.com/spider.jar;md5;abc'
        builder.build(data, 'https://example.com/')
        data['vod']['sites'][0].pop('jar'); data['vod']['sites'][0]['api'] = 'https://example.com/spider.js'
        builder.build(data, 'https://example.com/')

    def test_generation_copies_only_public_assets_and_rejects_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            builder.publish_files(sample(), 'https://example.com/', output)
            self.assertTrue((output / 'index.html').is_file())
            self.assertFalse((output / 'README.md').exists())
            self.assertFalse((output / 'app').exists())
            (output / 'private.txt').write_text('do not publish')
            with self.assertRaises(ValueError): builder.publish_files(sample(), 'https://example.com/', output)

    def test_base_url_and_repository_cannot_add_query_strings_or_path_escape(self):
        with self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/?token=x')
        with self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', '../private')


class PublisherTests(unittest.TestCase):
    def test_only_generated_files_are_committed_and_real_staged_work_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); repo = root / 'repo'; repo.mkdir(); remote = root / 'remote.git'
            def git(*args): return subprocess.run(['git', *args], cwd=repo, capture_output=True, check=True, text=True).stdout.strip()
            git('init', '-b', 'main'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.com')
            (repo / 'app.txt').write_text('existing'); git('add', '--', 'app.txt'); git('commit', '-m', 'baseline')
            subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
            git('remote', 'add', 'origin', str(remote)); git('push', '-u', 'origin', 'main')
            (repo / 'app.txt').write_text('uncommitted app work'); git('add', '--', 'app.txt')
            before = git('diff', '--cached', '--binary'); head = git('rev-parse', 'HEAD')
            output = root / 'site'; data = sample(); data['warehouses'] *= 7
            builder.publish_files(data, 'https://example.com/', output)
            subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, check=True, capture_output=True)
            self.assertEqual(before, git('diff', '--cached', '--binary'))
            self.assertEqual(head, git('rev-parse', 'HEAD'))
            git('fetch', 'origin', 'source-data')
            published = git('ls-tree', '-r', '--name-only', 'FETCH_HEAD').splitlines()
            self.assertIn('box.json', published); self.assertNotIn('app.txt', published)
            self.assertIn('live.txt', published)
            self.assertEqual((output / 'live.txt').read_text(), git('show', 'FETCH_HEAD:live.txt') + '\n')
            self.assertIn('warehouse-2.json', published)
            self.assertNotIn('README.md', published)
            self.assertEqual('uncommitted app work', (repo / 'app.txt').read_text())
            hosting = json.loads((output / 'hosting.json').read_text())
            hosting['warehouseGroups'][0]['path'] = '../private.txt'
            (output / 'hosting.json').write_text(json.dumps(hosting))
            rejected = subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, capture_output=True)
            self.assertNotEqual(0, rejected.returncode)
            self.assertEqual(before, git('diff', '--cached', '--binary'))


if __name__ == '__main__': unittest.main()
