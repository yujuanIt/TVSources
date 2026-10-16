import base64
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vod_sync', ROOT / 'scripts/sync-vod.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def library():
    return {'version': 1, 'name': '我的源', 'live': {'name': '直播', 'playlists': []},
            'vod': {'name': '片库', 'url': 'https://example.com/data/vod-sites.json', 'sites': []}, 'warehouses': []}


def registry():
    return {'version': 1, 'automaticSyncEnabled': True, 'newSitesEnabled': True,
            'sources': [{'id': 'upstream', 'name': '上游', 'url': 'https://up.example/box/main.json', 'enabled': True}]}


def fixture(name='上游影片', address='https://api.example/vod?sign=a%2Bb%2F'):
    return {'spider': './engine.jar;md5;abc',
            'parses': [{'name': '同名解析', 'type': 1, 'url': './parse?url=', 'ext': {'header': {'Referer': 'https://up.example/'}}}],
            'headers': [{'host': 'video.example', 'header': {'Cookie': 'fixture=public'}}],
            'flags': ['line1'], 'ads': ['ads.example'], 'rules': [{'hosts': ['video.example'], 'regex': ['ad.*']}],
            'sites': [{'key': '中文站点', 'name': name, 'type': 1, 'api': address, 'header': {'User-Agent': 'Fixture TV'},
                       'ext': {'url': './rules.json', 'token': 'a+b%2F$#'}, 'searchable': 1}]}


def documents(data=None, source=None):
    return sync.expand(source or registry()['sources'][0], lambda row: json.dumps(data or fixture(), ensure_ascii=False).encode())


def first(data=None):
    return sync.merge(library(), registry(), None, [documents(data)])


