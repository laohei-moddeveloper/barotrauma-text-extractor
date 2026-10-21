"""AbyssText translation workbench. All Tk access stays on the main thread."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font as tkfont
from urllib.parse import urlparse

from extractor import Entry, Report, VERSION, scan
from live_bridge import LiveBridge
from languages import NAMES
from translation_api import Settings, batches, translate, game_auto_allowed
from free_online import PROVIDER as FREE_ONLINE, TranslationCache
from workbench import Project, STATES, Unit, export_copy, export_csv, export_native, native_xml, source_id
from ui_i18n import Localizer, canonical, tr

BG, CARD, FIELD, LINE = "#f5f2ed", "#ffffff", "#fcfbf8", "#dfd8d3"
FG, MUTED, ACCENT, GOLD = "#2f2935", "#817988", "#704a82", "#a56824"
PAGE_SIZE = 150


class WorkbenchWindow:
    def __init__(self, root=None, preferences_path=None):
        self.root = root or tk.Tk()
        self.preferences_path=(Path(preferences_path) if preferences_path else
            Path(os.environ.get("LOCALAPPDATA",str(Path.home()/".config")))/"AbyssText"/"preferences.json") if preferences_path is not False else None
        preferences={}
        if self.preferences_path and self.preferences_path.is_file():
            try:
                if self.preferences_path.stat().st_size<1024*1024:preferences=json.loads(self.preferences_path.read_text(encoding="utf-8"))
            except (OSError,ValueError):pass
        if not isinstance(preferences,dict):preferences={}
        preferences={k:v for k,v in preferences.items() if isinstance(v,str)}
        self.ui_language=preferences.get("language","zh") if preferences.get("language") in {"zh","en"} else "zh"
        self.localizer=Localizer(self.root,self.ui_language)
        self.canon=canonical
        self.root.title(f"译潜 AbyssText {VERSION} · 汉化工作台")
        assets=Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))/"assets"
        if (assets/"abysstext.png").is_file():
            self.app_icon=tk.PhotoImage(file=str(assets/"abysstext.png"))
            self.root.iconphoto(True,self.app_icon)
        self.root.geometry("1440x900")
        self.root.minsize(1060, 700)
        self.root.configure(bg=BG)
        available=set(tkfont.families(self.root))
        self.ui_font=next((name for name in ["Microsoft YaHei UI","PingFang SC","Noto Sans CJK SC","WenQuanYi Micro Hei"] if name in available),"TkDefaultFont")
        self.project = None
        self.cache = {}
        self.api = Settings(preferences.get("endpoint","http://127.0.0.1:11434/v1"),preferences.get("model","qwen2.5:7b"))
        self.provider = tk.StringVar(value=preferences.get("provider",FREE_ONLINE))
        self.source_language=tk.StringVar(value="Auto")
        self.target_language=tk.StringVar(value="Simplified Chinese")
        self.folder = tk.StringVar()
        self.search = tk.StringVar()
        self.state_filter = tk.StringVar(value="全部状态")
        self.include_candidates = tk.BooleanVar(value=False)
        self.registered_only = tk.BooleanVar(value=True)
        self.category = "全部文本"
        self.status = tk.StringVar(value="从一个模组开始：打开文件夹、提取、校对、导出。源模组始终只读。")
        self.summary = tk.StringVar(value="0 条原文    /    0 已校对    /    0 个来源")
        self.mode_label = tk.StringVar(value="桌面工作台 · "+self.provider.get())
        self.page_label = tk.StringVar(value="0 / 0")
        self.qa_label = tk.StringVar(value="选择一条原文，开始翻译。")
        self.current_id = None
        self.filtered_units = []
        self.page = 0
        self.busy = False
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.pending_search = None
        self.pending_edit = None
        self.pending_save = None
        self.task_error = ""
        self.loading_editor = False
        self.bridge = None
        self.live_request = ""
        self.live_drafts = tk.BooleanVar(value=True)
        self.live_online = tk.BooleanVar(value=False)
        self.online_cache=TranslationCache()
        self._style()
        self._build()
        for var in [self.status,self.summary,self.mode_label,self.page_label,self.qa_label]:self.localizer.variable(var)
        self.localizer.apply()
        self.root.bind("<Control-f>", lambda _: self.search_entry.focus_set())
        self.root.bind("<Control-s>", lambda _: self.save_project())
        self.root.bind("<Control-Return>", lambda _: self.review_next())
        self.root.bind("<F5>", lambda _: self.start_scan())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.poll)
        self.root.after(1500, self.poll_live)
        self.root.after(500,self.localize_widgets)

    def tr(self,text):return tr(text,self.ui_language)

    def localize_widgets(self):
        self.localizer.apply()
        self.root.after(500,self.localize_widgets)

    def save_preferences(self):
        if not self.preferences_path:return
        from workbench import atomic_write
        try:atomic_write(self.preferences_path,json.dumps({"language":self.ui_language,"provider":self.canon(self.provider.get()),"endpoint":self.api.endpoint,"model":self.api.model},ensure_ascii=False))
        except OSError as error:self.status.set("设置保存失败："+str(error))

    def set_language(self,language):
        self.commit_editor()
        self.ui_language=language
        self.localizer.switch(language)
        self.language_choice.set("English" if language=="en" else "中文")
        self.table.column("state",width=102 if language=="en" else 74)
        self.refresh(reset_page=False)
        self.save_preferences()
        if self.bridge:self.write_live_preferences()

    def write_live_preferences(self):
        if self.bridge:
            self.bridge.configure(self.ui_language,self.project.source_language if self.project and self.source_language.get()=="Auto" else self.source_language.get(),self.target_language.get())

    def change_languages(self):
        if self.busy:
            if self.project:
                self.source_language.set(self.project.source_choice)
                self.target_language.set(self.project.target_language)
            return
        self.commit_editor()
        if self.project:
            if not self.confirm_unsaved():
                self.source_language.set(self.project.source_choice)
                self.target_language.set(self.project.target_language)
                return
            previous=self.project
            project=Project(previous.report,previous,self.source_language.get(),self.target_language.get())
            if (project.source_language,project.target_language)==(previous.source_language,previous.target_language):project.path=previous.path
            project.dirty=True
            self.install_project(project)
            self.status.set(f"{project.source_language} → {project.target_language} · {project.detection}")
        self.live_request=""
        if self.bridge:self.write_live_preferences()

    def _style(self):
        self.root.option_add("*Font", (self.ui_font, 10))
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=LINE)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Card.TLabel", background=CARD)
        style.configure("Title.TLabel", font=(self.ui_font, 23, "bold"))
        style.configure("TButton", background=CARD, foreground=FG, padding=(12, 8), borderwidth=0)
        style.map("TButton", background=[("active", LINE), ("disabled", BG)], foreground=[("disabled", MUTED)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=(self.ui_font, 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#886094"), ("disabled", LINE)])
        style.configure("Nav.TButton", anchor="w", padding=(10, 7))
        style.configure("Selected.Nav.TButton", anchor="w", background="#e9ddeb", foreground=ACCENT, padding=(10, 7))
        style.configure("TEntry", padding=7, fieldbackground=FIELD, foreground=FG)
        style.configure("TCombobox", padding=6, fieldbackground=FIELD, foreground=FG, arrowcolor=ACCENT)
        style.map("TCombobox", fieldbackground=[("readonly",FIELD)], foreground=[("readonly",FG)])
        style.configure("TCheckbutton", padding=4, background=BG)
        style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FG, rowheight=38, borderwidth=0)
        style.map("Treeview", background=[("selected", "#e9ddeb")], foreground=[("selected", "#492956")])
        style.configure("Treeview.Heading", background=CARD, foreground=MUTED, padding=(10, 12), relief="flat")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, padding=(14, 9))
        style.map("TNotebook.Tab", background=[("selected",LINE)], foreground=[("selected",ACCENT)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=CARD)

    def _text(self, parent, height, readonly=False):
        widget = tk.Text(parent, height=height, wrap="word", bg=FIELD, fg=FG, insertbackground=ACCENT,
                         selectbackground="#e9ddeb", relief="flat", padx=12, pady=10, undo=not readonly,
                         font=(self.ui_font, 11), highlightthickness=1, highlightbackground=LINE)
        if readonly: widget.configure(state="disabled")
        return widget

    @staticmethod
    def set_text(widget, content):
        disabled = str(widget.cget("state")) == "disabled"
        if disabled: widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        if disabled: widget.configure(state="disabled")

    def _build(self):
        shell = ttk.Frame(self.root, padding=18)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 16))
        brand = ttk.Frame(header)
        brand.pack(side="left")
        ttk.Label(brand, text="译潜  AbyssText", style="Title.TLabel",font=(self.ui_font,23,"bold")).pack(anchor="w")
        ttk.Label(brand, text="把模组文字整理成可校对、可交付的汉化项目", style="Muted.TLabel").pack(anchor="w", pady=(4,0))
        ttk.Button(header, text="导出汉化…", style="Accent.TButton", command=self.export_dialog).pack(side="right")
        ttk.Button(header, text="连接游戏", command=self.connect_live).pack(side="right", padx=6)
        ttk.Button(header, text="翻译设置", command=self.settings_dialog).pack(side="right")
        self.language_choice=tk.StringVar(value="English" if self.ui_language=="en" else "中文")
        picker=ttk.Combobox(header,textvariable=self.language_choice,state="readonly",width=8,values=["中文","English"])
        picker.pack(side="right",padx=12)
        picker.bind("<<ComboboxSelected>>",lambda _:self.set_language("en" if self.language_choice.get()=="English" else "zh"))
        sourcebar = ttk.Frame(shell)
        sourcebar.pack(fill="x", pady=(0,10))
        ttk.Label(sourcebar,text="模组目录").pack(side="left",padx=(0,10))
        ttk.Entry(sourcebar,textvariable=self.folder).pack(side="left",fill="x",expand=True)
        ttk.Button(sourcebar,text="选择文件夹",command=self.choose_folder).pack(side="left",padx=6)
        self.scan_button = ttk.Button(sourcebar,text="提取 / 刷新  F5",command=self.start_scan)
        self.scan_button.pack(side="left")
        ttk.Button(sourcebar,text="打开项目",command=self.open_project).pack(side="left",padx=6)
        ttk.Button(sourcebar,text="保存  Ctrl+S",command=self.save_project).pack(side="left")
        languagebar=ttk.Frame(shell)
        languagebar.pack(fill="x",pady=(0,10))
        ttk.Label(languagebar,text="识别语言").pack(side="left",padx=(0,8))
        sourcebox=ttk.Combobox(languagebar,textvariable=self.source_language,values=["Auto",*NAMES],state="readonly",width=22)
        sourcebox.pack(side="left")
        ttk.Label(languagebar,text="→   目标语言").pack(side="left",padx=12)
        targetbox=ttk.Combobox(languagebar,textvariable=self.target_language,values=NAMES,state="readonly",width=22)
        targetbox.pack(side="left")
        sourcebox.bind("<<ComboboxSelected>>",lambda _:self.change_languages())
        targetbox.bind("<<ComboboxSelected>>",lambda _:self.change_languages())
        ttk.Label(languagebar,text="无标签的拉丁文字建议手动指定语言",style="Muted.TLabel").pack(side="left",padx=12)
        stats=ttk.Frame(shell)
        stats.pack(fill="x",pady=(0,12))
        ttk.Label(stats,textvariable=self.summary,foreground=ACCENT).pack(side="left")
        ttk.Label(stats,textvariable=self.mode_label,style="Muted.TLabel").pack(side="right")
        workspace=ttk.Panedwindow(shell,orient="horizontal")
        workspace.pack(fill="both",expand=True)
        sidehost=ttk.Frame(workspace,padding=(0,0,12,0))
        workspace.add(sidehost,weight=0)
        sidecanvas=tk.Canvas(sidehost,width=205,bg=BG,highlightthickness=0)
        sidecanvas.pack(side="left",fill="both",expand=True)
        sidescroll=ttk.Scrollbar(sidehost,orient="vertical",command=sidecanvas.yview)
        sidescroll.pack(side="right",fill="y")
        sidecanvas.configure(yscrollcommand=sidescroll.set)
        sidebar=ttk.Frame(sidecanvas)
        sidewindow=sidecanvas.create_window((0,0),window=sidebar,anchor="nw")
        sidebar.bind("<Configure>",lambda _:sidecanvas.configure(scrollregion=sidecanvas.bbox("all")))
        sidecanvas.bind("<Configure>",lambda event:sidecanvas.itemconfigure(sidewindow,width=event.width))
        ttk.Label(sidebar,text="文本分类",style="Muted.TLabel").pack(anchor="w",pady=(8,10))
        self.nav=ttk.Frame(sidebar)
        self.nav.pack(fill="x")
        self.nav_buttons={}
        for label in ["全部文本","物品 / 生物","症状 / 效果","职业 / 天赋","任务 / 对话","描述 / 提示","界面 / 语言表","脚本 / 待核查"]:
            button=ttk.Button(self.nav,text=label,width=18,style="Nav.TButton",command=lambda name=label:self.set_category(name))
            button.pack(fill="x",pady=2)
            self.nav_buttons[label]=button
        ttk.Separator(sidebar).pack(fill="x",pady=14)
        ttk.Checkbutton(sidebar,text="显示待核查候选",variable=self.include_candidates,command=self.refresh).pack(anchor="w")
        ttk.Checkbutton(sidebar,text="按清单筛选 XML",variable=self.registered_only).pack(anchor="w")
        ttk.Label(sidebar,text="去重后的一行原文\n仍保留每个来源位置。",style="Muted.TLabel",justify="left").pack(anchor="w",pady=12)
        ttk.Button(sidebar,text="导入术语 / 译文表",command=self.import_table).pack(fill="x",pady=3)
        ttk.Button(sidebar,text="新增本地化词条",command=self.add_unit).pack(fill="x",pady=3)
        ttk.Button(sidebar,text="诊断 / 未解析引用",command=self.show_diagnostics).pack(fill="x",pady=3)
        center=ttk.Frame(workspace,padding=(4,0,12,0))
        workspace.add(center,weight=3)
        filters=ttk.Frame(center)
        filters.pack(fill="x",pady=(0,8))
        self.search_entry=ttk.Entry(filters,textvariable=self.search)
        self.search_entry.pack(fill="x",expand=True,side="left",padx=(0,6))
        self.search_entry.bind("<Escape>",lambda _:self.search.set(""))
        combo=ttk.Combobox(filters,textvariable=self.state_filter,state="readonly",width=12,
                           values=["全部状态",*STATES,"有质量问题"])
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>",lambda _:self.refresh())
        ttk.Label(center,text="搜索原文、译文、键名、文件或上下文  ·  Ctrl+F",style="Muted.TLabel").pack(anchor="w",pady=(0,8))
        actions=ttk.Frame(center)
        actions.pack(fill="x",pady=(0,10))
        ttk.Button(actions,text="生成草稿 · 当前筛选",style="Accent.TButton",command=self.start_drafts).pack(side="left")
        ttk.Button(actions,text="翻译选中",command=lambda:self.start_drafts(selected=True)).pack(side="left",padx=6)
        ttk.Button(actions,text="取消任务",command=self.cancel.set).pack(side="right")
        tableframe=ttk.Frame(center)
        tableframe.pack(fill="both",expand=True)
        tableframe.rowconfigure(0,weight=1)
        tableframe.columnconfigure(0,weight=1)
        self.table=ttk.Treeview(tableframe,columns=("state","source","target","count"),show="headings",selectmode="extended")
        for name,label,width in [("state","进度",102 if self.ui_language=="en" else 74),("source","原文",240),("target","译文",220),("count","来源",48)]:
            self.table.heading(name,text=label)
            self.table.column(name,width=width,minwidth=40)
        self.table.grid(row=0,column=0,sticky="nsew")
        scroll=ttk.Scrollbar(tableframe,orient="vertical",command=self.table.yview)
        scroll.grid(row=0,column=1,sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.tag_configure("reviewed",foreground=ACCENT)
        self.table.tag_configure("issue",foreground=GOLD)
        self.table.tag_configure("ignored",foreground=MUTED)
        self.table.bind("<<TreeviewSelect>>",self.select_unit)
        self.table.bind("<Double-1>",lambda _:self.target_text.focus_set())
        pager=ttk.Frame(center)
        pager.pack(fill="x",pady=(8,0))
        ttk.Button(pager,text="上一页",command=lambda:self.turn_page(-1)).pack(side="left")
        ttk.Label(pager,textvariable=self.page_label).pack(side="left",padx=12)
        ttk.Button(pager,text="下一页",command=lambda:self.turn_page(1)).pack(side="left")
        ttk.Label(pager,text="每页 150 条",style="Muted.TLabel").pack(side="right")
        center.columnconfigure(0,weight=1)
        packed=[(child,child.pack_info()) for child in center.winfo_children()]
        for child,options in packed:child.pack_forget()
        for row,(child,options) in enumerate(packed):
            child.grid(row=row,column=0,sticky="nsew" if child==tableframe else "ew",pady=options.get("pady",0))
            if child==tableframe:center.rowconfigure(row,weight=1)
        right=ttk.Frame(workspace,padding=(6,0,0,0))
        workspace.add(right,weight=2)
        self.tabs=ttk.Notebook(right)
        self.tabs.pack(fill="both",expand=True)
        editorhost=ttk.Frame(self.tabs)
        editorcanvas=tk.Canvas(editorhost,bg=CARD,highlightthickness=0)
        editorscroll=ttk.Scrollbar(editorhost,orient="vertical",command=editorcanvas.yview)
        editorscroll.pack(side="right",fill="y")
        editorcanvas.pack(side="left",fill="both",expand=True)
        editorcanvas.configure(yscrollcommand=editorscroll.set)
        editor=ttk.Frame(editorcanvas,padding=8)
        editorwindow=editorcanvas.create_window((0,0),window=editor,anchor="nw")
        editor.bind("<Configure>",lambda _:editorcanvas.configure(scrollregion=editorcanvas.bbox("all")))
        def fit_editor(event):
            # Keep the editor usable at high font DPI; excess height is scrollable.
            scale=float(self.root.tk.call("tk","scaling"))/(96/72)
            editorcanvas.itemconfigure(editorwindow,width=event.width,height=max(event.height,int(550*scale)))
        editorcanvas.bind("<Configure>",fit_editor)
        evidence=ttk.Frame(self.tabs,padding=8)
        xmltab=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(editorhost,text="翻译与校对")
        self.tabs.add(evidence,text="来源与依据")
        self.tabs.add(xmltab,text="汉化 XML")
        ttk.Label(editor,text="原文",style="Muted.TLabel").pack(anchor="w",pady=(8,6))
        self.source_text=self._text(editor,6,True)
        self.source_text.pack(fill="both",expand=True)
        ttk.Label(editor,text="目标译文",foreground=ACCENT).pack(anchor="w",pady=(14,6))
        self.target_text=self._text(editor,7)
        self.target_text.pack(fill="both",expand=True)
        self.target_text.bind("<<Modified>>",self.editor_changed)
        ttk.Label(editor,textvariable=self.qa_label,foreground=GOLD,wraplength=350).pack(anchor="w",pady=8)
        review=ttk.Frame(editor)
        review.pack(fill="x")
        ttk.Button(review,text="校对完成 → 下一条",style="Accent.TButton",command=self.review_next).pack(side="left")
        ttk.Button(review,text="忽略",command=self.ignore_current).pack(side="right")
        ttk.Label(editor,text="Ctrl+Enter 校对并跳转 · 编辑译文会恢复草稿状态",style="Muted.TLabel",wraplength=350).pack(anchor="w",pady=(6,10))
        ttk.Label(editor,text="显示预览（排版示意）",style="Muted.TLabel").pack(anchor="w",pady=(0,6))
        self.preview=self._text(editor,4,True)
        self.preview.pack(fill="both",expand=True)
        # Grid lets all three text fields shrink together on smaller windows.
        editor.columnconfigure(0,weight=1)
        packed=[(child,child.pack_info()) for child in editor.winfo_children()]
        for child,options in packed:child.pack_forget()
        for row,(child,options) in enumerate(packed):
            child.grid(row=row,column=0,sticky="nsew" if isinstance(child,tk.Text) else "ew",pady=options.get("pady",0))
            if isinstance(child,tk.Text):editor.rowconfigure(row,weight=2 if child==self.target_text else 1,minsize=45)
        self.evidence_text=self._text(evidence,16,True)
        self.evidence_text.pack(fill="both",expand=True)
        ttk.Button(evidence,text="同文不同义：按来源拆分",command=self.split_context).pack(fill="x",pady=8)
        self.notes=self._text(evidence,3)
        self.notes.pack(fill="x")
        self.notes.bind("<<Modified>>",self.editor_changed)
        ttk.Label(evidence,text="备注随项目保存",style="Muted.TLabel").pack(anchor="w",pady=5)
        ttk.Label(xmltab,text="预览包含草稿；正式导出仅包含已校对且通过检查的条目。",wraplength=350,style="Muted.TLabel").pack(anchor="w",pady=6)
        self.xml_text=self._text(xmltab,25,True)
        self.xml_text.configure(font=(self.ui_font,10))
        self.xml_text.pack(fill="both",expand=True)
        self.progress=ttk.Progressbar(shell,mode="indeterminate")
        self.progress.pack(fill="x",pady=(12,6))
        ttk.Label(shell,textvariable=self.status,style="Muted.TLabel",wraplength=1320).pack(anchor="w")
        # Reserve footer space before giving remaining height to the workspace.
        shell.columnconfigure(0,weight=1)
        packed=[(child,child.pack_info()) for child in shell.winfo_children()]
        for child,options in packed:child.pack_forget()
        for row,(child,options) in enumerate(packed):
            child.grid(row=row,column=0,sticky="nsew" if child==workspace else "ew",pady=options.get("pady",0))
            if child==workspace:shell.rowconfigure(row,weight=1)
        self.search.trace_add("write",self.search_changed)
        self.set_category("全部文本")

    def error(self, error):
        self.status.set(str(error))
        messagebox.showerror("AbyssText",self.tr(str(error)),parent=self.root)

    def choose_folder(self):
        path=filedialog.askdirectory(title=self.tr("选择待汉化模组"))
        if path: self.folder.set(path)

    def ensure_project(self):
        if not self.project:
            self.status.set("先选择模组目录并提取文字，或打开已有项目。")
            return False
        return True

    def confirm_unsaved(self):
        self.commit_editor()
        if not self.project or not self.project.dirty:return True
        answer=messagebox.askyesnocancel(self.tr("保存更改"),self.tr("当前项目有未保存更改，先保存吗？"),parent=self.root)
        if answer is None:return False
        return self.save_project() if answer else True

    def set_busy(self,value):
        self.busy=value
        self.scan_button.configure(state="disabled" if value else "normal")
        if value:self.progress.start(12)
        else:self.progress.stop()

    def start_scan(self):
        if self.busy:return
        self.commit_editor()
        path=self.folder.get()
        if not Path(path).is_dir():return self.error(ValueError("请选择存在的模组目录"))
        if self.project and Path(path).resolve()!=Path(self.project.report.root) and not self.confirm_unsaved():return
        previous=self.project if self.project and (Path(path).resolve()==Path(self.project.report.root) or not Path(self.project.report.root).is_dir()) else None
        self.cancel.clear()
        self.set_busy(True)
        self.status.set("正在扫描；相同原文将自动归并。")
        # Scope the cache to this source to avoid retaining old projects indefinitely.
        self.cache={k:v for k,v in self.cache.items() if k[0]==str(Path(path).resolve())}
        registered_only=self.registered_only.get()
        source_language,target_language=self.source_language.get(),self.target_language.get()
        def worker():
            try:
                report=scan(Path(path),self.cancel.is_set,self.cache,
                    lambda file,count:self.events.put(("progress",f"已扫描 {count} 文件 · {file}")) if count%25==0 else None,
                    registered_only=registered_only)
                self.cache={k:v for k,v in self.cache.items() if k[2]==report.fingerprints.get(k[1])}
                project=Project(report,previous,source_language,target_language)
                if previous:project.path,project.dirty=previous.path,True
                self.events.put(("project",project))
            except Exception as error:self.events.put(("error",str(error)))
            finally:self.events.put(("done",None))
        threading.Thread(target=worker,daemon=True).start()

    def install_project(self,project):
        self.current_id=None
        self.project=project
        self.folder.set(project.report.root)
        self.source_language.set(project.source_choice)
        self.target_language.set(project.target_language)
        self.refresh()
        self.update_summary()
        diagnostics=len(project.report.diagnostics)
        self.status.set(f"归并为 {len(project.units)} 条原文，保留 {sum(len(u.occurrences) for u in project.units)} 个来源。诊断 {diagnostics} 条；未解析引用 {len(project.unresolved)} 条。")
        first=self.table.get_children()
        if first:self.table.selection_set(first[0]);self.select_unit()

    def update_summary(self):
        if not self.project:return
        counts=Counter(u.state for u in self.project.units)
        self.summary.set(f"{len(self.project.units):,} 条去重原文    /    {counts['已校对']:,} 已校对    /    {counts['草稿']:,} 草稿    /    {sum(len(u.occurrences) for u in self.project.units):,} 个来源" + ("    ● 未保存" if self.project.dirty else ""))
        cats=Counter(c for u in self.project.units for c in u.categories)
        for label,button in self.nav_buttons.items():
            button.configure(text=f"{label}  {len(self.project.units) if label=='全部文本' else cats[label]}")
        if self.project.dirty and self.project.path:
            if self.pending_save:self.root.after_cancel(self.pending_save)
            self.pending_save=self.root.after(2000,self.autosave)

    def autosave(self):
        self.pending_save=None
        if self.project and self.project.path and self.project.dirty:
            try:self.project.save(self.project.path);self.update_summary()
            except (OSError,ValueError) as error:self.status.set("自动保存失败："+str(error))

    def set_category(self,name):
        self.category=name
        for label,button in self.nav_buttons.items():button.configure(style="Selected.Nav.TButton" if label==name else "Nav.TButton")
        self.refresh()

    def search_changed(self,*_):
        if self.pending_search:self.root.after_cancel(self.pending_search)
        self.pending_search=self.root.after(180,self.refresh)

    def refresh(self,reset_page=True):
        self.pending_search=None
        self.commit_editor()
        if not self.project:return
        if reset_page:self.page=0
        self.filtered_units=self.project.filtered(self.search.get(),self.category,self.canon(self.state_filter.get()),self.include_candidates.get())
        maxpage=max(0,(len(self.filtered_units)-1)//PAGE_SIZE)
        self.page=min(self.page,maxpage)
        self.table.delete(*self.table.get_children())
        for unit in self.filtered_units[self.page*PAGE_SIZE:(self.page+1)*PAGE_SIZE]:
            tag="issue" if unit.issues else "reviewed" if unit.state=="已校对" else "ignored" if unit.state=="忽略" else ""
            self.table.insert("","end",iid=unit.id,values=(self.tr(unit.state),unit.source.replace("\n"," ↵ ")[:180],unit.translation.replace("\n"," ↵ ")[:160],len(unit.occurrences)),tags=(tag,))
        self.page_label.set(f"{self.page+1 if self.filtered_units else 0} / {maxpage+1 if self.filtered_units else 0}  ·  {len(self.filtered_units):,} 条")
        if self.current_id and self.table.exists(self.current_id):self.table.selection_set(self.current_id)

    def turn_page(self,offset):
        self.page=max(0,self.page+offset)
        self.refresh(reset_page=False)

    def select_unit(self,_=None):
        selection=self.table.selection()
        if not selection or not self.project:return
        unit_id=selection[0]
        if unit_id==self.current_id:return
        self.commit_editor()
        self.current_id=unit_id
        unit=self.project.by_id[unit_id]
        self.loading_editor=True
        self.set_text(self.source_text,unit.source)
        self.set_text(self.target_text,unit.translation)
        self.set_text(self.notes,unit.notes)
        self.target_text.edit_reset();self.target_text.edit_modified(False)
        self.notes.edit_modified(False)
        details=[f"归并来源：{len(unit.occurrences)}\n分类：{' / '.join(unit.categories)}\n译文来源：{unit.origin or '人工编辑'}\n键名：{', '.join(unit.keys) or '无原生键，属于硬编码或待核查文字'}\n"]
        for e in unit.occurrences:
            details.append(f"{e.file}:{e.line}:{e.column}\n{e.context}\n{e.evidence}\n")
        self.set_text(self.evidence_text,self.tr(details[0])+"\n"+"\n".join(details[1:]))
        self.loading_editor=False
        self.update_preview()

    def editor_changed(self,_=None):
        if self.loading_editor:return
        if not self.target_text.edit_modified() and not self.notes.edit_modified():return
        self.target_text.edit_modified(False);self.notes.edit_modified(False)
        if self.pending_edit:self.root.after_cancel(self.pending_edit)
        self.pending_edit=self.root.after(350,self.commit_editor)

    def commit_editor(self):
        if self.pending_edit:self.root.after_cancel(self.pending_edit);self.pending_edit=None
        if self.loading_editor or not self.project or self.current_id not in self.project.by_id:return
        unit=self.project.by_id[self.current_id]
        target=self.target_text.get("1.0","end-1c")
        notes=self.notes.get("1.0","end-1c")
        if target!=unit.translation or notes!=unit.notes:
            self.project.update(unit.id,target,notes=notes)
            if self.table.exists(unit.id):self.table.set(unit.id,"state",self.tr(unit.state));self.table.set(unit.id,"target",target.replace("\n"," ↵ ")[:160])
            self.update_summary()
            self.update_preview()

    def update_preview(self):
        if not self.project or self.current_id not in self.project.by_id:return
        unit=self.project.by_id[self.current_id]
        self.qa_label.set(" · ".join(unit.issues) if unit.issues else "格式检查通过；请结合上下文校对。" if unit.translation else "等待译文；可人工输入或生成草稿。")
        self.set_text(self.preview,re.sub(r"‖[^‖]+‖","",unit.translation or unit.source))
        # Generate the large XML only on demand, not for every editor keystroke.
        if self.tabs.index(self.tabs.select())==2:self.refresh_xml()

    def refresh_xml(self):
        if not self.project:return
        try:
            content,notes,count=native_xml(self.project,include_drafts=True)
            self.set_text(self.xml_text,content+f"\n\n<!-- {count} 个可用键；{len(notes)} 条需人工适配 -->")
        except ValueError as error:self.set_text(self.xml_text,str(error))

    def review_next(self):
        if not self.ensure_project() or not self.current_id:return
        self.commit_editor()
        unit=self.project.by_id[self.current_id]
        try:self.project.update(unit.id,unit.translation,state="已校对",notes=unit.notes)
        except ValueError as error:return self.error(error)
        ids=[u.id for u in self.filtered_units]
        index=ids.index(unit.id) if unit.id in ids else -1
        next_id=next((uid for uid in ids[index+1:] if self.project.by_id[uid].state not in {"已校对","忽略"}),None)
        self.update_summary()
        if self.table.exists(unit.id):self.table.set(unit.id,"state",self.tr("已校对"));self.table.item(unit.id,tags=("reviewed",))
        if next_id:
            self.page=ids.index(next_id)//PAGE_SIZE
            self.refresh(reset_page=False)
            self.table.selection_set(next_id);self.table.see(next_id);self.select_unit()
        else:self.status.set("当前筛选内没有下一条待校对文本。")

    def ignore_current(self):
        if not self.project or not self.current_id:return
        self.commit_editor()
        unit=self.project.by_id[self.current_id]
        self.project.update(unit.id,unit.translation,state="忽略",notes=unit.notes)
        self.refresh(reset_page=False);self.update_summary()

    def split_context(self):
        if not self.project or not self.current_id:return
        self.commit_editor()
        if self.project.split_context(self.current_id):
            self.current_id=None;self.refresh();self.update_summary()
            self.status.set("已按文件和键/上下文拆分，可分别编写译文。")
        else:self.status.set("当前文本只有一个来源语境，无需拆分。")

    def save_project(self,as_new=False):
        if not self.ensure_project():return False
        self.commit_editor()
        path=None if as_new else self.project.path
        if not path:path=filedialog.asksaveasfilename(title=self.tr("保存汉化项目"),defaultextension=".abyss.json",filetypes=[(self.tr("译潜项目"),"*.json")],initialfile=self.tr("汉化项目.abyss.json"))
        if not path:return False
        try:self.project.save(path);self.update_summary();self.status.set("项目已保存："+str(path));return True
        except (OSError,ValueError) as error:self.error(error);return False

    def open_project(self):
        if self.busy or not self.confirm_unsaved():return
        path=filedialog.askopenfilename(title=self.tr("打开汉化项目"),filetypes=[(self.tr("译潜项目"),"*.json")])
        if not path:return
        try:self.install_project(Project.load(path))
        except (OSError,ValueError,KeyError,TypeError) as error:self.error(error)

    def import_table(self):
        if not self.ensure_project():return
        path=filedialog.askopenfilename(filetypes=[("译文 CSV / 术语 JSON","*.csv *.json")])
        if not path:return
        self.commit_editor()
        try:
            count=self.project.import_table(path)
            current=self.current_id;self.current_id=None
            self.refresh();self.update_summary()
            if current and self.table.exists(current):self.table.selection_set(current);self.select_unit()
            self.status.set(f"导入 {count} 条；已有译文不会被覆盖，导入内容作为草稿。")
        except (OSError,ValueError,KeyError) as error:self.error(error)

    def add_unit(self):
        if not self.ensure_project():return
        dialog=tk.Toplevel(self.root);dialog.title("新增本地化词条");dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=18);frame.pack(fill="both",expand=True)
        fields=[]
        for name in ["原文","本地化键（需要由模组实际引用）"]:
            ttk.Label(frame,text=name).pack(anchor="w",pady=(8,4))
            field=ttk.Entry(frame,width=52);field.pack(fill="x");fields.append(field)
        def apply():
            text,key=(field.get() for field in fields)
            if not text.strip() or not re.fullmatch(r"[A-Za-z_][\w.\-]*",key):return self.error(ValueError("请填写原文和有效本地化键"))
            entry=Entry(source_id(text),"<手动>",1,1,"语言表","literal",text,key=key,language=self.project.source_language,location={"native_key":key},evidence="用户新增，键需要模组引用")
            uid=source_id(text,self.project.source_language)
            if uid in self.project.by_id:self.project.by_id[uid].occurrences.append(entry)
            else:self.project.units.append(Unit(uid,text,occurrences=[entry],source_language=self.project.source_language))
            self.project._index();self.project.dirty=True
            self.refresh();self.update_summary();dialog.destroy()
        ttk.Button(frame,text="添加词条",style="Accent.TButton",command=apply).pack(pady=14)

    def settings_dialog(self):
        dialog=tk.Toplevel(self.root);dialog.title("翻译服务设置");dialog.configure(bg=BG)
        dialog.geometry("780x650")
        frame=ttk.Frame(dialog,padding=22);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="选择草稿来源",font=(self.ui_font,16,"bold")).pack(anchor="w")
        ttk.Label(frame,text="默认免配置联网翻译，点击翻译才发送文字；也可选择离线或自定义 AI，不下载模型。",wraplength=700,style="Muted.TLabel").pack(anchor="w",pady=12)
        mode=tk.StringVar(value=self.provider.get())
        ttk.Combobox(frame,textvariable=mode,state="readonly",values=[FREE_ONLINE,"离线复用","本地 / 自定义API"]).pack(fill="x")
        ttk.Label(frame,text="免配置联网翻译无需账号、模型或密钥，使用 MyMemory 免费接口，有日额度限制。下面的 API 字段仅供自定义服务。",wraplength=700,style="Muted.TLabel").pack(anchor="w",pady=6)
        entries=[]
        for label,value,secret in [("兼容 API 地址（本地 Ollama 可用 http://127.0.0.1:11434/v1）",self.api.endpoint,False),("模型（需已安装 / 已可用）",self.api.model,False),("API 密钥（可空，只在当前会话内存中保留）",self.api.key,True)]:
            ttk.Label(frame,text=label,wraplength=590).pack(anchor="w",pady=(14,5))
            field=ttk.Entry(frame,show="•" if secret else "");field.insert(0,value);field.pack(fill="x");entries.append(field)
        online=tk.BooleanVar(value=self.live_online.get())
        ttk.Checkbutton(frame,text="允许游戏按钮使用当前在线服务（仅本次桌面会话）",variable=online).pack(anchor="w",pady=(12,0))
        ttk.Label(frame,text="开启后，游戏按钮会发送采集文字、语境和相关术语到上面的服务。请自行确认服务费用；程序不购买额度、不下载模型、不自动重试。",wraplength=700,foreground=GOLD).pack(anchor="w",pady=16)
        def save():
            self.api=Settings(entries[0].get().strip(),entries[1].get().strip(),entries[2].get())
            self.provider.set(self.canon(mode.get()))
            self.live_online.set(online.get())
            self.mode_label.set("已连接游戏" if self.bridge else "桌面工作台" + " · " + self.provider.get())
            dialog.destroy()
            self.save_preferences()
        ttk.Button(frame,text="保存设置（不发送请求）",style="Accent.TButton",command=save).pack(anchor="e")

    def start_drafts(self,selected=False,units=None):
        if self.busy or not self.ensure_project():return
        self.commit_editor()
        if self.project.source_language==self.project.target_language:
            self.status.set("识别语言和目标语言相同，请选择不同的语言对。")
            return
        if units is None:
            units=[self.project.by_id[i] for i in self.table.selection()] if selected else self.project.filtered(self.search.get(),self.category,self.canon(self.state_filter.get()),self.include_candidates.get())
        units=[u for u in units if not u.translation and u.state!="忽略"]
        if not units:self.status.set("范围内没有未翻译文本；已有译文不会自动覆盖。");return
        local_ids=self.project.draft_local(units)
        units=[u for u in units if not u.translation]
        self.reload_current_editor()
        self.refresh(reset_page=False);self.update_summary()
        if self.canon(self.provider.get())=="离线复用" or not units:
            self.status.set(f"复用 {len(local_ids)} 条译文；{len(units)} 条尚无匹配。可配置已安装的本地 AI 继续生成。")
            self.reload_current_editor()
            if self.bridge and self.live_request:self.publish_live()
            return
        self.cancel.clear();self.set_busy(True)
        self.task_error=""
        destination="MyMemory 免费联网翻译" if self.canon(self.provider.get())==FREE_ONLINE else self.api.endpoint
        self.status.set(f"发送 {len(units)} 条去重原文到 {destination}；生成后仍需校对。")
        snapshots=[replace(u,occurrences=list(u.occurrences)) for u in units]
        settings=replace(self.api)
        provider=self.canon(self.provider.get())
        target_language=self.project.target_language
        # Only send relevant glossary, bounded independently of import size.
        sources="\n".join(u.source for u in units)
        glossary={k:v for k,v in self.project.glossary.items() if k in sources}
        glossary=dict(list(glossary.items())[:128])
        def worker():
            try:
                if provider==FREE_ONLINE:
                    # At most two requests in flight and four queued units;
                    # never create one thread/future per game string.
                    with ThreadPoolExecutor(max_workers=2,thread_name_prefix='AbyssText-online') as pool:
                        for start in range(0,len(snapshots),4):
                            if self.cancel.is_set():break
                            pending=[pool.submit(self.online_cache.translate,u,target_language,cancelled=self.cancel.is_set) for u in snapshots[start:start+4]]
                            for future in as_completed(pending):
                                if self.cancel.is_set():break
                                self.events.put(("drafts",future.result()))
                            self.online_cache.flush()
                    return
                for group in batches(snapshots):
                    if self.cancel.is_set():break
                    result=translate(settings,group,glossary,target_language=target_language)
                    if self.cancel.is_set():break
                    self.events.put(("drafts",result))
            except Exception as error:self.events.put(("error",str(error)))
            finally:
                try:self.online_cache.flush()
                except (OSError,ValueError) as error:self.events.put(("error",str(error)))
                self.events.put(("draft_done",None))
        threading.Thread(target=worker,daemon=True).start()

    def reload_current_editor(self):
        if not self.current_id:return
        uid=self.current_id;self.current_id=None
        if self.table.exists(uid):self.table.selection_set(uid);self.select_unit()

    def export_dialog(self):
        if not self.ensure_project():return
        self.commit_editor()
        dialog=tk.Toplevel(self.root);dialog.title("导出汉化成果");dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=22);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="选择交付方式",font=(self.ui_font,17,"bold")).pack(anchor="w",pady=(0,16))
        def run(kind):
            try:
                if kind=="csv":
                    path=filedialog.asksaveasfilename(defaultextension=".csv",initialfile="汉化工作表.csv")
                    if not path:return
                    export_csv(self.project,path);self.status.set("去重工作表已导出，包含全部译文、状态和来源。")
                elif kind=="project":
                    if not self.save_project(as_new=True):return
                else:
                    parent=filedialog.askdirectory(title=self.tr('选择输出父目录；将在其中创建新目录'))
                    if not parent:return
                    name="AbyssTextTranslations" if kind=="native" else "TranslatedMod"
                    target=Path(parent)/name
                    count,notes=(export_native if kind=="native" else export_copy)(self.project,target)
                    self.status.set(f"已导出到 {target}；{count} 个键/文件，{len(notes)} 条需人工适配。")
                dialog.destroy()
            except (OSError,ValueError) as error:self.error(error)
        for name,desc,kind in [("原生汉化包","已有本地化键 → Translations.xml + filelist.xml；仅导出已校对译文。","native"),("翻译后的模组副本","处理硬编码 XML / Lua / C# 字面量；检查源文件版本，写入全新目录。","copy"),("CSV 校对工作表","每条原文只导出一次，保留全部来源；可重新导入。","csv"),("完整汉化项目","包含进度、备注、术语和译文记忆，便于继续工作。","project")]:
            ttk.Button(frame,text=name,style="Accent.TButton" if kind=="native" else "TButton",command=lambda k=kind:run(k)).pack(fill="x",pady=(8,4))
            ttk.Label(frame,text=desc,wraplength=530,style="Muted.TLabel").pack(anchor="w",pady=(0,8))

    def show_diagnostics(self):
        if not self.ensure_project():return
        lines=["扫描诊断"]+[f"{d['file']}: {d['message']}" for d in self.project.report.diagnostics]
        lines += ["\n未解析引用（不会把键名当作英文原文翻译）"]+[f"{e.file}:{e.line}  {e.key}" for e in self.project.unresolved]
        dialog=tk.Toplevel(self.root);dialog.title("诊断与未解析引用");dialog.geometry("850x580");dialog.configure(bg=BG)
        text=self._text(dialog,25,True);text.pack(fill="both",expand=True,padx=14,pady=14);self.set_text(text,"\n".join(lines))

    def connect_live(self):
        dialog=tk.Toplevel(self.root);dialog.title(self.tr("连接游戏"));dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=22);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="安装或连接 AbyssTextLive",font=(self.ui_font,16,"bold")).pack(anchor="w")
        ttk.Label(frame,text="先安装 LuaCs 客户端，再将本工具的客户端插件放入游戏 LocalMods。",wraplength=500).pack(pady=12)
        def connect():dialog.destroy();self.select_live()
        def install():
            from companion import install_companion
            parent=filedialog.askdirectory(title=self.tr("选择游戏 LocalMods 目录"))
            if not parent:return
            try:
                path=install_companion(parent)
                self.status.set("已安装插件："+str(path))
                dialog.destroy();self.select_live(path)
            except (OSError,ValueError) as error:self.error(error)
        ttk.Button(frame,text="安装到 LocalMods（新目录）",command=install,style="Accent.TButton").pack(fill="x",pady=6)
        ttk.Button(frame,text="连接已安装插件",command=connect).pack(fill="x",pady=6)

    def select_live(self,path=None):
        path=path or filedialog.askdirectory(title=self.tr('选择游戏 LocalMods 中已安装的 AbyssTextLive 插件目录'))
        if not path:return
        try:
            self.bridge=LiveBridge(path)
            self.write_live_preferences()
        except (OSError,ValueError) as error:return self.error(error)
        self.mode_label.set("游戏桥接已连接 · 本地文件交换")
        dialog=tk.Toplevel(self.root);dialog.title("游戏内一键试译");dialog.configure(bg=BG)
        frame=ttk.Frame(dialog,padding=20);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="游戏内按钮 → 采集源语言文字 → 本地草稿 → 原生文本刷新",font=(self.ui_font,12,"bold"),wraplength=540).pack(anchor="w")
        ttk.Label(frame,text="保持桌面工作台运行，游戏按钮默认直接联网翻译，无需填写配置；译文直接更新原生文字。也可选择离线或自定义 AI。",wraplength=540,style="Muted.TLabel").pack(anchor="w",pady=12)
        ttk.Checkbutton(frame,text="允许游戏内试用未校对草稿（格式有问题的条目会跳过）",variable=self.live_drafts).pack(anchor="w")
        ttk.Button(frame,text="把当前译文应用到游戏",style="Accent.TButton",command=self.publish_live).pack(fill="x",pady=12)
        ttk.Label(frame,text="插件需 LuaCs 客户端。尚未认证真实游戏；重建或缓存的界面可能需重开。可在游戏中停止试译并恢复原文本。",wraplength=540,foreground=GOLD).pack(anchor="w")

    def publish_live(self,complete=True):
        if not self.bridge or not self.project:return
        self.commit_editor()
        try:
            keys,literals,notes=self.bridge.publish(self.project,self.live_request,self.live_drafts.get(),complete=complete)
            self.status.set(f"发送到游戏：{keys} 个语言键，{literals} 条显示文字；{len(notes)} 条跳过。等待客户端刷新。")
        except (OSError,ValueError) as error:self.error(error)

    def poll_live(self):
        try:
            if self.bridge:
                status=self.bridge.status()
                if status:
                    running="试译运行中" if status.get('active') else "试译已停止"
                    self.mode_label.set(f"{running} · 已采集 {status.get('submitted_records',0)} · 已译 {status.get('translated_records',0)}")
                    if status.get('last_error') and not self.busy:self.status.set('游戏桥接：'+str(status['last_error']))
            if self.bridge and not self.busy:
                request=self.bridge.read_request()
                if request:
                    report,generate,self.live_request=request
                    self.commit_editor()
                    if self.project:
                        entries=list(self.project.report.entries)
                        known={(e.file,e.key,e.text) for e in entries}
                        entries.extend(e for e in report.entries if (e.file,e.key,e.text) not in known)
                        report=Report(self.project.report.root,entries,
                            list(self.project.report.diagnostics),self.project.report.scanned,self.project.report.skipped,dict(self.project.report.fingerprints))
                    previous=self.project
                    project=Project(report,previous,self.source_language.get(),self.target_language.get())
                    if previous:project.path=previous.path
                    project.dirty=True
                    self.install_project(project)
                    allowed=self.canon(self.provider.get())==FREE_ONLINE or game_auto_allowed(self.api.endpoint,self.canon(self.provider.get())=="离线复用",self.live_online.get())
                    if generate and allowed:
                        self.start_drafts(units=[u for u in project.units if any(e.file=="<游戏内>" for e in u.occurrences)])
                    elif generate:
                        self.status.set("请在翻译设置中开启游戏按钮联网，或使用离线/本机服务。")
                        self.publish_live()  # Acknowledge so the client can submit later requests.
                    else:self.publish_live()
        except (OSError,ValueError,KeyError,TypeError) as error:self.status.set("游戏桥接："+str(error))
        finally:self.root.after(1500,self.poll_live)

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=="progress":self.status.set(value)
                elif kind=="project":
                    self.commit_editor()
                    if self.project and value.report.root==self.project.report.root and (value.source_language,value.target_language)==(self.project.source_language,self.project.target_language):
                        for unit in value.units:
                            if unit.id in self.project.by_id:
                                old=self.project.by_id[unit.id]
                                unit.translation,unit.state,unit.notes,unit.origin=old.translation,old.state,old.notes,old.origin
                        value.memory.update(self.project.memory)
                        value._index()
                    self.install_project(value)
                elif kind=="error":self.task_error=value;self.status.set("任务失败："+value)
                elif kind in {"done","draft_done"}:
                    self.set_busy(False)
                    if kind=="draft_done":
                        self.reload_current_editor();self.refresh(reset_page=False);self.update_summary()
                        if self.bridge and self.live_request:self.publish_live()
                    if self.task_error:self.status.set("任务未全部完成："+self.task_error)
                elif kind=="drafts" and self.project:
                    self.commit_editor()
                    count=0
                    for uid,result in value.items():
                        if uid in self.project.by_id and not self.project.by_id[uid].translation:
                            self.project.update(uid,result["translation"])
                            self.project.by_id[uid].origin="机器翻译草稿（未校对）"
                            count+=1
                    self.reload_current_editor()
                    if self.bridge and self.live_request:self.publish_live(complete=False)
                    self.status.set(f"本批生成 {count} 条草稿，请检查右侧质量提示并校对。")
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def close(self):
        if not self.confirm_unsaved():return
        self.cancel.set();self.root.destroy()


def run():
    window=WorkbenchWindow()
    window.tabs.bind("<<NotebookTabChanged>>",lambda _:window.refresh_xml() if window.tabs.index(window.tabs.select())==2 else None)
    window.root.mainloop()
