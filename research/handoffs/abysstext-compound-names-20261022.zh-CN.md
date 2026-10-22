# 连写生物名称：2026-10-22 补充交接

此补充候选仍标记 **0.2.0-rc5**，绑定源码 [81af2b2706343f51e6a3404f95bc57243483a14b](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/commit/81af2b2706343f51e6a3404f95bc57243483a14b)。不要与早先 rc5 的 `f416817` 包混淆；下载下列最新 CI 附件，解压后检查 VERSION.txt 的提交号。本文件和证据随后单独提交，不改变已测运行代码。

## 行为

- `huskmudraptor`、`HuskMudraptor`、`HUSKMUDRAPTOR` 均可直接本地组合为“画皮泥偶迅猛龙”，无需网络。完整单词须能被 2–4 个内置生物名完整且唯一拆开；不做任意子串替换。
- 确认属于生物名称/介绍的文字，或有明确 CamelCase 边界的名称，支持已知词在前、在后或两端。未知中间部分在同一次免费联网请求中翻译，已知词用保护标记固定游戏译名，仍保留周围句子、富文本和占位符。
- 例如 `huskabysswalker`、`abysswalkerhusk`、`huskabysswalkermudraptor`（生物字段）。字母全小写且没有生物元数据的部分匹配不强拆。未知片段仍可能被免费服务错译或原样保留，不保证作者认可的译名。
- 完整项目术语/短语优先于拆词；组件的项目术语也优先。若 `AbyssWalker` 已有项目译名，`HuskAbyssWalker` 可以全部本地组合，不需联网，也不会为了拆 CamelCase 而破坏该术语。
- 只处理送去翻译的副本，不修改原文件、游戏标识符或名称。内部含下划线/数字的标识符、未知前后缀、常见词形及歧义组合不强行命中。
- 拆词策略版本已更新，旧在线缓存不会串用；**已有工程中的草稿/译文仍不自动覆盖**。要修正已保存的旧译名，请备份后清空对应草稿，再停止/重新开启试译。

## 速度与验证

没有增加正常 HTTP 次数、联网并发、轮询频率或游戏线程工作。完整已知组合直接本地返回；未知部分与保护标记共用一次请求。使用有界动态规划、最大词长 64 字母和两个各 512 项的分析缓存，避免无限猜词。完整拼接最多 4 段，部分匹配每侧最多 3 个已知生物名、未知段至少 3 个字母。

本地计算仍有少量成本，不能保证零开销。若服务破坏保护标记，安全回退仍可能追加请求，不为速度接受错误格式。

- Linux Python **169/169**、Windows Python **169/169**，均 0 失败/跳过；覆盖前后/两端、大小写、未知片段、完整与组件术语优先、格式保护/回退、旧缓存隔离及防误拆。
- 最新 [Windows CI 39714943564](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39714943564) 成功；实际 Tk 事件检查、合成桥接对比、构建和包一致性检查通过。
- 实际 Windows EXE 核心 **5/5**；默认 HTTPS 成功（1.000 s），Google 可选 HTTPS 成功（0.703 s）。实际 EXE 另执行不联网的 `HuskMudraptor` 检查，返回“画皮泥偶迅猛龙”。完整回执见 [包审计](abysstext-compound-package-audit.json) 和 [冻结程序检查](abysstext-compound-frozen-checks.json)。部分未知名称的 EXE 专项实网未单独执行，源代码实网如下。
- 两个免费渠道各测前置、后置、两端三个自建生物名，共 **6/6 次成功，每条均 1 次 HTTP**，游戏词保留正确；未知部分的译法有渠道差异。[实网原文和输出](abysstext-compound-real-network.json)。这不是全语义准确率，也不是大陆本机网络保证。
- 无网络合成：同版本 1000 个有空格名称 vs 相同连写名称，本地总耗时 **0.5283 / 0.5275 s**，均为 1000 次模拟 HTTP；10000 次热缓存读取 **0.5914 / 0.6171 s**，均新增 0 次 HTTP。只比较这些输入形态的本地处理，不是游戏 FPS 或严格统计的前后性能承诺。[原始数据](abysstext-compound-overhead.json)。

本补充没有更改 Lua 插件的三个有效载荷文件，沿用既有 32 项隔离检查记录；没有重测真实游戏。没有控制桌面、启动游戏、替换游戏 DLL、修改第三方模组或存档、下载模型或调用收费服务。

## 下载、校验和、本机操作

[最新私有候选附件](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39714943564/artifacts/12398628009)，保留至 **2026-11-05 11:06 香港时间**，需登录有仓库权限的 GitHub 账号。3 个 ZIP 和 SHA256/EXE 校验文件齐全；云端已下载，逐文件复核源码与 Windows Git 换行属性、插件和已测 EXE，见 [下载复核](abysstext-compound-cloud-audit.json)。

```text
348beeb201d15ff6a8a266d6f065859933ede6ed6cb224e231fa210d4114c1c3  AbyssText-0.2.0-rc5-source.zip
e35a28699365af51b2f2a5aa79362299c96ee9ee0b7d4a4e980aba9fa0051a12  AbyssText-0.2.0-rc5-Windows-x64.zip
508786655c145c2a291fb2f8cb7da7406dd78ba4939d82d0a9ad7737d4dc04ec  AbyssTextLive-0.2.0-rc5.zip
56a80c1216847603eebf4cf240b001525bd9392d5a14c67453ebf6bba7b6cd5c  BarotraumaTextExtractor.exe
```

如果已安装匹配的 rc5 插件，此补充只需退出旧工作台后更新工作台；更早版本按 [安装说明](../../docs/INSTALL-rc5.zh-CN.md) 一起更新自己的工作台/插件。检查新目录 VERSION.txt 的提交号，再自行进行游戏验收。旧错误草稿不会自动重译。云端副本在 `/workspace/shared/downloads/rc5-compounds/contents`，没有下载到或替换用户电脑。

源码仍同步原分支，PR #1 保持草稿；未合并 main，未发布公开 Release 或工坊。
