# 译潜 AbyssText · 潜渊症汉化文字提取器

[Steam Workshop / 创意工坊](https://steamcommunity.com/sharedfiles/filedetails/?id=3823861796)
**Extract first. Translate with context.**

[下载 Windows 预发布版](https://github.com/laohei-moddeveloper/barotrauma-text-extractor/releases/tag/v0.1.0) · [English](README_EN.md)

Windows 用户解压 Release 中的 Windows x64 ZIP，双击 `BarotraumaTextExtractor.exe`；不需要安装 Python。

独立的离线 Python 工具，供模组汉化人员建立原文清单。0.1 为可运行原型，**静态规则提取，不承诺精准识别所有玩家可见文字**。不修改源模组，不运行 Lua/C#，无需连接游戏或 Steam。与 BaroDock 分开运行。

## 启动

安装 Python 3.12（包含 Tkinter；Windows 官方安装器通常默认包含），双击 `启动工具.bat`，或运行：

```console
python app.py
```

选择模组目录 → 提取文字 → 筛选/搜索 → 点击条目查看依据与行列 → 导出全部 CSV 或 JSON。扫描在后台线程运行，可取消；取消后的报告会注明不完整。筛选仅影响窗口显示，导出包含全部条目。

CSV 使用 UTF-8 BOM，可用 Excel 打开；在 `translation` 列填写译文。以公式符号开头的单元格加英文单引号，避免被表格程序当成公式；需要逐字符原文时使用 JSON。CSV 旁会写入 `.diagnostics.json`，不要漏掉其中的失败文件和不支持项。**本版只做提取与导出，不支持译文回写或自动生成可用汉化包。**

无图形环境可使用命令行：

```console
python app.py "D:\SteamLibrary\steamapps\workshop\content\602960\模组编号" -o "D:\汉化\原文.json"
python app.py examples -o sample.csv
```

输出应在被扫描的模组目录之外。命令行退出码：0 扫描完成且无诊断；1 参数/导出失败；2 已导出，但有解析失败、取消或不支持的 DLL/潜艇内容等诊断。

## 提取与核查

| 类型 | 处理方式 | 注意 |
| --- | --- | --- |
| 直接文本 | 识别物品、生物/角色、症状、职业、天赋等定义上的名称介绍；对话、选项、部分组件界面文字；原生 `infotexts` 语言表 | 命中字段规则不代表当前版本一定显示，也不代表实际加载、启用或触发 |
| 本地化引用 | 识别引用字段、`Text.Get` 系列调用首参数；将值与目录内语言表键匹配 | 保留所有语言及重复定义，不判断加载顺序；无法解析时保留键，不能把键当作待翻译原文 |
| 推导名称键 | 无显式名称时，对常见定义推导 `entityname.*` / `afflictionname.*` / `jobname.*` / `talentname.*` | 是待核实的命名约定，不等于已证明的运行时查找结果 |
| 脚本显示调用 | 识别部分 GUI、消息和 Speak 调用中的字符串，以及 Text/Tooltip 等赋值 | 始终标记待核查；不进行类型分析、重载解析或跨函数数据流追踪 |
| 其他候选 | 保留其余 Lua/C# 字符串和未知 XML 显示相关字段，单列标识符/路径候选 | 会混入内部键、日志、调试字符串；用于人工补漏，不应整表直接翻译 |

每条包含稳定的定位 ID（位置/内容改变会改变 ID）、文件相对路径、行列、用途、类型、原文、引用键、语言、上下文、识别依据、解析到的语言表条目和空白译文列。不同位置的同一原文分别保留，方便判断语境。XML 属性实体由解析器解码；XML 属性换行按 XML 规范归一化；原文件仍是最终依据。

脚本词法扫描跳过注释，支持常见引号字符串、Lua 长字符串、C# 逐字/原始字符串；插值只保留源码形式，不计算表达式。直接传入变量的文字通常在变量定义处列为候选；多段拼接不会自动还原完整句子。传入 `Text.Get(prefix .. suffix)` 等动态键时，提取到的只能是字面量片段，不能视为完整可解析的键。

## 已知边界

- 扫描指定目录内 `.xml`、`.lua`、`.cs`；不自动读取游戏原版和其他依赖包，不基于 `filelist.xml` 判断哪些文件实际加载，未启用文件也可能被提取。
- 普通 StatusEffect 的内部名称、标签、伤害标识符不应直接汉化。症状显示名通过 Affliction 定义及语言表核查；脚本自定义效果、HUD、能力名称可能仅列为候选或漏报。
- 不还原运行时计算、反射、外部文件、网络消息、编译 DLL 字符串、图片上的文字、压缩 `.sub` 文件或字体图集。DLL/`.sub` 会给诊断，其他格式计入跳过文件数。
- C# 插值表达式内嵌引号、复杂多引号原始字符串、完整 Lua/C# 语法和类型系统不在支持范围；可能误分词或报告失败。这不是编译器级解析。
- UTF-8（可带 BOM）及带 BOM 的 UTF-16；其他编码给出失败诊断，不用替换字符悄悄丢失内容。单文件上限 16 MiB。不跟随目录或文件符号链接，拒绝 XML DTD/实体声明。
- 解析失败会丢弃该文件的部分结果，并记录诊断；扫描完成不意味着覆盖所有文本。导出只读清单之后仍需按实际模组与游戏版本核查。精确率/召回率尚未在标注好的真实模组语料上测量。

更完整的版本需要针对具体模组补充 XML 组件与脚本 API 规则、增加 AST/数据流分析，并可另做游戏内观察记录补充实际显示文本。运行观察只能覆盖触发过的内容，也无法单独保证完整性。

## Windows EXE 构建

在 Windows Python 3.12+ 环境运行 `build-windows.bat`，或 `powershell -File build-windows.ps1 -Python "你的python.exe路径"`。构建依赖锁定于 `requirements-build.txt`，输出 `dist/BarotraumaTextExtractor.exe`。源码运行只需标准库。实际 Windows 验证见 `docs/VALIDATION.zh-CN.md`。

## 验证

```console
python -m unittest discover -s tests -v
```

测试覆盖字段分类、语言表匹配与重复定义、行列、注释、脚本字符串、变量候选、编码失败、XML 安全解析、符号链接、取消、CSV/JSON 以及命令行不完整报告。`examples` 全部为虚构自建数据，可直接试用。
