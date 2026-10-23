# 卡顿修复候选：工坊正式更新回执（2026-10-23）

## 实际结果

已获用户本轮明确上传授权，更新原有 [工坊条目 3823861796](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)，App ID 602960，没有创建新条目。Steam Submit 返回 OK；更新后重新查询简体中文及英文内容，更新时间均为 **2026-10-23T02:46:17Z（北京时间 10:46:17）**，晚于上传前。

标题保持：**泥偶迅猛龙汉化——游戏内一键实时汉化工具|游戏外快捷翻译工作台**。上传仅设置内容目录、中文更新日志和构建元数据；没有设置标题、简介、封面或依赖。前后查询确认两种语言的标题、完整简介、封面 URL 均一致，公开可见状态仍为 Public。

已真实回下载 8 个文件，逐个 SHA256 与上传清单一致，没有旧文件残留；再次从回下载 Windows ZIP 内取出 EXE 核验哈希和 VERSION.txt，并检查回下载插件的运行标记。不是仅凭退出码认定成功。

## 源码、候选与校验

工作区开始干净，从 1ace363 fetch 并快进到报告提交 `26c109c`，无覆盖或丢弃未提交成果。相对构建源码，该报告提交只补充报告和证据。下载指定 [CI](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39889590638) 的 Artifact `12474151479`，API 元数据记录的构建源码为 **c337f2c0a69768aec85b04bf066ed1675d9e9a68**。Artifact 外层 SHA256 与 GitHub 元数据一致，内层三 ZIP 完整性及 SHA256 均通过。

| 文件 | SHA256 |
| --- | --- |
| Artifact 外层 ZIP | `6bf7800298c17c70f3f7f1c2bdd7c6bf08405be1b1bc542438f27744b27b30ec` |
| Windows ZIP | `f051ce37faecd764b42f38474f612741ee4c0252f6159bb51ca8bde54dcb9aee` |
| 插件 ZIP | `8bfeb7226b5b37badd5715cca25cc97bf4a6698380328e3a5379fddca275fa45` |
| 源码 ZIP | `156409892b61429f0803c4930fbfa1b12b710826ea6b7db1fa6cc5e523e42884` |
| ZIP 内 EXE，上传前及回下载后 | `ca2492429663ad701581b789a6fee2d705c41534267bdaf12ba32faaedfafca2` |

Windows ZIP 和插件 ZIP 的版本文本均绑定上述 c337f2c 完整提交。插件 ZIP 的三个有效文件逐字节匹配当前分支源码；运行标记 **bounded-render-fix-20261023**。没有使用此前 1c883de 或旧公开 rc5 包。

工坊 API 回读的 Metadata 包含 runtime=c337f2c 完整提交、build=bounded-render-fix-20261023、Windows ZIP SHA256 和 EXE SHA256，均与本次上传清单一致。回读内容大小为 17,408,753 字节。

## 发布内容与更新日志

在新的独立目录重建清单，只发布以下 8 个文件：

1. filelist.xml
2. Lua/Autorun/abysstext.lua
3. Live/Translations.xml（仓库干净模板）
4. Workbench/AbyssText-0.2.0-rc5-Windows-x64.zip
5. Workbench/EXE-SHA256.txt
6. INSTALL.txt
7. HUMAN-MEMORY.zh-CN.md
8. RENDER-PERFORMANCE-20261023.zh-CN.md

桌面程序仍位于可解压的独立 ZIP，不作为游戏 Lua 执行。没有个人缓存、Live 请求/响应/状态、日志、凭据、第三方译文/脚本、模型、游戏 DLL 或存档。Windows ZIP 内文件也核查了敏感/运行时文件名称。

正式上传命令指向新目录，未调用上一轮旧暂存目录：

```powershell
& 'D:\Codex\abysstext-render-publish-20261023\workshop-3823861796\publish.ps1' -ConfirmUpload
```

[公开更新日志](https://steamcommunity.com/sharedfiles/filedetails/changelog/3823861796) 实际 HTTP 200，包含以下全部行，已逐行核对：

> 大量文本与持续试译卡顿修复（构建 c337f2c / bounded-render-fix-20261023）
>
> · 减少大量文本及持续试译时的重复控件处理和临时对象创建。
>
> · 缓存提示框与数字模板，逐步清理旧页面引用。
>
> · 合并语言资源刷新，保留可见文字优先。
>
> · 保留人工汉化缓存及来源字段兼容修复。
>
> · 请更新程序和配套插件后，在安全时机重启游戏或重载插件；已有人工缓存无需重新导入。
>
> 本次通过的是隔离检查与 Windows 程序检查，不是真实游戏帧率验收；不承诺固定 FPS 提升，也不保证消除所有卡顿。

## 验证边界与本机状态

- 本轮本机执行的是候选获取、清单/哈希/标记校验、正式上传、Steam API 元数据与更新时间回读、真实回下载、公开日志核验。
- 195 项 Python、42 项隔离 Lua 及 Windows 冻结 EXE 检查来自指定构建的云端/Windows CI 证据，本轮没有重新执行，也不代表本机真实游戏验收。
- 没有操作、关闭或重启正在运行的游戏，没有覆盖运行中的 EXE、LocalMods 插件、第三方模组、游戏 DLL 或存档。回下载由 Steam 写入该条目的 Workshop 下载目录；这不等于当前 LocalMods 版本或游戏内存中的旧 Lua 已经更新。
- 用户需在安全时机保存工程、使用包内新工作台，并更新/启用配套插件后重启游戏或重载 Lua；只启用一个 AbyssTextLive。核对实际状态 runtime_build，再比较大页面、持续翻译和停止恢复。已有人工缓存无需重新导入。
- 没有合并 main、创建公开 Release 或新工坊条目，没有索取或公开凭据。

原始证据只存本机 `D:/Codex/abysstext-render-publish-20261023/`：artifact-info.json、artifact.zip、candidate/、package-audit.json、publish.log、download.log、public-changelog.html、public-verification.json；子目录 workshop-3823861796 内有内容清单、before-submit.json、submission-receipt.json、publication-receipt.json 和 download-verification.json。凭据未写入这些材料。
