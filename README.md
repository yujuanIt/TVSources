# 居安的源站

网站：[居安源站](https://yujuanit.github.io/TVSources/)。已按用户要求同步 App 默认源地址，之后可以自行添加、改名、停用或删除；只维护配置和播放地址，没有复制影片文件。

当前维护 2 个直接点播接口（非凡、360）、6 份完整 TVBox 配置（饭太硬、心魔、Clun、FongMI、香雅情、肥猫）和直播订阅。`data/live.m3u` 已合并原有常看频道及 7 份直播列表，共 1,894 个频道条目、2,917 条播放线路。外部独立订阅仍保留原开关，常看原列表保持停用备份；需要精简 App 的直播列表时，可以在 `data/library.json` 停用已合并的独立订阅。点播配置、接口、插件和解析仍由各自上游维护。

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

2026-10-15 按用户要求合并以下列表，原有 5 个常看频道保留在前。合并按分组、名称、台标、EPG 标识、请求头和播放选项识别相同频道；相同频道下完全相同的播放地址只保留一次，共去掉 155 条重复线路。不同请求头或播放选项不会混用，IPv4、IPv4 备用和 IPv6 的分组添加相应前缀；频道地址及签名参数保持原样，两个台标地址中的空格编码为 `%20`。

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

这是一次清单导入，之后可自行编辑，不会定时从上游覆盖文件。此次检查了列表读取、去重、播放地址与请求头保留以及输出格式，没有逐台验证实际播放。

TXT 使用 `分组名,#genre#` 和 `频道名,播放地址` 格式，备用线路逐行列出。TXT 不包含图标与请求头，需要这些信息时使用 M3U / JSON；综合源默认引用 M3U，额外的播放器选项也保留在 M3U 输出中。

多仓分组随已启用的外部配置数量自动生成，网页总览会列出当前全部分组。删除配置后可能减少分组数，请以网页显示为准。此处同步的是 App 默认地址，没有重新逐条验证所有影片与频道的实际播放。

加速用于公开配置、直播清单和片库脚本，视频仍连接原播放地址，不中转影片。GH-Proxy / GHFast 是公共文件代理，不等同于自有大陆 CDN，不保证所有地区持续可用。2026-10-15 本机抽查 GH-Proxy、GHFast、ghproxy.net 均取得 HTTP 200，JSON 与 GitHub 原文件 SHA-256 一致；jsDelivr 两个域名在本机超时，未选为默认。官方服务与限制见 [GH-Proxy 文档](https://gh-proxy.com/docs/github-accelerator)；各网络的速度与可用性应以自己的电视为准。

## 填写与发布

维护直播频道时，只改项目 data 目录的 [live.m3u](https://github.com/yujuanIt/TVSources/edit/main/data/live.m3u)。外部直播订阅和点播接口在 [data/library.json](https://github.com/yujuanIt/TVSources/edit/main/data/library.json) 中维护。

1. 直播频道可直接在 GitHub 编辑 `data/live.m3u`，修改名称、`group-title` 分组、`tvg-logo` 图标和下一行的真实播放地址。网页「直播电视」提供「复制 M3U 链接」和文件编辑入口；直播列表中可以改订阅名称、开关和 URL。
2. 改外部直播列表或点播接口时，在「配置与发布」中复制 JSON，再打开 GitHub 的 `data/library.json` 全选替换并提交。网页修改先存为浏览器草稿；需要登录有仓库写权限的 GitHub 账号才能发布，网页不收集或保存 GitHub Token。
3. 等待仓库 [Publish personal sources](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 成功。检查失败时本次内容不会部署，修正文件后再提交。
4. 在电视刷新相应配置。客户端可能有首页缓存，必要时刷新源或重开应用；免费代理也可能缓存旧文件。

发布脚本只在本地 / Actions 构建时读取 `data/live.m3u`，不会向上游重新抓取或覆盖你的列表。M3U 格式错误时检查失败，已有线上版本保留。Pages 是公开站点，源文件也在公开仓库，不要填写账号密码、私密 Cookie 或令牌。

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
- 默认不再填写 `live.channelFile`。自己的 M3U 也在 `live.playlists` 中以 URL 引用，默认用 GH-Proxy 加速地址；构建器识别本站 Pages、Raw、GH-Proxy、GHFast 的完整 M3U 地址，并从本地 `data/live.m3u` 生成输出，不读取其他远程列表。
- `live.channels`：默认保持空数组以兼容 App，不再存放自建 M3U 的频道副本。旧配置仍可使用 JSON 频道；本项目的频道内容直接改 `data/live.m3u`。
- `vod.sites`：采集 API 或脚本条目，需要唯一 `key`、名称 `name`、接口 `type`（JSON=1、XML=0、HTTP=4、插件=3）、地址 `api`；可选 `headers`、`ext`、`playUrl`、`jar`。`csp_` 类型必须配置 JAR；已有一整份 TVBox JSON 请放 `warehouses`，不要当成采集 API。
- 当前默认配置不包含 `vod.movies`，只维护点播接口与完整配置。构建器、网页和新版 App 允许省略该字段，不会插入空的自建片库入口。旧备份若包含自有影片仍可读取；省略字段时网页隐藏「自有影片」。
- `vod.categories`：保留给旧自建片库的分类定义；外部点播源的分类由各自接口返回。
- `warehouses`：其他 TVBox / 多仓配置的 `name`、`url`。保留完整配置，不错误地作为采集 API。超过应用单次最多 6 份的导入上限时，网页提供全部分组地址供依次添加。
- 列表条目可设置 `enabled: false` 暂停发布，内容保留在维护文件中。

## 发布结构

`main` 保存源码、可编辑的 `data/live.m3u` 和 `data/library.json`。工作流先检查格式与脚本，再发布 M3U 链接及旧格式备用输出到 `source-data` 和 GitHub Pages。修改 `data/` 下任一文件都会触发发布，不触发 APK 构建。

`source-data` 全部由工作流维护，请修改 `main` 的源文件，不要直接修改生成物。工作流仅向该分支写入公开源站文件，不强推、不操作应用暂存区，也不会把 APK、签名、SDK 或工具缓存传到 Pages。

本地验证：

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --experimental-vm-modules --test tests/*.test.mjs
python3 scripts/build-source-site.py
python3 -m http.server 8765 --directory .tools/site
```

打开 `http://localhost:8765/` 预览。生成目录在 `.tools/`，不进入 `main`。

GitHub Pages 是静态托管，无法自己保存服务器数据；因此网页草稿通过 GitHub 提交发布，不把「浏览器保存」显示成「已经上线」。官方说明：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[自定义 Actions 发布](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

## 仓库与迁移

本仓库独立公开维护源站页面、配置和发布工具，Android 客户端保存在独立的私有仓库。公开仓库使用全新的 Git 历史，包含源站代码与许可证。

迁移后的站点是 `https://yujuanit.github.io/TVSources/`。此前 `/TVApp/` 下的网页和原仓库 Raw / 免费代理订阅入口停止使用；请在电视端依次添加本页列出的两个新多仓分组。以后在本仓库的 `data/live.m3u` 维护频道，在 `data/library.json` 维护其他配置。

本地完整检查：`./scripts/check.sh`。需要 Python 3.11+、Node.js 22+，不需要 Android SDK 或 JDK。源站代码采用仓库中的 [GPL-3.0](LICENSE)。
