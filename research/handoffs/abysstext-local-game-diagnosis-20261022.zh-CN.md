# 本机游戏排查：2026-10-22

## 结论及验收边界

**尚未完成人物物品栏真实游戏验收，不能宣称整体修复成功。** 已在真实游戏潜艇编辑器观察到同一个 Pressure Injector Headset 的名称和整段简介由英文变成中文。用户手动启动试译和悬停物品，Codex 读取画面及本机文件；自动输入不能可靠触发游戏操作。随后电脑操作工具检测到用户物理 Escape 并停止，本轮未继续发送桌面输入。

未完成：人物物品栏至少三个样本、修复候选的同物品前后对照、停止恢复和再次开启、真实动态占位符/连续悬停帧时间。不能用下面的隔离检查代替这些项目。

## 现场与构建

- 工作区原先干净；fetch 后从 735714e 快进至 4385769，没有覆盖未提交工作。
- 原工作台 VERSION.txt 绑定 `81af2b2706343f51e6a3404f95bc57243483a14b`。
- 原 EXE SHA256：`56a80c1216847603eebf4cf240b001525bd9392d5a14c67453ebf6bba7b6cd5c`，与交接包一致。
- 原工作台位于桌面 `AbyssText-rc5-Windows-candidate/0.2.0-rc5/AbyssText-0.2.0-rc5-Windows-x64/AbyssText/`；仍在使用这个 EXE，没有趁游戏测试覆盖正在运行的程序。
- 游戏：`D:/steam/steamapps/common/Barotrauma/Barotrauma.exe`，画面显示 **1.13.4.0**、引擎修订 `0d380afcd1`；LuaCs 显示 active、C# enabled。进程未提升管理员权限。
- 游戏配置确实启用 `LocalMods/AbyssTextLive/filelist.xml`，控制台也显示从该目录执行 abysstext.lua。
- 工作台连接 `D:/steam/steamapps/common/Barotrauma/LocalMods/AbyssTextLive`。游戏语言简体中文；桌面 Auto、插件实际 English → Simplified Chinese。
- 原插件 Lua SHA256：`8e7f4949788614b31009f94177a6f07fe6eb40a8796a3e044a73a646b1cc773b`，与任务分支一致。
- 最初试译 inactive，可用译文 0；没有重装、清缓存或清草稿。先备份自己的整个插件及桌面缓存/诊断数据。

## 已确认的故障及真实链路

1. 默认 **MyMemory 当前被限流或拒绝**。原 EXE 的固定 HTTPS 样本失败；桌面 translation-status.json 也记录同样的失败和一小时冷却。不是版本不匹配、没有模型或用户没有正确安装。
2. 用户手动执行 abyss_translate 并悬停英文物品后，真实插件状态为 active，已提交 33、已接收译文 0、队列 64、applied_sequence 7。requests.json 有 Husker Venom 名称、完整简介和带颜色标记的组合提示框，工作台也显示 33 条原文。response.json 正确回传确认，但 translations 为空，progress.failed 为 2，错误是免费渠道限流。
3. 同时保存了真实 Pressure Injector Headset 英文名称、简介截图。选定 Google 网页兼容实验渠道后，原 EXE 固定 HTTPS 样本成功（1.016 秒）；这次选择在桌面保存，不是自动跨服务重试。
4. 同一游戏会话随后达到已提交 81、已接收译文 62、applied_sequence 66；response.json sequence 67 带有效译文。重新悬停原位置，Pressure Injector Headset 名称及整段简介显示中文，模组出处仍用紫色文字显示。机器译名和长句只证明显示链路有效，不等于语义已经人工校对。
5. 本轮没有保存每一次短寿命请求，因此不能提供该物品全部七阶段各自独立的原始快照；完整请求证据以 Husker Venom 为主，Pressure Injector Headset 有同物品真实画面前后证据。人物物品栏尚未进入完成验收。

last-error.txt 在初始现场不存在；status.last_error 为空。网络失败在桌面诊断及 response.progress 中，不能只检查 Lua last-error.txt。

## 代码修复

运行代码提交：`da1e4f000aa4271769121271ffe6389e4f5525a3`，同一任务分支。

