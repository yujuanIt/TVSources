import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_builder', ROOT / 'scripts/build-source-site.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def sample():
    data = builder.vod_config.materialize(json.loads((ROOT / 'data/library.json').read_text()), json.loads((ROOT / 'data/vod-sites.json').read_text()))
    data['vod'].pop('contexts', None)
    data['live']['playlists'] = [{'name': '直播列表', 'url': 'https://example.com/channels.m3u?sign=a%2Fb',
                                 'headers': {'User-Agent': 'List Player'}, 'enabled': True}]
    data['vod']['sites'] = [{'key': 'my_api', 'name': '我的 API', 'type': 1, 'api': 'https://example.com/api.php',
                           'headers': {'Referer': 'https://example.com/'}, 'ext': {'value': 'keep'}}]
    data['warehouses'] = [{'name': '另一个配置', 'url': 'https://example.com/box.json?sign=a+b%2F'}]
    return data


def channels():
    return [{'name': '居安频道', 'group': '我的频道', 'logo': 'https://example.com/logo.png',
             'urls': ['https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc', 'http://example.com/backup.m3u8'],
             'headers': {'User-Agent': 'My Player', 'Referer': 'https://example.com/'}}]


def source_tree(path, content=None, registry=None):
    source = Path(path) / 'source'; (source / 'data').mkdir(parents=True)
    shutil.copy2(ROOT / 'index.html', source / 'index.html'); shutil.copytree(ROOT / 'assets', source / 'assets')
    if content is not None: (source / 'data/live.m3u').write_text(content, encoding='utf-8')
    if registry is not None: (source / 'data/live-sources.json').write_text(json.dumps(registry))
    return source


def live_sources():
    return {'version': 1, 'playlist': 'data/live.m3u', 'automaticSyncEnabled': False,
            'sources': [{'id': 'alpha', 'name': '来源甲', 'url': 'https://example.com/alpha.m3u', 'format': 'm3u'},
                        {'id': 'beta', 'name': '来源乙', 'url': 'https://example.com/beta.m3u', 'format': 'm3u'},
                        {'id': 'collection', 'name': '合集', 'url': 'https://example.com/box.json', 'format': 'tvbox-lives', 'enabled': False, 'includes': ['alpha', 'beta']}],
            'mergePolicy': {'sourceOrder': ['alpha', 'beta']}}


