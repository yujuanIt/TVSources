"""Read 88zhibo's public schedules/line API without executing remote JavaScript.

Publish stable /live/<id>/play entries for the Android resolver, never expiring CDN
tickets. A new entry must pass both an HLS playlist and a media-prefix check.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from html.parser import HTMLParser
import ipaddress
import json
import re
import ssl
import time
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = 'https://www.88zhibo.tv'
UA = 'Mozilla/5.0'
ZONE = ZoneInfo('Asia/Shanghai')
PAGES = {'channels': BASE + '/match/21/live', 'NBA': BASE + '/match/1/live', 'CBA': BASE + '/match/2/live'}
WRAPPER = 'https://cloud.yumixiu768.com/player/pap.html'


def public_http(value):
    try:
        u = urlsplit(value)
        if u.scheme not in {'http', 'https'} or not u.hostname or u.username or u.password or u.port not in {None, 80, 443}:
            return False
        host = u.hostname.lower()
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def media(value):
    return public_http(value) and bool(re.search(r'\.(?:m3u8|mpd|flv|ts)$', urlsplit(value).path, re.I))


def decode_lines(payload):
    body = json.loads(payload)
    encoded = body.get('data') if isinstance(body, dict) else None
    if not isinstance(encoded, str) or len(encoded) < 12 or len(encoded) > 256 * 1024:
        raise ValueError('88直播线路响应格式变化')
    body = json.loads(base64.b64decode(encoded[6:-2], validate=True).decode('utf-8'))
    if not isinstance(body, dict) or 'links' not in body:
        raise ValueError('88直播缺少线路字段')
    links = body['links']
    if links is None:
        return []
    if not isinstance(links, list) or len(links) > 64:
        raise ValueError('88直播线路数量无效')
    result = []
    for line in links:
        if not isinstance(line, dict) or line.get('shareLock', 0) not in (None, False, 0, '0'):
            continue  # Never follow a link requiring a share/payment/unlock action.
        if not isinstance(line.get('url'), str):
            continue
        value = line['url'].strip()
        headers = {'User-Agent': UA, 'Referer': BASE + '/'}
        u = urlsplit(value)
        if u.scheme == 'https' and u.netloc == 'cloud.yumixiu768.com' and u.path == '/player/pap.html':
            try:
                encoded = parse_qs(u.query, strict_parsing=True).get('id', [''])[0]
                if not encoded or len(encoded) > 16384:
                    continue
                value = base64.b64decode(base64.b64decode(encoded, validate=True)[::-1], validate=True).decode('utf-8')[::-1]
            except (ValueError, UnicodeError):
                continue
            headers = {'User-Agent': UA, 'Referer': 'https://cloud.yumixiu768.com/', 'Origin': 'https://cloud.yumixiu768.com'}
        if media(value) and (value, headers) not in result:
            result.append((value, headers))
    return result


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def all(self, tag=None, cls=None):
        for node in self.children:
            if isinstance(node, Node):
                if (tag is None or node.tag == tag) and (cls is None or cls in node.attrs.get('class', '').split()):
                    yield node
                yield from node.all(tag, cls)

    def text(self):
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children).strip()


class ScheduleParser(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.stack = [self.root]; self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 30000 or len(self.stack) > 128:
            raise ValueError('88直播页面结构过大')
        node = Node(tag, attrs); self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]; break

    def handle_data(self, value):
        self.stack[-1].children.append(value)


def schedule(payload, kind, now):
    if kind not in PAGES:
        raise ValueError('仅支持体育频道、NBA、CBA')
    tree = ScheduleParser(); tree.feed(payload.decode('utf-8-sig'))
    if not list(tree.root.all('ul', 'list-group')):
        raise ValueError('88直播赛程页面结构变化')
    result, day, seen = [], None, set()
    for item in tree.root.all('li'):
        classes = item.attrs.get('class', '').split()
        if 'live-list-group-time' in classes:
            match = re.search(r'\b(20\d\d-\d\d-\d\d)\b', item.text())
            day = match[1] if match else None
        if 'group-game-item' not in classes:
            continue
        links = [a.attrs.get('href', '') for a in item.all('a')]
        entry = next((urljoin(BASE, value) for value in links if re.fullmatch(r'/live/[1-9]\d{0,8}/play', value)), None)
        if not entry or entry in seen:
            continue
        labels = list(item.all(cls='game-type'))
        teams = [re.sub(r'\s+', ' ', el.text()).strip() for el in item.all(cls='team-name')]
        label = labels[0].text() if labels else ''
        start = None
        if kind == 'channels':
            if not label:
                continue
            name, group = label, '体育'
        else:
            if not label.upper().startswith(kind) or len(teams) < 2:
                continue
            times = list(item.all(cls='category-game-time'))
            stamp = re.search(r'\b(\d{2}:\d{2})\b', times[0].text()) if times else None
            if not day or not stamp:
                raise ValueError('88直播赛事缺少开赛时间')
            start = datetime.fromisoformat(day + 'T' + stamp[1]).replace(tzinfo=ZONE)
            if not now - timedelta(hours=6) < start <= now + timedelta(hours=36):
                continue
            # Do not show a replay/result entry as a current live event.
            if any(word in item.text() for word in ('已结束', '已完赛', '比赛结束')):
                continue
            name, group = start.strftime('%m-%d %H:%M') + ' ' + teams[0] + ' vs ' + teams[1], kind + '赛事'
        images = [urljoin(BASE, img.attrs.get('data-src', img.attrs.get('src', '')).strip()) for img in item.all('img')]
        logo = next((url for url in images if public_http(url) and '/static/img/default' not in urlsplit(url).path), '')
        result.append({'url': entry, 'name': name, 'group': group, 'logo': logo, 'start': start})
        seen.add(entry)
        if len(result) > 64:
            raise ValueError('88直播候选频道过多')
    return result


def get(url, headers, limit, prefix=False):
    if not public_http(url):
        raise ValueError('不是公开 HTTP 播放地址')
    began = time.monotonic()
    request_headers = {'User-Agent': UA, 'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache', **headers}
    if prefix:
        request_headers['Range'] = 'bytes=0-' + str(limit - 1)
    with urlopen(Request(url, headers=request_headers), timeout=8, context=ssl.create_default_context()) as response:
        if not public_http(response.geturl()):
            raise ValueError('无效的播放重定向')
        if prefix:
            return response.read(limit)
        chunks, size = [], 0
        while True:
            if time.monotonic() - began > 16:
                raise ValueError('88直播读取超时')
            chunk = response.read1(min(65536, limit + 1 - size))
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk); size += len(chunk)
            if size > limit:
                raise ValueError('88直播响应过大')


def playable(url, headers, fetcher=get, depth=0):
    # Currently ingest only verified HLS. Other link types are left out of the
    # published list until there is a matching playback validation strategy.
    if depth > 2 or not media(url) or not urlsplit(url).path.lower().endswith('.m3u8'):
        return False
    body = fetcher(url, headers, 256 * 1024).decode('utf-8-sig')
    if not body.lstrip().startswith('#EXTM3U') or '#EXT-X-ENDLIST' in body:
        return False
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if any(line.startswith('#EXT-X-KEY:') and 'METHOD=NONE' not in line for line in lines):
        return False
    address = next((urljoin(url, line) for line in lines if not line.startswith('#')), None)
    if not address or not public_http(address):
        return False
    if any(line.startswith('#EXT-X-STREAM-INF:') for line in lines):
        return playable(address, headers, fetcher, depth + 1)
    if not any(line.startswith('#EXTINF:') for line in lines):
        return False
    prefix = fetcher(address, headers, 8192, prefix=True)
    return (len(prefix) > 188 and prefix[0] == 0x47 and prefix[188] == 0x47
            or len(prefix) >= 12 and prefix[4:8] in (b'ftyp', b'moof', b'styp'))


def escape(value):
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ').replace('\r', ' ')


def fetch_playlist(source, fetcher=get, now=None, verifier=playable):
    kind = source['kind']
    if source['url'] != PAGES.get(kind):
        raise ValueError('88直播赛程地址无效')
    candidates = schedule(fetcher(source['url'], {}, 2 * 1024 * 1024), kind, now or datetime.now(ZONE))

    def check(item):
        page = item['url']
        # An API/JSON failure fails the whole snapshot, protecting existing events.
        lines = decode_lines(fetcher(page[:-4] + 'source', {'Referer': page}, 256 * 1024))
        for address, headers in lines:
            try:
                if verifier(address, headers, fetcher):
                    return item
            except (OSError, ValueError, UnicodeError):
                continue
        return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        verified = [row for row in pool.map(check, candidates) if row is not None]
    if kind == 'channels' and not verified:
        raise ValueError('88直播未取得可验证的体育频道')
    result = ['#EXTM3U']
    for item in verified:
        game_id = urlsplit(item['url']).path.split('/')[2]
        attrs = {'tvg-id': '88zhibo-' + game_id, 'tvg-logo': item['logo'], 'group-title': item['group']}
        if item['start']:
            attrs['x-event-start'] = item['start'].isoformat()
        name = item['name'].replace('\r', ' ').replace('\n', ' ')
        result.append('#EXTINF:-1 ' + ' '.join(key + '="' + escape(value) + '"' for key, value in attrs.items()) + ',' + name)
        result.append(item['url'])
    return ('\n'.join(result) + '\n').encode('utf-8')
