# JSON 桥接与轻量采集版：本机验证及工坊发布（2026-10-23）

## 发布结果

已按用户本轮明确授权更新现有 [Steam 工坊条目 3823861796](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)，App ID 602960，没有新建条目。Submit 返回 OK。重新查询简体中文和英文详情，更新时间均为 **2026-10-23T03:30:30Z（北京时间 11:30:30）**，晚于上传前。

标题仍为 **泥偶迅猛龙汉化——游戏内一键实时汉化工具|游戏外快捷翻译工作台**。实际编辑器只设置内容、中文更新日志与构建 Metadata，没有设置标题、封面、简介或依赖。中英文标题、完整简介、封面 URL 在上传前后均一致，条目仍为 Public。

Steam 回读 Metadata 的 runtime 为 `3320fa40b41adcdeaef3627619419a4a3acf2a9d`，build 为 `snapshot-native-fix-20261023`，Windows ZIP 及 EXE 哈希与本轮清单相符。内容大小 17,416,287 字节。

随后真实回下载 8 个文件，逐个 SHA256 与暂存清单一致，文件集合一致，无旧文件残留。再次核验下载 ZIP 内 EXE 和 VERSION.txt，以及下载 Lua 的哈希与运行标记。公开更新日志 HTTP 200，包含本轮日志全部行。以上不是仅凭上传命令退出码认定成功。

## 源码与候选核验

工作区开始干净，从 bf4f904 fetch 并快进到报告提交 `22d2428`；没有强制重置或覆盖本地成果。22d2428 相对候选源码只修改报告和证据。

下载指定 [CI 39893485639](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39893485639) 的 Artifact `12475881482`，GitHub API 记录的源码提交为 `3320fa40b41adcdeaef3627619419a4a3acf2a9d`。Artifact 外层摘要、内层 ZIP 完整性与哈希、两种包的提交标记、Windows ZIP 内 EXE，以及插件 ZIP 三个文件与当前源码的逐字节一致性均通过。

| 内容 | SHA256 |
| --- | --- |
| Artifact 外层 ZIP | `6288d9aa3ec6a082f2e986ea33368cd3dc05543d2961fea43f8e6dc6d0b06262` |
| Windows ZIP | `49f63629a6c32fedd09c7cd2f76a2e085c29e1818edb693a5f898c78f62bb693` |
| 插件 ZIP | `9f74eec12747238552fdd598b5cbaa90d4b377fee368f73a8cb1eed731a31c64` |
| 源码 ZIP | `6ce799d6383e8d9ea0cf427895a548869eb9ba3e62ea967dcdf08080e52a42e1` |
| EXE（本机、上传包内及回下载后） | `c73cf1e440eb3dd7647636ea926f60ebc600ad56805fabe41e1d381e1e96d518` |
| 插件 Lua（本机、上传前及回下载后） | `3563002e57592a75504fa88de0c61bf32b13ad77151efc223b692e00ce11839f` |

没有误用此前 c337f2c、3832812 或旧公开 rc5 包。

## 本机安装与备份

进程检查没有发现游戏或工作台运行。桌面 `AbyssText-snapshot-native-3320fa4` 中的实际 EXE 已匹配本次哈希；游戏 `D:/steam/steamapps/common/Barotrauma/LocalMods/AbyssTextLive` 的 Lua 也已匹配，故没有重复覆盖。

已将自己的桌面程序目录、完整插件和 Live、默认 AppData/AbyssText 备份到独立证据目录的 backup/。读取游戏配置确认只启用 LocalMods/AbyssTextLive，没有同时启用工坊同项目插件。工坊回下载路径由 Steam 管理，发布不意味着强行切换用户启用路径。

只读的既有磁盘 status.json 已含 `runtime_build=snapshot-native-fix-20261023`、`capture_mode=native`、active=false、render_hook_calls=0。settings.json 的 compatibility_capture=false。该状态是本轮开始前已有文件，不代表本轮启动或实测了游戏，也不能将 inactive 状态的零 Hook 次数当作实际性能数据。

测试结束后比较 AppData 全部文件 SHA256，均与备份前一致。已有人工缓存、机器缓存、工程相关设置及用户选择的 Google 渠道保留，没有删除缓存、重建默认库或更换渠道。缓存无需重新导入。

## 本轮本机无游戏验证

