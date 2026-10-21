# v0.2 设计与参考

工作台与游戏客户端共享“原文、语境、语言对、译文、校对状态”的工程模型。桌面负责翻译/校对/文件导出，客户端只做观察与可撤销显示更新；没有新增常驻网络服务。当前不另造前置模组：LuaCs 已提供所需客户端 Hook/文件/JSON 接口，自有 AbyssTextLive 作为可选适配器。

## 参考并核对的公开项目

- [Poedit](https://github.com/vslavik/poedit)：借鉴上下文与翻译记忆流程。
- [Weblate](https://github.com/WeblateOrg/weblate)：借鉴草稿/校对分离、术语和格式检查。
- [BaroTranslatorTool](https://github.com/communitytranslations/BaroTranslatorTool)：参考游戏 XML 读取/翻译/保存交互。没有采用网页翻译抓取或声称无限免费 API。
- [Barotrauma ItemPrefab](https://github.com/FakeFishGames/Barotrauma/blob/master/Barotrauma/BarotraumaShared/SharedSource/Items/ItemPrefab.cs)：核对 entityname、nameidentifier 与名称回退。
- [AfflictionPrefab](https://github.com/FakeFishGames/Barotrauma/blob/master/Barotrauma/BarotraumaShared/SharedSource/Characters/Health/Afflictions/AfflictionPrefab.cs)：核对 translationoverride、名称/描述键。
- [游戏源码](https://github.com/FakeFishGames/Barotrauma)：核对 TextManager/TextPack 的公开语言缓存接口、GUI.AddToUpdateList、GUITextBlock.Text、RichString，以及 ScalableFont.DrawString 重载。主分支会变化，必须本机按安装版本复核。
- [LuaCs Hook 文档](https://github.com/LuaCs/luacs-docs/blob/master/lua/lua/Hooks.lua)：精确重载参数、Before 回调和移除 Patch。测试使用 LuaCs 的 MoonSharp fork [b556e550](https://github.com/evilfactory/moonsharp/tree/b556e550eb20b950a7db3ef69006104af3f654da)，不是不兼容的普通 MoonSharp NuGet 2。

参考的是公开格式和工作流；没有复制上述编辑器实现、没有把第三方模组内容提交仓库。

## 准确性与安全替换

明确字段、可解析键和显示调用优先；普通脚本常量留候选。简单变量流向只认同文件的静态赋值与已知显示调用，不是有作用域/类型的 AST。已知限制公开，不能把静态猜测包装成可见性证明。

每个位置保留字符区间和文件 SHA-256。新副本导出前后检查原文件指纹，只对已定位、已校对、格式有效的显示位置改写。混在同文组内的内部标识符不会随可见原文一起替换。文本相同但含义不同需要人工拆分。源模组目录不可作为输出目标。

语言表导出使用 `<Override>`，并报告没有原生键的硬编码文字；新增键不会自动改造原模组调用点。语言键冲突直接拒绝导出。切换语言对不继承其他目标语言的旧翻译记忆。

## 实时更新

原生语言包更新后调用 IncrementLanguageVersion；GUITextBlock 使用原 Text 属性，普通字体字符串在原调用参数中替换。保留 RichString 的 NestedStr 标记。直接带颜色索引的绘制调用未盲目替换，避免破坏格式偏移。

绘制回调只查字典/排队，推理在桌面后台线程。本地桥接原子写入，协议按 request_id/revision 匹配，分批响应，已发送文字去重；纯数字变化使用模板占位符。请求上限、控件追踪上限和超时限制避免无界工作量。上限是稳定性折衷，不代表无限场景覆盖。

停止时移除本插件 Patch、尽力还原控件、卸载自己的语言包。不能还原由其他 Hook/动态 getter 后续修改的所有状态，可能需要重开界面。本机验收必须检查停用、换场景和联机客户端不影响游戏逻辑。
