#!/usr/bin/env python3
"""Publish only validated generated files to source-data, without touching the real index."""
import argparse
import copy
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def run(*args, env=None, data=None):
    return subprocess.run(['git', *args], env=env, input=data, cwd=env.get('GIT_WORK_TREE') if env else None,
                          text=True, check=True, capture_output=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--remote', default='origin')
    parser.add_argument('--branch', default='source-data')
    args = parser.parse_args()
    directory = args.directory.resolve()
    expected = {'index.html', 'assets/style.css', 'assets/editor.js', 'data/library.json', 'data/live.m3u', 'data/vod-sites.json', '.nojekyll',
                'box.json', 'vod.json', 'live.json', 'live.m3u', 'live.txt', 'warehouse.json', 'manifest.json', 'hosting.json'}
    try:
        entries = json.loads((directory / 'warehouse.json').read_text(encoding='utf-8'))['urls']
        hosting = json.loads((directory / 'hosting.json').read_text(encoding='utf-8'))
        sites = json.loads((directory / 'data/vod-sites.json').read_text(encoding='utf-8'))
        library = json.loads((directory / 'data/library.json').read_text(encoding='utf-8'))
        if hosting.get('vodSiteFile') != 'data/vod-sites.json' or sites.get('version') != 1 or not isinstance(sites.get('sites'), list) or set(library.get('vod', {})) != {'name', 'url'}:
            raise ValueError('Invalid standalone VOD site list')
        modules = hosting.get('modules')
        module_names = {'television': '简视直播', 'entertainment': '简视娱乐', 'vod': '简视点播', 'sports': '简视体育'}
        if not isinstance(modules, list) or len(modules) != len(module_names):
            raise ValueError('Missing module subscriptions')
        own_urls = {endpoint['base'] + 'data/live.m3u' for endpoint in hosting['endpoints']}
        for link, (module, name) in zip(modules, module_names.items()):
            path = 'data/modules/' + module + '.json'
            if link != {'module': module, 'name': name, 'path': path}:
                raise ValueError('Invalid module subscription path or identity')
            document = {'version': 1, 'name': name, 'module': module}
            if module in {'television', 'entertainment'}:
                playlist_path = 'data/modules/' + module + '.m3u'
                document['live'] = copy.deepcopy(library['live'])
                for playlist in document['live']['playlists']:
                    if playlist['url'] in own_urls:
                        playlist['url'] = playlist['url'][:-len('data/live.m3u')] + playlist_path
                if not (directory / playlist_path).read_text(encoding='utf-8').startswith('#EXTM3U\n'):
                    raise ValueError('Invalid module live playlist')
                expected.add(playlist_path)
            elif module == 'vod':
                document['vod'] = library['vod']
                document['warehouses'] = library['warehouses']
            if json.loads((directory / path).read_text(encoding='utf-8')) != document:
                raise ValueError('Module subscription differs from the maintained library')
            expected.add(path)
        for item in hosting.get('vodContexts', []):
            path = item.get('path', '')
            if not re.fullmatch(r'vod/[A-Za-z0-9_-]+\.json', path):
                raise ValueError('Invalid managed VOD configuration path')
            config = json.loads((directory / path).read_text(encoding='utf-8'))
            if not isinstance(config.get('sites'), list) or len(config['sites']) != item.get('count') or any(key in config for key in ('lives', 'urls')):
                raise ValueError('Invalid managed VOD configuration')
            expected.add(path)
        links = hosting.get('warehouseGroups', [])
        if 'liveSources' in hosting:
            if hosting['liveSources'] != 'data/live-sources.json':
                raise ValueError('Invalid live source registry path')
            registry = json.loads((directory / 'data/live-sources.json').read_text(encoding='utf-8'))
            if registry.get('version') != 1 or registry.get('playlist') != 'data/live.m3u' or not isinstance(registry.get('sources'), list):
                raise ValueError('Invalid live source registry')
            expected.add('data/live-sources.json')
        if not isinstance(entries, list) or not isinstance(links, list):
            raise ValueError('Invalid warehouse manifest')
        count = (len(entries) + 5) // 6 if len(entries) > 6 else 0
        if len(links) != count:
            raise ValueError('Missing warehouse groups')
        for index, link in enumerate(links):
            path = 'warehouse-' + str(index + 1) + '.json'
            chunk = entries[index * 6:(index + 1) * 6]
            if link.get('path') != path or link.get('count') != len(chunk):
                raise ValueError('Invalid warehouse group name or size')
            if json.loads((directory / path).read_text(encoding='utf-8')) != {'urls': chunk}:
                raise ValueError('Warehouse group differs from the public list')
            expected.add(path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.error(str(error))
    files = sorted(p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file())
    if set(files) != expected or any(p.is_symlink() for p in directory.rglob('*')):
        parser.error('Public directory does not match the generated-file allowlist')
    ref = 'refs/heads/' + args.branch
    run('check-ref-format', ref)
    head = run('ls-remote', '--heads', args.remote, ref).split()
    parent = head[0] if head else None
    if parent:
        run('fetch', '--no-tags', args.remote, ref)
    with tempfile.TemporaryDirectory(prefix='juan-source-index-') as temp:
        env = os.environ.copy(); env['GIT_INDEX_FILE'] = str(Path(temp) / 'index')
        env['GIT_DIR'] = run('rev-parse', '--absolute-git-dir')
        env['GIT_WORK_TREE'] = str(directory)
        run('read-tree', '--empty', env=env)
        run('add', '--', *files, env=env)
        tree = run('write-tree', env=env)
        if parent and tree == run('rev-parse', parent + '^{tree}'):
            print('Public source data is unchanged'); return
        env.setdefault('GIT_AUTHOR_NAME', 'github-actions[bot]')
        env.setdefault('GIT_AUTHOR_EMAIL', '41898282+github-actions[bot]@users.noreply.github.com')
        env.setdefault('GIT_COMMITTER_NAME', env['GIT_AUTHOR_NAME'])
        env.setdefault('GIT_COMMITTER_EMAIL', env['GIT_AUTHOR_EMAIL'])
        commit = run('commit-tree', tree, *(['-p', parent] if parent else []), env=env,
                     data='Publish personal source metadata\n')
        # A concurrent update causes a safe non-fast-forward rejection; never force-push.
        run('push', args.remote, commit + ':' + ref)
        print('Published source data: ' + commit)


if __name__ == '__main__':
    main()
