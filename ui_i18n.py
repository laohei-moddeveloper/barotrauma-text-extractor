"""UI-only localization. Game source/translation editors are never rewritten."""
import tkinter as tk
from tkinter import ttk

CATALOG = {
    'MyMemory 免费接口':'MyMemory free endpoint',
    'Google 网页兼容（实验）':'Google web compatibility (experimental)',
    '免费联网渠道（切换只影响未完成文字，已有译文保留）':'Free online channel (changes affect unfinished text only)',
    'MyMemory 有每日额度；Google 网页兼容是实验接口，大陆可能无法直连，稳定性无保证。只发送到你选的渠道，不自动转发至其他服务。':'MyMemory has daily limits. Google web compatibility is experimental, may be unreachable in mainland China, and has no stability guarantee. Text is sent only to your selected channel; no automatic forwarding.',

    "试译运行中":"Translation running", "试译已停止":"Translation stopped", "已采集 ":"Captured: ", "已译 ":"Translated: ",
    "默认免配置联网翻译，点击翻译才发送文字；也可选择离线或自定义 AI，不下载模型。":"Online translation needs no setup. Text is sent only when translating. Offline and custom AI options remain available; no models are downloaded.",
    "保持桌面工作台运行，游戏按钮默认直接联网翻译，无需填写配置；译文直接更新原生文字。也可选择离线或自定义 AI。":"Keep the desktop running. The game button translates online by default, with no setup, and updates native text. Offline or custom AI is also available.",
    "免配置联网翻译":"Online translation · no setup",
    "MyMemory 免费联网翻译":"MyMemory free online translation",
    "机器翻译草稿（未校对）":"Machine translation draft (unreviewed)",
    "免配置联网翻译无需账号、模型或密钥，使用 MyMemory 免费接口，有日额度限制。下面的 API 字段仅供自定义服务。":"No account, model or key needed. Uses the free MyMemory endpoint with daily limits. API fields below are for custom providers only.",
    "允许游戏按钮使用当前在线服务（仅本次桌面会话）":"Allow the game button to use this online provider (this session only)",
    "开启后，游戏按钮会发送采集文字、语境和相关术语到上面的服务。请自行确认服务费用；程序不购买额度、不下载模型、不自动重试。":"When enabled, the game button sends captured text, context and relevant terms to this provider. Check its pricing. No credit purchases, model downloads or automatic retries.",
    "保持桌面工作台运行，游戏按钮可用离线记忆、本机 AI，或在翻译设置中明确开启的在线服务。译文直接更新原生文字。":"Keep the desktop running. The game button uses offline memory, local AI, or the online provider explicitly enabled in Translation settings. Translations update native text directly.",
    "请在翻译设置中开启游戏按钮联网，或使用离线/本机服务。":"Enable online game requests in Translation settings, or use an offline/local provider.",
    "离线":"Offline", "归并为 ":"Grouped into ", " 条原文，保留 ":" source rows; retained ", "诊断 ":"Diagnostics: ", " 条。":" rows.",

    "无标签的拉丁文字建议手动指定语言":"Select untagged Latin languages manually",

    "识别语言和目标语言相同，请选择不同的语言对。":"Source and target languages match. Select a different pair.",
    "同一原文对应多个已有目标译文，请按上下文校对或拆分语境。":"Multiple existing target translations. Review the contexts or split the meanings.",
    "本地化键（需要由模组实际引用）":"Localization key (must be referenced by the mod)",
    "插件目录已存在；请连接已有插件，或先手动备份旧版本":"Companion folder exists. Connect it, or back up the older version first.",
    "添加词条":"Add entry", "模型（需已安装 / 已可用）":"Model (must already be available)",
    "条；未解析引用":"rows; unresolved references", "条草稿，请检查右侧质量提示并校对。":"drafts. Check the quality panel and review.",
    "条；已有译文不会被覆盖，导入内容作为草稿。":"rows. Existing translations preserved; imports are drafts.",
    "个语言键，":"language keys, ","条显示文字；":"displayed strings; ","条跳过。等待客户端刷新。":"skipped. Awaiting client refresh.",
    "发送到游戏：":"Sent to game: ","本批生成 ":"Drafted this batch: ","导入 ":"Imported: ",
    "条译文；":"translations; ","条尚无匹配。可配置已安装的本地 AI 继续生成。":"unmatched. Configure an installed local model to continue.",
    "复用 ":"Reused: ", "发送 ":"Sending: ", "条去重原文到 ":"unique sources to ", "；生成后仍需校对。":"; review the drafts afterward.",
    "用户指定":"Manually selected", "语言表 language 属性":"Language-pack metadata",
    " 条":" rows", " 已校对":" reviewed", " 草稿":" drafts", " 个来源":" occurrences",
    "扫描 ":"Scanned ", " 文件":" files", " 去重":" unique ", " 完成":" completed",

    "安装或连接 AbyssTextLive":"Install or connect AbyssTextLive",
    "先安装 LuaCs 客户端，再将本工具的客户端插件放入游戏 LocalMods。":"Install the LuaCs client, then install this companion in the game's LocalMods folder.",
    "选择游戏 LocalMods 目录":"Choose the game's LocalMods folder",
    "安装到 LocalMods（新目录）":"Install in LocalMods (new folder)", "连接已安装插件":"Connect installed companion",
    "模组已有目标译文":"Existing target translation", "已安装插件：":"Companion installed: ",

    "识别语言":"Source language", "→   目标语言":"→   Target language", "目标译文":"Target translation",
    "译潜  AbyssText":"AbyssText", "采集源语言文字":"Capture source-language text",

    "译潜 AbyssText": "AbyssText", "汉化工作台": "Localization workbench",
    "把模组文字整理成可校对、可交付的汉化项目": "Extract with context. Translate, review, and deliver.",
    "导出汉化…": "Export…", "连接游戏": "Connect game", "翻译设置": "Translation settings",
    "模组目录": "Mod folder", "选择文件夹": "Browse", "提取 / 刷新  F5": "Extract / refresh  F5",
    "打开项目": "Open project", "保存  Ctrl+S": "Save  Ctrl+S", "文本分类": "Categories",
    "全部文本": "All text", "物品 / 生物": "Items / creatures", "症状 / 效果": "Afflictions / effects",
    "职业 / 天赋": "Jobs / talents", "任务 / 对话": "Missions / dialogue", "描述 / 提示": "Descriptions / hints",
    "界面 / 语言表": "UI / text packs", "脚本 / 待核查": "Scripts / candidates",
    "显示待核查候选": "Show candidates", "按清单筛选 XML": "Use filelist XML scope",
    "去重后的一行原文\n仍保留每个来源位置。": "One source row.\nEvery occurrence retained.",
    "导入术语 / 译文表": "Import glossary / CSV", "新增本地化词条": "Add localization entry",
    "诊断 / 未解析引用": "Diagnostics / missing keys", "全部状态": "All states", "有质量问题": "Quality issues",
    "未翻译": "Untranslated", "草稿": "Draft", "已校对": "Reviewed", "忽略": "Ignored",
    "搜索原文、译文、键名、文件或上下文  ·  Ctrl+F": "Search source, translation, key, file or context · Ctrl+F",
    "生成草稿 · 当前筛选": "Draft filtered text", "翻译选中": "Translate selection", "取消任务": "Cancel",
    "进度": "Status", "原文": "Source", "译文": "Translation", "来源": "Uses",
    "上一页": "Previous", "下一页": "Next", "每页 150 条": "150 rows per page",
    "翻译与校对": "Translate / review", "来源与依据": "Context", "汉化 XML": "Native XML",
    "简体中文译文": "Simplified Chinese translation", "校对完成 → 下一条": "Review → next",
    "Ctrl+Enter 校对并跳转 · 编辑译文会恢复草稿状态": "Ctrl+Enter: review and next · Editing returns to draft",
    "显示预览（排版示意）": "Display preview (layout illustration)",
    "同文不同义：按来源拆分": "Split contexts / meanings", "备注随项目保存": "Notes are saved in the project",
    "预览包含草稿；正式导出仅包含已校对且通过检查的条目。": "Preview includes drafts. Final exports include reviewed text that passes checks.",
    "选择一条原文，开始翻译。": "Select a source row to start translating.",
    "格式检查通过；请结合上下文校对。": "Format checks passed. Review the wording in context.",
    "等待译文；可人工输入或生成草稿。": "Enter a translation or generate a draft.",
    "选择草稿来源": "Choose a draft provider", "离线复用": "Offline reuse", "本地 / 自定义API": "Local / custom API",
    "默认离线，不会自动联网或下载模型。AI 仅在生成草稿时发送原文与相关术语。": "Offline by default. No automatic network requests or model downloads. AI receives source text and relevant terms only when drafting.",
    "兼容 API 地址（本地 Ollama 可用 http://127.0.0.1:11434/v1）": "Compatible API URL (local Ollama: http://127.0.0.1:11434/v1)",
    "模型（需已安装 / 已可用）": "Model (must already be installed / available)",
    "API 密钥（可空，只在当前会话内存中保留）": "API key (optional; session memory only)",
    "本地模型不产生 API 账单；自选外部服务可能按供应商计费。游戏内自动请求仅允许离线或本机地址。程序不预付、不代购、不自动重试收费请求。": "Local models have no API bill. External services may charge you. In-game automatic requests are restricted to offline or loopback providers. No purchases or automatic paid retries.",
    "保存设置（不发送请求）": "Save settings (no request)", "选择交付方式": "Choose an output",
    "原生汉化包": "Native language pack", "已有本地化键 → Translations.xml + filelist.xml；仅导出已校对译文。": "Known localization keys → Translations.xml + filelist.xml. Reviewed translations only.",
    "翻译后的模组副本": "Translated mod copy", "处理硬编码 XML / Lua / C# 字面量；检查源文件版本，写入全新目录。": "Translate hardcoded XML / Lua / C# literals into a new copy after verifying source fingerprints.",
    "CSV 校对工作表": "CSV review worksheet", "每条原文只导出一次，保留全部来源；可重新导入。": "One row per source with all occurrences retained. Can be imported again.",
    "完整汉化项目": "Complete project", "包含进度、备注、术语和译文记忆，便于继续工作。": "Keep progress, notes, glossary and translation memory for later.",
    "添加词条": "Add entry", "本地化键（需要由模组实际引用）": "Localization key (must actually be used by the mod)",
    "游戏内一键试译": "In-game translation preview", "游戏内按钮 → 采集未译英文 → 本地草稿 → 原生文本刷新": "Game button → collect English → local drafts → refresh native text",
    "保持桌面工作台运行，在游戏中点“译潜 · 一键试译”。使用离线记忆或你已安装的本地 AI。译文写入插件自己的语言文件和原控件文本，不加翻译悬浮层。": "Keep the workbench running and click the AbyssText button in game. Use offline memory or your installed local AI. Text is replaced in the plugin language file and native controls, without a translation overlay.",
    "允许游戏内试用未校对草稿（格式有问题的条目会跳过）": "Preview unreviewed drafts in game (invalid formats are skipped)",
    "把当前译文应用到游戏": "Apply translations to game",
    "插件需 LuaCs 客户端。尚未认证真实游戏；重建或缓存的界面可能需重开。可在游戏中停止试译并恢复原文本。": "Requires LuaCs client. Real-game behavior is not yet certified. Cached screens may need reopening. Stop preview in game to restore original text.",
    "保存更改": "Save changes", "当前项目有未保存更改，先保存吗？": "This project has unsaved changes. Save first?",
    "请输入不含账号、查询参数的 HTTP(S) API 地址": "Enter an HTTP(S) API URL without embedded credentials or query parameters.",
    "请填写模型名称": "Enter a model name.", "请输入原文和有效本地化键": "Enter source text and a valid localization key.",
    "请填写原文和有效本地化键": "Enter source text and a valid localization key.",
    "请选择存在的模组目录": "Select an existing mod folder.", "先选择模组目录并提取文字，或打开已有项目。": "Extract a mod folder or open a project first.",
    "从一个模组开始：打开文件夹、提取、校对、导出。源模组始终只读。": "Start with a mod: browse, extract, review, export. Source mods stay read-only.",
    "正在扫描；相同原文将自动归并。": "Scanning; exact duplicate sources will be grouped.",
    "范围内没有未翻译文本；已有译文不会自动覆盖。": "No untranslated rows in this scope. Existing translations are preserved.",
    "当前筛选内没有下一条待校对文本。": "No next unreviewed row in this filter.",
    "已按文件和键/上下文拆分，可分别编写译文。": "Split by file and key/context. You can now translate each meaning separately.",
    "当前文本只有一个来源语境，无需拆分。": "This text has only one context.",
    "去重工作表已导出，包含全部译文、状态和来源。": "Deduplicated worksheet exported with translations, states and occurrences.",
    "游戏内自动请求只支持离线或本机 AI；外部服务需在桌面手动生成。": "In-game automatic requests require offline or local AI. Start external requests manually on desktop.",
    "译文为空": "Empty translation", "占位符或格式标记不一致": "Placeholder / format marker mismatch",
    "首尾空白发生变化": "Leading / trailing whitespace changed", "换行数量不同": "Line break count changed",
    "译文与英文原文相同": "Translation is unchanged English", "包含无效 XML / 控制字符": "Invalid XML / control character",
    "项目已保存：": "Project saved: ", "自动保存失败：": "Autosave failed: ", "任务失败：": "Task failed: ",
    "任务未全部完成：": "Task incomplete: ", "游戏桥接：": "Game bridge: ",
    "桌面工作台": "Desktop workbench", "已连接游戏": "Game connected", "游戏桥接已连接 · 本地文件交换": "Game bridge connected · local file exchange",
    "条去重原文": "unique sources", "个来源": "occurrences", "未保存": "unsaved", "来源位置": "source locations",
    "扫描诊断": "Scan diagnostics", "诊断与未解析引用": "Diagnostics and unresolved references",
    "未解析引用（不会把键名当作英文原文翻译）": "Unresolved references (keys are not translated as English prose)",
    "归并来源": "Occurrences", "分类": "Category", "译文来源": "Translation origin", "人工编辑": "Manual edit",
    "键名": "Keys", "无原生键，属于硬编码或待核查文字": "No native key: hardcoded text or candidate",
    "同一原文对应多个已有中文，请按上下文校对或拆分语境。": "Multiple existing Chinese translations. Review context or split meanings.",
    "模组已有中文": "Existing Chinese in mod", "AI 草稿（未校对）": "AI draft (unreviewed)",
    "译文记忆 / 术语表": "Translation memory / glossary",
    "导出汉化成果": "Export localization", "选择待汉化模组": "Choose a source mod",
    "保存汉化项目": "Save localization project", "打开汉化项目": "Open localization project",
    "译潜项目": "AbyssText project", "汉化项目.abyss.json": "localization.abyss.json",
    "汉化工作表.csv": "localization.csv", "选择输出父目录；将在其中创建新目录": "Select a parent folder for the new output directory",
    "请选择安装后的 AbyssTextLive 插件目录": "Choose the installed AbyssTextLive plugin folder.",
    "请选择游戏 LocalMods 中已安装的 AbyssTextLive 插件目录": "Choose AbyssTextLive in the game's LocalMods folder",
    "请选择保存到源模组目录之外": "Save outside the source mod folder.",
    "请保存到源模组目录之外": "Save outside the source mod folder.",
    "请选择尚不存在的新目录，避免覆盖已有文件": "Choose a new directory; existing files will not be overwritten.",
    "请选择尚不存在的新目录": "Choose a directory that does not exist yet.",
    "没有已校对且可导出的本地化键；请先校对，硬编码文字使用翻译副本": "No reviewed exportable localization keys. Review first; use a translated copy for hardcoded text.",
    "没有可安全替换的已校对条目": "No reviewed entries can be safely replaced.",
    "无法连接翻译服务或请求超时；请确认本地模型已运行。本批次未写入。": "Could not connect or request timed out. Check that the local model is running. This batch was not applied.",
    "翻译服务返回格式无效，本批次未写入": "Invalid translation response. This batch was not applied.",
    "API 返回条目不完整，本批次未写入": "Incomplete API response. This batch was not applied.",
    "API 返回重复、未知 ID 或无效译文": "API returned duplicate/unknown IDs or invalid translations.",
    "请先处理质量检查：": "Resolve quality issues first: ",
    "源文件已变化，请重新扫描再导出：": "Source changed. Rescan before exporting: ",
    "本地化键译文冲突：": "Conflicting translations for localization key: ",
    "条原文": "source rows", "个来源。诊断": "occurrences. Diagnostics", "条；未解析引用": "entries; unresolved references",
    "汉化 XML": "Native XML", "简体中文": "Simplified Chinese",
}

