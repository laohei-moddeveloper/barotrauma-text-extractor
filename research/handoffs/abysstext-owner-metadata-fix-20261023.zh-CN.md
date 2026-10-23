# 游戏桥接来源 ID 校验兼容修复

用户截图显示“游戏桥接：无效的模组来源 ID”。代码确认：此前把可选的 mod_id 字段当成必须合规的字段，遇到 null、数值或其他异常类型时抛异常，导致整批合法文字也不处理。截图无法确定本机实际发来的字段值，未把推测的 null 当成已读取的真实请求。

修复：缺失/null 视为未知来源；可精确表示的正整数 ID 转成字符串。其他不合规来源丢弃该字段，继续处理文字；标记为来源异常，禁止该条目扩大为无来源人工缓存匹配，仍可使用既有术语/所选翻译渠道。文字、键、语境、会话及每批最多 8 条的检查保持。Lua 对普通 GUI 文字显式写空字符串来源，构建标记为 owner-metadata-fix-20261023。

Linux Python 3.12：195 项通过，0 失败，0 跳过。隔离 MoonSharp/Lua：36 项通过，包含空来源序列化、null/数值/恶意来源不丢整批及异常来源不误用人工缓存。Windows 候选等待本提交 CI，不把这些检查写成真实游戏验证。

本机报告 abysstext-human-memory-local-20261023.zh-CN.md 已确认导入 2,759 条人工记录。本报错不代表缓存需要重新导入。云端本次没有替换本机正在运行的 EXE 或插件；需更新本轮候选后再由用户本机验证。

## Windows 修复候选已构建

设置窗口原有保存按钮裁切检查失败，已将保存按钮固定在滚动区外。最终测试/打包源码为 `3832812576d2fe2f365d07a7f31e26951e2d47f0`。Windows Python、真实 Tk、合成回归、实际冻结 EXE 的全部必需检查及包审核均通过；下载后再次核验三个 ZIP 的 SHA256 一致。真实游戏仍未代测。

候选：https://github.com/laohei-moddeveloper/barotrauma-text-extractor/actions/runs/39887646388 ，Artifact ID `12473183352`。

```text
fc79470e6368b29cb077047d92b188f85a6b308f5a6b45577c1e53e210b94726  AbyssText-0.2.0-rc5-source.zip
c75e1e665bfdb4a5c0451cd56c522a107a5be9cebe2d00a8ac21bb8c3e9e80bc  AbyssText-0.2.0-rc5-Windows-x64.zip
ccd1d563be32c40021421bc8facd4e2aec36acb8b3773dcfcfbc7c55d10bdb91  AbyssTextLive-0.2.0-rc5.zip
81aaaaecabe6461053e0f6e6dd7ea5a31ef3135ddba8b587a56dce02823a5383  BarotraumaTextExtractor.exe
```