- **增量请求时序缺陷**：游戏确认一个请求后，可因新悬停发出下一个请求；桌面可能还有上个请求的增量正在传输。旧实现要求所有响应 request_id 等于最新请求，拒绝这个旧请求增量；桌面等待其序号 ACK，双方可能永久等待。新增隔离回归在旧代码明确失败，修复后通过。此次真实游戏没有单独捕获该竞态，不能把它认作这次限流现场的唯一根因。
- 带完整相同会话、源/目标语言的增量按全会话连续序号接受；仍拒绝序号缺口、超大包、错误会话及语言。旧协议继续严格匹配请求。旧增量不能误确认新请求已经导入。
- status.json 新增 `runtime_build: request-sequence-fix-20261022`，用于区分磁盘候选和实际载入模块。
- 工作台显示当前渠道、已提交数量、游戏已收译文数量；周期性发布不会再把失败原因覆盖成笼统的等待提示。没有改成收费渠道、自动换供应商或清除已有草稿。

已读取本机实际 Barotrauma.dll 的元数据/IL：Inventory.DrawFront → Inventory.DrawToolTip → GUIComponent.DrawToolTip(SpriteBatch, RichString, Rectangle, Anchor, Pivot)，SubEditorScreen.Draw 也调用该五参数路径；参数名 toolTip 与插件一致。没有修改 DLL。接口匹配不能替代人物物品栏实测。

## 验证

- Windows Python 3.12：169 项执行，**168 通过、1 跳过、0 失败**。跳过是 Windows 账号无符号链接权限，不能计为通过。
- LuaCs/MoonSharp **34 项隔离检查通过**；此前 32 项，加两项请求/增量竞态和隔离回归。使用真实 MoonSharp 库、模拟引擎对象，不是游戏验收。
- 实际 Tk 事件检查通过：100% 字体 DPI、1060×700/1440×900、中英切换、长富文本/占位符、保存重开、3000 行分页及未保存取消；这次没有验证 OS 150% 缩放。
- Windows EXE 已重新构建。冻结程序扫描、内置插件一致性、拒绝覆盖已有插件、拒绝覆盖报告输出通过；**默认 MyMemory HTTPS 失败**，因此完整 frozen checker 的 passed 为 false。Google 可选 HTTPS 通过，不能把整套检查写成全绿。
- 真实游戏：编辑器一个物品名称/简介实际中文显示通过；人物物品栏三个样本未验证。颜色实际画面保留；动态数字/占位符和中文跳过本轮只有隔离回归，未完成真实界面专项验收。未测整局 FPS，不宣称无卡顿。

## 本机候选、证据、恢复

本机证据目录：`D:/Codex/abysstext-evidence-20261022/`，原始日志/缓存未提交 Git。

- `initial-plugin/`、`initial-desktop-data/`：修改前备份。
- `active-mymemory/`：真实请求、响应、状态和 XML；`after-ui-stop/`：停止桌面操作后的快照。
- `before-pressure-injector.png`、`after-pressure-injector-google.png`：真实编辑器同物品前后画面。
- `mymemory-probe.json`、`google-probe.json`：原 EXE 本机实网。
- `python-after.log`、`lua-race-before.log`、`lua-after.log`、`tk-after.log`、`windows-build.log`、`frozen-final/`：回归、失败复现、构建及冻结 EXE 检查。
- `actual-game-tooltip-api.txt`、`game-dll-sha256.txt`：只读核对本机接口。

候选源码/Windows/插件 ZIP 位于仓库本机 `artifacts/0.2.0-rc5/`，VERSION.txt 应为 **da1e4f0**。没有发布公开 Release 或工坊。

新 EXE SHA256：`8aaec8f11c9254b0f9c35c7afd17a3dc2c2d10debfd68274323efb21f0fc42bb`。

新插件已写入 `D:/steam/steamapps/common/Barotrauma/LocalMods/AbyssTextLive/Lua/Autorun/abysstext.lua`，SHA256：`395ae1897773368b491fd5d9c8f8b2be7ce708cb3b929d7cd9e31ee4153354a0`。**磁盘已更新不等于运行中已重载**；必须核对 status.runtime_build。Escape 停止后未继续用 UI 验证最终标记，当前运行模块不能宣称已验收。

继续测试：保存桌面工程；退出旧工作台后从独立候选目录启动新版，连接上述插件目录并选 Google（当前 MyMemory 失败）。游戏 F3 停止试译、cl_reloadlua、重新试译，先核对 runtime_build，再在不保存的测试会话完成人物栏三个物品、停止恢复/再开和连续悬停。无需重装游戏或替换 DLL。

恢复：游戏停止试译并退出候选工作台；仅将 initial-plugin 中自己的 Lua/Live 数据恢复到原插件目录，再重载 Lua 或重启客户端。原桌面 EXE 从未覆盖，仍可启动；如恢复 MyMemory，需接受当前限流仍然存在。不要把备份放回 LocalMods 形成重复插件。未触碰正式存档、第三方模组源码、游戏 DLL、工坊或 main。
