# 译潜 AbyssText · 汉化工作台

[English](README_EN.md) · [既有创意工坊条目](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)

0.2 开发预览：独立桌面工作台 + 可选的 LuaCs 客户端实时试译插件。此分支尚未替换 v0.1.0 的 Windows 发布版或工坊内容。源码运行需要 Python 3.12+ 和 Tkinter，运行依赖只有标准库。

```console
python app.py
```

打开模组 → 选择识别语言/目标语言 → 提取 → 搜索/分类 → 生成草稿或编辑 → 校对 → 导出。暖白与梅紫界面支持中文/English 切换；原文和译文不随界面语言改变。

- **同文去重、保留语境**：完全相同的原文合并一行，保留所有文件、行列、键和识别依据；空白/大小写不同不合并。同文不同义可按文件与键拆分。
- **提取依据可查**：读取 XML、Lua、C#，解析语言表引用、常见名称/介绍/症状键、静态常量拼接与简单显示调用流向。内部标识符和低置信候选默认隐藏。按 filelist 筛选只约束 XML，不能证明脚本在游戏中一定执行。
- **语言对**：源语言 Auto 或手选，目标语言可选。优先使用语言表元数据；日/韩/汉字字符特征仅作候选。无标签的法语、德语等拉丁文字请手动选择；不是逐句通用语言识别模型。译文记忆按工程语言对隔离。
- **编辑与质量检查**：人工编辑、原生 XML/排版示意预览、备注、翻译记忆、术语导入；校对检查占位符、重复格式标记、换行、边界空白和非法 XML 字符。AI 不会自动标记已校对，也不能用格式检查代替语义校对。
- **导出**：工程 JSON、可回导 CSV、独立原生语言包、已校对文字的完整模组副本。副本只替换有明确位置的内容，校验扫描指纹；源模组始终只读。语言表无法覆盖全部硬编码文字，未适配内容列在导出报告中。
- **可选 AI**：默认离线复用，无匹配时保留空白。可连接自己已运行的 Ollama 或 OpenAI 兼容 API；不自动下载模型，不附送免费额度，密钥仅本次会话内存保存。自选外部 API 可能产生供应商费用，程序不代付。云端开发未调用付费翻译服务。
- **大项目**：后台扫描/翻译、取消、内容哈希解析缓存、搜索防抖、每页 150 行；保存过的工程修改后自动保存。

## 游戏内试译（实验功能）

桌面“连接游戏”可安装自带 `AbyssTextLive` 到你选择的 LocalMods 新目录，也可连接已安装目录。需要 **LuaCs 客户端**，并在游戏中启用插件。工作台选择源/目标语言与离线或本机模型，保持运行；游戏点“译潜 · 一键试译 / AbyssText · Translate”。

客户端采集语言键、原生 GUI 文本和部分原生字体绘制字符串，通过插件自己的 `Live/requests.json` 交给桌面翻译；结果更新插件自己的 `Live/Translations.xml`、原控件或原字体调用参数。**不增加翻译字幕层，不改其他模组源码或游戏逻辑。** 自动游戏请求只允许离线复用/回环地址，外部服务需桌面手动启动。再次点击可停止并恢复本插件替换的控件文字、卸载本插件语言资源。F3 命令：`abyss_translate`、`abyss_stop`、`abyss_apply`。

源语言 Auto 在游戏侧使用游戏默认语言（通常 English）；需要日语等来源时请手动选择。原生语言键的显示受游戏当前语言控制，建议游戏语言与目标语言一致。运行中切换语言对后，应在游戏先停止再开始。

**真实游戏尚未验收。** 已通过隔离 LuaCs/MoonSharp 测试，不等于在你的游戏版本能正常工作。图像文字、未触发场景、自定义渲染、直接带颜色索引的字体绘制、复杂动态 getter/布局等不保证覆盖；部分缓存界面需重开。实时替换可能受字体、控件宽度和其他 Hook 影响。详见 [覆盖与验证](docs/VALIDATION-v0.2.md) 和 [本地 Codex 接手话术](docs/LOCAL-CODEX-HANDOFF.zh-CN.md)。

## 命令行与构建

```console
python app.py examples/workbench --source-language Auto --target-language French -o ../french-project.json
python app.py examples/workbench -o ../worksheet.csv
python app.py examples/workbench --raw -o ../raw-evidence.json
python -m unittest discover -s tests -v
python tools/check_workbench_ui.py
python tools/benchmark.py
```

输出必须放在被扫描模组以外。命令行退出码 0 完成、1 错误、2 带诊断/不完整。Windows 运行 `build-windows.bat`，得到 `dist/BarotraumaTextExtractor.exe`，已捆绑本项目的客户端 Lua 资源。构建依赖见 requirements-build.txt；不捆绑模型、第三方模组或游戏 DLL。

扫描拒绝符号链接、DTD/实体声明、超大文件；支持 UTF-8 和有 BOM 的 UTF-16。不执行脚本，不分析完整 AST/类型系统，不自动解包 DLL、图片或 .sub。动态拼接/跨函数数据流可能漏报；静态字段命中不等于玩家一定看见。没有标注真实语料的精确率/召回率结果，不能承诺“全部文字零遗漏”。

本版本借鉴 Poedit/Weblate 的上下文、翻译记忆、校对与质量检查流程，并核对 Barotrauma、LuaCs 公开接口；[研究与设计说明](docs/DESIGN-v0.2.md)。`examples` 全为自建虚构内容。历史 v0.1 Windows 验证记录保留在原文档中，不适用于此次升级。
