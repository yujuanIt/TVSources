# 居安源站

居安影院的公开配置站，集中维护点播接口、TVBox 配置和直播列表。使用 GitHub Pages 托管静态页面，GitHub Actions 按登记的上游定时同步直播，并校验、生成和发布订阅文件。

[打开源站](https://yujuanit.github.io/TVSources/) · [编辑配置](https://github.com/yujuanIt/TVSources/edit/main/data/library.json) · [编辑直播 M3U](https://github.com/yujuanIt/TVSources/edit/main/data/live.m3u) · [同步与发布工作流](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml)

## 维护入口

| 文件 | 用途 | 维护方式 |
| --- | --- | --- |
| [data/library.json](data/library.json) | 点播接口、完整 TVBox 配置、直播订阅的名称、地址与开关 | 编辑文件，或在网页修改后复制 JSON 提交 |
| [data/live.m3u](data/live.m3u) | 自有直播频道、分组、台标、线路与来源备注 | 手工维护显示信息，同步程序更新上游线路 |
| [data/live-sources.json](data/live-sources.json) | 上游 URL、稳定 ID、默认请求头、选取范围、合并规则与同步开关 | 新增或调整上游时编辑 |
| [data/live-sync-state.json](data/live-sync-state.json) | 频道绑定、删除记录及上次有效同步状态 | 同步程序维护，与 M3U 一起保留 |

点播由采集接口和完整 TVBox 配置组成。默认独立直播订阅为「居安直播 · 我的 M3U」，频道内容统一维护在 `data/live.m3u`；上游清单是同步依赖，不作为额外的独立订阅加入 App。频道和线路数量以网页总览及工作流摘要为准。

## 接入客户端

居安影院默认自动同步本站的 `data/library.json`，可在「设置 → 居安源站 → 立即同步」检查更新。

其他支持 TVBox 的客户端可使用以下订阅地址：

| 内容 | GH-Proxy 加速入口 | Pages 原址 |
| --- | --- | --- |
| 综合源：直接点播接口与直播 | [box.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/box.json) | [box.json](https://yujuanit.github.io/TVSources/box.json) |
| 直接点播配置 | [vod.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/vod.json) | [vod.json](https://yujuanit.github.io/TVSources/vod.json) |
| 全部来源的多仓索引 | [warehouse.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse.json) | [warehouse.json](https://yujuanit.github.io/TVSources/warehouse.json) |
| 直播 M3U | [data/live.m3u](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/data/live.m3u) | [data/live.m3u](https://yujuanit.github.io/TVSources/data/live.m3u) |
| 直播 TXT | [live.txt](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.txt) | [live.txt](https://yujuanit.github.io/TVSources/live.txt) |
| 直播 JSON | [live.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.json) | [live.json](https://yujuanit.github.io/TVSources/live.json) |

综合源包含本站的直接点播接口与直播列表；完整外部 TVBox 配置通过多仓索引接入。对于限制单次导入数量的客户端，网页总览提供每组最多 6 份配置的 `warehouse-N.json`，依次添加页面列出的全部分组即可。

网页总览可切换 GH-Proxy、GHFast、Pages 和 GitHub Raw 入口。公共代理用于配置、清单和脚本，视频仍连接原播放地址。M3U / JSON 可以保留台标、请求头和线路信息；TXT 使用普通频道列表格式，不承载完整播放元数据。

## 配置点播与直播订阅

编辑 `data/library.json` 中对应的列表：

| 字段 | 填写内容 |
| --- | --- |
| `live.playlists` | M3U、TXT 或直播 JSON 的 `name`、`url`、`enabled`，可选 `headers` |
| `vod.sites` | 采集 API / 扩展接口的唯一 `key`、`name`、`type`、`api`，可选 `headers`、`ext`、`playUrl`、`jar` |
| `warehouses` | 完整 TVBox 配置或多仓的 `name`、`url`、`enabled` |

`vod.sites` 的接口类型为 JSON `1`、XML `0`、HTTP `4`、插件 `3`；`csp_` 插件需配置相应 JAR。完整 TVBox JSON 放在 `warehouses`，采集 API 放在 `vod.sites`。

默认配置只维护上表三类来源，通过 `live.playlists` 的完整加速 URL 引用本站 M3U，频道直接写入 `data/live.m3u`。`data/library.json` 不填写 `live.channels`、`vod.categories` 或 `vod.movies`；点播分类和影片由相应接口提供，App 的推荐分类由客户端维护。

维护文件、网页草稿与发布的 `data/library.json` 使用同一结构，不自动补字段。`live` 只填写名称和直播列表；`vod` 只填写名称、点播接口与可选的公共 `spider`。配置不再接受内嵌频道、自建分类和自有影片，网页也不提供这些编辑入口；频道统一在 M3U 维护，点播内容通过接口或完整 TVBox 配置接入。

列表项设置 `enabled: false` 可暂停发布并保留配置。网页编辑先保存在当前浏览器草稿中，需要把「配置与发布」中的完整 JSON 提交到 GitHub 才会上线。

## 维护直播频道

M3U 中每条线路由频道信息、可选播放参数和完整播放地址组成：

```m3u
#EXTM3U
#EXTINF:-1 tvg-id="my-channel" tvg-logo="https://example.com/logo.png" group-title="央视",我的频道
#EXTVLCOPT:http-user-agent=okhttp/3.8.1
https://example.com/live.m3u8
```

- 修改频道显示名、`tvg-name`、`group-title`、`tvg-logo` 和显示开关时，保留已有 `x-sync-id`；同一频道的各条线路使用一致的显示信息。
- `tvg-id` 用于匹配 EPG，保留原始标识。请求头可使用 `#EXTHTTP`，User-Agent / Referer 也可使用 `#EXTVLCOPT`；KODIPROP 与其他播放器选项随线路保存。
- `x-enabled="false"` 隐藏频道，生成的 M3U / TXT / JSON 会排除该频道；改为 `true` 可恢复。
- 带 `x-source-id` 的线路由对应上游同步，`x-source-name` 是可读来源备注；同一线路可以记录多个来源，备注不写入频道显示名。
- 手工新增、没有来源标记的线路保留。需要独立维护某条播放地址时，移除该条的 `x-source-id` / `x-source-name`，保留频道身份与显示信息。
- 删除已建立绑定的频道后，同步状态会记录删除，后续同步不会自动补回。保留 `data/live-sync-state.json`，需要恢复时还原带原 `x-sync-id` 的频道条目。

频道名称与分组使用简体中文。分组顺序由来源清单的 `normalization.groupOrder` 维护：央视、地方卫视、抖音、虎牙、B站、斗鱼、港澳台、体育、影视、少儿、音乐、游戏、综合频道、Twitch、SOOP、YY、公告。

构建器识别本站 Pages、Raw、GH-Proxy、GHFast 的完整 M3U 地址，从本地 `data/live.m3u` 生成输出；普通构建不抓取远程直播列表。

## 直播自动同步

[scripts/sync-live.py](scripts/sync-live.py) 按 `data/live-sources.json` 抓取启用的 M3U 上游，遵循 `mergePolicy.sourceOrder` 合并。选取范围为 `keep-selected` 的来源只更新登记的频道；合集已登记子源时不重复抓取。

同步保留文件中手工维护的名称、分组、台标、EPG 与开关，补充新频道，并更新已匹配频道的完整播放 URL、请求头和播放器选项。新频道使用 OpenCC 转为简体并归组。完全相同的线路去重并合并来源备注，不同请求头或不同播放器选项的线路分别保留。

读取失败、非法列表或线路数低于上次有效数量 50% 时保留该源的有效数据；上游移除及匹配不明确的频道保留待核对。全部上游失败时不修改 M3U / 状态，也不执行本次发布。

工作流按北京时间 **04:25、10:25、16:25、22:25** 定时执行，也可在 [Actions](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 点击 **Run workflow**：

- 勾选 `sync_live`：先同步上游，再校验和发布。
- 取消勾选：仅校验和发布仓库中的内容。
- `automaticSyncEnabled: false` 暂停全部抓取；单个来源的 `enabled: false` 暂停该源并保留其现有线路。

定时安排由 [source-pages.yml](.github/workflows/source-pages.yml) 的 `schedule` 控制；调整频率时，同步更新来源清单的 `sync` 记录。

有数据变化时，工作流只自动提交 `data/live.m3u` 与 `data/live-sync-state.json`，随后在同一次运行中更新 `source-data` 和 GitHub Pages；无变化不产生数据提交。推送冲突会停止，不覆盖人工提交。各源结果和待核对数量可在工作流摘要查看。

本地同步命令：

```sh
# 只生成候选清单与状态，不覆盖 data 中的内容
.tools/sync-venv/bin/python scripts/sync-live.py --dry-run --preview-dir .tools/live-preview

# 写入本地 M3U 与状态，检查后通过 Git 提交发布
.tools/sync-venv/bin/python scripts/sync-live.py
```

依赖安装见下节。同步报告默认写入 `.tools/live-sync-report.json`；本地运行同步器不会自动推送或发布。

## 校验、预览与发布

本地需要 Python 3.11+、Node.js 22+，以及固定版本的 OpenCC 同步依赖：

```sh
python3 -m venv .tools/sync-venv
.tools/sync-venv/bin/python -m pip install -r scripts/requirements-sync.txt
PATH="$PWD/.tools/sync-venv/bin:$PATH" ./scripts/check.sh
.tools/sync-venv/bin/python -m http.server 8765 --directory .tools/site
```

打开 `http://localhost:8765/` 预览。检查脚本运行 Python 构建与同步测试、JavaScript 编辑器测试及脚本语法校验，并把静态站生成到 `.tools/site/`；这些步骤不联网同步上游、不发布内容。

发布流程：

1. 在 `main` 修改频道、配置或上游清单，检查格式及本地预览。
2. 提交并推送内容变更，等待 **Publish personal sources** 成功。普通内容推送校验和发布仓库数据，定时或手动启用同步的运行才抓取上游。
3. 工作流生成订阅文件，更新 `source-data` 并部署 GitHub Pages。校验失败保留已有线上版本。
4. 客户端刷新订阅；居安影院也会按自身同步周期检查更新。

`source-data` 是自动生成的发布分支，请在 `main` 修改维护文件。仓库与订阅内容公开，配置中只放可公开的数据；源站仅发布页面、配置和直播清单。App 源码、APK、签名和本机工具保存在客户端项目中，构建的安装包只在本机交付，不上传 GitHub。

## 项目结构

```text
data/                配置、自有 M3U、上游清单与同步状态
assets/              页面样式与配置编辑器
scripts/             构建、直播同步、发布与检查工具
tests/               Python / JavaScript 固定测试
.github/workflows/   定时同步与 Pages 发布工作流
index.html           源站总览、内容编辑与发布入口
```

本站维护配置与播放地址，影片、信号和网络连通性由相应上游提供；列表校验通过不代表所有地址均可播放。Git 操作遵循 [AGENTS.md](AGENTS.md)，源站代码采用 [GPL-3.0](LICENSE)，同步依赖 OpenCC 采用 Apache-2.0。
