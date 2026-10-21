"""Standalone Tk window; scanning runs off the UI thread."""
import argparse
from collections import Counter
from pathlib import Path
import queue
import threading

from extractor import export_report, scan


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("译潜 AbyssText · 潜渊症汉化文字提取器 0.1.0")
    root.geometry("1180x760")
    root.minsize(800, 540)
    folder = tk.StringVar()
    search = tk.StringVar()
    mode = tk.StringVar(value="全部")
    status = tk.StringVar(value="选择模组文件夹开始。只读取源文件，不执行模组代码。")
    results = queue.Queue()
    cancelled = threading.Event()
    state = {"report": None, "busy": False, "entries": {}}
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)
    top = ttk.Frame(frame)
    top.pack(fill="x")
    ttk.Label(top, text="模组目录").pack(side="left")
    ttk.Entry(top, textvariable=folder).pack(side="left", fill="x", expand=True, padx=8)

    def choose():
        path = filedialog.askdirectory(title="选择待汉化模组的目录")
        if path:
            folder.set(path)

    ttk.Button(top, text="浏览…", command=choose).pack(side="left")

    def worker(path):
        try:
            results.put((scan(Path(path), cancelled.is_set), None))
        except Exception as error:
            results.put((None, str(error)))

    def start():
        if state["busy"]:
            return
        state["busy"] = True
        cancelled.clear()
        scan_button.configure(state="disabled")
        export_button.configure(state="disabled")
        status.set("正在扫描 XML / Lua / C#…")
        threading.Thread(target=worker, args=(folder.get(),), daemon=True).start()

    scan_button = ttk.Button(top, text="提取文字", command=start)
    scan_button.pack(side="left", padx=8)
    ttk.Button(top, text="取消扫描", command=cancelled.set).pack(side="left")
    ttk.Label(frame, text="字段规则命中不等于运行时必然显示。脚本文字均需核查；引用键请查看语言表解析结果。", wraplength=1000).pack(anchor="w", pady=10)
    filters = ttk.Frame(frame)
    filters.pack(fill="x", pady=(0, 8))
    ttk.Label(filters, text="搜索").pack(side="left")
    ttk.Entry(filters, textvariable=search).pack(side="left", fill="x", expand=True, padx=8)
    combo = ttk.Combobox(filters, textvariable=mode, state="readonly", width=22,
                         values=["全部", "直接文本", "本地化引用", "待核查", "未解析引用", "脚本标识符/路径候选"])
    combo.pack(side="left")
    pane = ttk.Panedwindow(frame, orient="vertical")
    pane.pack(fill="both", expand=True)
    table_frame = ttk.Frame(pane)
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)
    table = ttk.Treeview(table_frame, columns=("kind", "category", "text", "file", "line"), show="headings")
    for key, label, width in [("kind", "类型", 80), ("category", "用途", 135), ("text", "原文 / 引用键", 420), ("file", "源文件", 240), ("line", "行", 55)]:
        table.heading(key, text=label)
        table.column(key, width=width, minwidth=45)
    table.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    hscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=table.xview)
    hscroll.grid(row=1, column=0, sticky="ew")
    table.configure(yscrollcommand=scroll.set, xscrollcommand=hscroll.set)
    pane.add(table_frame, weight=3)
    detail_frame = ttk.Frame(pane)
    detail = tk.Text(detail_frame, height=10, wrap="word", state="disabled")
    detail.pack(fill="both", expand=True)
    pane.add(detail_frame, weight=1)

    def show(text):
        detail.configure(state="normal")
        detail.delete("1.0", "end")
        detail.insert("1.0", text)
        detail.configure(state="disabled")

    kinds = {"literal": "直接文本", "reference": "引用键", "candidate": "待核查"}

    def refresh(*_):
        table.delete(*table.get_children())
        state["entries"] = {}
        report = state["report"]
        if not report:
            return
        query = search.get().casefold()
        selected = mode.get()
        for index, entry in enumerate(report.entries):
            if selected == "直接文本" and entry.kind != "literal": continue
            if selected == "本地化引用" and entry.kind != "reference": continue
            if selected == "待核查" and entry.kind != "candidate": continue
            if selected == "未解析引用" and (entry.kind != "reference" or entry.resolved): continue
            if selected == "脚本标识符/路径候选" and entry.category != selected: continue
            if query and query not in (entry.text + entry.file + entry.category + entry.context + str(entry.resolved)).casefold(): continue
            iid = str(index)
            state["entries"][iid] = entry
            table.insert("", "end", iid=iid, values=(kinds[entry.kind], entry.category, entry.text.replace("\n", " ↵ ")[:300], entry.file, entry.line))

    search.trace_add("write", refresh)
    combo.bind("<<ComboboxSelected>>", refresh)

    def select(_):
        selection = table.selection()
        if not selection:
            return
        entry = state["entries"][selection[0]]
        report = state["report"]
        text = (f"{Path(report.root) / entry.file}:{entry.line}:{entry.column}\n"
                f"类型：{kinds[entry.kind]}　用途：{entry.category}\n"
                f"上下文：{entry.context}\n识别依据：{entry.evidence}\n\n原文：\n{entry.text}\n")
        if entry.kind == "reference":
            text += "\n语言表解析（保留所有同名定义，不判断最终加载优先级）：\n"
            text += "\n".join(f"[{x['language']}] {x['text']} ({x['file']}:{x['line']})" for x in entry.resolved) or "当前目录没有找到该键。可能来自原版、依赖模组或动态拼接。"
        show(text)

    table.bind("<<TreeviewSelect>>", select)
    bottom = ttk.Frame(frame)
    bottom.pack(fill="x", pady=(8, 0))

    def diagnostics():
        report = state["report"]
        if report:
            show("扫描诊断\n" + ("\n".join(f"{d['file']}: {d['message']}" for d in report.diagnostics) or "没有读取或解析错误。静态规则仍可能漏报/误报；不代表提取完整。"))

    ttk.Button(bottom, text="查看诊断", command=diagnostics).pack(side="left")

    def export():
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("Excel / CSV", "*.csv"), ("完整 JSON", "*.json")], initialfile="汉化文字表.csv")
        if not path:
            return
        try:
            target = Path(path).resolve()
            source_root = Path(state["report"].root)
            if target.is_relative_to(source_root):
                raise ValueError("请导出到模组目录以外，避免覆盖源文件或再次扫描导出结果。")
            export_report(state["report"], target)
            messagebox.showinfo("导出完成", f"已导出全部提取结果：{target}\nCSV 附带诊断 JSON；筛选只影响窗口显示。")
        except (OSError, ValueError) as error:
            messagebox.showerror("导出失败", str(error))

    export_button = ttk.Button(bottom, text="导出全部 CSV / JSON", command=export, state="disabled")
    export_button.pack(side="right")
    ttk.Label(frame, textvariable=status, wraplength=1050).pack(anchor="w", pady=(8, 0))

    def poll():
        try:
            report, error = results.get_nowait()
        except queue.Empty:
            pass
        else:
            state["busy"] = False
            scan_button.configure(state="normal")
            if error:
                status.set("扫描失败：" + error)
                messagebox.showerror("扫描失败", error)
            else:
                state["report"] = report
                counts = Counter(e.kind for e in report.entries)
                status.set(f"扫描 {report.scanned} 文件 · 直接文本 {counts['literal']} · 引用 {counts['reference']} · 待核查 {counts['candidate']} · 诊断 {len(report.diagnostics)} · 跳过其他文件 {report.skipped}")
                refresh()
                export_button.configure(state="normal")
                diagnostics()
        root.after(100, poll)

    root.protocol("WM_DELETE_WINDOW", lambda: (cancelled.set(), root.destroy()))
    poll()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="潜渊症模组汉化文字提取器：无参数启动窗口")
    parser.add_argument("folder", nargs="?", help="模组文件夹")
    parser.add_argument("-o", "--output", type=Path, help="导出 CSV / JSON（放在模组目录外）")
    args = parser.parse_args()
    if args.folder is None:
        if args.output:
            parser.error("--output 需要指定模组目录")
        gui()
        return
    if not args.output:
        parser.error("命令行扫描需要 -o 输出文件")
    try:
        source = Path(args.folder).resolve()
        if args.output.resolve().is_relative_to(source):
            raise ValueError("输出文件必须在模组目录以外")
        report = scan(source)
        export_report(report, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"扫描 {report.scanned} 文件，提取 {len(report.entries)} 条，诊断 {len(report.diagnostics)} 条。")
    for issue in report.diagnostics:
        print(f"  {issue['file']}: {issue['message']}")
    # Distinguish incomplete inventory in automation.
    if report.diagnostics:
        parser.exit(2)


if __name__ == "__main__":
    main()
