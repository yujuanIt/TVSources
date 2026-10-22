# 居安源站

居安影院的公开配置站，集中维护点播接口、TVBox 配置和直播列表。使用 GitHub Pages 托管静态页面，GitHub Actions 按登记的上游定时同步直播，并校验、生成和发布订阅文件。

[打开源站](https://yujuanit.github.io/TVSources/) · [编辑配置](https://github.com/yujuanIt/TVSources/edit/main/data/library.json) · [编辑直播 M3U](https://github.com/yujuanIt/TVSources/edit/main/data/live.m3u) · [同步与发布工作流](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml)

## 维护入口

| 文件 | 用途 | 维护方式 |
| --- | --- | --- |
| [data/library.json](data/library.json) | 点播清单链接、完整 TVBox 配置、直播订阅的名称、地址与开关 | 编辑文件，或在网页选择主配置导出提交 |
| [data/vod-sites.json](data/vod-sites.json) | 实际点播站点、搜索开关与各组插件 / 解析依赖 | 独立增删、改名；网页选择站点文件导出提交 |
| [data/vod-sources.json](data/vod-sources.json) | 点播同步上游、镜像与新站点策略 | 后续增加 TVBox 上游时编辑 |
| [data/vod-sync-state.json](data/vod-sync-state.json) | 点播字段基线、绑定与删除决定 | 同步程序维护，与站点清单一起保留 |
| [data/live.m3u](data/live.m3u) | 自有直播频道、分组、台标、线路与来源备注 | 手工维护显示信息，同步程序更新上游线路 |
| [data/live-sources.json](data/live-sources.json) | 上游 URL、稳定 ID、默认请求头、选取范围、合并规则与同步开关 | 新增或调整上游时编辑 |
| [data/live-official.m3u](data/live-official.m3u) | 已验证的央视、卫视官方频道入口 | 维护频道 ID 与官方页面，不填写临时签名播放地址 |
| [data/live-sync-state.json](data/live-sync-state.json) | 频道绑定、删除记录及上次有效同步状态 | 同步程序维护，与 M3U 一起保留 |

点播由采集接口和完整 TVBox 配置组成。默认独立直播订阅为「居安直播 · 我的 M3U」，频道内容统一维护在 `data/live.m3u`；上游清单是同步依赖，不作为额外的独立订阅加入 App。频道和线路数量以网页总览及工作流摘要为准。

## 接入客户端

居安影院默认自动同步本站的 `data/library.json`，可在「设置 → 居安源站 → 立即同步」检查更新。

主配置的 `vod.url` 指向独立的 [点播站点清单](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/data/vod-sites.json)。App 读取两份文件后按站点列表聚合搜索；只修改站点文件也会触发更新。任一文件读取失败时保留本机配置，并按现有镜像顺序重试。该维护格式由居安影院读取，通用 TVBox 客户端继续使用下面的标准配置与多仓输出。

### 简视独立应用订阅

简视TV 保留完整功能；简视直播、简视娱乐、简视点播、简视体育分别读取以下订阅。每款应用可构建电视与手机横屏版，共十种安装包。源站只发布公开配置，安装包由私有客户端仓库在本机交付。

| 应用 | Pages 订阅 | 内容 |
| --- | --- | --- |
| 简视TV | [data/library.json](https://yujuanit.github.io/TVSources/data/library.json) | 综合主配置 |
| 简视直播 | [data/modules/television.json](https://yujuanit.github.io/TVSources/data/modules/television.json) | 电视直播，含央视、卫视、港澳台、地方、体育及所有非平台频道 |
| 简视娱乐 | [data/modules/entertainment.json](https://yujuanit.github.io/TVSources/data/modules/entertainment.json) | 原分组明确标记为抖音、快手、虎牙、斗鱼、B站、Twitch、SOOP、YY 等平台的直播间 |
| 简视点播 | [data/modules/vod.json](https://yujuanit.github.io/TVSources/data/modules/vod.json) | 同一份点播站点清单及完整 TVBox 配置 |
| 简视体育 | [data/modules/sports.json](https://yujuanit.github.io/TVSources/data/modules/sports.json) | 体育模块元数据；直播间与赛程由应用现有的斗球公开页面、CBA 官方赛历能力读取 |

这些文件由构建器生成在 `.tools/site/data/modules/`，随 Pages 与 `source-data` 发布，不在 `main` 手工维护第二份配置。继续只编辑 `data/library.json`、`data/live.m3u`、`data/vod-sites.json`。网页总览同时提供各模块的 GH-Proxy、GHFast、Pages、Raw 地址。

模块 JSON 使用 `version: 1`、`name`、`module`，再只携带对应来源：电视 / 娱乐为 `live`，点播为 `vod` 与 `warehouses`，体育只有元数据。电视 / 娱乐不依赖点播清单或完整 TVBox 配置；体育不依赖通用 M3U 或点播清单。体育 M3U 频道仍属于简视直播；简视体育面向赛事房间和赛程，两者不会按名称猜测合并。

本站 M3U 自动派生 `data/modules/television.m3u` 与 `data/modules/entertainment.m3u`。分流只看原始分组，不看频道标题或播放域名；未识别组归电视。电视模块与综合输出使用相同的央视、地方卫视名称和分组归一，并按来源优先级排列同台备用线路；CCTV-5+、独立超高清台和海外版本分别保留。平台房间在综合与娱乐输出中均保留原分组和名称，即使房间名包含 CCTV 或卫视。归一仅作用于发布显示信息，不改维护 M3U 和同步状态；逐线路请求头、播放选项、签名参数与来源备注保留。手工添加的外部直播订阅原样出现在两份直播模块配置中，由对应客户端按同一规则过滤；构建不会联网抓取或静默丢弃外部列表。完整 TVBox 配置继续只在综合 / 点播默认订阅中引用。

其他支持 TVBox 的客户端可使用以下订阅地址：

| 内容 | GH-Proxy 加速入口 | Pages 原址 |
| --- | --- | --- |
| 综合源：直接点播接口与直播 | [box.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/box.json) | [box.json](https://yujuanit.github.io/TVSources/box.json) |
| 直接点播配置 | [vod.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/vod.json) | [vod.json](https://yujuanit.github.io/TVSources/vod.json) |
| 全部来源的多仓索引 | [warehouse.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse.json) | [warehouse.json](https://yujuanit.github.io/TVSources/warehouse.json) |
| 直播 M3U | [data/live.m3u](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/data/live.m3u) | [data/live.m3u](https://yujuanit.github.io/TVSources/data/live.m3u) |
| 直播 TXT | [live.txt](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.txt) | [live.txt](https://yujuanit.github.io/TVSources/live.txt) |
| 直播 JSON | [live.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.json) | [live.json](https://yujuanit.github.io/TVSources/live.json) |

综合源包含本站的独立点播接口与直播列表；带共用插件和解析规则的站点按依赖配置生成 `vod/<ID>.json`，通过多仓索引接入。对于限制单次导入数量的客户端，网页总览提供每组最多 6 份配置的 `warehouse-N.json`，依次添加页面列出的全部分组即可。居安影院直接读取维护清单并聚合全部启用站点。

网页总览可切换 GH-Proxy、GHFast、Pages 和 GitHub Raw 入口。公共代理用于配置、清单和脚本，视频仍连接原播放地址。M3U / JSON 可以保留台标、请求头和线路信息；TXT 使用普通频道列表格式，不承载完整播放元数据。

## 配置点播与直播订阅

编辑 `data/library.json` 中对应的列表：

| 字段 | 填写内容 |
| --- | --- |
| `live.playlists` | M3U、TXT 或直播 JSON 的 `name`、`url`、`enabled`，可选 `headers` |
| `vod` | `name` 和 `url`：点播名称及独立 `data/vod-sites.json` 的完整链接 |
| `warehouses` | 完整 TVBox 配置或多仓的 `name`、`url`、`enabled` |

原生完整 TVBox JSON 或多仓地址继续放在 `warehouses`，无需先提取为站点列表，App 仍可直接接入；当前该数组为空，可自行追加。独立站点清单的接口类型为 JSON `1`、XML `0`、HTTP `4`、插件 `3`；`csp_` 插件需要相应 JAR。

现有 TVBox 同步上游登记在 `data/vod-sources.json`，实际站点放在 `data/vod-sites.json` 的 `sites` 中；同一文件的 `contexts` 保存各组共用的 JAR、解析器、请求头与规则，站点的 `context` 指向对应依赖配置，避免混用同名插件或解析器。未填 `context` 的站点独立加载，可使用该文件的 `spider` 公共插件。

直播通过 `live.playlists` 的完整加速 URL 引用本站 M3U，频道直接写入 `data/live.m3u`。`data/library.json` 不填写 `live.channels`、`vod.categories` 或 `vod.movies`；点播分类和影片由相应接口提供，App 的推荐分类由客户端维护。

主配置中的 `live` 填写名称和直播列表，`vod` 只填写名称和链接。独立站点文件填写 `version: 1`、`sites` 与可选的 `spider`、`contexts`。频道统一在 M3U 维护，配置不接受内嵌频道、自建分类或自有影片，也不再接受主配置内嵌站点。

列表项设置 `enabled: false` 可暂停发布并保留配置。网页编辑先保存在当前浏览器草稿中，在「配置与发布」选择 `library.json` 或 `vod-sites.json`，复制 / 导出后提交到对应文件；两份都修改时分别提交。

## 自己维护点播站点

直接编辑 [data/vod-sites.json](data/vod-sites.json) 的 `sites`：增加或删除整个站点对象，修改 `name` 改名，`enabled: false` 停用，`searchable: 0` 仅退出搜索。`key` 在同一 `context` 内唯一，允许中文；改名时保留 `key`、`context`，避免改变站点身份。没有来源标记的手工新增站点由你独立维护。

导入条目的 `origin` 记录上游名称、配置 URL 与原始 key；`_syncId` 用于关联更新和记住删除决定。保留剩余条目的 `_syncId`，删除站点只需删除这一条。`contexts` 中的共用依赖由脚本维护，仍被站点引用的依赖配置不能删除。生成的标准 TVBox 配置会移除管理字段，只包含当前启用的站点与所需依赖。

[scripts/sync-vod.py](scripts/sync-vod.py) 支持普通 JSON、JSON5 注释 / 尾逗号、Base64 和图片附带配置，以及有边界的递归多仓。同步只读取配置，不执行下载的插件，也不采集全部影片。

```sh
# 预览同步结果，不覆盖维护文件
.tools/sync-venv/bin/python scripts/sync-vod.py --dry-run

# 更新本地清单和同步状态；检查后通过 Git 提交发布
.tools/sync-venv/bin/python scripts/sync-vod.py
```

预览位于 `.tools/vod-preview/`，报告位于 `.tools/vod-sync-report.json`。首次接管其他项目中现有的 `warehouses`，可使用 `--bootstrap-from-warehouses`，将它们登记为上游并在导入后清空原列表；本项目已完成这一步，日常无需再传该参数。

后续增加上游，在 [data/vod-sources.json](data/vod-sources.json) 的 `sources` 追加条目：

```json
{
  "id": "my_new_box",
  "name": "新的上游",
  "url": "https://example.com/box.json",
  "enabled": true
}
```

`id` 保持稳定，更换同一上游的 URL 时不改 ID；可选 `mirrors` 提供备用配置地址，`headers` 设置配置下载的请求头。`newSitesEnabled: true` 自动收录新站点并启用，保留上游声明的不支持搜索标志；App 仍按自身兼容范围搜索。`automaticSyncEnabled: false` 暂停全部点播同步，单个来源的 `enabled: false` 只暂停该来源的抓取。

同步按字段比较上次上游值：你修改过的名称、API、请求头、扩展参数、开关和搜索设置保留，其余字段跟随上游更新。手动删除的站点记入 `data/vod-sync-state.json`，后续不自动补回；需要恢复时还原带原 `_syncId` 的站点条目。保留该状态文件；已有托管站点但状态丢失时脚本会停止，避免误覆盖人工决定。

上游暂时失败或移除的站点保留待核对，单个失败不清空其他来源；所有启用上游均失败时不改清单和状态。缺少 API 的分隔条目等非法内容会跳过并写入报告。导入成功只表示配置可解析，未逐站执行搜索或验证播放。

同一项目的同步脚本不能同时运行。清单和状态写入中断时，下次正常运行会从 `.tools/vod-sync-pending.json` 恢复；若中断后文件又被手动编辑，脚本会停止供你核对，不覆盖新编辑。

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

发布时将央视、卫视常见别名和画质后缀统一，使同台的多个来源在居安影院中合为一个频道、多条线路；CCTV-5 / 5+、独立 4K / 8K、CCTV-4 各地区版本仍分别保留。规范化只作用于发布输出，不改写维护文件的名称、分组、同步绑定和删除记录；每条线路的请求头、播放器选项、完整签名与来源备注保持独立。来源顺序由 `mergePolicy.sourceOrder` 控制，官方入口优先，App 可依据本机稳定性记录优先选择其他线路。

`official-ysp` 是 `local-m3u` 来源，从仓库内 `data/live-official.m3u` 导入 `data/live.m3u`。其中保存带 `pid`、`cnlid` 的央视频官方页面入口，新版居安影院播放时通过官方匿名接口实时取得 HLS 地址；无需另建解析服务器。普通 M3U 播放器通常不能解析这些页面，可使用同台保留的 IPTV 备用线路。不要把 API 返回的临时 HLS 地址写死进文件。官方接口随地区、时段和平台策略变化，受限节目不作额外授权处理。

### 体育频道与 NBA / CBA 赛事

`88-sports`、`88-nba`、`88-cba` 在 `data/live-sources.json` 分别登记 [88直播体育频道](https://www.88zhibo.tv/match/21/live)、[NBA](https://www.88zhibo.tv/match/1/live)、[CBA](https://www.88zhibo.tv/match/2/live)。`format: "88zhibo"` 配合 `kind: "channels" / "NBA" / "CBA"` 使用，单项 `enabled: false` 暂停该项同步。

[scripts/sports_88.py](scripts/sports_88.py) 读取公开赛程与线路接口，不执行网页 JavaScript。新增条目必须取得有效直播 HLS 清单及 TS / fMP4 视频分片；占位链接、广告、需解锁链接、回放及尚无播放线路的场次跳过。只检查公开线路，不登录或调用付费授权。2026-10-16 体育频道检查中只有纬来体育通过清单与分片验证并新增；CCTV5 / 5+ 已有官方入口，其他占位频道未收录。没有可用赛事时不生成空频道或占位比赛。

M3U 的「体育」「NBA赛事」「CBA赛事」分组保存稳定的 `/live/<ID>/play` 页面入口、简体显示名、台标及来源备注；不保存会过期的 CDN 签名地址。需要包含 `SportsLive` 解析器的简影TV 客户端在播放时取得实际地址，普通播放器不能直接把这些页面当视频播放。客户端短期复用解析结果，失败时换公开线路或重新请求；视频直接连接上游，不需要自行部署转发服务器。源站验证不代表海信电视持续播放已通过。

赛事抓取最近 6 小时至未来 36 小时的 NBA / CBA 赛程，只发布通过播放验证的场次。赛事来源的 `retireMissing: true` 允许在完整成功快照中移除不再提供有效直播的条目，避免比赛结束后长期积累；接口读取失败保留上次数据。手工删除仍不自动补回，自动清理的赛事若重新可播可恢复，并保留本地名称、分组与开关；普通直播来源继续采用失败保留和移除待核对规则。

2026-10-16 验证：52 个候选央视 / 卫视频道中，50 个取得官方 CDN 的 HLS 清单及至少 8 KiB 视频分片后收录；其余未验证通过的候选不新增官方线路。验证是本机网络的清单与分片读取，不能替代电视设备的持续播放测试。官方入口参考 [央视直播](https://tv.cctv.com/live/) 与 [央视频](https://www.yangshipin.cn/tv/home)，频道元数据和匿名接口实现参考 GPL-3.0 的 [akiralereal/iptv](https://github.com/akiralereal/iptv)；Android 适配及许可证说明在私有 App 项目维护。

## 直播自动同步

[scripts/sync-live.py](scripts/sync-live.py) 按 `data/live-sources.json` 抓取启用的 M3U 上游，遵循 `mergePolicy.sourceOrder` 合并。选取范围为 `keep-selected` 的来源只更新登记的频道；合集已登记子源时不重复抓取。

`local-m3u` 只读登记的本地官方入口文件，与其他上游一起合并；定时同步不会向官方取票接口批量请求或保存临时播放凭据。

同步保留文件中手工维护的名称、分组、台标、EPG 与开关，补充新频道，并更新已匹配频道的完整播放 URL、请求头和播放器选项。新频道使用 OpenCC 转为简体并归组。完全相同的线路去重并合并来源备注，不同请求头或不同播放器选项的线路分别保留。

读取失败、非法列表或线路数低于上次有效数量 50% 时保留该源的有效数据；上游移除及匹配不明确的频道保留待核对。全部上游失败时不修改 M3U / 状态，也不执行本次发布。

工作流按北京时间 **04:25、10:25、16:25、22:25** 定时执行，也可在 [Actions](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 点击 **Run workflow**：

- 勾选 `sync_live`：先同步上游，再校验和发布。
- 勾选 `sync_vod`：同步登记的 TVBox 站点，再校验和发布。
- 两项都取消：仅校验和发布仓库中的内容。
- `automaticSyncEnabled: false` 暂停全部抓取；单个来源的 `enabled: false` 暂停该源并保留其现有线路。

体育频道与 NBA / CBA 另在每小时 **07、37 分**检查，只抓取这三个来源，不重复刷新其他 IPTV 或点播接口；验证、数据保存和发布仍沿用同一工作流。GitHub 定时任务可能延迟，App 还受其刷新周期和公共加速缓存影响。

定时安排由 [source-pages.yml](.github/workflows/source-pages.yml) 的 `schedule` 控制；调整频率时，同步更新来源清单的 `sync` 记录。

直播与点播使用同一组每 6 小时的定时触发。有数据变化时，工作流只自动提交 `data/live.m3u`、`data/live-sync-state.json`、`data/vod-sites.json` 与 `data/vod-sync-state.json`，随后在同一次运行中更新 `source-data` 和 GitHub Pages；无变化不产生数据提交。推送冲突会停止，不覆盖人工提交。各源结果和待核对数量可在工作流摘要查看。

本地同步命令：

```sh
# 只生成候选清单与状态，不覆盖 data 中的内容
.tools/sync-venv/bin/python scripts/sync-live.py --dry-run --preview-dir .tools/live-preview

# 写入本地 M3U 与状态，检查后通过 Git 提交发布
.tools/sync-venv/bin/python scripts/sync-live.py

# 仅刷新体育频道及 NBA / CBA，其他来源和本地编辑保留
.tools/sync-venv/bin/python scripts/sync-live.py --sports-only
```

依赖安装见下节。同步报告默认写入 `.tools/live-sync-report.json`；本地运行同步器不会自动推送或发布。

## 校验、预览与发布

本地需要 Python 3.11+、Node.js 22+，以及固定版本的 OpenCC、JSON5 同步依赖：

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
scripts/             构建、直播 / 点播同步、发布与检查工具
tests/               Python / JavaScript 固定测试
.github/workflows/   定时同步与 Pages 发布工作流
index.html           源站总览、内容编辑与发布入口
```

本站维护配置与播放地址，影片、信号和网络连通性由相应上游提供；列表校验通过不代表所有地址均可播放。Git 操作遵循 [AGENTS.md](AGENTS.md)，源站代码采用 [GPL-3.0](LICENSE)，同步依赖 OpenCC、JSON5 采用 Apache-2.0。
