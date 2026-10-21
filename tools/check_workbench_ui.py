"""Real Tk event-loop checks; optional screenshot needs Pillow, app itself does not."""
import argparse
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from desktop_ui import WorkbenchWindow, PAGE_SIZE
from extractor import Entry, Report, scan
from workbench import Project, source_id


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--screenshot",type=Path);parser.add_argument("--ui-language",choices=["zh","en"],default="zh")
    parser.add_argument("--scale",type=float,choices=[1.0,1.5],default=1.0,help="Tk font DPI scale; does not change Windows display settings")
    args=parser.parse_args()
    root=tk.Tk();root.tk.call("tk","scaling",96/72*args.scale)
    window=WorkbenchWindow(root,preferences_path=False)
    window.provider.set("离线复用")  # UI regression never calls a live service.
    errors=[]
    root.report_callback_exception=lambda *values:errors.append(str(values[1]))
    def pump(seconds=0.12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            root.update();time.sleep(0.005)
        assert not errors, errors
    with tempfile.TemporaryDirectory() as directory:
        project=Project(scan(ROOT/"examples/workbench"))
        window.install_project(project);pump()
        assert len(window.table.get_children())==len(project.filtered())
        assert len(project.units)<len(project.report.entries)
        warning=next(u for u in project.units if u.source=="Pressure warning")
        window.table.selection_set(warning.id);window.select_unit();pump()
        window.target_text.insert("1.0","气压警告")
        window.commit_editor();assert warning.translation=="气压警告"
        window.review_next();pump();assert warning.state=="已校对"
        depart=next(u for u in project.units if u.source=="Ready to depart")
        window.table.selection_set(depart.id);window.select_unit()
        project.memory[depart.source]="准备出发"
        window.start_drafts(selected=True);pump()
        assert depart.translation=="准备出发", "Offline draft was lost to a stale editor"
        assert window.target_text.get("1.0","end-1c")=="准备出发"
        # API responses are injected, never sent to a real service.
        sonar=next(u for u in project.units if u.source=="Activate sonar")
        window.table.selection_set(sonar.id);window.select_unit()
        window.events.put(("drafts",{sonar.id:{"translation":"启动声呐","issues":[]}}))
        window.events.put(("draft_done",None));pump(0.25)
        assert sonar.translation=="启动声呐", "AI draft was lost to a stale editor"
        window.search.set("气压 English.xml");pump(0.3)
        assert len(window.table.get_children())==1
        window.search.set("");pump(0.3)
        path=Path(directory)/"project.json"
        with patch("tkinter.filedialog.asksaveasfilename",return_value=str(path)):
            assert window.save_project()
        assert Project.load(path).by_id[warning.id].state=="已校对"
        # Bounded table rendering for large projects.
        report=Report(str(Path(directory)/"source"),[Entry(str(i),"bulk.xml",i+1,1,"语言表","literal",f"Text {i}",key=f"bulk.{i}",language="English") for i in range(3000)])
        window.install_project(Project(report));pump()
        assert len(window.table.get_children())==PAGE_SIZE
        window.turn_page(1);assert window.page==1
        assert len(window.table.get_children())==PAGE_SIZE
        window.install_project(project);window.search.set("");window.set_category("全部文本");pump()
        window.table.selection_set(warning.id);window.select_unit();window.tabs.select(0)
        window.refresh_xml();pump()
        assert window.target_text.winfo_height()>60
        window.set_language("en");pump(0.6)
        assert window.target_text.get("1.0","end-1c")=="气压警告"
        assert window.ui_language=="en"
        window.set_language("zh");pump(0.6)
        assert window.target_text.get("1.0","end-1c")=="气压警告"
        root.geometry("1060x700");pump()
        assert window.target_text.winfo_height()>40
        parent=window.table.master.master
        pager=parent.winfo_children()[-1]
        assert pager.winfo_y()+pager.winfo_height()<=parent.winfo_height()+1, "Pager clipped on minimum window"
        # Verify unsaved decisions without writing into user settings or sources.
        project.dirty=True
        with patch("tkinter.messagebox.askyesnocancel",return_value=None):
            assert not window.confirm_unsaved()
        with patch("tkinter.messagebox.askyesnocancel",return_value=False):
            assert window.confirm_unsaved()
        # Cancellation is signalled from the same callback used by the UI button.
        window.cancel.set();assert window.cancel.is_set()
        window.cancel.clear()
        # Long rich text and placeholders must survive editor commits and locale switches.
        source_before=warning.source
        long_text="‖color:255,200,100‖长文本 [name] {0}‖color:end‖\n"*30
        window.target_text.delete("1.0","end");window.target_text.insert("1.0",long_text)
        window.commit_editor();assert warning.translation==long_text
        window.set_language("en");pump(0.6)
        assert warning.source==source_before and warning.translation==long_text
        window.target_text.delete("1.0","end");window.target_text.insert("1.0","气压警告")
        window.commit_editor()
        # Exercise the real bounded worker/event loop with simulated results.
        window.install_project(Project(report));window.provider.set("免配置联网翻译")
        units=window.project.units[:12]
        window.table.selection_set(units[0].id);window.select_unit();pump()
        window.target_text.delete("1.0","end");window.target_text.insert("1.0","已有译文")
        window.commit_editor()
        lock=threading.Lock();counts={"active":0,"peak":0,"calls":0}
        def mock_online(unit,target,**kwargs):
            with lock:
                counts["active"]+=1;counts["calls"]+=1
                counts["peak"]=max(counts["peak"],counts["active"])
            time.sleep(0.02)
            with lock:counts["active"]-=1
            return {unit.id:{"translation":"模拟译文 "+unit.source,"issues":[]}}
        with patch.object(window.online_cache,"translate",side_effect=mock_online):
            window.start_drafts(units=units)
            deadline=time.monotonic()+5
            while window.busy and time.monotonic()<deadline:pump(0.1)
        assert not window.busy and counts["peak"]<=2 and counts["calls"]==11, counts
        assert window.project.by_id[units[0].id].translation=="已有译文"
        window.install_project(project);window.provider.set("离线复用");pump()
        root.geometry("1440x900");pump()
        if args.ui_language=="en":window.set_language("en");pump(0.6)
        if args.screenshot:
            from PIL import ImageGrab
            x,y=root.winfo_rootx(),root.winfo_rooty()
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
            ImageGrab.grab().crop((x,y,x+root.winfo_width(),y+root.winfo_height())).save(args.screenshot)
        # Prevent a final unsaved prompt and close without network/game activity.
        window.project.dirty=False
        root.destroy()
    print(f"Tk workbench checks passed at {args.scale*100:.0f}% font DPI: edit, review, search, offline/API draft retention, save/reopen, 3000-row pagination, unsaved cancellation, long rich text/placeholders, zh/en, 1060x700 and 1440x900.")


if __name__=="__main__":main()
