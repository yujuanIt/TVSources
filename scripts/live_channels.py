"""Conservative display grouping for simulcast CCTV and provincial satellite routes."""
import copy
import re
import unicodedata

SATELLITES = ['北京', '东方', '天津', '重庆', '黑龙江', '吉林', '辽宁', '内蒙古', '宁夏', '甘肃', '青海', '陕西', '山西', '河北', '河南',
              '山东', '湖北', '湖南', '江西', '浙江', '江苏', '安徽', '东南', '广东', '深圳', '广西', '贵州', '云南', '四川', '西藏', '新疆', '兵团', '海南', '三沙']
CCTV_NAMES = {1: '综合', 2: '财经', 3: '综艺', 4: '中文国际', 5: '体育', 6: '电影', 7: '国防军事', 8: '电视剧', 9: '纪录', 10: '科教',
              11: '戏曲', 12: '社会与法', 13: '新闻', 14: '少儿', 15: '音乐', 16: '奥林匹克', 17: '农业农村'}
ROOM_GROUPS = {'抖音', 'DOUYIN', '快手', 'KUAISHOU', '虎牙', 'HUYA', '斗鱼', 'DOUYU',
               'B站', '哔哩哔哩', 'BILIBILI', 'TWITCH', 'SOOP', 'YY', 'TIKTOK', 'YOUTUBE'}
ROOM_GROUP_SUFFIXES = ('直播', '直播间', '平台', '直播平台', '频道', '直播频道', '直播源')
ROOM_GROUP_SEPARATORS = '·•:/|-_—–'


def is_platform_group(raw):
    """Match Android LiveModule using the original group, never a title or playback URL."""
    normalized = unicodedata.normalize('NFKC', raw or '').upper()
    normalized = ''.join(character for character in normalized if not character.isspace())
    normalized = normalized.translate(str.maketrans('鬥魚嗶頻間臺', '斗鱼哔频间台'))
    boundary = next((index for index, character in enumerate(normalized) if character in ROOM_GROUP_SEPARATORS), len(normalized))
    platform = normalized[:boundary]
    return platform in ROOM_GROUPS or any(platform.endswith(suffix) and platform[:-len(suffix)] in ROOM_GROUPS for suffix in ROOM_GROUP_SUFFIXES)


def title(name):
    text = unicodedata.normalize('NFKC', name).strip()
    compact = re.sub(r'\s+', '', text).upper()
    for theatre in ('风云剧场', '第一剧场', '怀旧剧场'):
        if compact in {theatre, 'CCTV' + theatre, 'CCTV·' + theatre}:
            return ('央视', 'CCTV · ' + theatre)
    cctv = re.match(r'^(?:CCTV|央视|中央)[-—]?(\d{1,2})(?!\d)(\+|PLUS)?', compact)
    if cctv:
        number, plus = int(cctv[1]), bool(cctv[2]); tail = compact[cctv.end():]
        if tail.startswith('K') and number in (4, 8): return ('央视', 'CCTV-' + str(number) + 'K 超高清')
        if number in CCTV_NAMES and (not plus or number == 5):
            variant = '欧洲' if re.search(r'欧洲|欧版|EUROPE', tail) else '美洲' if re.search(r'美洲|美版|AMERICA', tail) else ''
            if number == 5 and '体育赛事' in tail: plus = True
            return ('央视', f"CCTV-{number}{'+' if plus else ''} " + ('体育赛事' if plus and number == 5 else CCTV_NAMES[number]) + (' · ' + variant if variant else ''))
    # Do not merge overseas/international variants into the domestic satellite channel.
    if re.search(r'国际|海外|美洲|欧洲', text): return None
    aliases = {'上海卫视': '东方卫视', '福建卫视': '东南卫视', '旅游卫视': '海南卫视', '海南旅游卫视': '海南卫视'}
    for alias, canonical in aliases.items():
        if compact.startswith(alias): return ('地方卫视', canonical)
    for province in SATELLITES:
        if compact.startswith(province + '卫视'): return ('地方卫视', province + '卫视')
    return None


def public_channels(rows, source_registry=None):
    """Keep route-specific headers/options while sharing channel metadata in all public outputs."""
    active = [copy.deepcopy(row) for row in rows if row.get('enabled', True)]
    for row in active:
        canonical = title(row['name'])
        if canonical:
            row['group'], row['name'] = canonical
    representatives = {}
    for row in active:
        key = (row['group'], row['name'])
        if key not in representatives: representatives[key] = row
        elif not representatives[key].get('logo') and row.get('logo'): representatives[key]['logo'] = row['logo']
    for row in active:
        first = representatives[(row['group'], row['name'])]
        row['logo'] = first.get('logo', ''); row['tvgId'] = first.get('tvgId', '')
    order = (source_registry or {}).get('mergePolicy', {}).get('sourceOrder', [])
    rank = {key: index for index, key in enumerate(order)}
    def priority(row):
        origins = {key for keys in row.get('origins', {}).values() for key in keys}
        return min((rank.get(key, len(order)) for key in origins), default=len(order))
    # Stable ordering within each logical channel: configured source priority, then original order.
    groups = {}
    for row in active: groups.setdefault((row['group'], row['name']), []).append(row)
    return [row for group in groups.values() for row in sorted(group, key=priority)]
