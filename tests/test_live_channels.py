import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import live_channels


def channel(name, address, origin='old', group='央视', **extra):
    return dict(name=name, group=group, urls=[address], origins={address: [origin]}, **extra)


class LiveChannelTests(unittest.TestCase):
    def test_module_classifier_matches_explicit_platform_groups_without_title_or_domain_guesses(self):
        for group in ['抖音', ' Douyin ', '快手直播', '虎牙 · 游戏', 'Huya/户外', '鬥魚直播間',
                      'Ｂ站', '嗶哩嗶哩頻道', 'bilibili_音乐', 'Twitch-游戏', 'SOOP直播平台',
                      'YY直播源', 'TikTok', 'YouTube | 音乐']:
            with self.subTest(group=group):
                self.assertTrue(live_channels.is_platform_group(group))
        for group in [None, '', '未分组', '央视', '卫视', '港澳台', '地方', '体育', 'NBA赛事',
                      'CBA赛事', '影视', '游戏', '其他', 'YYDS', '虎牙新闻台', 'B站精选影视', '我的Twitch频道']:
            with self.subTest(group=group):
                self.assertFalse(live_channels.is_platform_group(group))

    def test_aliases_and_quality_names_form_one_channel_but_distinct_programs_stay_separate(self):
        for name in ['CCTV1', 'CCTV-1 综合 HD', 'ＣＣＴＶ１高清', '央视1套 Relay', '中央1台']:
            self.assertEqual(('央视', 'CCTV-1 综合'), live_channels.title(name))
        self.assertEqual(('央视', 'CCTV-5 体育'), live_channels.title('CCTV5高清'))
        self.assertEqual(('央视', 'CCTV-5+ 体育赛事'), live_channels.title('CCTV5体育赛事'))
        self.assertEqual(('央视', 'CCTV-5+ 体育赛事'), live_channels.title('CCTV5PLUS HD'))
        self.assertEqual(('央视', 'CCTV-4 中文国际 · 欧洲'), live_channels.title('CCTV4欧洲'))
        self.assertNotEqual(live_channels.title('CCTV4美洲'), live_channels.title('CCTV4亚洲'))
        self.assertEqual(('央视', 'CCTV-4K 超高清'), live_channels.title('CCTV4K'))
        self.assertNotEqual(live_channels.title('CCTV8K'), live_channels.title('CCTV8'))
        self.assertIsNone(live_channels.title('CCTV13+'))
        self.assertIsNone(live_channels.title('CCTV123'))
        self.assertEqual(live_channels.title('风云剧场'), live_channels.title('CCTV风云剧场'))
        self.assertNotEqual(live_channels.title('风云剧场'), live_channels.title('第一剧场'))
        self.assertEqual(('地方卫视', '东方卫视'), live_channels.title('上海卫视高清'))
        self.assertEqual(('地方卫视', '东南卫视'), live_channels.title('福建卫视-HD'))
        self.assertIsNone(live_channels.title('湖南卫视国际'))
        self.assertIsNone(live_channels.title('我的频道'))

    def test_public_routes_prioritize_official_keep_headers_signatures_options_and_source_metadata(self):
        rows = [channel('CCTV1高清', 'https://relay.test/a?token=a%2Bb', headers={'Cookie': 'private-route'}, directives=['#KODIPROP:keep=yes']),
                channel('CCTV-1 综合', 'https://www.yangshipin.cn/tv/home?pid=600001859&cnlid=2024078201', 'official', group='卫视', logo='https://img.test/one.png'),
                channel('CCTV1 Relay', 'https://relay.test/a?token=a%2Bb', headers={'Cookie': 'other-route'}),
                channel('央视一套（我改的名）', 'https://local.test/a'),
                channel('CCTV1停用', 'https://hidden.test/a', enabled=False)]
        original = copy.deepcopy(rows)
        out = live_channels.public_channels(rows, {'mergePolicy': {'sourceOrder': ['official', 'old']}})
        self.assertEqual(original, rows)
        self.assertEqual(4, len(out))
        self.assertEqual(['CCTV-1 综合'] * 3, [row['name'] for row in out[:3]])
        self.assertEqual(rows[1]['urls'], out[0]['urls'])
        self.assertEqual({'Cookie': 'private-route'}, out[1]['headers'])
        self.assertEqual({'Cookie': 'other-route'}, out[2]['headers'])
        self.assertEqual(['#KODIPROP:keep=yes'], out[1]['directives'])
        self.assertEqual('https://relay.test/a?token=a%2Bb', out[1]['urls'][0])
        self.assertEqual(rows[0]['origins'], out[1]['origins'])
        self.assertTrue(all(row['logo'] == rows[1]['logo'] for row in out[:3]))
        self.assertEqual('央视一套（我改的名）', out[3]['name'])

    def test_platform_rooms_keep_their_original_group_and_title_even_when_named_after_tv_channels(self):
        rows = [channel('CCTV1高清', 'https://room.test/cctv', group='虎牙 · 体育',
                        logo='https://img.test/room.png', tvgId='room-1',
                        headers={'Cookie': 'room=a%2Fb'}, directives=['#KODIPROP:room=yes']),
                channel('上海卫视HD', 'https://room.test/satellite', group='鬥魚直播間', logo='', tvgId='room-2'),
                channel('CCTV1高清', 'https://tv.test/cctv', group='其他')]
        before = copy.deepcopy(rows)
        out = live_channels.public_channels(rows)
        self.assertEqual(before, rows)
        self.assertEqual(rows[:2], out[:2])
        self.assertEqual(('央视', 'CCTV-1 综合'), (out[2]['group'], out[2]['name']))


if __name__ == '__main__':
    unittest.main()
