# 一键翻译 JSON 弹窗及重启后仍卡顿：后续修复

用户明确确认已更新并重启游戏仍然卡顿。本轮不再归因于旧版本；先 fetch 并保留本机新提交 bf4f904 的工坊发布记录。该记录说明此前 c337f2c 已正式更新工坊，但本轮候选不自动再次上传。

## JSON 问题

代码和隔离测试复现了与截图一致的路径：Lua File.Write 短暂清空/半写 status.json；工作台 publish_live → LiveBridge.publish → status(fresh=True) 直接解析，异常会调用 messagebox.showerror。截图和用户操作只能定位到一键翻译，未读取用户本机原始失败文件，不能声称已取得其具体原始损坏字节。

新增一次性、限大小、不睡眠的快照读取。读到空/半截 JSON、非法编码、共享冲突或 stat 变化即延期。失败不提交请求指纹、会话、ACK 或 delivered，不覆盖未确认数据。持续 3 秒异常以文件名提示，修复即恢复；同元数据修复也不会被旧缓存掩盖。自动 publish 的异常改为状态栏信息，避免模态打断。非法协议、符号链接和超大输入仍拒绝。游戏侧暂时解析响应失败的旧提示也在有效恢复后清除。

## 卡顿问题与取舍

上一轮 Lua 内部计数压力测试没有测真实游戏 Harmony→MoonSharp 频繁回调；不能用那份“次数下降”声称实际游戏已流畅。本轮默认 native 模式不注册两个全局 DrawString、AddToUpdateList、GUITextBlock.Draw Hook，保留提示框 Hook。分帧扫描普通 GUI，每步 8 节点，跳过隐藏子树，定期发现新页面。兼容模式通过用户设置显式启用，恢复旧覆盖路径并承担较高开销。

另外对照公开游戏源码核对 prefab 公共成员：CharacterPrefab 没有 Description，AfflictionPrefab 用 Descriptions，通用试读会抛大量托管异常。已改按注册表读取有效成员，并对已知 LocalizedString 直接读 Value，避免 NestedStr/SanitizedValue 的异常探测。删除 GUI.Children 元素上无依据的 GUIComponent 字段试读。元数据字段表按一次扫描复用，避免每个 prefab 重建。

轻量模式有覆盖取舍：树外/自绘/动态 TextGetter 的文字可能漏采或等待原生资源更新；保留兼容模式。没有宣称相同覆盖下全局 Hook 零成本，也没有宣称 FPS 提升。大型语言包单次加载、布局、getter、后台预载、其他模组仍可能卡顿。

## 已验证

- Linux Python 3.12：202 项通过，0 失败，0 跳过。新回归覆盖空/截断状态不 ACK、请求恢复、命名告警及清除、共享冲突/UTF8 BOM、同元数据恢复、非法协议拒绝和采集设置。
- 隔离 MoonSharp/Lua：49 项通过。原有 42 项显式在兼容模式回归，新增默认轻量无四类高频 Hook、新页面发现、600 控件分步扫描、隐藏树跳过、严格模拟类型的无效属性访问为 0、LocalizedString 无 RichString 探测、响应解析恢复后清除旧错误。
- Windows 真实 Tk 回归增加了空 ACK 时自动回传不弹 messagebox、不覆盖未确认包的场景，等待 CI。
- Windows 实际 EXE、默认/Google HTTPS、ZIP 一致性和 SHA256：等待本提交 CI，随后补充证据。
- 没有启动或控制用户游戏，没有替换用户 EXE、游戏 DLL、LocalMods、第三方模组或存档，没有新工坊/Release/main 合并。

## 用户验收

更新配套程序和插件；已有人工缓存保留。确认运行标记 snapshot-native-fix-20261023，capture_mode=native，工作台显示轻量采集。测试同一大页面持续翻译、切换新页面、物品提示框、损坏文件后恢复及真实帧时间。若需特殊自绘文字，设置兼容采集后停止/重新开启试译，对比覆盖和流畅度。详见 docs/SNAPSHOT-NATIVE-20261023.zh-CN.md。
