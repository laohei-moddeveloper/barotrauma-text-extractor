# AbyssText 本地复用与持续翻译减负（2026-10-23）

## 当前结果

最终运行源码为 `314c95b809523b31d9312fdb73ed5e7d5cafb77e`，保留分支 `codex/abysstext-workbench`。版本仍是 0.2.0-rc5，运行标记 `local-reuse-fix-20261023`。本报告提交只更新证据，不把报告提交冒充已构建运行版本。

本轮没有控制用户电脑、启动游戏、替换游戏 DLL、改动第三方模组或存档。本机与工坊当前安装不会因云端推送而自动变更。用户已明确授权这轮通过云端更新现有工坊条目，仍需有效 Steam 身份才能执行。

## 落实的改善

1. 离线复用优先读取来源可靠的人工汉化，再读所选渠道、语言对及术语策略匹配的机器译文缓存，并支持能够确定的术语/医疗模板。未知条目不拼凑猜译、不联网。用户术语优先、冲突拒绝和格式校验保持。
2. 短名称合并中的缓存命中直接产出，避免同一人工命中在预检和单条翻译中重复查询；四条命中的回归验证为四次查询、零 HTTP。冷条目的独立网络回退保留。
3. 持续游戏翻译把桌面表格重绘合并为约 250 ms 间隔，立即回传结果，结束立即显示最终列表。
4. 单包只需 8 条，不再对整个积压队列完整排序。20000 条候选合成对照中，平均选择时间 4.16→1.54 ms；该段临时分配峰值 1488024→623 bytes。输出顺序相同。只计选择算法，不能解释为全流程内存、FPS 或网络加速。
5. 游戏控件仍检查文字变化，但字典版本及当前文字均未变时跳过重复翻译应用查询。隔离检查连续观察 20 次为零重复查询；后续内容变化、翻译、校对、删除和停止恢复均验证。

默认轻量采集与可选兼容采集保留，仍无游戏内联网、无额外并发，不自动切换翻译渠道。首次未知长文本仍受免费服务延迟/限流影响。自绘界面、树外控件和 TextGetter 覆写的文字仍可能漏采。

## 验证发现并修复的实际问题

- 首轮 Windows Tk 检查 39900178478 失败：同一轮连续收到译文时，当前编辑框尚未同步，下一次 commit_editor 会把刚收到的译文覆盖为空。已使选中条目的编辑框立即同步，与表格合并重绘分离，增加确定性回归。
- 中间版本 c191022 的完整 Windows CI 成功，但随后 Windows 2022 私有发布检查 39900799522 暴露重启请求偶发漏读：相同长度的 Lua 原地写入可能有相同时间戳。已对请求读取稳定内容摘要，不能只凭文件元数据跳过；相同摘要则不重复解析 JSON。半写入仍不推进请求/ACK，并增加同时间戳回归。没有把前一次偶然通过当成根因已经排除。

## 最终验证

- Linux Python：211 项通过，0 失败，0 跳过。
- 隔离 MoonSharp/Lua：50 项通过；没有真实游戏和 FPS 验收。
- Windows CI [39901018518](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39901018518)：211 项 Python、真实 Tk 事件循环、实际冻结 EXE 六项必需检查、可选 Google HTTPS、三种包审计均通过。
- 实际 EXE MyMemory 固定样本“打开舱门”1.485 秒，Google 样本“打开舱口”0.250 秒；复合生物名称检查“画皮泥偶迅猛龙”通过。这些是一次固定探测，不是持续吞吐承诺。
- 下载最终 artifact 并独立核对三种 ZIP SHA256。证据见 `local-reuse-windows-20261023-evidence.json` 和 `local-reuse-selection-20261023-evidence.json`。

下载：[最终候选附件](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39901018518/artifacts/12479330085)，需要 GitHub 登录，受 Actions 保留期限制。

| 文件 | SHA256 |
|---|---|
| Windows ZIP | `39dfb2ad3b23f69a52ceffb50075aac686475104cb55f2d3b223e18225ac952e` |
| 插件 ZIP | `14faa5bdf21a9e2f4746831a0a69e40d5feddd4bb37fe25d97e9d7d054857304` |
| 源码 ZIP | `5ffa10f2029236ae24ea42e4f679bb0a399a9cf55e7619233fe7b529111e133a` |
| EXE | `733064f699f254d02a9b493f28c9dbab4c52b340211a181836cf70b7bb46f9a3` |

## 云端工坊发布

新增私有发布自动化分支 `codex/abysstext-cloud-workshop`，PR https://github.com/laohei-moddeveloper/tsm-wiki/pull/5 。只修改发布工具和工作流，不改 wiki 页面、不合并 main、不创建公开 Release。

固定现有 App 602960 / 工坊条目 3823861796。Windows 构建通过 Python、Tk、实际 EXE 与包审计后，才生成十个明确允许的运行/安装文件；发布阶段验证作者及实际登录账户，不更改标题、简介、封面、可见性，上传后回下载全部文件逐个核对 SHA256。自动化本地 13 项 Python 和 2 项加密缓存检查通过。实际 Steam 登录及回下载仍未执行，模拟检查不代表登录可用。

真实云端发布预检 [39900682987](https://github.com/laohei-moddeveloper/tsm-wiki/actions/runs/39900682987) 明确失败：私有仓库工作流没有收到 STEAM_USERNAME、STEAM_OWNER_ID、STEAM_CONFIG_VDF。当前 GitHub 连接访问 Secrets API 为 403，无法代填。已经向用户请求通过 GitHub 的安全配置页面填写，未要求把凭据发到聊天。工坊本轮尚未更新。

配置后，使用私有库 steam-workshop.yml、ref codex/abysstext-cloud-workshop、target abysstext、完整 source_ref 314c95b809523b31d9312fdb73ed5e7d5cafb77e、publish=true 继续；无需再次请求发布授权。所有者公开 SteamID 已由 Steam 官方详情核对为 76561199532676984，STEAM_USERNAME 仍必须是此作者账户的登录名。

## 本机后续验证

由用户在安全时机一并更新工作台与插件，保留个人缓存。检查轻量模式及 runtime_build；在同一大量文本页面长时间翻译，记录开始和积压清空后的帧时间、桥接状态、失败原因。核对已译文不被编辑框回写清空、重启会话仍继续提交；离线模式命中缓存且未知内容不联网。游戏内帧率、特殊界面覆盖和实际 Steam 认证不在已通过范围内。
