# 本机人工缓存候选准备：2026-10-23

## 源码与候选

工作区最初干净，fetch 后从 884fee8 快进到 d1a342007aef91f3e2cb189e5fcf4687990a9105，没有重置、覆盖或丢弃本地成果。d1a3420 相对运行源码 1c883ded93fe50daef659e335e778b587f7c147f 只增加云端报告与证据，不改变运行代码。

本机已有桌面 `AbyssText-latest-1c883de` 候选，不需要重新下载或构建。实际运行 EXE 的 SHA256、VERSION.txt、三个 ZIP 及本机 LocalMods 插件 Lua 均核对一致。两个同路径工作台进程是父子关系，不能据此宣称启用了两个工作台。游戏配置只启用一个 LocalMods/AbyssTextLive，没有同时启用旧工坊插件。

| 文件 | SHA256 |
| --- | --- |
| Windows ZIP | `049890b4dd8aebb132df06753888fbd17b5726dfbc851a7359298e7d23f3c4a7` |
| Live ZIP | `883bc62c756ec7c0d185b4b838366bbcacea2db691291838562a351b6a166ea5` |
| 源码 ZIP | `4fe3db6faa0dbaa6116b157f5f87d337eb5c35cd88f3f3a64cfabd9490e8228b` |
| EXE | `8a21394e2749f5e8a0c91530c6d4e1f50e062ce08fa9146b835d7daee9561067` |
| 配套 Lua | `d5bbf34b339c5d964dd9db74598f3979fe1960398a2603b30204f3870d91a122` |

自己的程序、插件（含 Live）及 AppData 已备份至本机独立证据目录。发现游戏和候选工作台正在运行后，没有关闭、重载或操作游戏，也没有覆盖程序或插件。用户正在运行的会话不作为本轮游戏验收。

## 本机只读导入

使用实际冻结 EXE 的 `--import-human-memory`，扫描用户数据中的 WorkshopMods/Installed，写入默认 `%LOCALAPPDATA%/AbyssText/human-memory.sqlite3`。识别 53 个有清单的包；实际可靠配对来自本机老虎脱粒机整合包 2861028841（清单版本 1.38）：

| 原模组 | 简体记录 | 繁体记录 |
| --- | ---: | ---: |
| Neurotrauma 3190189044（1.0.36） | 456 | 0 |
| Enhanced Armaments 2764968387（1.42） | 1,158 | 1,145 |
| 合计 | 1,614 | 1,145 |

共 2,759 条记录及 2,759 个互异模组/键/原文/语言组合；本机集合没有冲突组，不能写成真实冲突样本通过。8 次格式拒绝、56 次含糊键拒绝，无解析问题。另用隔离数据库重复导入，前后 4,563 个 XML 的 SHA256 全部一致，重复导入约 1.164 秒。没有运行或启用第三方汉化脚本。

与云端 17,030 条不同是订阅内容不同，不应复制云端第三方缓存补数。目前启用的 Barotraumatic 不在此次可靠配对里；不能承诺其文字走人工命中。

## 本机验证

- Windows Python 3.12：执行 193 项，191 通过、2 跳过、0 失败。两项跳过都是当前账号无符号链接权限，未算通过。
- 35 项隔离 MoonSharp/Lua 桥接检查通过，包括来源 ID；不是游戏验收。
- 真实 Tk 事件循环检查通过：100% 字体 DPI、1060×700/1440×900、中英切换、编辑/校对/搜索、离线人工缓存、草稿保留、保存重开、3000 行分页、未保存取消、长富文本与占位符。未测试 OS 150% 缩放。
- 实际冻结 EXE 移到临时目录、移除 Python 路径后，扫描、内置插件、拒绝覆盖插件、人工缓存导入和拒绝覆盖报告通过（5/6 必需项）。默认 MyMemory HTTPS 被限流，必需项失败，因此 frozen-checks 的 passed=false；Google 可选 HTTPS 通过。保留用户原先 Google 渠道设置，没有自动换渠道。
- 真实本地库全部 2,759 条逐条经过 TranslationCache 返回人工译文，传输函数设为调用即报错，网络请求为 0。包含格式标记的 24 条逐条校验通过；其余条目也通过质量检查。这是格式/链路验证，不是逐条人工语义校对。
- 现有中文零网络返回、实际条目用户术语优先通过；未命中使用所选 Google 渠道的测试传输回退通过。真实 Google HTTPS 另由冻结 EXE 检查验证，未将模拟响应冒称真实翻译。
- 本机数据无冲突；冲突排除由 Python 隔离回归覆盖。

程序在此次 CLI 建库之前已经运行；本轮没有读取其进程内数据库对象，不能声称现有工作台已发现新库。为可靠生效，应保存工程后重开工作台，或使用其后台导入入口重新导入。没有改动当前游戏会话。

## 工坊更新准备，尚未上传

仅目标 3823861796、App 602960，不新建条目。保留中文标题、封面和现有中英文简介，另准备中文更新说明。暂存内容精确为 7 个文件：

1. filelist.xml
2. Lua/Autorun/abysstext.lua
3. Live/Translations.xml（仓库干净模板）
4. Workbench/AbyssText-0.2.0-rc5-Windows-x64.zip
5. Workbench/EXE-SHA256.txt
6. INSTALL.txt
7. HUMAN-MEMORY.zh-CN.md

未携带个人缓存、请求/响应、日志、凭据、第三方译文/脚本、模型或游戏 DLL。桌面程序仍为独立 ZIP，不放入游戏脚本目录。包完整性、内置 EXE、插件与清单校验通过，发布脚本仅做 PowerShell 语法解析，没有调用上传。脚本默认拒绝上传，必须明确传入 `-ConfirmUpload`。没有新建 Release、合并 main 或修改现有公开包。

本机暂存：`D:/Codex/abysstext-human-memory-local-20261023/workshop-3823861796/`。用户确认正式上传后才执行：

```powershell
& 'D:\Codex\abysstext-human-memory-local-20261023\workshop-3823861796\publish.ps1' -ConfirmUpload
```

## 后续验收与恢复

需要用户先确认的游戏操作：保存工作台工程并重开；核对连接 LocalMods/AbyssTextLive 与原先语言对/Google 渠道；在不保存的测试会话中停止试译、必要时重载自己的 Lua、重新试译；验证原有英文物品名称/简介、停止恢复、再次启动以及连续悬停。若要实测此次 NT/EA 人工命中，需要另行确认测试配置，不能悄悄改变当前启用包。后台缓存命中不是游戏显示生效证明。

本机证据根目录 `D:/Codex/abysstext-human-memory-local-20261023/`：backup-workbench、backup-plugin、backup-appdata、processes.json、import-report.json、actual-memory-validation.json、package-stage-audit.json、python-tests.log、lua-tests.log、tk-tests.log、frozen/。原始样本/译文只留本机，不提交 Git。

恢复人工缓存：先退出工作台，再移走本轮新建的 `%LOCALAPPDATA%/AbyssText/human-memory.sqlite3`；原缓存不存在，其他既有设置和机器缓存未主动修改。工作台与插件本轮未替换，备份保存在游戏目录之外，避免被当成重复模组启用。正式上传仍须等待用户确认。
