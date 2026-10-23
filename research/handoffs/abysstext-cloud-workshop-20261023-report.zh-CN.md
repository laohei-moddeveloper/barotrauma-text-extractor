# AbyssText 云端工坊发布完成（2026-10-23）

现有 [工坊条目 3823861796](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796) 已于香港时间 **2026-10-23 13:13:57** 更新。没有新建条目；中文标题、完整简介、封面 URL 和可见性均与发布前一致。用户电脑关闭不影响这次 GitHub Actions 上传和下载核验，本次未控制或更新用户本机。

运行源码：`314c95b809523b31d9312fdb73ed5e7d5cafb77e`；版本标签仍为 `0.2.0-rc5`，Lua 标记 `local-reuse-fix-20261023`。GitHub 源码及报告继续同步在 `codex/abysstext-workbench`，未合并 main、未创建公开 Release。

## 发布与独立确认

- 上传：[39904478449](https://github.com/laohei-moddeveloper/tsm-wiki/actions/runs/39904478449)。Steam 账户认证、SteamID 与工坊所有权核对通过，实际上传已被 Steam 接受。由于旧成功回执正则不识别实际输出，该任务显示失败，不能直接把任务状态作为是否上传的结论。随后通过官方详情确认更新时间与大小发生变化。
- 回下载核验：[39904775482](https://github.com/laohei-moddeveloper/tsm-wiki/actions/runs/39904775482)，任务成功。只下载、不重复上传；回执明确 `upload_performed=false`、`downloaded_bytes_verified=true`。
- 在全新的 Steam 临时目录回下载 10 个文件，文件集合、大小、SHA256 全部与已审计发布包一致。云端另外下载包与回执，独立核对全部文件、ZIP 内 EXE 和 VERSION.txt，确认源码提交一致；再次读取官方详情比对发布前的标题、简介、封面和可见性，均相同。
- 本次复用已经验证的 [发布包构建 39902584597](https://github.com/laohei-moddeveloper/tsm-wiki/actions/runs/39902584597)，artifact `12479791122`。在用户要求停止重复检测后，没有重新构建游戏工具，也没有再次上传。验证回执 artifact 为 `12480332543`。

## 本轮发布工具修复

1. SteamCMD 的首次更新会以 7 退出并要求重新启动，旧工具把它误报为认证失败。现在在无凭据的干净安装中完成初始化，只对这一阶段的 7 做有上限的重新启动；正常退出后才导入凭据，复制完整运行文件。
2. 删除“日志出现 FAILED 就判失败”的笼统规则。认证仍必须核对实际 SteamID；上传仍检查远端版本及下载内容，保留具体认证/权限失败处理，原始认证日志不公开。
3. 支持复用同一私有仓库中已经验证的发布包，严格核对目标和完整 40 位源码提交；支持仅回下载验证，避免因回执兼容问题重复上传。
4. AbyssText 后续遇到未识别的成功回执格式时，必须有新远端版本和逐文件回下载匹配才能成功；其他目标仍保持原有要求。这一补丁的针对性隔离回归通过，没有为此再上传。

私有自动化位于 `codex/abysstext-cloud-workshop` / [PR #5](https://github.com/laohei-moddeveloper/tsm-wiki/pull/5)，没有改 wiki 页面或合并 wiki main。三项 Steam Secrets 已经被云端正确读取和实际使用，已证明本次可以在云端登录并上传。刷新后的认证配置仅在私有任务/加密缓存中保存；未来 Steam 若要求重新验证，仍需重新认证，不承诺永久有效。

## 校验和

以下为**实际发布到工坊**的包，和独立 Windows 候选 CI 的 ZIP 不是同一轮构建，不能混用两者的哈希。

| 文件 | SHA256 |
|---|---|
| Workbench Windows ZIP | `c8b20eee44045882202c8809fadc759b5b5871a91c7de9d5713f3d721a0ff5a6` |
| ZIP 内 EXE | `edf7073ba1f699b6a2fa9d1c09a12fb6537debfee1649ad4f0e51fc4b4244588` |
| 游戏插件 Lua | `aca835228be965017b05127eed4512cc649b3152bd4403278f2e9ee3abe3ff37` |

全部十项文件及回执见 `cloud-workshop-20261023-evidence.json`。

## 检查范围及本机后续

运行源码此前已通过 Linux/Windows 各 211 项 Python、50 项隔离 Lua 检查、真实 Windows Tk、冻结 EXE HTTPS 和三种候选包审计。发布包构建也通过其 Windows 检查和实际 EXE 审计；工坊内容已回下载核实。游戏内帧时间、长时间实战及特殊界面覆盖仍未验证，不能据此宣称零卡顿或全覆盖。

下次开机让 Steam 更新订阅，然后从工坊目录的 `Workbench/AbyssText-0.2.0-rc5-Windows-x64.zip` 解压新版工作台；退出旧工作台后再替换自己的安装。桌面 EXE 不会因云端上传自动被覆盖。个人缓存与工程保留，不要为了更新清空。使用配套新版插件，检查 `local-reuse-fix-20261023` 标记，真实游戏验收由用户完成。
