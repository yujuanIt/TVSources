# 居安的源站

网站：[居安源站](https://yujuanit.github.io/TVSources/)。已按用户要求同步 App 默认源地址，之后可以自行添加、改名、停用或删除；没有复制影片文件或展开远程频道内容。

当前同步了 2 个直接点播接口（非凡、360），6 份完整 TVBox 配置（饭太硬、心魔、Clun、FongMI、香雅情、肥猫），以及 App 的 9 个默认直播列表。配置与接口保持原地址，直播请求头与 App 一致；完整配置的插件、解析和站点内容继续由上游维护。

## 固定订阅地址

电视中「设置 → 源管理 → 添加源地址」依次添加下方两个多仓分组，可接入全部来源。每组最多 6 份配置，兼容现有 App 的单次导入上限；第一组已包含综合源，添加完两组后无需重复添加综合源。

| 用途 | 免费加速入口 |
| --- | --- |
| 综合源 | [box.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/box.json) |
| 点播配置 | [vod.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/vod.json) |
| 全部来源 · 多仓分组 1 | [warehouse-1.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse-1.json) |
| 全部来源 · 多仓分组 2 | [warehouse-2.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse-2.json) |
| 自建频道 M3U | [live.m3u](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.m3u) |
| 自建频道 JSON，保留完整请求头 | [live.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/live.json) |
| 完整多仓索引，客户端可能限制一次导入数量 | [warehouse.json](https://gh-proxy.com/https://raw.githubusercontent.com/yujuanIt/TVSources/source-data/warehouse.json) |

原址备用：[综合源](https://yujuanit.github.io/TVSources/box.json)、[点播](https://yujuanit.github.io/TVSources/vod.json)、[直播 M3U](https://yujuanit.github.io/TVSources/live.m3u)。网站总览提供 GHFast 与 GitHub Raw 的备用入口，切换下拉框后复制即可。

综合源包含自己填写的频道和外部直播列表；`live.m3u`、`live.json` 仅导出自己填写的频道。已有的外部 M3U 不会复制到自建频道中。

多仓分组随已启用的外部配置数量自动生成，网页总览会列出当前全部分组。删除配置后可能减少分组数，请以网页显示为准。此处同步的是 App 默认地址，没有重新逐条验证所有影片与频道的实际播放。

加速用于公开配置、直播清单和片库脚本，视频仍连接原播放地址，不中转影片。GH-Proxy / GHFast 是公共文件代理，不等同于自有大陆 CDN，不保证所有地区持续可用。2026-10-15 本机抽查 GH-Proxy、GHFast、ghproxy.net 均取得 HTTP 200，JSON 与 GitHub 原文件 SHA-256 一致；jsDelivr 两个域名在本机超时，未选为默认。官方服务与限制见 [GH-Proxy 文档](https://gh-proxy.com/docs/github-accelerator)；各网络的速度与可用性应以自己的电视为准。

## 填写与发布

只需要维护 [data/library.json](https://github.com/yujuanIt/TVSources/edit/main/data/library.json) 这一份文件。

1. 打开维护页，添加 / 编辑 / 停用直播频道、直播列表、点播接口或自有影片。网页修改先保存在当前浏览器，可撤销、导入或导出备份。
2. 「配置与发布」点击「复制完整配置」，再点击「打开 GitHub 文件」，全选替换 JSON 并提交 Commit changes。需要登录有仓库写权限的 GitHub 账号；网页不收集或保存 GitHub Token。
3. 等待仓库 [Publish personal sources](https://github.com/yujuanIt/TVSources/actions/workflows/source-pages.yml) 成功。检查失败时本次内容不会部署，修正文件后再提交。
4. 在电视刷新相应配置。自己的影片目录通过脚本读取，客户端可能仍有首页 / 模块缓存，必要时刷新源或重开应用；免费代理也可能缓存旧文件。

也可直接在 GitHub 编辑 JSON，跳过网页表单。Pages 是公开站点，源文件也在公开仓库，不要填写账号密码、私密 Cookie 或令牌。

## 内容格式

- `live.playlists`：外部 M3U / TXT / 直播 JSON 地址，用 `name`、`url` 和可选 `headers`。
- `live.channels`：自己填写的频道，用 `name`、`group`、`logo`、`urls`，支持多个备用地址、`tvgId` 和 `headers`。JSON 订阅保留完整请求头；M3U 输出 User-Agent / Referer，其他头部请使用 JSON。
- `vod.sites`：采集 API 或脚本条目，需要唯一 `key`、名称 `name`、接口 `type`（JSON=1、XML=0、HTTP=4、插件=3）、地址 `api`；可选 `headers`、`ext`、`playUrl`、`jar`。`csp_` 类型必须配置 JAR；已有一整份 TVBox JSON 请放 `warehouses`，不要当成采集 API。
- `vod.movies`：自有影片，使用稳定唯一的 `id`、`name`、`category`、`routes`。表单编辑第一条线路，已有其他线路保留；完整 JSON 可编辑所有线路及逐集请求头。
- `vod.categories`：影片大分类，`id` 与影片 `category` 对应。默认电影、电视剧、综艺、动漫、纪录片、短剧，可自行增加。
- `warehouses`：其他 TVBox / 多仓配置的 `name`、`url`。保留完整配置，不错误地作为采集 API。超过应用单次最多 6 份的导入上限时，网页提供全部分组地址供依次添加。
- 列表条目可设置 `enabled: false` 暂停发布，内容保留在维护文件中。

下面仅为结构示例，`example.com` 地址不是真实片源，不会自动发布：

```json
{
  "id": "my-film-001",
  "name": "我的影片",
  "category": "movie",
  "year": "2026",
  "poster": "",
  "description": "自己填写简介",
  "routes": [
    {
      "name": "主线路",
      "episodes": [
        {"name": "第01集", "url": "https://example.com/episode-1.m3u8"},
        {"name": "第02集", "url": "https://example.com/episode-2.m3u8"}
      ]
    }
  ]
}
```

自己的影片由 `vod.js` 转为居安影院现有 JavaScript 片库接口，实现分类、精确详情、搜索及多集 / 多线路播放。每集使用内部标识，实际视频 URL 与请求头在播放阶段原样取出，避免签名中的 `$` / `#` 被片单分隔符截断。该脚本没有引入额外 JAR，其他客户端是否支持这一 JavaScript 接口需实际验证。

## 发布结构

`main` 保存源码与可编辑的 `library.json`。工作流先执行构建器 / 脚本测试，再生成白名单内的公开文件，发布到 `source-data` 分支供免费代理读取，最后部署 GitHub Pages。只有源站、测试或发布脚本改动触发该工作流；应用源码改动不会触发 APK 构建或源站部署。

`source-data` 全部由工作流维护，请修改 `main` 的源文件，不要直接修改生成物。工作流仅向该分支写入公开源站文件，不强推、不操作应用暂存区，也不会把 APK、签名、SDK 或工具缓存传到 Pages。

本地验证：

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --experimental-vm-modules --test tests/adapter.test.mjs
python3 scripts/build-source-site.py
python3 -m http.server 8765 --directory .tools/site
```

打开 `http://localhost:8765/` 预览。生成目录在 `.tools/`，不进入 `main`。

GitHub Pages 是静态托管，无法自己保存服务器数据；因此网页草稿通过 GitHub 提交发布，不把「浏览器保存」显示成「已经上线」。官方说明：[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[自定义 Actions 发布](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

## 仓库与迁移

本仓库独立公开维护源站页面、配置和发布工具，Android 客户端保存在独立的私有仓库。公开仓库使用全新的 Git 历史，包含源站代码与许可证。

迁移后的站点是 `https://yujuanit.github.io/TVSources/`。此前 `/TVApp/` 下的网页和原仓库 Raw / 免费代理订阅入口停止使用；请在电视端依次添加本页列出的两个新多仓分组。以后在本仓库维护 `data/library.json`。

本地完整检查：`./scripts/check.sh`。需要 Python 3.11+、Node.js 22+，不需要 Android SDK 或 JDK。源站代码采用仓库中的 [GPL-3.0](LICENSE)。