class BuilderTests(unittest.TestCase):
    def test_module_manifests_share_maintenance_and_only_reference_their_function(self):
        data = sample()
        for endpoint in builder.source_endpoints('https://example.com/source/', 'owner/Sources'):
            own = dict(name='我的 M3U', url=endpoint['base'] + 'data/live.m3u', enabled=False,
                       headers={'User-Agent': 'List Player', 'Referer': 'https://example.com/'})
            data['live']['playlists'] = [own, dict(name='远程列表', url='https://elsewhere.test/live?sig=a%2Bb',
                                                 enabled=True, headers={'Cookie': 'public-fixture=keep'})]
            before = copy.deepcopy(data)
            out = builder.build(data, 'https://example.com/source/', repository='owner/Sources')
            with self.subTest(route=endpoint['name']):
                for module in ['television', 'entertainment']:
                    document = out['data/modules/' + module + '.json']
                    self.assertEqual({'version', 'name', 'module', 'live'}, set(document))
                    self.assertEqual(module, document['module'])
                    self.assertEqual(data['live']['name'], document['live']['name'])
                    expected = {**own, 'url': endpoint['base'] + 'data/modules/' + module + '.m3u'}
                    self.assertEqual([expected, data['live']['playlists'][1]], document['live']['playlists'])
                self.assertEqual({'version': 1, 'name': '简视点播', 'module': 'vod',
                                  'vod': {'name': data['vod']['name'], 'url': data['vod']['url']},
                                  'warehouses': data['warehouses']}, out['data/modules/vod.json'])
                self.assertEqual({'version': 1, 'name': '简视体育', 'module': 'sports'}, out['data/modules/sports.json'])
                self.assertEqual(data['live']['playlists'][1]['url'], out['box.json']['lives'][0]['url'])
                self.assertEqual(['television', 'entertainment', 'vod', 'sports'], [item['module'] for item in out['hosting.json']['modules']])
                self.assertEqual(before, data)

    def test_module_playlists_partition_original_groups_and_keep_every_route_playback_attribute(self):
        rows = builder.parse_m3u('''#EXTM3U
#EXTINF:-1 tvg-id="room-1" tvg-logo="https://images.test/one.png" group-title="虎牙 · 体育" x-source-id="alpha",CCTV5高清
#KODIPROP:inputstream.adaptive.manifest_type=hls
#EXTVLCOPT:network-caching=1000
#EXTHTTP:{"Cookie":"fixture=a%2Fb","User-Agent":"Room Player","Referer":"https://huya.test/"}
https://cdn.test/room.m3u8?sig=a%2Bb%2F&keep=1
#EXTINF:-1 tvg-id="room-1" tvg-logo="https://images.test/one.png" group-title="虎牙 · 体育" x-source-id="beta",CCTV5高清
#EXTHTTP:{"Cookie":"backup=keep"}
https://cdn.test/backup?signature=unchanged+%2F
#EXTINF:-1 group-title="鬥魚直播間",地方卫视
https://cdn.test/douyu
#EXTINF:-1 group-title="其他",虎牙直播
https://huya.test/tv
#EXTINF:-1 group-title="体育",CCTV5高清
https://cdn.test/sport
#EXTINF:-1 group-title="NBA赛事",比赛入口
https://www.88zhibo.tv/live/123/play
#EXTINF:-1 group-title="虎牙" x-enabled="false",停用房间
https://cdn.test/off
''')
        data = sample(); before = copy.deepcopy(rows)
        out = builder.build(data, 'https://example.com/', source_registry=live_sources(), channel_rows=rows)
        expected = {module: [row for row in rows if row['enabled'] and builder.live_channels.is_platform_group(row['group']) == (module == 'entertainment')]
                    for module in ['television', 'entertainment']}
        for module, selected in expected.items():
            self.assertEqual(selected, builder.parse_m3u(out['data/modules/' + module + '.m3u']))
        self.assertEqual(['虎牙 · 体育', '虎牙 · 体育', '鬥魚直播間'], [row['group'] for row in expected['entertainment']])
        self.assertEqual(['其他', '体育', 'NBA赛事'], [row['group'] for row in expected['television']])
        self.assertIn('x-source-name="来源甲"', out['data/modules/entertainment.m3u'])
        self.assertNotIn('https://cdn.test/off', out['data/modules/entertainment.m3u'])
        self.assertEqual(before, rows)

    def test_module_files_publish_with_the_site_and_regenerate_after_maintenance_changes(self):
        content = '#EXTM3U\n#EXTINF:-1 group-title="央视",电视台\nhttps://example.com/tv\n#EXTINF:-1 group-title="B站",直播间\nhttps://example.com/room\n'
        with tempfile.TemporaryDirectory() as temporary:
            source = source_tree(temporary, content); output = Path(temporary) / 'site'
            data = sample(); data['live']['playlists'] = [{'name': '维护文件', 'url': 'https://example.com/data/live.m3u'}]
            with patch.object(builder, 'SOURCE', source):
                builder.publish_files(data, 'https://example.com/', output)
                self.assertIn('https://example.com/tv', (output / 'data/modules/television.m3u').read_text())
                self.assertNotIn('https://example.com/room', (output / 'data/modules/television.m3u').read_text())
                self.assertIn('https://example.com/room', (output / 'data/modules/entertainment.m3u').read_text())
                (source / 'data/live.m3u').write_text('#EXTM3U\n#EXTINF:-1 group-title="影视",新频道\nhttps://example.com/new\n')
                builder.publish_files(data, 'https://example.com/', output)
                self.assertIn('https://example.com/new', (output / 'data/modules/television.m3u').read_text())
                self.assertEqual('#EXTM3U\n', (output / 'data/modules/entertainment.m3u').read_text())
                self.assertEqual({'version': 1, 'name': '简视体育', 'module': 'sports'}, json.loads((output / 'data/modules/sports.json').read_text()))
                self.assertEqual(builder.vod_config.manifest(data), json.loads((output / 'data/library.json').read_text()))

    def test_standalone_sites_are_the_only_published_copy_and_direct_tvbox_stays_separate(self):
        data = sample(); before = copy.deepcopy(data); files = builder.build(data, 'https://example.com/')
        self.assertEqual(builder.vod_config.site_list(data), files['data/vod-sites.json'])
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'site'; builder.publish_files(data, 'https://example.com/', output)
            manifest = json.loads((output / 'data/library.json').read_text())
            sites = json.loads((output / 'data/vod-sites.json').read_text())
            self.assertEqual({'name', 'url'}, set(manifest['vod']))
            self.assertEqual(data['warehouses'], manifest['warehouses'])
            self.assertEqual(data, builder.vod_config.materialize(manifest, sites))
            self.assertEqual('data/vod-sites.json', files['hosting.json']['vodSiteFile'])
            self.assertIn('/edit/main/data/vod-sites.json', files['hosting.json']['vodSiteEditUrl'])
        self.assertEqual(before, data)

    def test_standalone_file_is_bounded_and_cannot_read_a_symlink_or_inline_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / 'data/vod-sites.json'; path.parent.mkdir(); path.write_text('{"version":1,"sites":[]}')
            self.assertEqual([], builder.vod_config.read_site_list(root)['sites'])
            path.unlink(); path.symlink_to(ROOT / 'data/vod-sites.json')
            with self.assertRaisesRegex(ValueError, '真实文件'): builder.vod_config.read_site_list(root)
        with self.assertRaisesRegex(ValueError, 'vod 仅支持'): builder.vod_config.materialize(sample(), {'version': 1, 'sites': []})
        for value in [{'version': 2, 'sites': []}, {'version': 1}, {'version': 1, 'sites': [], 'warehouses': []}]:
            with self.assertRaises(ValueError): builder.vod_config.materialize(builder.vod_config.manifest(sample()), value)
    def test_official_and_iptv_variants_share_channel_names_in_every_output_without_losing_route_headers(self):
        registry = {'version': 1, 'playlist': 'data/live.m3u', 'automaticSyncEnabled': False,
                    'sources': [{'id': key, 'name': name, 'url': 'https://example.com/' + key, 'format': 'm3u'} for key, name in [('official', '官方直播'), ('iptv', 'IPTV备用')]],
                    'mergePolicy': {'sourceOrder': ['official', 'iptv']}}
        rows = [dict(name='CCTV1高清', group='央视', urls=['https://relay.test/a?sig=old%2B'], headers={'Cookie': 'a'}, origins={'https://relay.test/a?sig=old%2B': ['iptv']}),
                dict(name='CCTV-1 综合', group='地方卫视', urls=['https://www.yangshipin.cn/tv/home?pid=600001859&cnlid=2024078201'], headers={'User-Agent': 'qqlive'}, origins={'https://www.yangshipin.cn/tv/home?pid=600001859&cnlid=2024078201': ['official']})]
        files = builder.build(sample(), 'https://example.com/', source_registry=registry, channel_rows=rows)
        self.assertEqual(1, files['manifest.json']['channels'])
        parsed = builder.parse_m3u(files['data/live.m3u'])
        self.assertEqual(['CCTV-1 综合', 'CCTV-1 综合'], [row['name'] for row in parsed])
        self.assertEqual(rows[1]['urls'], parsed[0]['urls']); self.assertEqual(rows[0]['headers'], parsed[1]['headers'])
        self.assertIn('x-source-name="官方直播"', files['live.m3u'])
        self.assertIn('CCTV-1 综合,https://relay.test/a?sig=old%2B', files['live.txt'])
        self.assertEqual(['央视'], [group['name'] for group in files['live.json']['groups']])
    def test_scoped_site_list_generates_independent_standard_tvbox_configs_and_only_selected_sites(self):
        data = sample()
        data['vod']['contexts'] = {
            'one': {'name': '配置甲', 'url': 'https://one.example/path/box.json', 'spider': './one.jar;md5;abc',
                    'parses': [{'name': '解析', 'type': 1, 'url': './parse?url='}], 'flags': ['line1']},
            'two': {'name': '配置乙', 'url': 'https://two.example/box.json', 'spider': './two.jar'}}
        for context in ('one', 'two'):
            data['vod']['sites'].append({'context': context, 'key': '中文站点', 'name': '自己维护', 'type': 3, 'api': 'csp_Test',
                                        '_syncId': context, 'origin': {'name': '上游'}})
        data['vod']['sites'].append({'context': 'one', 'key': 'hidden', 'name': '停用站点', 'type': 3, 'api': 'csp_Test', 'enabled': False})
        before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'site'; builder.publish_files(data, 'https://example.com/', output)
            one = json.loads((output / 'vod/one.json').read_text()); two = json.loads((output / 'vod/two.json').read_text())
            self.assertEqual(one['spider'], 'https://one.example/path/one.jar;md5;abc')
            self.assertEqual(two['spider'], 'https://two.example/two.jar')
            self.assertEqual(one['parses'][0]['url'], 'https://one.example/path/parse?url=')
            self.assertEqual(len(one['sites']), 1); self.assertNotIn('_syncId', one['sites'][0]); self.assertNotIn('context', one['sites'][0])
            urls = json.loads((output / 'warehouse.json').read_text())['urls']
            self.assertEqual([item['url'] for item in urls[1:3]], ['./vod/one.json', './vod/two.json'])
            self.assertEqual(json.loads((output / 'data/library.json').read_text()), builder.vod_config.manifest(before))
            data['vod']['sites'] = [item for item in data['vod']['sites'] if item.get('context') != 'two']
            builder.publish_files(data, 'https://example.com/', output)
            self.assertFalse((output / 'vod/two.json').exists())
        self.assertEqual(data['vod']['contexts'], before['vod']['contexts'])

    def test_invalid_dependency_references_and_nested_source_lists_are_rejected(self):
        data = sample(); data['vod']['sites'][0]['context'] = 'missing'
        with self.assertRaisesRegex(ValueError, '不存在'): builder.validate(data)
        data['vod']['contexts'] = {'missing': {'name': '配置', 'url': 'https://example.com/box.json', 'sites': []}}
        with self.assertRaisesRegex(ValueError, '不能内嵌'): builder.validate(data)

    def test_scoped_plugins_can_inherit_the_owners_shared_spider(self):
        data = sample(); data['vod']['spider'] = 'https://owner.example/shared.jar;md5;abc'
        data['vod']['contexts'] = {'owner': {'name': '自建分组', 'url': 'https://owner.example/source.json'}}
        data['vod']['sites'].append({'context': 'owner', 'key': 'plugin', 'name': '插件站点', 'type': 3, 'api': 'csp_Test'})
        self.assertEqual(builder.build(data, 'https://example.com/')['vod/owner.json']['spider'], data['vod']['spider'])

    def test_source_only_configuration_publishes_exactly_the_maintained_library(self):
        data = sample(); before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'; builder.publish_files(data, 'https://example.com/', output)
            self.assertEqual(builder.vod_config.manifest(before), json.loads((output / 'data/library.json').read_text()))
            self.assertEqual(before, data)
            box = json.loads((output / 'box.json').read_text())
            self.assertEqual(['my_api'], [site['key'] for site in box['sites']])
            self.assertEqual(data['vod']['sites'][0]['headers'], box['sites'][0]['headers'])
            self.assertEqual(data['live']['playlists'][0]['url'], box['lives'][0]['url'])
            self.assertEqual(data['live']['playlists'][0]['headers'], box['lives'][0]['headers'])
            self.assertEqual(data['warehouses'][0]['url'], json.loads((output / 'warehouse.json').read_text())['urls'][1]['url'])
            self.assertFalse((output / 'vod.js').exists()); self.assertFalse((output / 'catalog.json').exists())
            self.assertEqual([], json.loads((output / 'live.json').read_text())['groups'])

    def test_library_accepts_only_the_three_source_lists(self):
        for owner, key in [('live', 'channels'), ('live', 'channelFile'), ('vod', 'categories'), ('vod', 'movies')]:
            for value in [[], [{'name': '不属于订阅配置'}], None, {}]:
                data = sample(); data[owner][key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, owner + ' 仅支持'):
                    builder.build(data, 'https://example.com/')
        for owner, key in [('live', 'playlists'), ('vod', 'sites'), (None, 'warehouses')]:
            for value in [None, {}, 'not-an-array']:
                data = sample(); parent = data[owner] if owner else data; parent[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError): builder.build(data, 'https://example.com/')
                del parent[key]
                with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_provenance_roundtrip_keeps_per_route_sources_without_splitting_or_renaming_channels(self):
        rows = channels(); channel = rows[0]
        channel['origins'] = {channel['urls'][0]: ['alpha', 'beta'], channel['urls'][1]: ['beta']}
        before = copy.deepcopy(rows); registry = live_sources(); saved = copy.deepcopy(registry)
        out = builder.build(sample(), 'https://example.com/', source_registry=registry, channel_rows=rows)
        self.assertEqual([{**channel, 'tvgId': '', 'enabled': True}], builder.parse_m3u(out['live.m3u']))
        self.assertIn('x-source-id="alpha,beta" x-source-name="来源甲 / 来源乙"', out['data/live.m3u'])
        self.assertIn('#SOURCE-MANIFEST:https://example.com/data/live-sources.json', out['live.m3u'])
        self.assertEqual(channel['origins'], out['live.json']['groups'][0]['channels'][0]['origins'])
        self.assertEqual(before, rows); self.assertEqual(saved, registry)

    def test_invalid_or_unknown_provenance_is_rejected_before_output(self):
        for origins in [{'https://example.com/not-in-this-channel': ['alpha']},
                        {'https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc': ['alpha\n#EXTINF:-1']},
                        {'https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc': [{}]}]:
            rows = channels(); rows[0]['origins'] = origins
            with self.subTest(origins=origins), self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', channel_rows=rows)
        rows = channels(); rows[0]['origins'] = {rows[0]['urls'][0]: ['unknown']}
        with self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', source_registry=live_sources(), channel_rows=rows)
        for attr in ['alpha,../bad', 'alpha,beta&x=y', 'alpha,,beta']:
            with self.subTest(attr=attr), self.assertRaises(ValueError): builder.parse_m3u('#EXTM3U\n#EXTINF:-1 x-source-id="' + attr + '",频道\nhttps://example.com/live\n')

    def test_registry_checks_ids_addresses_collection_members_and_merge_order(self):
        builder.validate_live_sources(live_sources())
        for change in [lambda d: d.update(playlist='../private'),
                       lambda d: d['sources'].append(copy.deepcopy(d['sources'][0])),
                       lambda d: d['sources'][0].update(url='file:///private'),
                       lambda d: d['sources'][2].update(includes=['missing']),
                       lambda d: d['sources'][2].update(includes=['collection']),
                       lambda d: d['sources'][0].update(headers={'User-Agent': 'bad\nheader'}),
                       lambda d: d['sources'][0].update(selection={'mode': 'keep-selected', 'names': []}),
                       lambda d: d['sources'][0].update(selection={'mode': 'keep-selected', 'names': ['bad\nname']}),
                       lambda d: d.update(sync={'minimumPreviousRouteRatio': 0}),
                       lambda d: d.update(sync={'minimumPreviousRouteRatio': 2}),
                       lambda d: d['mergePolicy'].update(sourceOrder=['alpha']),
                       lambda d: d['sources'][2].update(enabled=True)]:
            registry = live_sources(); change(registry)
            with self.subTest(registry=registry), self.assertRaises(ValueError): builder.validate_live_sources(registry)

    def test_bad_registry_leaves_the_previous_site_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            source = source_tree(temp, registry=live_sources()); output = Path(temp) / 'site'
            with patch.object(builder, 'SOURCE', source):
                builder.publish_files(sample(), 'https://example.com/', output)
                self.assertEqual(live_sources(), json.loads((output / 'data/live-sources.json').read_text()))
                previous = (output / 'data/library.json').read_text()
                registry = source / 'data/live-sources.json'; registry.write_text('{"version":99}')
                with self.assertRaises(ValueError): builder.publish_files(sample(), 'https://example.com/', output)
                self.assertEqual(previous, (output / 'data/library.json').read_text())
                registry.unlink(); builder.publish_files(sample(), 'https://example.com/', output)
                self.assertFalse((output / 'data/live-sources.json').exists())
                self.assertNotIn('liveSources', json.loads((output / 'hosting.json').read_text()))

    def test_m3u_roundtrip_keeps_logos_epg_multiple_routes_and_all_headers(self):
        rows = channels(); channel = rows[0]; channel.update(group='组名,含 & "引号"', tvgId='channel-1')
        channel['headers']['X-Playback-Token'] = 'public-example=a%2Fb'
        out = builder.build(sample(), 'https://example.com/', channel_rows=rows)
        self.assertEqual([{**channel, 'enabled': True}], builder.parse_m3u(out['live.m3u']))

    def test_m3u_accepts_bom_crlf_single_quotes_and_resets_headers_between_channels(self):
        content = '\ufeff#EXTM3U\r\n#EXTINF:-1 tvg-logo=\'https://example.com/logo.png?a=1&amp;b=2\' group-title=\'游戏,直播\',名称,含逗号\r\n#EXTVLCOPT:http-user-agent=Test Player\r\nhttps://example.com/1?id=1,2#keep\r\n#EXTINF:-1,另一频道\r\n#EXTGRP:其他\r\n#EXTHTTP:{"Referer":"https://example.com/"}\r\nhttps://example.com/2\r\n#EXTINF:-1 x-enabled="false",已停用\r\nhttps://example.com/off\r\n'
        rows = builder.parse_m3u(content)
        self.assertEqual('游戏,直播', rows[0]['group']); self.assertEqual('名称,含逗号', rows[0]['name'])
        self.assertEqual('https://example.com/logo.png?a=1&b=2', rows[0]['logo'])
        self.assertEqual(['https://example.com/1?id=1,2#keep'], rows[0]['urls'])
        self.assertEqual({'User-Agent': 'Test Player'}, rows[0]['headers'])
        self.assertEqual({'Referer': 'https://example.com/'}, rows[1]['headers']); self.assertFalse(rows[2]['enabled'])
        out = builder.build(sample(), 'https://example.com/', channel_rows=rows)
        self.assertNotIn('https://example.com/off', out['live.m3u']); self.assertNotIn('https://example.com/off', out['live.txt'])

    def test_m3u_keeps_player_options_and_extended_http_headers(self):
        content = '#EXTM3U\n#EXTINF:-1 group-title="电视",频道\n#KODIPROP:inputstream.adaptive.manifest_type=mpd\n#EXTVLCOPT:network-caching=1000\n#EXTVLCOPT:http-referer=https://example.com/\n#EXTVLCOPT:http-origin=https://example.com\n#EXTVLCOPT:http-cookie=public-example=a%2Fb\nhttps://example.com/one.mpd?sign=a+b%2F\n#EXTINF:-1 group-title="电视",频道\n#KODIPROP:inputstream.adaptive.manifest_type=hls\nhttps://example.com/two.m3u8\n'
        rows = builder.parse_m3u(content)
        self.assertEqual(2, len(rows))
        self.assertEqual(['#KODIPROP:inputstream.adaptive.manifest_type=mpd', '#EXTVLCOPT:network-caching=1000'], rows[0]['directives'])
        self.assertEqual({'Referer': 'https://example.com/', 'Origin': 'https://example.com', 'Cookie': 'public-example=a%2Fb'}, rows[0]['headers'])
        self.assertEqual({}, rows[1]['headers'])
        self.assertEqual(rows, builder.parse_m3u(builder.build(sample(), 'https://example.com/', channel_rows=rows)['data/live.m3u']))
        for value in ['#KODIPROP:x=y\nhttps://other.example/', '#EXTHTTP:{}', 'https://other.example/']:
            rows[0]['directives'] = [value]
            with self.subTest(value=value), self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', channel_rows=rows)

    def test_invalid_m3u_fails_instead_of_silently_losing_channels(self):
        for content in ['<html>error</html>', '#EXTM3U\nhttps://example.com/live', '#EXTM3U\n#EXTINF:-1,没有地址',
                        '#EXTM3U\n#EXTINF:-1,一\n#EXTINF:-1,二\nhttps://example.com/live',
                        '#EXTM3U\n#EXTINF:-1,一\n#EXTHTTP:[]\nhttps://example.com/live',
                        '#EXTM3U\n#EXTINF:-1,一\nfile:///private', '#EXTM3U\n#EXTINF:-1 x-enabled="yes",一\nhttps://example.com/live']:
            with self.subTest(content=content), self.assertRaises(ValueError): builder.parse_m3u(content)

    def test_project_m3u_updates_all_live_outputs_without_writing_channels_into_the_library(self):
        content = '#EXTM3U\n#EXTINF:-1 group-title="我的分组",我的频道\n#EXTVLCOPT:http-user-agent=Player\nhttps://example.com/original?sig=a+b%2F\n#EXTINF:-1 group-title="另一分组",另一频道\nhttps://example.com/other\n'
        with tempfile.TemporaryDirectory() as temp:
            source = source_tree(temp, content); output = Path(temp) / 'site'
            data = sample(); data['live']['playlists'] = [{'name': '我的 M3U', 'url': 'https://example.com/data/live.m3u'}]
            before = copy.deepcopy(data)
            with patch.object(builder, 'SOURCE', source):
                result = builder.publish_files(data, 'https://example.com/', output)
                self.assertEqual(2, result['channels'])
                self.assertEqual(builder.vod_config.manifest(before), json.loads((output / 'data/library.json').read_text()))
                self.assertEqual(before, data)
                self.assertEqual([data['live']['playlists'][0]['url']], [item['url'] for item in json.loads((output / 'box.json').read_text())['lives']])
                self.assertEqual(builder.parse_m3u(content), builder.parse_m3u((output / 'data/live.m3u').read_text()))
                self.assertEqual((output / 'data/live.m3u').read_text(), (output / 'live.m3u').read_text())
                self.assertEqual({'User-Agent': 'Player'}, json.loads((output / 'live.json').read_text())['groups'][0]['channels'][0]['headers'])
                hosting = json.loads((output / 'hosting.json').read_text())
                self.assertEqual('https://example.com/data/live.m3u', hosting['channelUrl']); self.assertEqual(2, hosting['channelCount'])
                self.assertTrue(hosting['channelEditUrl'].endswith('/data/live.m3u'))
                path = source / 'data/live.m3u'; path.write_text('#EXTM3U\n#EXTINF:-1,第二版频道\nhttps://example.com/updated\n', encoding='utf-8')
                builder.publish_files(data, 'https://example.com/', output)
                self.assertIn('第二版频道', (output / 'data/live.m3u').read_text()); self.assertNotIn('original', (output / 'data/live.m3u').read_text())
                self.assertIn('第二版频道,https://example.com/updated', (output / 'live.txt').read_text())
                previous = (output / 'data/live.m3u').read_bytes()
                path.write_text('#EXTM3U\n#EXTINF:-1,缺少地址', encoding='utf-8')
                with self.assertRaises(ValueError): builder.publish_files(data, 'https://example.com/', output)
                self.assertEqual(previous, (output / 'data/live.m3u').read_bytes())

    def test_project_m3u_accelerator_links_read_only_the_local_file_for_this_repository(self):
        content = '#EXTM3U\n#EXTINF:-1 tvg-logo="https://example.com/logo.png" group-title="IPTV IPv6 · 央视",频道\n#EXTVLCOPT:http-user-agent=Player\nhttp://[2001:db8::1]/live.m3u8?sign=a+b%2F\n'
        with tempfile.TemporaryDirectory() as temp:
            source = source_tree(temp, content); output = Path(temp) / 'site'
            repository = 'example-owner/OwnSources'; base = 'https://example.com/source/'
            for endpoint in builder.source_endpoints(base, repository):
                data = sample(); address = endpoint['base'] + 'data/live.m3u'
                data['live']['playlists'] = [{'name': '我的 M3U', 'url': address, 'enabled': True}]; before = copy.deepcopy(data)
                with self.subTest(address=address), patch.object(builder, 'SOURCE', source):
                    result = builder.publish_files(data, base, output, repository)
                    self.assertEqual(1, result['channels'])
                    self.assertEqual(builder.parse_m3u(content), builder.parse_m3u((output / 'data/live.m3u').read_text()))
                    self.assertEqual(builder.vod_config.manifest(before), json.loads((output / 'data/library.json').read_text())); self.assertEqual(before, data)
                    hosting = json.loads((output / 'hosting.json').read_text())
                    self.assertEqual(address, hosting['channelUrl']); self.assertEqual(1, hosting['channelCount'])
            for address in ['https://gh-proxy.com/https://raw.githubusercontent.com/other/repository/source-data/data/live.m3u',
                            'https://gh-proxy.com/https://raw.githubusercontent.com/' + repository + '/source-data/data/live.m3u?other=true',
                            'https://example.com/source/data/live.m3u/../secret']:
                data['live']['playlists'][0]['url'] = address
                with self.subTest(unrelated=address), patch.object(builder, 'SOURCE', source):
                    self.assertEqual((None, []), builder.read_project_channels(data, base, repository))

    def test_project_m3u_does_not_read_symbolic_links(self):
        for parent_link in [False, True]:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); source = root / 'source'; source.mkdir(); target = root / 'target'; target.mkdir()
                (target / 'live.m3u').write_text('#EXTM3U\n#EXTINF:-1,频道\nhttps://example.com/live\n')
                if parent_link: (source / 'data').symlink_to(target, target_is_directory=True)
                else:
                    (source / 'data').mkdir(); (source / 'data/live.m3u').symlink_to(target / 'live.m3u')
                data = sample(); data['live']['playlists'][0]['url'] = 'https://example.com/data/live.m3u'
                with patch.object(builder, 'SOURCE', source), self.assertRaises(ValueError):
                    builder.read_project_channels(data, 'https://example.com/', 'yujuanIt/TVSources')

    def test_empty_library_has_no_synthetic_vod_or_live_entries(self):
        data = sample(); data['live']['playlists'] = []; data['vod']['sites'] = []; data['warehouses'] = []
        out = builder.build(data, 'https://example.com/project/')
        self.assertEqual([], out['box.json']['sites']); self.assertEqual([], out['box.json']['lives'])
        self.assertEqual([], out['live.json']['groups']); self.assertEqual('#EXTM3U\n', out['live.m3u']); self.assertEqual('', out['live.txt'])
        self.assertNotIn('catalog.json', out)

    def test_large_warehouses_split_into_complete_six_config_batches(self):
        for count in [5, 6, 12]:
            data = sample(); data['warehouses'] = [{'name': '配置 ' + str(i), 'url': 'https://example.com/' + str(i) + '.json?signature=a%2Fb'} for i in range(count)]
            data['warehouses'].append({'name': '停用配置', 'url': 'https://example.com/off.json', 'enabled': False})
            out = builder.build(data, 'https://example.com/'); groups = out['hosting.json']['warehouseGroups']
            if count == 5: self.assertEqual([], groups)
            else:
                combined = []
                for index, group in enumerate(groups):
                    self.assertEqual('warehouse-' + str(index + 1) + '.json', group['path']); urls = out[group['path']]['urls']
                    self.assertLessEqual(len(urls), 6); self.assertEqual(len(urls), group['count']); combined.extend(urls)
                self.assertEqual(out['warehouse.json']['urls'], combined); self.assertEqual(len(combined), len({item['url'] for item in combined}))

    def test_removing_warehouses_removes_old_batch_files_without_removing_other_files(self):
        data = sample(); data['warehouses'] *= 7
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'; builder.publish_files(data, 'https://example.com/', output)
            self.assertTrue((output / 'warehouse-2.json').exists()); data['warehouses'] = []; (output / 'private.txt').write_text('keep')
            with self.assertRaises(ValueError): builder.publish_files(data, 'https://example.com/', output)
            self.assertEqual('keep', (output / 'private.txt').read_text()); self.assertTrue((output / 'warehouse-2.json').exists())
            (output / 'private.txt').unlink(); builder.publish_files(data, 'https://example.com/', output)
            self.assertFalse(list(output.glob('warehouse-*.json')))

    def test_relative_warehouse_links_keep_the_selected_accelerator(self):
        out = builder.build(sample(), 'https://example.com/project/')
        self.assertEqual('./box.json', out['warehouse.json']['urls'][0]['url'])
        self.assertTrue(out['hosting.json']['endpoints'][0]['base'].startswith('https://gh-proxy.com/'))

    def test_multi_route_live_preserves_groups_logos_headers_and_signed_urls(self):
        rows = channels(); out = builder.build(sample(), 'https://example.com/project/', channel_rows=rows)
        channel = out['live.json']['groups'][0]['channels'][0]
        self.assertEqual('我的频道', out['live.json']['groups'][0]['name'])
        self.assertEqual(rows[0]['urls'], channel['urls']); self.assertEqual(rows[0]['headers'], channel['headers'])
        self.assertEqual('https://example.com/logo.png', channel['logo']); self.assertEqual(2, out['live.m3u'].count('#EXTINF:'))
        self.assertIn('#EXTVLCOPT:http-referrer=https://example.com/', out['live.m3u'])

    def test_txt_groups_interleaved_channels_and_preserves_every_route_and_signed_url(self):
        rows = channels() + [
            {'name': '另一频道', 'group': '其他分组', 'urls': ['https://example.com/live?id=1,2&sign=a%2Fb#keep']},
            {'name': '同组频道', 'group': '我的频道', 'urls': ['https://example.com/third']},
            {'name': '停用频道', 'group': '不显示', 'urls': ['https://example.com/off'], 'enabled': False}]
        out = builder.build(sample(), 'https://example.com/', channel_rows=rows)
        self.assertEqual(3, out['manifest.json']['channels'])
        self.assertEqual(['我的频道,#genre#', '居安频道,https://example.com/live.m3u8?token=a%2Bb%2F&sign=abc',
                          '居安频道,http://example.com/backup.m3u8', '同组频道,https://example.com/third',
                          '其他分组,#genre#', '另一频道,https://example.com/live?id=1,2&sign=a%2Fb#keep'], out['live.txt'].splitlines())

    def test_disabled_items_stay_in_input_but_not_public_subscriptions(self):
        data = sample(); rows = channels()
        for records in [data['live']['playlists'], data['vod']['sites'], data['warehouses'], rows]: records[0]['enabled'] = False
        before = copy.deepcopy(data); saved = copy.deepcopy(rows); out = builder.build(data, 'https://example.com/', channel_rows=rows)
        self.assertEqual(before, data); self.assertEqual(saved, rows); self.assertEqual([], out['box.json']['sites'])
        self.assertEqual([], out['box.json']['lives']); self.assertEqual([], out['live.json']['groups']); self.assertEqual('', out['live.txt'])
        self.assertEqual(1, len(out['warehouse.json']['urls']))

    def test_missing_duplicate_or_invalid_site_keys_are_rejected(self):
        for change in [lambda d: d['vod']['sites'].append(copy.deepcopy(d['vod']['sites'][0])),
                       lambda d: d['vod']['sites'][0].pop('key'), lambda d: d['vod']['sites'][0].update(key='bad/key')]:
            data = sample(); change(data)
            with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_header_injection_and_invalid_url_schemes_never_reach_output(self):
        rows = channels(); rows[0]['headers']['Referer'] = 'good\r\nInjected: bad'
        with self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', channel_rows=rows)
        rows = channels(); rows[0]['logo'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): builder.build(sample(), 'https://example.com/', channel_rows=rows)
        for owner, key in [('playlists', 'url'), ('sites', 'api')]:
            data = sample(); records = data['live'][owner] if owner == 'playlists' else data['vod'][owner]; records[0][key] = 'file:///private'
            with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')

    def test_csp_requires_an_explicit_jar_but_js_does_not(self):
        data = sample(); data['vod']['sites'][0].update(type=3, api='csp_MySpider')
        with self.assertRaises(ValueError): builder.build(data, 'https://example.com/')
        data['vod']['sites'][0]['jar'] = 'https://example.com/spider.jar;md5;abc'; builder.build(data, 'https://example.com/')
        data['vod']['sites'][0].pop('jar'); data['vod']['spider'] = 'https://example.com/shared.jar'; out = builder.build(data, 'https://example.com/')
        self.assertEqual(data['vod']['spider'], out['vod.json']['spider'])
        del data['vod']['spider']; data['vod']['sites'][0]['api'] = 'https://example.com/spider.js'; builder.build(data, 'https://example.com/')

    def test_generation_copies_only_public_assets_and_rejects_unexpected_files(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'; builder.publish_files(sample(), 'https://example.com/', output)
            self.assertTrue((output / 'index.html').exists()); self.assertTrue((output / 'assets/editor.js').exists())
            self.assertFalse((output / 'vod.js').exists()); self.assertFalse((output / 'catalog.json').exists())
            self.assertFalse((output / 'scripts').exists()); self.assertFalse((output / 'README.md').exists())
            (output / 'private.apk').write_text('not a source file')
            with self.assertRaises(ValueError): builder.publish_files(sample(), 'https://example.com/', output)
            self.assertEqual('not a source file', (output / 'private.apk').read_text())

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
            data['vod']['contexts'] = {'owner': {'name': '自管配置', 'url': 'https://up.example/path/box.json', 'spider': './engine.jar'}}
            data['vod']['sites'].append({'context': 'owner', 'key': '中文站点', 'name': '自管站点', 'type': 3, 'api': 'csp_Test'})
            builder.publish_files(data, 'https://example.com/', output)
            subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, check=True, capture_output=True)
            self.assertEqual(before, git('diff', '--cached', '--binary'))
            self.assertEqual(head, git('rev-parse', 'HEAD'))
            git('fetch', 'origin', 'source-data')
            published = git('ls-tree', '-r', '--name-only', 'FETCH_HEAD').splitlines()
            self.assertIn('box.json', published); self.assertNotIn('app.txt', published)
            self.assertIn('live.txt', published)
            self.assertIn('data/live.m3u', published)
            self.assertTrue({'data/modules/' + module + '.json' for module in ['television', 'entertainment', 'vod', 'sports']} <= set(published))
            self.assertIn('data/modules/television.m3u', published)
            self.assertIn('data/modules/entertainment.m3u', published)
            self.assertIn('data/live-sources.json', published)
            self.assertIn('vod/owner.json', published)
            self.assertEqual('https://up.example/path/engine.jar', json.loads(subprocess.check_output(['git', 'show', 'FETCH_HEAD:vod/owner.json'], cwd=repo, text=True))['spider'])
            self.assertNotIn('data/vod-sync-state.json', published)
            self.assertEqual((output / 'live.txt').read_text(), subprocess.check_output(['git', 'show', 'FETCH_HEAD:live.txt'], cwd=repo, text=True))
            self.assertIn('warehouse-2.json', published)
            self.assertNotIn('README.md', published)
            self.assertNotIn('vod.js', published); self.assertNotIn('catalog.json', published)
            self.assertEqual('uncommitted app work', (repo / 'app.txt').read_text())
            hosting = json.loads((output / 'hosting.json').read_text())
            hosting['warehouseGroups'][0]['path'] = '../private.txt'
            (output / 'hosting.json').write_text(json.dumps(hosting))
            rejected = subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, capture_output=True)
            self.assertNotEqual(0, rejected.returncode)
            self.assertEqual(before, git('diff', '--cached', '--binary'))
            hosting['warehouseGroups'][0]['path'] = 'warehouse-1.json'; hosting['liveSources'] = '../private.txt'
            (output / 'hosting.json').write_text(json.dumps(hosting))
            rejected = subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, capture_output=True)
            self.assertNotEqual(0, rejected.returncode); self.assertEqual(before, git('diff', '--cached', '--binary'))
            hosting['liveSources'] = 'data/live-sources.json'; hosting['modules'][0]['path'] = '../private.json'
            (output / 'hosting.json').write_text(json.dumps(hosting))
            rejected = subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, capture_output=True)
            self.assertNotEqual(0, rejected.returncode); self.assertIn(b'Invalid module', rejected.stderr)
            hosting['modules'][0]['path'] = 'data/modules/television.json'; (output / 'hosting.json').write_text(json.dumps(hosting))
            module_file = output / 'data/modules/sports.json'
            module = json.loads(module_file.read_text()); module['vod'] = data['vod']; module_file.write_text(json.dumps(module))
            rejected = subprocess.run(['python3', str(ROOT / 'scripts/publish-source-data.py'), '--directory', str(output)], cwd=repo, capture_output=True)
            self.assertNotEqual(0, rejected.returncode); self.assertIn(b'Module subscription differs', rejected.stderr)
            self.assertEqual(before, git('diff', '--cached', '--binary'))


if __name__ == '__main__': unittest.main()
