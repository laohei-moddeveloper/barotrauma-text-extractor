# GitHub 公开成品同步 · 2026-10-22

用户在工坊发布完成后要求同步成品到 GitHub，并进一步要求公开。本次已将成品公开为 **预发布版**，仓库本身也已确认为 Public；保持任务分支，不合并 main。此前报告“未公开 Release”描述的是先前阶段，不代表本次完成后的状态。

- [公开 Release：v0.2.0-rc5-workshop-20261022](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/releases/tag/v0.2.0-rc5-workshop-20261022)
- [Windows 直接下载](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/releases/download/v0.2.0-rc5-workshop-20261022/AbyssText-0.2.0-rc5-Windows-x64.zip)
- [对应工坊条目 3823861796](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)
- [持续开发分支](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/tree/codex/abysstext-workbench)

## 附件与验证

共 **11 个附件**：Windows 工作台 ZIP、客户端插件 ZIP、当前源码 ZIP、工坊完整有效载荷 ZIP、B 像素风封面、30 秒实录 GIF、中英文工坊简介、发布说明、构建清单 JSON、SHA256SUMS.txt。

所有附件均从 GitHub 回下载逐个核对 SHA256，全部一致。公开后无认证 API 可读取 Release 和 11 个附件；另以无认证方式下载 Windows ZIP 验证普通访问者可以获取成品。所有 ZIP 完整性检查通过。

Windows 包及客户端插件沿用工坊已发布的运行构建，**未重新改变运行代码**：

- 运行代码：`da1e4f000aa4271769121271ffe6389e4f5525a3`。
- 源码与展示文件快照：`fe87e85c8a9dc8053a26057b907e71ab60808674`，包含后续封面、简介和工坊发布回执。
- Windows EXE SHA256：`8aaec8f11c9254b0f9c35c7afd17a3dc2c2d10debfd68274323efb21f0fc42bb`。
- Windows ZIP SHA256：`de5d4b3f721f12cd4835f59e4865a2b471f902e56a55c7d1af1b4536f8ad22bc`。
- 工坊完整 ZIP 包含该条目已回下载确认一致的 6 个有效载荷文件。

成品 ZIP/EXE 作为 Release 附件上传，未混入 Git 源码树。没有上传个人设置、游戏日志、缓存、模型、第三方模组源码、凭据或游戏 DLL。完整本机上传/下载回执保存在 `.local-release/github-product-sync-20261022/`，不进 Git。

此同步不增加游戏覆盖或测试结论，仍保留 [本机验收边界和渠道限制](abysstext-local-game-diagnosis-20261022.zh-CN.md)。GitHub Release 标为 prerelease；仓库 PR #1 继续为草稿，main 未合并。
