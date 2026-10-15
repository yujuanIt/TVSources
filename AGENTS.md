# 居安源站开发约定

- 这是独立公开的源站仓库 `yujuanIt/TVSources`，只维护静态页面、公开源地址、构建和测试工具。
- 自建列表维护 `data/live.m3u`，在 `data/library.json` 的 `live.playlists` 中以完整 URL 引用，默认使用 GH-Proxy 加速；构建器识别本站 Pages、Raw、GH-Proxy、GHFast 地址，仍只读取本地 M3U。默认配置不再填写 `channelFile` 或内嵌频道，`live.channels` 保持空数组以兼容客户端，不下载其他远程列表。保留已有名称、开关、分组、图标、请求头、签名参数、KODIPROP / EXTVLCOPT 播放选项和影片条目。
- 默认配置不包含 `vod.movies`，只维护直播与点播来源；缺省时按空片库读取，不自动补回该字段或空的自建片库入口。保留旧非空影片备份的读取兼容。
- 不放入 Android 客户端源码、APK、签名文件、密码或私密令牌。公开 Git 历史也只包含本站文件。
- 运行 `./scripts/check.sh` 检查 Python 构建器、JavaScript 片库和页面脚本。生成文件放在 `.tools/site/`。
- `.github/workflows/source-pages.yml` 负责更新 `source-data` 分支和 GitHub Pages；生成分支不手工编辑。
- 多仓每组最多 6 份，完整导入不能丢失来源；原始播放地址、配置和请求头保持原样。
- 新文件创建后用明确路径 `git add -- <文件>` 暂存，不使用 `git add .` 或 `git add -A`。
- 日常只暂存；用户明确要求发布、提交或推送时才 commit / push，不强推。
