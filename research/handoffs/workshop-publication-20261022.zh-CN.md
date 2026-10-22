# 2026-10-22 工坊更新回执

已更新现有公开条目：https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796

App ID **602960**，Workshop ID **3823861796**。用户本轮明确要求覆盖原外部工具条目，加入客户端插件和工作台入口；没有新建重复条目。未发布公开 GitHub Release，未合并 main。

## 线上内容

- 标题完整保持：**泥偶迅猛龙汉化——游戏内一键实时汉化工具|游戏外快捷翻译工作台**。
- 封面采用用户选择的 **B 像素冒险**，无实机译文截图。
- 简介加入连续 30 秒真实录屏动图、安装及连接步骤、两个免费渠道、持续试译和停止恢复、翻译质量持续改进说明，以及用户作为老虎脱粒机汉化组成员的开发初衷。
- 加入 GitHub 仓库与 Issues 入口，诚恳邀请漏译、错译、卡顿和功能建议。
- 简体中文与英文简介分别更新；两种语言均保留用户指定的同一标题。完整文字见 `workshop/description.bbcode.txt` 与 `description.en.bbcode.txt`。
- LuaCs 条目 **2559634234** 已添加为前置，并从 Steam 查询实际子依赖确认存在。

## 上传及回下载验证

Steam 上传回执 **OK**；内容更新时间 2026-10-22 **16:26:43 香港时间**。之后另更新简介的反馈邀请和作者说明。简体中文/英文经指定查询语言并禁用缓存回读，标题与完整简介均和本机发布文件相同，条目仍为 Public。

通过 Steam 回下载至该条目自己的 Workshop 缓存目录，**6 个文件逐个 SHA256 匹配**，没有旧版残留文件：

| 路径 | 验证 |
| --- | --- |
| `filelist.xml` | 与干净插件资源一致 |
| `Lua/Autorun/abysstext.lua` | `395ae1897773368b491fd5d9c8f8b2be7ce708cb3b929d7cd9e31ee4153354a0` |
| `Live/Translations.xml` | 干净发布资源，未上传运行期请求/响应/设置 |
| `Workbench/AbyssText-0.2.0-rc5-Windows-x64.zip` | `de5d4b3f721f12cd4835f59e4865a2b471f902e56a55c7d1af1b4536f8ad22bc` |
| `Workbench/EXE-SHA256.txt` | 与准备包一致 |
| `INSTALL.txt` | 与准备包一致 |

下载的 Windows ZIP 无损坏，内含 EXE SHA256 **8aaec8f11c9254b0f9c35c7afd17a3dc2c2d10debfd68274323efb21f0fc42bb**，VERSION.txt 绑定运行代码 **da1e4f000aa4271769121271ffe6389e4f5525a3**。桌面程序以独立 ZIP 提供，不作为 Lua 脚本安装。

公开页面匿名 HTTP **200**，包含最终标题、动图 img 标签、老虎脱粒机汉化组成员说明和反馈邀请。GitHub 链接经 Steam 正常 linkfilter 编码，解码后核对仓库与 Issues 地址；不是缺失链接。

Steam CDN 封面匿名 HTTP 200、image/jpeg，SHA256 与所选 B 图一致：**2ce513581a5d2eb53bf4fd8416ba705fc7adfe4a27e1b21e1ceadb594382836e**。

动图匿名 HTTP 200、image/gif，SHA256 与源码资产一致：**57fa6d110c0c6136b8a3ab7f7dc6d60b8f4eecc294a8d935b20ca38791df6b3c**。960×540、150 帧、精确 30000 ms，约 3.4 MB。核对的是页面 img 标签和实际资源，不冒称进行了浏览器内播放操作。

## 保留与边界

本轮没有启动/操作游戏，没有替换游戏 DLL 或修改第三方模组。回下载只更新本项目自己的 Workshop 缓存；未覆盖此前测试使用的 LocalMods 插件。

个人路径、Steam 账号资料和完整运行日志不进 Git。原元数据备份、上传/语言回读回执、回下载文件哈希及公开页面核验保留在本机 `.local-release/publish-existing-3823861796/`。如需撤回本轮更新，应对同一条目发布备份或候选回退；不另建替代条目。

现有覆盖和免费渠道限制仍以 [真实游戏排查报告](abysstext-local-game-diagnosis-20261022.zh-CN.md) 为准；本轮发布验证没有把历史跳过项、默认渠道限流或未完成的专项测试改写为全部通过。
