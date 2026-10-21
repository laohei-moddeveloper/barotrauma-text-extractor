# 译潜 AbyssText rc4 云端交接 · 2026-10-22（香港时间查收）

云端完成时间：2026-10-21 23:52 HKT。本轮云端可做的修复、回归、Windows 构建、实际 EXE 验证及打包已完成；**真实游戏未验收，本机仍是 rc2，云端没有替换本机程序**。

## 提交、PR 与候选定位

- 仓库仅操作 barotrauma-text-extractor；初始 fetch 后分支为 `codex/abysstext-workbench`、提交 `735714eb352ecc883e123045cb9323defba157d3`，工作区干净，没有需要覆盖或清理的用户未提交改动。已阅读 AGENTS.md 及两份交接/根因文档。
- 候选版本：`0.2.0-rc4`；[构建源码提交 b49d535](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/commit/b49d53519b170781982e9cc061e391bc2807ab4a)。本轮提交串：eb48a55（TLS/桥接/缓存）、a6521b0（Windows 编码）、a2ce51b（语言切换及验证环境）、64aba8e/b49d535（交付包审计）。
- [PR #1](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/pull/1) 继续保持草稿、开放状态，目标 main；已同步同一任务分支。没有合并 main、创建公开 Release 或更新创意工坊。
- [最终 Windows CI](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39628964102)：成功。[下载唯一推荐的 rc4 候选附件](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39628964102/artifacts/12358810774)：`AbyssText-rc4-Windows-candidate`。请勿混用之前失败运行中的同名候选包。
- 此候选包绑定上述构建提交；随后最终交接报告提交只更新 `research/handoffs/`，不改变运行代码、版本号或已经验证的二进制。源码 ZIP 内含构建时的预交接记录；最终结果以 PR 分支本文件及同目录验证回执为准，避免报告引用自身校验和产生循环。

## 根因与实际修复

用户本机已确认的 rc2 根因：修改过的 Python 3.12 SSLContext 会读取 ssl.py 相邻的 `codex-rejected-cas.pem`；PyInstaller 漏包，创建上下文即抛 FileNotFoundError，**尚未发送翻译请求**，却被归为网络超时。rc3 已在用户本机打包 EXE 返回“打开舱门”、约 2 秒，但未覆盖正在运行的 rc2；该历史证据不当作本轮 rc4 或游戏通过。

rc4 具体改动：

1. 保留从实际构建解释器发现并原样打包 TLS 策略资源。普通 CPython 不要求 Codex 专属文件；修改过的解释器声明依赖却找不到资源时直接构建失败，不再悄悄产出坏包。隔离回归覆盖两类解释器及缺失资源，不硬编码个人路径，不修改证书策略，不关闭证书/主机名验证。
2. 默认免费联网逐条区分直接/URLError 包装的资源缺失、SSL 证书/握手错误、暂时网络错误及额度错误；TLS 错误不伪装超时、不盲目自动重试。拒绝畸形 JSON/响应结构、空白或非字符串译文，单条失败不丢同批成功结果及后续批次。
3. 缓存写盘失败仅告警，继续后续批次并保留内存中的成功结果；缓存命中仍检查格式，不合格缓存淘汰重译；取消状态不能通过缓存命中绕过。暂时网络失败按条目冷却 30 秒、同会话最多 2 次尝试，其他正常条目继续；403/429 或额度错误才使提供方整体冷却 1 小时。
4. 修复单文件邮箱 `requests.json` 在桌面确认导入前被可见提示框请求覆盖而丢失整批的问题。未确认时保留原请求；匹配的部分响应确认导入后，可见提示框仍优先进入后续请求。
5. 回传补上会话/源目标语言；Lua 校验请求及这些范围。桌面结果、错误、缓存告警和任务完成事件都检查任务编号及会话/语言对，旧任务不能解除新任务 busy 或污染新状态。重连清理旧调度，停止取消本次游戏自动任务；旧启动延迟回调用 generation 隔离。桌面切换语言暂停自动试译，等待游戏停止再开启的新请求。
6. 保留默认免配置 MyMemory 免费 HTTPS、已有译文不覆盖、英文→中文时保守跳过已有汉字/中英混合文字、可见文字优先、缓存。游戏每批最多 8 条、桌面每次调度 4 条、最多 2 个联网请求并发；可选自定义 AI 批次也限制最多 8 条。没有改成必须手填 API 或仅本地 AI，没有下载模型或调用收费服务。
7. CLI 的 `--check-online NEW_JSON` 拒绝已有文件/符号链接及冲突参数，使用独占创建防止请求期间其他进程创建文件后被覆盖；输出失败有明确退出码。Windows CLI 重定向输出显式 UTF-8，修复英文系统编码导致中文诊断异常退出；测试文件显式 UTF-8，不靠 CI 强开 UTF-8 掩盖问题。
8. 分支原来没有可用的 `.github/workflows`；新增仅任务分支推送触发的 Windows 候选工作流，构建、检查 EXE 版本、实际执行无窗口 EXE、打包与审计并上传私有附件。后续只有交接资料变更不重复构建，不写 main 或发布 Release。

## 分层验证结果：通过 / 失败 / 跳过

| 层次 | 最终通过 | 最终失败 | 跳过 / 未验证 | 证据与限制 |
| --- | --- | --- | --- | --- |
| Linux Python 3.12.14 源码回归 | 105 项 | 0 | 0 | `python -m unittest discover -s tests -v`；含 TLS、逐条失败、缓存、取消、语言切换、重试上限、旧事件隔离等；不等于 EXE 或游戏 |
| Windows CI Python 3.12.10 x64 源码回归 | 105 项 | 0 | 0 | 最终 Actions python-tests.txt；0.900 秒。此 runner 可创建符号链接，本轮没有权限跳过；用户本机此前 85 通过/1 权限跳过是另一份历史结果 |
| LuaCs/MoonSharp 隔离执行 | 26 项 | 0 | 0 | [逐项日志](abysstext-rc4-lua-isolated-checks.txt)；.NET 8.0.32 + 已有 LuaCs MoonSharp DLL，模拟游戏对象和 Hook，不启动真实游戏 |
| Windows 实际冻结 EXE | 5 项 | 0 | 0 | [EXE 回执](abysstext-rc4-frozen-checks.json)，独立临时目录、PATH 仅 System32，无 GUI；见下 |
| 三个 ZIP、摘要及包内一致性 | 审计通过 | 0 | 0 | [包审计/联网回执](abysstext-rc4-package-audit.json)；Windows CI 内核对，Git 换行规则纳入比较 |
| 云端下载附件再次本地复核 | 0 | 下载受阻 | 未完成 | 附件存储域 CONNECT 返回 403；没有宣称已在 Linux 下载并复核二进制。Windows CI 已读回 ZIP、计算摘要、逐文件检查并上传，用户明日浏览器下载后再核对 |
| 真实游戏/当前 LuaCs 接口绑定/第三方 Hook 共存 | 0 | 未判定 | 未执行 | 用户亲自验收；没有控制桌面、启动游戏或修改游戏 DLL |
| rc4 桌面 UI 视觉/真实 FPS、帧时间/用户修改过的 Python 上重打 rc4 | 0 | 未判定 | 未执行 | 不用历史 rc3、模拟对象或普通 Windows CI 冒充这些检查 |

实际 EXE 5 项分别是：只读扫描自建 XML 测试模组且原文件不变；安装内置插件并核对三份资源字节；已有插件目录拒绝覆盖且内容不变；实际免费 HTTPS 翻译；已存在联网检查报告拒绝覆盖。预期的拒绝覆盖退出码 1/2 是测试通过，不是验收失败。

最终 EXE `--check-online` 输出：`ok=true`、`translation=打开舱门`、`issues=[]`、`elapsed_seconds=1.0`，退出 0。这是固定样本联网路径内部计时，不是 EXE 完整启动时间或游戏翻译完成时间。未使用模拟翻译回包来代替这一项。

Lua 26 项包含 700 个语言键有界分批不丢失、物品/Buff/生物/任务/职业字段、富文本与 tooltip 优先、既有中文跳过、换回合持续采集、停止恢复/同缓存再启用、未确认请求保留、错会话/错语言拒绝及旧延迟回调失效。引用的 MoonSharp DLL SHA256：`5eee2f74079cb48018a5f9b1a55d3856c283858fb6a04c6a70adccc27df254ba`，只用于隔离检查，没有把游戏/第三方 DLL 打进交付包。

复现 Lua 隔离检查时，先自行提供可用的 LuaCs MoonSharp.Interpreter.dll，再执行：

```console
dotnet run --project tools/live-tests/LiveTests.csproj -p:MoonSharpAssembly=<已有DLL的绝对路径> -- live-mod/AbyssTextLive/Lua/Autorun/abysstext.lua
```

### 本轮失败及修复历史

- [首次 Windows CI](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39627611517)：104 项中 4 个断言失败、2 个异常；暴露测试读取中文依赖默认编码，以及真实 CLI 输出编码导致错误退出。均已修复，未通过项没有被直接删除或改为跳过。
- [第二轮](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39627826036)：Windows 源码回归和 EXE 构建通过，但新增验证脚本将 Windows 环境字典中的 SYSTEMROOT 写为 SystemRoot，脚本在执行 EXE 前失败；修正为正确键名。
- [功能与 EXE 通过轮](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39628062627)：源码 105 项和实际 EXE 5 项通过，随后增加独立包内容审计。
- [第一次包审计](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39628649779)：源码/实际 EXE 均通过，但审计错误地以原始 Git blob 比较会经过 Git 换行规则的导出文件，报 `.gitattributes` 不同。修正为按仓库 Git 属性比较，并验证 LF/CRLF 两种规则。
- 最终推荐运行是 [39628964102](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39628964102)，全部通过；此前失败运行不作为交付包。

## 包、SHA256 与安装说明

附件内 `0.2.0-rc4/` 提供源码、Windows x64、干净插件 ZIP、SHA256SUMS.txt 与 EXE-SHA256.txt；`evidence/` 提供原始 Python 日志、Windows 版本、实际 EXE/联网回执及包审计。没有模型、第三方模组/游戏 DLL、登录凭据或运行期 requests/response/settings/status 数据。

| 文件 | SHA256 |
| --- | --- |
| `AbyssText-0.2.0-rc4-source.zip` | `1710f525c975f96d1a3a826ddabef66d4b56b86ee7b773bf19bcb40dc4d87de5` |
| `AbyssText-0.2.0-rc4-Windows-x64.zip` | `f8548cf9a2c046b1c9ed209b3aad0f8e0352bf23b05970d0e425ab03268f7926` |
| `AbyssTextLive-0.2.0-rc4.zip` | `378c3a61bde3da3087fa9bd17c7f7300c17d93f44de6bbd0b5d1b80238085f13` |
| Windows ZIP 内 `BarotraumaTextExtractor.exe` | `fa9bc00dccd0046106171f07c26773c6c943345ea4f7d8469f3aa7aebe6806ea` |

Actions 外层附件 ZIP 的服务端 SHA256 为 `2ff9ea973a09cb3d6520699ea10c21c8de486ef43158b634830141ef74b6a7b4`，约 12.9 MB，与上表三个内层 ZIP 的摘要不同。附件保留至 **2026-11-04 15:49:08 UTC**（香港 23:49:08）；明天可从上面的附件链接登录 GitHub 下载，过期后可按构建提交和工作流重新构建，不保证重构建的二进制摘要相同。

CI 已确认 Windows ZIP 中 EXE 摘要等于实际测试 EXE、插件只含自己的三份资源与版本/安装说明、源码 ZIP 含全部 tracked 文件且符合构建提交的 Git 换行属性。标准 SHA256SUMS.txt 只列三个 ZIP；EXE 摘要单列，便于下载后核对。

完整安装与回退见 [INSTALL-rc4.zh-CN.md](../../docs/INSTALL-rc4.zh-CN.md)。

## 实际覆盖与剩余问题

- 持续读取已加载 Item/Affliction/Character/Mission/Job 公开 prefab 和语言表，覆盖可访问的名称、简介、症状说明、任务成功/失败及消息等。原生 GUI、字体绘制和 tooltip 观察到的任务/对话也可入队；某条内容能否采集仍受实际 getter 和显示路径影响。
- 未保证覆盖图片文字、自定义绘制、未加载/未触发内容、所有对白路径、复杂动态 getter、特殊字体重载、第三方 Hook 冲突和所有布局。字体/控件宽度和缓存界面可能需要重开。字面量同文异义仍需上下文拆分/人工适配；格式通过不代表译文语义正确。
- 英文→中文按普通范围汉字保守跳过混合文本，可能保留其中未译英文；稀有扩展汉字不能保证识别。不是完整语言识别或“全覆盖”承诺。
- 每步最多访问 32 个 prefab，每个可读取多个字段；语言表/队列分步推进。队列/已见身份/控件/缓存有限额，达到限额会漏采；桌面项目与回传词典随已导入数据增长，不宣称恒定内存或实测 FPS 提升。可见内容优先不能抢占已经发出的 HTTP 请求；停止后当前请求可能等到响应或超时才结束。
- 免费服务有日额度、可用性和翻译质量限制，分段会损失上下文，大项目不会瞬间完成。额度恢复仅做了隔离回归，没有通过耗尽真实额度来验证；切换/重启会话不等于重置提供方额度。私密文本不要发到该第三方服务。
- 逐条失败隔离与有限重试描述针对默认免费入口；可选自定义 AI 仍按批次完整性校验，失败批次不写入，本轮未调用真实自定义/收费接口。
- 普通 Windows CPython 的 rc4 实网成功，不证明已在用户修改过的 Python 上重新打包 rc4 的额外 PEM。该路径由隔离资源回归及用户此前 rc3 证据支持，若用户未来自己在那个环境重新构建，需再次检查 EXE 资源及 --check-online。

## 明天本机需执行的步骤

1. **先保存项目、停止旧试译并退出 rc2。** 本机没有被云端更新，rc3 也只是此前构建验证；明天可直接使用本次 rc4 候选，不必先安装 rc3。
2. 下载本报告指定的最终附件，核对三个 ZIP 的 SHA256；解压 Windows ZIP 到新目录。备份自己的旧 EXE、AbyssTextLive 和 Live/项目数据，不动游戏 DLL、第三方模组或存档。不要继续点旧快捷方式。
3. 先自行运行新 EXE 的 `--check-online 新的JSON路径`，确认 ok/translation/issues。若失败，保留 JSON 和错误，不反复刷额度；这一步仍不代表游戏通过。
4. 游戏退出时只更新自己的 AbyssTextLive：把旧目录备份到 LocalMods 外，再解压干净插件包或用 EXE 安装到新目录；安装器拒绝直接覆盖。不要把备份中的旧 requests/response/status/settings 复制回新插件。自己的工程/翻译缓存可保留。
5. 你自行启动游戏或在支持时自行重新加载 Lua，确认 LuaCs 客户端与自己的插件启用；打开新工作台并连接新插件目录，用默认免费模式、English/Auto→Simplified Chinese 一键试译。运行中改语言对要先停止再开始。
6. 人工检查物品/生物名称简介、症状、任务/对话、提示框/下拉框、已有中文、占位符/颜色/换行；再检查换回合、新文本持续采集、断网恢复、停止与再开启。记录版本、截图、复现步骤和错误；结果不足前不发布工坊或公开 Release。
7. 如要回退，保存退出新工作台并停止试译，恢复自己的 EXE/插件备份，再自行重载客户端/重开缓存界面。不要恢复或替换第三方文件。

本轮没有控制桌面、启动游戏、替换游戏 DLL、修改第三方模组/存档、下载模型、调用收费服务或向其他本地对话发送操作指令。没有创建定时主动通知；本报告和云端最终回复供你明天打开后查收。