| 检查 | 实际结果 |
| --- | --- |
| Windows Python 3.12 全套 | 202 项执行，200 通过、2 跳过、0 失败 |
| 跳过 | 两项符号链接检查，当前账号缺少相应权限；不算通过 |
| 隔离 MoonSharp/Lua | 49 项通过；模拟引擎对象，不是游戏验收 |
| Tk 真实事件循环 | 100% 字体 DPI、1060×700/1440×900、中英切换、编辑/校对/分页/保存等通过；新增空 ACK 自动回传不弹 messagebox、不覆盖未确认包通过 |
| 冻结 EXE 功能 | 独立临时目录、移除 Python 路径，扫描、内置插件、拒绝覆盖插件、人工缓存导入、拒绝覆盖报告共 5 项通过 |
| 冻结 EXE 默认 MyMemory HTTPS | 失败，服务限流/拒绝，因此必需检查总体 passed=false；没有写成全绿 |
| 冻结 EXE Google 可选 HTTPS | 通过，固定样本约 2.468 秒，不保证持续可用或模组吞吐 |
| 原有真实人工缓存 | 2,759 条逐条本地命中，联网请求 0；含格式标记 24 条保持一致 |
| 本地术语/中文/回退 | 现有中文零联网、用户显式术语优先通过；未命中按 Google 所选渠道的模拟传输回退通过 |
| 只读导入核验 | 另建隔离库重复扫描，4,563 个 XML 前后哈希一致；没有写默认库或执行第三方脚本 |

JSON 专项实际包含：空/截断/非法字节状态不 ACK、不丢 pending；空/截断请求不推进 session/stamp，修复后继续；持续异常指出 status.json、修复后清除；UTF-8 BOM 和共享占用后恢复；相同元数据修复和 ACK 恢复；非法协议仍拒绝。上述断言均在本机回归中通过，Tk 自动回传场景也通过。

人工缓存仍为本机已配对的 NT 与 EA 来源，共 1,614 简体、1,145 繁体记录，实际库无冲突组；冲突排除由隔离 Python 回归覆盖。格式通过不等于逐条人工语义校对，也不意味着所有启用模组都有人工缓存。

云端报告的 202 Python、49 隔离 Lua、Tk 与 Windows EXE 结果另见上游报告；本机实测默认渠道失败与云端成功有差异，未隐藏。OS 150% 缩放、本机游戏帧时间、物品/新页面实际显示、特殊自绘覆盖、游戏停止恢复/再次开启均未在本轮测试。

## 干净发布内容及更新说明

新暂存根目录：`D:/Codex/abysstext-snapshot-publish-20261023/workshop-3823861796/`。精确 8 个有效文件：

1. filelist.xml
2. Lua/Autorun/abysstext.lua
3. Live/Translations.xml（干净模板）
4. Workbench/AbyssText-0.2.0-rc5-Windows-x64.zip
5. Workbench/EXE-SHA256.txt
6. INSTALL.txt
7. HUMAN-MEMORY.zh-CN.md
8. SNAPSHOT-NATIVE-20261023.zh-CN.md

不包含个人缓存、Live 请求/响应/状态、日志、凭据、第三方译文/脚本、模型、游戏 DLL 或存档。桌面 EXE 保持独立 ZIP 结构。发布脚本做语法解析和清单校验，并只从此新暂存目录执行：

```powershell
& 'D:\Codex\abysstext-snapshot-publish-20261023\workshop-3823861796\publish.ps1' -ConfirmUpload
```

[公开更新日志](https://steamcommunity.com/sharedfiles/filedetails/changelog/3823861796) 包含 JSON 竞态重试、不推进 ACK/不丢待确认译文、默认轻量采集、隐藏树跳过、无效属性探测优化、兼容模式的额外覆盖及开销取舍、配套更新与安全重载、人工缓存无需重导入。明确不承诺固定 FPS 提升或彻底消除卡顿。

## 真实游戏边界及下一步

没有启动或操作游戏，也未强关工作台。未替换游戏 DLL、第三方模组或存档，没有 main 合并、新公开 Release 或新工坊条目。

如需继续游戏验收，须先获得用户确认后再启动工作台及不保存的游戏测试会话，核对连接目录、snapshot-native-fix-20261023/native 和“轻量采集”，复测 JSON 弹窗、大页面持续翻译、新页面/物品/提示框、特殊自绘文字覆盖、停止恢复及再次开启。轻量与兼容模式覆盖不完全相同，不能用隔离 Hook 数替代真实帧时间。

本机证据目录 `D:/Codex/abysstext-snapshot-publish-20261023/` 保存 backup/、artifact-info.json、candidate/、local-install-audit.json、package-audit.json、actual-memory-validation.json、python-tests.log、lua-tests.log、tk-tests.log、frozen/、publish.log、download.log、public-verification.json 和公开日志快照；暂存子目录含前后 API 查询、上传回执及逐文件回下载核验。原始个人设置、缓存和真实译文样本只留本机，未提交 Git；凭据未写入证据文件。