FRAGMENTS = {k:v for k,v in CATALOG.items() if len(k)>=2}
REVERSE = {v:k for k,v in CATALOG.items()}


def canonical(value): return REVERSE.get(value,value)


def tr(value,language):
    if language=="zh":return value
    if value in CATALOG:return CATALOG[value]
    for chinese,english in sorted(FRAGMENTS.items(),key=lambda pair:len(pair[0]),reverse=True):
        value=value.replace(chinese,english)
    return value


class Localizer:
    def __init__(self,root,language="zh"):
        self.root,self.language=root,language
        self.widgets={}
        self.vars={}

    def variable(self,var):
        record={"source":var.get(),"last":None,"busy":False}
        self.vars[str(var)]=(var,record)
        def changed(*_):
            if record["busy"]:return
            value=var.get()
            if value!=record["last"]:record["source"]=value
            out=tr(record["source"],self.language)
            record["last"]=out
            if out!=value:
                record["busy"]=True;var.set(out);record["busy"]=False
        var.trace_add("write",changed)
        changed()

    def _text(self,widget,key,get,setter):
        try:value=get()
        except tk.TclError:return
        state=self.widgets.get((str(widget),key))
        if state is None or value!=state[1]:source=canonical(value)
        else:source=state[0]
        out=tr(source,self.language)
        self.widgets[(str(widget),key)]=(source,out)
        if out!=value:setter(out)

    def apply(self,widget=None):
        widget=widget or self.root
        self._text(widget,"text",lambda:widget.cget("text"),lambda v:widget.configure(text=v))
        if isinstance(widget,(tk.Tk,tk.Toplevel)):
            self._text(widget,"title",widget.title,widget.title)
        if isinstance(widget,ttk.Notebook):
            for tab in widget.tabs():self._text(widget,tab,lambda t=tab:widget.tab(t,"text"),lambda v,t=tab:widget.tab(t,text=v))
        if isinstance(widget,ttk.Treeview):
            for column in widget.cget("columns"):
                self._text(widget,"heading"+column,lambda c=column:widget.heading(c,"text"),lambda v,c=column:widget.heading(c,text=v))
        if isinstance(widget,ttk.Combobox):
            values=widget.cget("values")
            if values and all(canonical(v) in CATALOG for v in values):
                current=canonical(widget.get())
                widget.configure(values=[tr(canonical(v),self.language) for v in values])
                if current in CATALOG:widget.set(tr(current,self.language))
        for child in widget.winfo_children():self.apply(child)

    def switch(self,language):
        self.language=language
        for var,record in self.vars.values():
            record["busy"]=True
            record["last"]=tr(record["source"],language)
            var.set(record["last"])
            record["busy"]=False
        self.apply()
