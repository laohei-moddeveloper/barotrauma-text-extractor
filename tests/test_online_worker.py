import json
import queue
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from online_worker import run_online
from translation_diagnostics import TranslationDiagnostics
from desktop_ui import WorkbenchWindow
from extractor import Entry,Report
from workbench import Project
from live_bridge import LiveBridge


class OnlineWorkerTests(unittest.TestCase):
    def window(self):
        window=WorkbenchWindow.__new__(WorkbenchWindow)
        window.project=Project(Report('isolated',[Entry(str(i),'<游戏内>',i+1,1,'游戏内显示','literal','English '+str(i),language='English',location={'live_priority':1}) for i in range(4)]))
        window.live_session='one';window.live_request='request';window.live_failures={}
        window.live_attempted=set();window.live_cooldown_until=0;window.live_generate=True
        window.events=queue.Queue();window.root=SimpleNamespace(after=Mock())
        window.status=SimpleNamespace(set=Mock());window.mode_label=SimpleNamespace(set=Mock())
        window.bridge=SimpleNamespace(status=lambda:None,read_request=lambda:None)
        window.diagnostics=TranslationDiagnostics(enabled=False)
        for name in ['commit_editor','reload_current_editor','refresh','update_summary','publish_live','start_drafts']:setattr(window,name,Mock())
        window.canon=lambda x:x;window.provider=SimpleNamespace(get=lambda:'免配置联网翻译')
        window.set_busy=lambda flag:setattr(window,'busy',flag)
        window.busy=False;window.task_error=''
        return window

    def test_failure_is_recorded_while_other_scoped_results_reach_project(self):
        window=self.window();scope={'session':'one','source':'English','target':'Simplified Chinese'}
        units=window.project.units
        window.events.put(('draft_failure',{**scope,'id':units[0].id,'error':'timeout','retry_after':30}))
        for unit in units[1:]:window.events.put(('drafts_scoped',{**scope,'result':{unit.id:{'translation':'译文','issues':[]}}}))
        window.events.put(('draft_done',None));window.poll()
        self.assertEqual(sum(bool(u.translation) for u in units),3)
        self.assertEqual(window.live_failures[units[0].id]['error'],'timeout')
        self.assertGreater(window.live_cooldown_until,time.monotonic())
        self.assertTrue(window.publish_live.called)

    def test_old_target_language_result_is_never_applied(self):
        window=self.window();unit=window.project.units[0]
        window.events.put(('drafts_scoped',{'session':'one','source':'English','target':'French','result':{unit.id:{'translation':'Wrong pair','issues':[]}}}))
        window.poll();self.assertFalse(unit.translation)

    def test_failed_record_does_not_leave_actual_bridge_response_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'AbyssTextLive';root.mkdir()
            (root/'filelist.xml').write_text('<contentpackage name="AbyssTextLive"/>')
            window=self.window();window.bridge=LiveBridge(root)
            window.live_drafts=SimpleNamespace(get=lambda:True)
            window.publish_live=WorkbenchWindow.publish_live.__get__(window)
            scope={'session':'one','source':'English','target':'Simplified Chinese'}
            window.events.put(('draft_failure',{**scope,'id':window.project.units[0].id,'error':'one failed','retry_after':30}))
            for unit in window.project.units[1:]:
                window.events.put(('drafts_scoped',{**scope,'result':{unit.id:{'translation':'成功译文','issues':[]}}}))
            window.events.put(('draft_done',None));window.poll()
            response=json.loads((root/'Live/response.json').read_text(encoding='utf-8'))
            self.assertEqual(len(response['translations']),3)
            self.assertEqual(response['progress']['failed'],1)
            self.assertEqual(response['progress']['last_error'],'one failed')

    def test_unusable_translation_is_reported_as_rejected_not_success(self):
        window=self.window();unit=window.project.units[0]
        window.events.put(('drafts_scoped',{'session':'one','source':'English','target':'Simplified Chinese',
            'result':{unit.id:{'translation':unit.source,'issues':[]}}}))
        window.poll()
        self.assertIn('原文相同',window.live_failures[unit.id]['error'])

    def test_transient_failure_retries_only_once_after_cooldown(self):
        window=self.window();uid=window.project.units[0].id
        window.live_attempted={u.id for u in window.project.units}
        window.live_failures[uid]={'error':'timeout','attempts':1,'retry_at':time.monotonic()-1}
        window.poll_live();self.assertEqual(window.start_drafts.call_args.kwargs['units'],[window.project.units[0]])
        window.start_drafts.reset_mock();window.live_failures[uid].update(attempts=2,retry_at=time.monotonic()-1)
        window.poll_live();window.start_drafts.assert_not_called()

    def test_one_failure_does_not_discard_other_successes_or_later_batches(self):
        lock=threading.Lock();active=peak=0
        units=[SimpleNamespace(id=str(i)) for i in range(9)]
        def translate(unit,*args,**kwargs):
            nonlocal active,peak
            if unit.id=='0':raise ValueError('one bad record')
            with lock:active+=1;peak=max(peak,active)
            time.sleep(.01)
            with lock:active-=1
            return {unit.id:{'translation':'译文','issues':[]}}
        results=[];errors=[]
        cache=SimpleNamespace(translate=translate,flush=lambda:None)
        run_online(units,'Simplified Chinese',cache,lambda:False,results.append,lambda u,e:errors.append((u.id,str(e))))
        self.assertEqual({uid for result in results for uid in result},{str(i) for i in range(1,9)})
        self.assertEqual(errors,[('0','one bad record')])
        self.assertLessEqual(peak,2)

    def test_cancelled_work_does_not_publish_or_schedule(self):
        def forbidden(*args,**kwargs):raise AssertionError('Cancelled work started')
        run_online([SimpleNamespace(id='x')],'French',SimpleNamespace(translate=forbidden,flush=forbidden),lambda:True,forbidden,forbidden)

    def test_diagnostics_are_bounded_and_store_failure_after_later_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'status.json';ledger=TranslationDiagnostics(path)
            for i in range(205):ledger.record('translated',str(i))
            ledger.record('failed','hash-only-id',error='network timeout',attempts=1)
            ledger.record('translated','another-id')
            data=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(data['events']),200)
            self.assertEqual(data['events'][-2]['error'],'network timeout')
            self.assertNotIn('source',data['events'][-2])