class VodSyncTests(unittest.TestCase):
    def test_regular_sync_updates_only_standalone_sites_and_keeps_owner_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); current, state, _ = first(); current['vod']['sites'][0]['name'] = '本机自定义名称'; current['vod']['sites'][0]['searchable'] = 0
            manifest = sync.config.manifest(current); manifest['warehouses'] = [{'name': '直接保留的 TVBox', 'url': 'https://other.example/box.json'}]
            sync.write_json(root / 'data/library.json', manifest); original = (root / 'data/library.json').read_bytes()
            sync.write_json(root / 'data/vod-sites.json', sync.config.site_list(current)); sync.write_json(root / 'data/vod-sync-state.json', state)
            sync.write_json(root / 'data/vod-sources.json', registry())
            upstream = fixture('上游改名'); new = copy.deepcopy(upstream['sites'][0]); new.update(key='新站点', name='新片库'); upstream['sites'].append(new)
            with patch.object(sync, 'expand', return_value=documents(upstream)):
                self.assertEqual(0, sync.main(['--root', str(root), '--report', str(root / 'report.json')]))
            result = sync.read_json(root / 'data/vod-sites.json'); self.assertEqual(2, len(result['sites']))
            self.assertEqual('本机自定义名称', result['sites'][0]['name']); self.assertEqual(0, result['sites'][0]['searchable'])
            self.assertTrue(result['sites'][1]['enabled']); self.assertEqual(original, (root / 'data/library.json').read_bytes())
            result['sites'].pop(0); sync.write_json(root / 'data/vod-sites.json', result)
            with patch.object(sync, 'expand', return_value=documents(upstream)):
                self.assertEqual(0, sync.main(['--root', str(root), '--report', str(root / 'report.json')]))
            self.assertEqual(['新站点'], [row['key'] for row in sync.read_json(root / 'data/vod-sites.json')['sites']])
            self.assertEqual(original, (root / 'data/library.json').read_bytes())

    def test_json5_base64_and_image_wrapped_configs_keep_signed_values(self):
        body = b'// comment\n{sites:[{key:"x", name:"test", type:1, api:"https://api.example/?sign=a+b%2F#x",},],}'
        for payload in (body, base64.b64encode(body), b'base64://' + base64.b64encode(body), b'\xff\xd8binary\xff**' + base64.b64encode(body)):
            self.assertEqual(sync.parse(payload)['sites'][0]['api'], 'https://api.example/?sign=a+b%2F#x')
        for payload in (b'<html>failed</html>', b'null', b'{"sites": [], "sites": [broken]}'):
            with self.assertRaises(ValueError): sync.parse(payload)

    def test_nested_warehouse_expands_relative_urls_and_skips_cycles(self):
        source = registry()['sources'][0]
        values = {source['url']: {'urls': [{'name': '子配置', 'url': './one.json'}, {'name': '循环', 'url': './main.json'}]},
                  'https://up.example/box/one.json': fixture()}
        calls = []
        def fetch(row):
            calls.append(row['url']); return json.dumps(values[row['url']]).encode()
        result = sync.expand(source, fetch)
        self.assertEqual(len(result['documents']), 1); self.assertEqual(len(calls), 2)
        context = result['documents'][0]['context']
        self.assertEqual(context['spider'], 'https://up.example/box/engine.jar;md5;abc')
        self.assertEqual(context['parses'][0]['url'], 'https://up.example/box/parse?url=')
        site = result['documents'][0]['sites'][0]
        self.assertEqual(site['ext']['url'], 'https://up.example/box/rules.json')
        self.assertEqual(site['ext']['token'], 'a+b%2F$#')
        self.assertEqual(context['headers'][0]['header']['Cookie'], 'fixture=public')

    def test_redirects_and_mirrors_do_not_change_binding_or_context_identity(self):
        source = registry()['sources'][0]; source['mirrors'] = ['https://mirror.example/box/main.json']
        def fetch(row):
            if row['url'] == source['url']: raise OSError('down')
            return json.dumps(fixture()).encode(), 'https://cdn.example/new/main.json'
        mirrored = sync.expand(source, fetch)['documents'][0]
        ordinary = documents()['documents'][0]
        self.assertEqual(mirrored['id'], ordinary['id']); self.assertEqual(mirrored['url'], ordinary['url'])
        self.assertEqual(mirrored['context']['spider'], 'https://cdn.example/new/engine.jar;md5;abc')

    def test_changing_a_registered_root_url_keeps_site_identity_and_owner_changes(self):
        current, state, _ = first(); current['vod']['sites'][0]['name'] = '保留的名称'
        source = {**registry()['sources'][0], 'url': 'https://new.example/new.json'}
        output, _, report = sync.merge(current, registry(), state, [documents(source=source)])
        self.assertEqual(report['added'], 0); self.assertEqual(len(output['vod']['sites']), 1)
        self.assertEqual(output['vod']['sites'][0]['name'], '保留的名称')
        self.assertEqual(output['vod']['sites'][0]['_syncId'], current['vod']['sites'][0]['_syncId'])

    def test_local_names_switches_removals_nested_headers_and_new_fields_survive_refresh(self):
        current, state, _ = first(); row = current['vod']['sites'][0]
        row['name'] = '自己命名'; row['enabled'] = False; row['searchable'] = 0
        row['header']['User-Agent'] = 'Owner TV'; row['ext']['token'] = 'owner-value'
        del row['ext']['url']
        upstream = fixture('上游改名', 'https://api.example/vod?sign=new%2B%2F')
        upstream['sites'][0]['ext']['newField'] = 'added'
        refreshed, next_state, report = sync.merge(current, registry(), state, [documents(upstream)])
        updated = refreshed['vod']['sites'][0]
        self.assertEqual(updated['name'], '自己命名'); self.assertFalse(updated['enabled']); self.assertEqual(updated['searchable'], 0)
        self.assertEqual(updated['header']['User-Agent'], 'Owner TV'); self.assertEqual(updated['ext']['token'], 'owner-value')
        self.assertNotIn('url', updated['ext']); self.assertEqual(updated['ext']['newField'], 'added')
        self.assertEqual(updated['api'], 'https://api.example/vod?sign=new%2B%2F')
        self.assertEqual(current['vod']['sites'][0]['api'], fixture()['sites'][0]['api'])
        again, final_state, report = sync.merge(refreshed, registry(), next_state, [documents(upstream)])
        self.assertEqual(refreshed, again); self.assertEqual(next_state, final_state); self.assertEqual(report['added'], 0)

    def test_deleted_sites_are_tombstoned_and_explicit_restoration_works(self):
        current, state, _ = first(); restored = copy.deepcopy(current['vod']['sites'][0]); current['vod']['sites'].clear()
        for _ in range(3):
            current, state, report = sync.merge(current, registry(), state, [documents()])
            self.assertEqual(current['vod']['sites'], []); self.assertEqual(report['keptDeleted'], 1)
        current['vod']['sites'].append(restored)
        current, state, report = sync.merge(current, registry(), state, [documents()])
        self.assertEqual(len(current['vod']['sites']), 1); self.assertEqual(state['deleted'], [])

    def test_local_entries_and_upstream_disappearances_are_retained(self):
        current, state, _ = first()
        own = {'key': 'own', 'name': '自己加的', 'type': 1, 'api': 'https://own.example/api'}
        current['vod']['sites'].append(own)
        current, _, report = sync.merge(current, registry(), state, [])
        self.assertEqual(len(current['vod']['sites']), 2); self.assertEqual(current['vod']['sites'][1], own)
        self.assertEqual(report['retainedMissing'], 1)

    def test_new_sites_are_enabled_and_retain_upstream_non_searchable_flags(self):
        upstream = fixture(); upstream['sites'][0]['searchable'] = 0
        output, _, _ = first(upstream)
        self.assertTrue(output['vod']['sites'][0]['enabled']); self.assertEqual(output['vod']['sites'][0]['searchable'], 0)
        reg = registry(); reg['newSitesEnabled'] = False
        output, _, _ = sync.merge(library(), reg, None, [documents()])
        self.assertFalse(output['vod']['sites'][0]['enabled'])

    def test_scoped_keys_keep_independent_plugins_and_parser_definitions(self):
        source = {**registry()['sources'][0], 'id': 'second', 'url': 'https://second.example/box.json'}
        alternative = fixture(); alternative['spider'] = './different.jar'; alternative['parses'][0]['url'] = './different?url='
        output, _, _ = sync.merge(library(), registry(), None, [documents(), documents(alternative, source)])
        self.assertEqual(len(output['vod']['sites']), 2)
        self.assertEqual(output['vod']['sites'][0]['key'], output['vod']['sites'][1]['key'])
        bundles = sync.config.bundles(output['vod']); self.assertEqual(len(bundles), 2)
        self.assertEqual(len({item['spider'] for item in bundles.values()}), 2)
        self.assertEqual(len({item['parses'][0]['url'] for item in bundles.values()}), 2)
        self.assertTrue(all('origin' not in item['sites'][0] and '_syncId' not in item['sites'][0] for item in bundles.values()))

    def test_duplicate_and_invalid_sites_are_reported_without_breaking_valid_sites(self):
        upstream = fixture(); upstream['sites'] += [copy.deepcopy(upstream['sites'][0]), {'key': 'bad', 'api': 'file:///private'}]
        result = documents(upstream)
        self.assertEqual(len(result['documents'][0]['sites']), 1); self.assertEqual(len(result['rejected']), 2)

    def test_failed_sources_keep_working_sites_and_report_failure(self):
        current, state, _ = first()
        failed = sync.expand(registry()['sources'][0], lambda row: (_ for _ in ()).throw(OSError('offline')))
        output, _, report = sync.merge(current, registry(), state, [failed])
        self.assertEqual(output, current); self.assertFalse(report['complete'])

    def test_bad_dependency_document_does_not_block_other_sources(self):
        bad = fixture(); bad['parses'] = 'not-an-array'
        failed = documents(bad); self.assertEqual(failed['documents'], []); self.assertTrue(failed['failed'])
        other = {**registry()['sources'][0], 'id': 'healthy'}
        output, _, report = sync.merge(library(), registry(), None, [failed, documents(source=other)])
        self.assertEqual(len(output['vod']['sites']), 1); self.assertEqual(output['vod']['sites'][0]['context'], 'healthy')

    def test_bootstrap_dry_run_and_full_failure_do_not_mutate_maintained_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'data').mkdir(); path = root / 'data/library.json'
            original = library(); original['warehouses'] = [{'name': '上游', 'url': 'https://up.example/box/main.json', 'enabled': True}]
            path.write_text(json.dumps(sync.config.manifest(original), ensure_ascii=False)); sync.write_json(root / 'data/vod-sites.json', sync.config.site_list(original))
            with patch.object(sync, 'expand', return_value=documents()):
                self.assertEqual(sync.main(['--root', str(root), '--bootstrap-from-warehouses', '--dry-run', '--preview-dir', str(root / 'preview'), '--report', str(root / 'report.json')]), 0)
            preview = json.loads((root / 'preview/library.json').read_text())
            self.assertEqual(preview['warehouses'], []); self.assertTrue(json.loads((root / 'preview/vod-sites.json').read_text())['sites'])
            self.assertEqual(json.loads(path.read_text()), sync.config.manifest(original)); self.assertFalse((root / 'data/vod-sync-state.json').exists())
            failed = {'id': 'upstream', 'name': 'failed', 'documents': [], 'failed': [{'reason': 'offline'}], 'rejected': []}
            with patch.object(sync, 'expand', return_value=failed):
                self.assertEqual(sync.main(['--root', str(root), '--bootstrap-from-warehouses', '--report', str(root / 'report.json')]), 1)
            self.assertEqual(json.loads(path.read_text()), sync.config.manifest(original))

    def test_owner_changes_during_fetch_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'data').mkdir(); path = root / 'data/library.json'
            original = library(); path.write_text(json.dumps(sync.config.manifest(original))); sync.write_json(root / 'data/vod-sites.json', sync.config.site_list(original))
            (root / 'data/vod-sources.json').write_text(json.dumps(registry()))
            fetched = documents()
            def fetch(_):
                changed = copy.deepcopy(original); changed['name'] = '正在编辑'; path.write_text(json.dumps(sync.config.manifest(changed))); return fetched
            with patch.object(sync, 'expand', side_effect=fetch), self.assertRaisesRegex(ValueError, '抓取期间清单被修改'):
                sync.main(['--root', str(root), '--report', str(root / 'report.json')])
            self.assertEqual(json.loads(path.read_text())['name'], '正在编辑')

    def test_interrupted_state_write_recovers_without_freezing_later_upstream_updates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); before = sync.config.site_list(library()); expanded, state, _ = first(); output = sync.config.site_list(expanded)
            sync.write_json(root / 'data/vod-sites.json', before)
            original_write = sync.write_json
            def interrupted(path, value):
                if path.name == 'vod-sync-state.json': raise OSError('interrupted')
                return original_write(path, value)
            with patch.object(sync, 'write_json', side_effect=interrupted), self.assertRaises(OSError):
                sync.save_pair(root, before, output, None, state)
            self.assertEqual(sync.read_json(root / 'data/vod-sites.json'), output)
            self.assertFalse((root / 'data/vod-sync-state.json').exists())
            with self.assertRaisesRegex(ValueError, '未完成同步'): sync.recover(root, dry_run=True)
            sync.recover(root)
            self.assertEqual(sync.read_json(root / 'data/vod-sync-state.json'), state)
            self.assertFalse((root / '.tools/vod-sync-pending.json').exists())

    def test_interrupted_update_does_not_overwrite_subsequent_owner_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); before = sync.config.site_list(library()); expanded, state, _ = first(); output = sync.config.site_list(expanded)
            sync.write_json(root / '.tools/vod-sync-pending.json', {'version': 1, 'files': {
                'vod-sites.json': {'before': before, 'after': output}, 'vod-sync-state.json': {'before': None, 'after': state}}})
            edited = copy.deepcopy(output); edited['sites'][0]['name'] = '中断后修改'; sync.write_json(root / 'data/vod-sites.json', edited)
            with self.assertRaisesRegex(ValueError, '手动编辑'): sync.recover(root)
            self.assertEqual(sync.read_json(root / 'data/vod-sites.json'), edited)

    def test_concurrent_sync_cannot_write_the_same_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with sync.sync_lock(root), self.assertRaisesRegex(ValueError, '另一个点播同步'):
                with sync.sync_lock(root): pass


if __name__ == '__main__':
    unittest.main()
