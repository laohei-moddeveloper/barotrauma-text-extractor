# 译潜人工汉化缓存接入（2026-10-22）

## 结果

已从 Steam 实际获取老虎脱粒机整合包 `2861028841`（1.38.1，内容 manifest `8642401891416651691`）、作者合集中的 24 个其他文本包，并核对可下载的原模组文本。没有执行第三方脚本或启动游戏。

源码分支：`codex/abysstext-workbench`。实现提交：[ca962b6](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/commit/ca962b6e10a90041c2448c072ada2d1c5dfb0523)，Windows 资源清理修正及最终测试源码：[1c883de](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/commit/1c883ded93fe50daef659e335e778b587f7c147f)。本轮只同步源码和候选 CI，不更新工坊、公开 Release 或 main；已有本机发布不变。

## 实际数据与速度

- 导入识别 54 个有可用清单的包；建立 17,030 条带提供者记录。多个提供者对相同配对的记录会分别保留，这个数字不是互异短语总数。
- 去提供者重复后有 13,642 个模组/语言键/原文/目标语言组合，其中 171 组译法冲突，查询拒绝自动采用。
- 对 10,994 个无冲突简体配对逐条调用实际 `TranslationCache.translate`，全部取得对应人工译文，HTTP 请求数为 **0**。繁体已建索引，但没有用同样全量遍历宣称其语义质量通过。
- 云端一次构建约 1.853 秒；上述实际 SQLite 查询中位数 0.0169 ms、P95 0.0346 ms、最大 1.1052 ms。结果只代表该云端桌面路径；不代表本机耗时、游戏总翻译时间或 FPS。
- 配对阶段拒绝 547 次格式质量失败、920 次含糊键（按路线/语言遍历次数计，非互异短语数）。完整包版本、哈希、路线与计数在 `human-memory-20261022-evidence.json`。

## 行为与质量

1. 先匹配人工缓存，再查旧机器缓存或调用所选接口；短名称合并同样先排除人工命中，不浪费外部配额。自定义 AI 和离线模式也可读取该缓存。
2. 用户显式术语优先。当前原文和语言必须一致；有来源时限定模组，有语言键时限定语言键。模糊短词没有来源/键时不猜，同一匹配出现不同译法也不猜。
3. 占位符、颜色标记、换行、边缘空白及非法字符检查不通过则不导入/不使用；原文改变不会沿用相同键的旧句子。
4. SQLite 持久索引按需查找，后台导入，每个 XML 最多 16 MiB，最多 20 万候选。事务失败保留旧缓存；零可靠配对不清空旧缓存。禁止 DTD/实体、链接 XML 和越界文件引用。
5. 插件有界预载读已有包元数据，传递可识别的工坊来源 ID；游戏绘制回调不读数据库、不扫描模组目录、不联网。每请求最多 8 条、可见优先、原并发限制保持。

## 覆盖与来源边界

确认的路线包括 NT 本体/Infections、EA、AA、AOCS、EK 各旧包及现代整合包、Hungry Europans、Abnormalities、Nosophobia、Smarter Bot AI、Backpacks、Ammo Mod、BaroPlus 等。详见 `assets/human-translation-sources.json`。

不是所有合集条目都可可靠配对。部分旧原包已无法获取；NT 各扩展、Aquatic Arsenal、More Unique Weapons、LFB 等缺对应英文或确认来源；脚本拼接句、非普通语言表的故事/对话未静态配对；NEEDS 的 NotWorking 文本未自动导入。精确同名键仍可能有作者译法或同文异义，人工来源不代表绝对语义准确。原桥接最终按字面量更新控件的边界仍存在，不能宣称所有同文异义都已按模组隔离。

译文版权和署名属于老虎脱粒机汉化组及原译者。本仓库只提交导入器、来源路线、聚合证据和自写夹具，不提交第三方译文/脚本/模组包。真实生成的缓存位于云端 scratch，不是本机已安装内容；新工作台让用户从本地订阅文件重建自己的缓存。

## 验证

- 云端 Linux Python 3.12：193 项通过、0 失败、0 跳过。
- 隔离 MoonSharp/Lua 桥接：35 项通过，包含语言包/预制体来源 ID 的传递；不等于真实 LuaCs/游戏验收。
- Windows CI：193 项 Python 通过、0 失败、0 跳过；真实 Tk 事件循环回归通过（含离线人工缓存）；合成吞吐回归通过。首轮验证代码漏关独立 SQLite 读取连接，Windows 清理临时目录失败，已显式关闭并重跑通过。
- 实际冻结 EXE 的 6 项必需检查全部通过：只读扫描、插件资源、拒绝覆盖已有插件、人工缓存导入（含打包来源索引/SQLite）、默认渠道真实 HTTPS、拒绝覆盖报告。Google 实验渠道额外检查通过。默认固定样本 0.984 秒，Google 0.234 秒；不是模组长文本或大陆网络测量，也不保证服务持续可用。
- 三种包一致性审核通过，并下载 GitHub artifact 再核验 3 个 ZIP 的 SHA256 一致。测试源码为 `1c883de`，没有拿旧 EXE 代替验证。

### 候选包与校验和

[Windows CI / 下载 Artifact](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39794249682)，Artifact ID `12433101445`，保留期 14 天。选 `AbyssText-rc5-Windows-candidate`，内部包含源码、Windows、插件 ZIP、SHA256SUMS 与 evidence。本轮不新建公开 Release。版本沿用 rc5，以源码提交与校验和区别于之前的 rc5 发布。

```text
4fe3db6faa0dbaa6116b157f5f87d337eb5c35cd88f3f3a64cfabd9490e8228b  AbyssText-0.2.0-rc5-source.zip
049890b4dd8aebb132df06753888fbd17b5726dfbc851a7359298e7d23f3c4a7  AbyssText-0.2.0-rc5-Windows-x64.zip
883bc62c756ec7c0d185b4b838366bbcacea2db691291838562a351b6a166ea5  AbyssTextLive-0.2.0-rc5.zip
8a21394e2749f5e8a0c91530c6d4e1f50e062ce08fa9146b835d7daee9561067  BarotraumaTextExtractor.exe
```

冻结检查与包审核原始 JSON 另存 `human-memory-windows-20261022-evidence.json`。
- 本机游戏帧时间、多人游戏、真实背包/模组完整界面：本轮未验证；没有控制桌面、游戏或修改第三方文件。

## 本机启用

更新工作台及自己的配套插件后，在侧栏选择“导入工坊人工汉化缓存…”，指向含原模组和汉化包的 `WorkshopMods/Installed` 或 Steam `workshop/content/602960` 目录。无需启用汉化包脚本。一次导入后持久复用，更新原包/汉化包后重新导入。默认缓存为 `%LOCALAPPDATA%/AbyssText/human-memory.sqlite3`。

详细使用和回退见 `docs/HUMAN-MEMORY.zh-CN.md`。本轮没有安装或替换用户本机 EXE、插件，也不声称用户已实际启用这些改动。
