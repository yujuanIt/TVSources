# 居安的源站

网站：[居安源站](https://yujuanit.github.io/TVSources/)。已按用户要求同步 App 默认源地址，之后可以自行添加、改名、停用或删除；只维护配置和播放地址，没有复制影片文件。

当前维护 2 个直接点播接口（非凡、360）、6 份完整 TVBox 配置（饭太硬、心魔、Clun、FongMI、香雅情、肥猫）和自己的 M3U 直播订阅。`live.playlists` 只保留「居安直播 · 我的 M3U」。同步程序按 [data/live-sources.json](data/live-sources.json) 登记的上游每 6 小时更新 `data/live.m3u`，保留本地名称、分组和来源备注，校验后自动发布到源站；频道总数以网页总览和工作流摘要为准。

## 直播分组

自己的 M3U 按以下顺序分组：「央视、地方卫视、抖音、虎牙、B站、斗鱼、港澳台、体育、影视、少儿、音乐、游戏、综合频道、Twitch、SOOP、YY、公告」。央视常规频道按频道号排列，地方卫视中的卫视频道排在地方频道前；各平台的游戏、娱乐和其他直播统一放在相应平台组，赛事直播也按所属平台归类。港澳台频道集中到一组。

原 105 个分组合并为 17 个，IPv4 / IPv6、各省及平台内容子分类不再单独成组。2026-10-15 整理时全部频道和 2,917 条线路保留，台标、EPG 标识、播放请求头、签名参数与播放器选项未改动。频道条目从 1,894 合并为 1,825，是分组统一后同一频道的线路归并，并未筛掉频道。公告和上游更新时间也保留在最后一组。整理前的完整清单可从 [9356a29 版本](https://github.com/yujuanIt/TVSources/blob/9356a29559fcb2fe04f3e884f6e445f6f8237216/data/live.m3u) 查看或恢复。

此分组调整作用于自己的 `data/live.m3u` 及其 M3U / TXT / JSON 输出，上游列表仅登记为来源依赖，不再重复作为默认独立直播订阅。完整点播 TVBox 配置仍保留上游自己的原始内容。

自建 M3U 的频道显示名、`tvg-name` 与分组显示使用简体中文。2026-10-15 将 199 个频道条目的繁体名称转为简体，仍保留 1,825 个频道、17 个分组和 2,917 条线路。`tvg-id` 保留原始 EPG 标识，台标地址、播放地址、请求头与播放器选项不随文字转换修改。

## 固定订阅地址

电视中「设置 → 源管理 → 添加源地址」依次添加下方两个多仓分组，可接入全部来源。每组最多 6 份配置，兼容现有 App 的单次导入上限；第一组已包含综合源，添加完两组后无需重复添加综合源。

| 用途 | 免费加速入口 |
| --- | --- |
| 综合源 | [box.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/box.json) |
| 点播配置 | [vod.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/vod.json) |
| 全部来源 · 多仓分组 1 | [warehouse-1.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse-1.json) |
| 全部来源 · 多仓分组 2 | [warehouse-2.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse-2.json) |
| 自建频道 TXT | [live.txt](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.txt) |
| 自建频道 M3U | [live.m3u](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/data/live.m3u) |
| 自建频道 JSON，保留完整请求头 | [live.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.json) |
| 完整多仓索引，客户端可能限制一次导入数量 | [warehouse.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse.json) |

原址备用：[综合源](https://yujuanit.github.io/TVSources/box.json)、[点播](https://yujuanit.github.io/TVSources/vod.json)、[直播 TXT](https://yujuanit.github.io/TVSources/live.txt)、[直播 M3U](https://yujuanit.github.io/TVSources/data/live.m3u)。网站总览提供 GHFast 与 GitHub Raw 的备用入口，切换下拉框后复制即可。

综合源默认通过免费加速链接引用自己的 [data/live.m3u](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/data/live.m3u)。频道内容在仓库 [data/live.m3u](https://github.com/yujuanIt/TVSources/blob/main/data/live.m3u) 维护，订阅名称与 URL 在 `data/library.json` 的 `live.playlists` 中维护。网页「复制 M3U 链接」也使用这个加速地址。发布后的 `live.channels` 保持空数组，不再把 M3U 频道重复写成内嵌 JSON；旧 `/live.m3u`、`live.txt`、`live.json` 仍输出兼容内容。

2026-10-15 按用户要求合并以下列表，原有 5 个常看频道保留。首次合并按分组、名称、台标、EPG 标识、请求头和播放选项识别相同频道；相同频道下完全相同的播放地址只保留一次，共去掉 155 条重复线路。不同请求头或播放选项不会混用；当时添加的 IPv4 / IPv6 分组前缀已按上方「直播分组」重新整理。频道地址及签名参数保持原样，两个台标地址中的空格编码为 `%20`。

| 来源 | 读取的频道条目 | 新增频道条目 | 新增播放线路 |
| --- | ---: | ---: | ---: |
| [IPTV IPv4 · 综合](https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u) | 224 | 224 | 473 |
| [IPTV IPv4 · 备用](https://raw.githubusercontent.com/YueChan/Live/refs/heads/main/IPTV.m3u) | 96 | 96 | 96 |
| [电视 · IPTV](https://iptv.yang-1989.xyz/playlist.m3u) | 329 | 329 | 341 |
| [myTV · 港澳](https://iptv.yang-1989.xyz/myTV/playlist.m3u) | 93 | 91 | 91 |
| [体育 · 赛事](https://migu.yang-1989.xyz/playlist.m3u) | 151 | 0 | 0 |
| [IPTV IPv6](https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv6/result.m3u) | 541 | 541 | 1,303 |
| [网络直播](https://live.yang-1989.eu.org/Live.m3u) | 610 | 608 | 608 |

体育列表此次全部包含在电视 IPTV 中，仍保留其频道及线路；[Gather](https://yang-1989.eu.org/Gather.json) 引用的三份列表也均已覆盖，不重复展开。myTV 的 245 条 `KODIPROP` 播放选项保留在 M3U 中，是否能使用这些选项取决于播放器支持；没有新增 DRM 适配或解密逻辑。IPv6 分组需要设备和网络具备 IPv6 连通性。

上表保留首次导入记录；现在的定时程序按下方规则更新已有线路、补充新频道。列表格式校验不等于逐台实际播放验证。

## 直播来源记录与自动同步

[data/live-sources.json](data/live-sources.json) 是机器可读的 `version: 1` 来源清单，也随源站发布为 `/data/live-sources.json`。网页「直播电视 → 查看导入来源」可以查看。它记录原始 URL、稳定 ID、名称、M3U / TVBox lives 格式、请求头、上次导入日期与 SHA-256、合集依赖、原独立订阅开关及后续合并规则；不会作为新的直播列表导入 App。

| ID | 上游 | 同步用途 |
| --- | --- | --- |
| `yang-favorites` | 原常看 `sub/yujuan.m3u` | 保留最初选取的 5 个频道，仅更新这些选择 |
| `guovin-ipv4` | Guovin IPv4 | 综合电视频道 |
| `yuechan-ipv4` | YueChan IPTV | 补充电视线路 |
| `yang-tv` | 电视 IPTV | 电视及赛事线路 |
| `yang-mytv` | myTV | 港澳频道 |
| `yang-sports` | 体育赛事 | 首次已由电视列表覆盖，仍记录共同来源，更新时去重 |
| `guovin-ipv6` | Guovin IPv6 | IPv6 备用线路 |
| `yang-network` | 网络直播 Live | 抖音、虎牙、B站、斗鱼等直播 |
| `yang-gather` | Gather 合集 | 引用电视、网络、myTV；子源已逐项登记，不重复抓取 |

来源按本次合并时保留的原始快照核对，完整 URL、请求头和播放器选项一致才标记；不靠域名猜测。首次归因核对的 2,917 条线路均可追溯，其中 155 条线路在多个上游有相同记录，保留所有匹配来源。来源备注不会追加到频道显示名，不影响简体名称、17 个分组、台标、EPG、原请求头、签名和 KODIPROP / EXTVLCOPT。上游快照只证明导入来源，不代表频道当前一定可播放。

例如同一线路出现在电视与体育两个列表中：

```m3u
#EXTINF:-1 group-title="体育" x-source-id="yang-tv,yang-sports" x-source-name="电视 · IPTV / 体育 · 赛事",体育频道
https://example.com/live.m3u8?original-signature=keep
```

`x-source-id` 用逗号分隔稳定 ID，`x-source-name` 便于人工阅读；M3U 文件头的 `#SOURCE` JSON 注释列出 ID、名称与 URL。生成后的 M3U 保留这些备注，`live.json` 用每个频道的 `origins` 对象按完整线路地址记录来源 ID；TXT 保持普通频道列表格式，不承载来源元数据。

[scripts/sync-live.py](scripts/sync-live.py) 已实现同步。`automaticSyncEnabled: true` 表示开启；只抓取 `sources` 中启用的 M3U，按 `mergePolicy.sourceOrder` 合并。Gather 已展开为子源，不重复请求，原常看列表只同步 `selection.names` 选中的五个频道。来源清单不会重新变成 App 的独立订阅。

- 保留现有频道的名称、分组、台标、EPG、显示开关与自定义属性；新频道用 OpenCC 转成简体，并按上述 17 类归组。已有频道以稳定的 `x-sync-id` 匹配，绑定保存在 [data/live-sync-state.json](data/live-sync-state.json)，不依靠易过期的签名 URL 作为频道 ID。
- 已匹配频道更新完整播放 URL、请求头和 KODIPROP / EXTVLCOPT，签名参数原样保留。来源清单中的请求头作为默认值，频道显式设置的头优先。同 URL 使用不同头或不同顺序的播放选项时分别保留，完全相同的线路归并并保留所有来源备注。
- 每源至多请求两次，单次响应最多 8 MiB，设置网络超时。HTML、空列表、截断 / 非法 M3U 或线路数量低于上次有效值的 50% 均视为异常，该源沿用旧数据；其他正常源仍可更新。全部失败则不修改清单和状态，也不发布。
- 上游暂时删掉的频道、匹配不明确的频道保留待核对；不随一次空响应删台。`x-enabled="false"` 保持隐藏；从文件手工删除已建立绑定的频道后，后续同步不会自动加回来。要恢复可从 Git 历史恢复含原 `x-sync-id` 的频道条目。
- 手工新增且没有来源标记的线路保留。带 `x-source-id` 的线路由对应上游维护；需要独立手工维护某条播放地址时，移除该条的 `x-source-id` / `x-source-name`。修改频道信息时保留 `x-sync-id`，同一频道的各条线路使用相同的显示信息。

[source-pages 工作流](.github/workflows/source-pages.yml) 在北京时间 **04:25、10:25、16:25、22:25** 运行；也可在 [Actions → Publish personal sources](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 点 **Run workflow**，默认先同步再发布。取消勾选 `sync_live` 可只发布本地内容。把来源清单的 `automaticSyncEnabled` 改为 `false` 并提交，可暂停全部抓取；把单个来源的 `enabled` 改为 `false` 可暂停该来源，旧频道保留。调整频率请修改工作流的 `schedule`，来源清单的 `sync` 记录当前安排。

工作流依次同步、测试、生成、提交有变化的 M3U / 状态文件，再在同一运行中更新 `source-data` 与 GitHub Pages；不依赖机器人提交再次触发 push 发布，也不需要个人 Token，符合 [GITHUB_TOKEN 的事件触发行为](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)。没有内容变化时不产生数据提交。并发运行不互相中断；运行期间若有人提交新内容，普通推送会拒绝覆盖远端，留给后续运行重新处理。[GitHub 定时任务](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) 可能延后，并非精确定时服务；仓库长期无活动时应检查 Actions 是否仍启用。

本地试跑（先按下文安装同步依赖）：

```sh
.tools/sync-venv/bin/python scripts/sync-live.py --dry-run --preview-dir .tools/live-preview
.tools/sync-venv/bin/python scripts/sync-live.py
```

第一条只把候选清单和状态放在 `.tools/live-preview/`，不覆盖源文件。第二条写入 `data/live.m3u` 和状态，仍需检查后提交才会上线。抓取结果和失败原因写在 `.tools/live-sync-report.json`；Actions 每次运行的摘要会列出成功、失败保留、新频道和待核对数量。

初始化用原始导入快照核对既有频道，保留全部 1,825 个频道及唯一的播放信息；原来分组归并后产生的 30 条完全相同条目去重，2,887 条唯一线路均保留。此后按实际上游变化更新，初始数量不作为当前总数。

2026-10-16 验证：45 项 Python、14 项 JavaScript 测试及 actionlint 工作流检查通过。8 个启用上游实际读取成功，候选合并为 1,926 个频道条目、3,046 条线路、17 个分组；原有频道的本地显示信息保留。对相同上游快照连续合并两次，M3U 与同步状态完全一致。此项验证针对列表同步与发布，不代表每个直播地址均已实播；未构建 APK。

TXT 使用 `分组名,#genre#` 和 `频道名,播放地址` 格式，备用线路逐行列出。TXT 不包含图标与请求头，需要这些信息时使用 M3U / JSON；综合源默认引用 M3U，额外的播放器选项也保留在 M3U 输出中。

多仓分组随已启用的外部配置数量自动生成，网页总览会列出当前全部分组。删除配置后可能减少分组数，请以网页显示为准。此处同步的是 App 默认地址，没有重新逐条验证所有影片与频道的实际播放。

加速用于公开配置、直播清单和片库脚本，视频仍连接原播放地址，不中转影片。GH-Proxy / GHFast 是公共文件代理，不等同于自有大陆 CDN，不保证所有地区持续可用。2026-10-15 本机抽查 GH-Proxy、GHFast、ghproxy.net 均取得 HTTP 200，JSON 与 GitHub 原文件 SHA-256 一致；jsDelivr 两个域名在本机超时，未选为默认。官方服务与限制见 [GH-Proxy 文档](https://gh-proxy.com/docs/github-accelerator)；各网络的速度与可用性应以自己的电视为准。

## 填写与发布

维护直播频道时，只改项目 data 目录的 [live.m3u](https://github.com/yujuanIt/TVSources/edit/main/data/live.m3u)。外部直播订阅和点播接口在 [data/library.json](https://github.com/yujuanIt/TVSources/edit/main/data/library.json) 中维护。

1. 直播频道可直接在 GitHub 编辑 `data/live.m3u`，修改名称、`group-title` 分组、`tvg-logo` 图标和下一行的真实播放地址。网页「直播电视」提供「复制 M3U 链接」和文件编辑入口；直播列表中可以改订阅名称、开关和 URL。
2. 改外部直播列表或点播接口时，在「配置与发布」中复制 JSON，再打开 GitHub 的 `data/library.json` 全选替换并提交。网页修改先存为浏览器草稿；需要登录有仓库写权限的 GitHub 账号才能发布，网页不收集或保存 GitHub Token。
3. 等待仓库 [Publish personal sources](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 成功。检查失败时本次内容不会部署，修正文件后再提交。
4. 在电视刷新相应配置。客户端可能有首页缓存，必要时刷新源或重开应用；免费代理也可能缓存旧文件。

普通 push 发布和本地构建只读取 `data/live.m3u` 与来源清单，不联网刷新；定时运行或手动勾选同步时，才先执行同步器。M3U / 来源清单格式错误时检查失败，已有线上版本保留。Pages 是公开站点，源文件也在公开仓库，不要填写账号密码、私密 Cookie 或令牌。

M3U 中每个频道示例：

```m3u
#EXTM3U
#EXTINF:-1 tvg-id="my-channel" tvg-logo="https://example.com/logo.png" group-title="我的分组",我的频道
#EXTVLCOPT:http-user-agent=okhttp/3.8.1
https://example.com/live.m3u8
```

同名、同分组且请求头一致的多段 `EXTINF + 地址` 会合并为备用线路。`#EXTHTTP:{"Referer":"https://example.com/"}` 可以设置更多请求头；`#EXTVLCOPT` 支持 User-Agent 和 Referer。网页停用频道会在源文件的 EXTINF 中写入本站扩展 `x-enabled="false"`，构建后该频道不会进入公开的 M3U / TXT / JSON；改为 `true` 可恢复，直接删除整段也可以。

## 内容格式

- `live.playlists`：外部 M3U / TXT / 直播 JSON 地址，用 `name`、`url` 和可选 `headers`。
- 默认 `live.playlists` 只有「我的 M3U」。已合并的上游地址单独保存在 `data/live-sources.json`，不重新加入订阅列表；需要新的独立来源时仍可自行添加。
- 默认不再填写 `live.channelFile`。自己的 M3U 也在 `live.playlists` 中以 URL 引用，默认用 GH-Proxy 加速地址；构建器识别本站 Pages、Raw、GH-Proxy、GHFast 的完整 M3U 地址，并从本地 `data/live.m3u` 生成输出，不读取其他远程列表。
- `live.channels`：默认保持空数组以兼容 App，不再存放自建 M3U 的频道副本。旧配置仍可使用 JSON 频道；本项目的频道内容直接改 `data/live.m3u`。
- `vod.sites`：采集 API 或脚本条目，需要唯一 `key`、名称 `name`、接口 `type`（JSON=1、XML=0、HTTP=4、插件=3）、地址 `api`；可选 `headers`、`ext`、`playUrl`、`jar`。`csp_` 类型必须配置 JAR；已有一整份 TVBox JSON 请放 `warehouses`，不要当成采集 API。
- 当前默认配置不包含 `vod.movies`，只维护点播接口与完整配置。构建器、网页和新版 App 允许省略该字段，不会插入空的自建片库入口。旧备份若包含自有影片仍可读取；省略字段时网页隐藏「自有影片」。
- `vod.categories`：保留给旧自建片库的分类定义；外部点播源的分类由各自接口返回。
- `warehouses`：其他 TVBox / 多仓配置的 `name`、`url`。保留完整配置，不错误地作为采集 API。超过应用单次最多 6 份的导入上限时，网页提供全部分组地址供依次添加。
- 列表条目可设置 `enabled: false` 暂停发布，内容保留在维护文件中。

## 发布结构

`main` 保存源码、可编辑的 `data/live.m3u`、`data/live-sources.json`、频道绑定状态 `data/live-sync-state.json` 与 `data/library.json`。工作流先检查格式与脚本，再发布 M3U、来源清单及旧格式备用输出到 `source-data` 和 GitHub Pages。修改 `data/` 下任一文件都会触发发布，不触发 APK 构建。

`source-data` 全部由工作流维护，请修改 `main` 的源文件，不要直接修改生成物。工作流仅向该分支写入公开源站文件，不强推、不操作应用暂存区，也不会把 APK、签名、SDK 或工具缓存传到 Pages。

本地验证：

```sh
python3 -m venv .tools/sync-venv
.tools/sync-venv/bin/python -m pip install -r scripts/requirements-sync.txt
PATH="$PWD/.tools/sync-venv/bin:$PATH" ./scripts/check.sh
.tools/sync-venv/bin/python -m http.server 8765 --directory .tools/site
```

打开 `http://localhost:8765/` 预览。生成目录在 `.tools/`，不进入 `main`。

GitHub Pages 是静态托管，无法自己保存服务器数据；因此网页草稿通过 GitHub 提交发布，不把「浏览器保存」显示成「已经上线」。官方说明：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[自定义 Actions 发布](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

## 仓库与迁移

本仓库独立公开维护源站页面、配置和发布工具，Android 客户端保存在独立的私有仓库。公开仓库使用全新的 Git 历史，包含源站代码与许可证。

迁移后的站点是 `https://yujuanit.github.io/TVSources/`。此前 `/TVApp/` 下的网页和原仓库 Raw / 免费代理订阅入口停止使用；请在电视端依次添加本页列出的两个新多仓分组。以后在本仓库的 `data/live.m3u` 维护频道，在 `data/library.json` 维护其他配置。

本地完整检查：`./scripts/check.sh`。需要 Python 3.11+、Node.js 22+，以及固定版本的 `opencc-python-reimplemented`（Apache-2.0，用于繁转简）；依赖见 `scripts/requirements-sync.txt`，不需要 Android SDK 或 JDK。源站代码采用仓库中的 [GPL-3.0](LICENSE)。
