# 居安源站开发约定

- 这是独立公开的源站仓库 `yujuanIt/TVSources`，只维护静态页面、公开源地址、构建和测试工具。
- 自建列表维护 `data/live.m3u`，在 `data/library.json` 的 `live.playlists` 中以完整 URL 引用，默认使用 GH-Proxy 加速；构建器识别本站 Pages、Raw、GH-Proxy、GHFast 地址，仍只读取本地 M3U。默认配置不再填写 `channelFile` 或内嵌频道，`live.channels` 保持空数组以兼容客户端，不下载其他远程列表。保留已有名称、开关、分组、图标、请求头、签名参数、KODIPROP / EXTVLCOPT 播放选项和影片条目。
- 默认独立直播订阅只保留「我的 M3U」。已合并的上游依赖在 `data/live-sources.json` 登记，M3U 用 `x-source-id` / `x-source-name` 按线路注明来源；允许同一线路对应多个来源，来源标记不能改变频道合并身份。源清单和备注随静态站发布，现在由 `scripts/sync-live.py` 每 6 小时同步，并在同一发布工作流中校验、保存数据变化和发布。不要把依赖清单重新注入 `live.playlists`，也不要在普通构建时联网刷新频道。同步器遵循清单里的去重、失败保留、本地编辑与中文分组规则；稳定绑定和删除记录保存在 `data/live-sync-state.json`，不要随意删除或重新生成。
- 默认配置不包含 `vod.movies`，只维护直播与点播来源；缺省时按空片库读取，不自动补回该字段或空的自建片库入口。保留旧非空影片备份的读取兼容。
- 不放入 Android 客户端源码、APK、签名文件、密码或私密令牌。公开 Git 历史也只包含本站文件。
- 构建的 APK / APKS / AAB 及其签名伴随文件只保存在客户端本机，不提交到任何 Git 仓库，不上传 GitHub Releases、Actions artifacts 或 Pages；源站自动发布仅包含页面、公开配置与直播清单。不要用 `git add -f` 绕过安装包忽略规则。
- 按 README 在 `.tools/sync-venv` 安装 `scripts/requirements-sync.txt`，使用该虚拟环境运行 `./scripts/check.sh` 检查 Python 构建器、JavaScript 片库和页面脚本。生成文件放在 `.tools/site/`。
- 用户已授权定时同步数据并自动发布；工作流仅可自动提交本次同步的 `data/live.m3u`、`data/live-sync-state.json`，无变化不提交，普通推送冲突则停止，不能强推或覆盖人工修改。
- `.github/workflows/source-pages.yml` 负责定时同步及更新 `source-data` 分支和 GitHub Pages；生成分支不手工编辑。
- 多仓每组最多 6 份，完整导入不能丢失来源；原始播放地址、配置和请求头保持原样。
- 新文件创建后用明确路径 `git add -- <文件>` 暂存，不使用 `git add .` 或 `git add -A`。
- README 描述当前配置、订阅、同步和发布流程，不堆叠迁移说明、过期数量或历史验证流水。
- 用户已授权：每次完成代码、配置或文档修改并通过相应检查后，自动 commit 并 push，无需再次确认。用户明确要求某次只暂存、不提交或不推送时，按该次要求执行。
- 开始前核对工作区、暂存区、当前分支和远端；只暂存、提交本次任务的文件，保留其他修改及其暂存状态，无实际改动不创建空提交。
- 推送前 fetch 并安全整合远端更新，目标为 `https://github.com/yujuanIt/TVSources.git`；沿用当前分支上游，无上游时设置到 origin 的同名分支。仅普通推送，不覆盖人工修改或强推。
- 检查失败先修复再提交；无法安全处理冲突或推送受阻时保留改动与提交并说明原因。完成后报告提交号和推送结果。
