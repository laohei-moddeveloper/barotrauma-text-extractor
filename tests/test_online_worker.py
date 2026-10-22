import json
import queue
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from online_worker import run_online, LiveFeed
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
        window.draft_task_id=0;window.live_worker=False;window.cancel=threading.Event()
        window.source_language=SimpleNamespace(get=lambda:'English')
        window.target_language=SimpleNamespace(get=lambda:'Simplified Chinese')
        window.online_channel=SimpleNamespace(get=lambda:'mymemory')
        return window

    def test_failure_is_recorded_while_other_scoped_results_reach_project(self):
        window=self.window();scope={'session':'one','source':'English','target':'Simplified Chinese'}
        units=window.project.units
        window.events.put(('draft_failure',{**scope,'id':units[0].id,'error':'timeout','retry_after':30}))
        for unit in units[1:]:window.events.put(('drafts_scoped',{**scope,'result':{unit.id:{'translation':'译文','issues':[]}}}))
        window.events.put(('draft_done',None));window.poll()
        self.assertEqual(sum(bool(u.translation) for u in units),3)
        self.assertEqual(window.live_failures[units[0].id]['error'],'timeout')
        self.assertEqual(window.live_cooldown_until,0)
        self.assertGreater(window.live_failures[units[0].id]['retry_at'],time.monotonic())
        self.assertTrue(window.publish_live.called)

    def test_language_change_stops_automatic_live_generation_until_new_request(self):
        window=self.window()
        window.target_language=SimpleNamespace(get=lambda:'French')
        window.confirm_unsaved=lambda:True
        window.install_project=lambda project:setattr(window,'project',project)
        window.write_live_preferences=Mock()
        window.change_languages()
        self.assertEqual(window.project.target_language,'French')
        self.assertFalse(window.live_generate);self.assertEqual(window.live_request,'')
        window.poll_live();window.start_drafts.assert_not_called();window.publish_live.assert_not_called()

    def test_old_target_language_result_is_never_applied(self):
        window=self.window();unit=window.project.units[0]
        window.events.put(('drafts_scoped',{'session':'one','source':'English','target':'French','result':{unit.id:{'translation':'Wrong pair','issues':[]}}}))
        window.poll();self.assertFalse(unit.translation)

    def test_failed_record_does_not_leave_actual_bridge_response_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'AbyssTextLive';root.mkdir()
            (root/'filelist.xml').write_text('<contentpackage name="AbyssTextLive"/>', encoding='utf-8')
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

    def test_cache_save_error_does_not_discard_later_batches(self):
        units=[SimpleNamespace(id=str(i)) for i in range(9)];results=[];warnings=[]
        def flush():raise PermissionError('cache temporarily locked')
        cache=SimpleNamespace(translate=lambda unit,*a,**k:{unit.id:{'translation':'译文','issues':[]}},flush=flush)
        run_online(units,'Simplified Chinese',cache,lambda:False,results.append,lambda u,e:self.fail(str(e)),warnings.append)
        self.assertEqual({key for result in results for key in result},{u.id for u in units})
        self.assertEqual(len(warnings),3)

    def test_quota_cools_down_provider_without_overwriting_successes(self):
        window=self.window();unit=window.project.units[0]
        window.events.put(('draft_failure',{'session':'one','source':'English','target':'Simplified Chinese',
            'id':unit.id,'error':'quota','retry_after':3600}))
        window.poll();self.assertGreater(window.live_cooldown_until,time.monotonic()+3500)

    def test_old_task_completion_cannot_clear_new_task_busy_flag(self):
        window=self.window();window.busy=True;window.draft_task_id=2
        window.events.put(('draft_done',{'session':'one','source':'English','target':'Simplified Chinese','task':1}))
        window.poll();self.assertTrue(window.busy);window.publish_live.assert_not_called()

    def test_cancelled_old_session_task_releases_busy_without_publishing_into_new_session(self):
        window=self.window();window.busy=True;window.draft_task_id=1;window.live_session='new'
        window.events.put(('draft_done',{'session':'old','source':'English','target':'Simplified Chinese','task':1}))
        window.poll();self.assertFalse(window.busy);window.publish_live.assert_not_called()

    def test_old_task_errors_and_cache_warnings_do_not_replace_current_status(self):
        window=self.window();window.draft_task_id=2
        for kind in ['draft_error','draft_warning']:
            window.events.put((kind,{'session':'one','source':'English','target':'Simplified Chinese','task':1,'error':'stale'}))
        window.poll();window.status.set.assert_not_called()

    def test_game_stop_cancels_only_live_worker(self):
        for live in [False,True]:
            with self.subTest(live=live):
                window=self.window();window.live_worker=live;window.bridge.status=lambda:{'active':False}
                window.poll_live();self.assertEqual(window.cancel.is_set(),live);window.start_drafts.assert_not_called()

    def test_mismatched_request_language_pair_cannot_change_or_translate_project(self):
        window=self.window();before=window.project
        window.bridge=SimpleNamespace(status=lambda:None,read_request=lambda:(Report('isolated'),True,'new-request'),
            source_language='English',target_language='French',session_id='new-session')
        window.poll_live();self.assertIs(window.project,before);window.start_drafts.assert_not_called();window.publish_live.assert_not_called()
        self.assertIn('语言对不同',window.status.set.call_args.args[0])

    def test_old_channel_results_do_not_fill_current_channel_project(self):
        window=self.window();unit=window.project.units[0]
        window.events.put(('drafts_scoped',{'session':'one','source':'English','target':'Simplified Chinese','channel':'google',
            'result':{unit.id:{'translation':'旧渠道结果','issues':[]}}}))
        window.poll();self.assertFalse(unit.translation)

    def test_rolling_scheduler_keeps_second_slot_busy_while_first_is_slow(self):
        release=threading.Event();last_fast=threading.Event();results=[]
        units=[SimpleNamespace(id=str(i)) for i in range(9)]
        def translate(unit,*a,**k):
            if unit.id=='0':
                self.assertTrue(release.wait(3))
            if unit.id=='8':last_fast.set()
            return {unit.id:{'translation':'译文','issues':[]}}
        cache=SimpleNamespace(translate=translate,flush=lambda:None)
        worker=threading.Thread(target=lambda:run_online(units,'French',cache,lambda:False,results.append,lambda u,e:self.fail(str(e))))
        worker.start()
        try:self.assertTrue(last_fast.wait(2),'One slow request blocked all later groups')
        finally:release.set();worker.join(3)
        self.assertFalse(worker.is_alive());self.assertEqual(len(results),9)

    def test_live_queue_is_bounded_and_visible_work_defers_background(self):
        feed=LiveFeed(limit=4)
        def snapshot(uid,priority):
            return SimpleNamespace(id=uid,occurrences=[SimpleNamespace(file='<游戏内>',location={'live_priority':priority})])
        for i in range(4):self.assertTrue(feed.submit(snapshot(str(i),2))[0])
        accepted,deferred=feed.submit(snapshot('visible',0))
        self.assertTrue(accepted);self.assertIsNotNone(deferred);self.assertEqual(feed.pending(),4)
        self.assertEqual(feed.pop()[0].id,'visible')
        remaining={feed.pop()[0].id for _ in range(3)}
        self.assertEqual(remaining|{deferred},{'0','1','2','3'})
        feed.close();self.assertFalse(feed.submit(snapshot('late',0))[0])

    def test_live_visible_arrival_preempts_queued_background_before_slow_task_finishes(self):
        feed=LiveFeed();slow=threading.Event();fast=threading.Event();started=threading.Event();visible=threading.Event()
        def snapshot(uid,priority=2):
            return SimpleNamespace(id=uid,occurrences=[SimpleNamespace(file='<游戏内>',location={'live_priority':priority})])
        for uid in ['slow','first','background']:feed.submit(snapshot(uid))
        def translate(unit,*a,**k):
            if unit.id=='slow':slow.wait(3)
            if unit.id=='first':started.set();fast.wait(3)
            if unit.id=='visible':visible.set()
            return {unit.id:{'translation':'译文','issues':[]}}
        cache=SimpleNamespace(translate=translate,flush=lambda:None)
        worker=threading.Thread(target=lambda:run_online([],'French',cache,lambda:False,lambda x:None,lambda u,e:None,feed=feed))
        worker.start()
        try:
            self.assertTrue(started.wait(2));feed.submit(snapshot('visible',0));fast.set()
            self.assertTrue(visible.wait(2));self.assertFalse(slow.is_set())
        finally:slow.set();fast.set();worker.join(4)
        self.assertFalse(worker.is_alive())

    def test_quota_stops_queued_network_work_without_losing_deferred_units(self):
        from free_online import TranslationServiceError
        feed=LiveFeed();calls=[];waiting=[]
        for i in range(16):feed.submit(SimpleNamespace(id=str(i)))
        def fail(unit,*a,**k):calls.append(unit.id);raise TranslationServiceError('quota',3600)
        cache=SimpleNamespace(translate=fail,flush=lambda:None)
        run_online([],'French',cache,lambda:False,lambda x:None,lambda u,e:None,feed=feed,deferred=lambda ids:waiting.extend(ids))
        self.assertLessEqual(len(calls),2);self.assertEqual(set(calls)|set(waiting),{str(i) for i in range(16)})

    def test_deferred_units_are_available_after_provider_cooldown(self):
        window=self.window();ids=[u.id for u in window.project.units];window.live_attempted=set(ids)
        window.events.put(('draft_deferred',{'session':'one','source':'English','target':'Simplified Chinese','ids':ids[1:]}))
        window.poll();self.assertEqual(window.live_attempted,{ids[0]})

    def test_diagnostics_are_bounded_and_store_failure_after_later_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'status.json';ledger=TranslationDiagnostics(path)
            for i in range(205):ledger.record('translated',str(i))
            ledger.record('failed','hash-only-id',error='network timeout',attempts=1)
            ledger.record('translated','another-id')
            ledger.flush(force=True)
            data=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(data['events']),200)
            self.assertEqual(data['events'][-2]['error'],'network timeout')
            self.assertNotIn('source',data['events'][-2])
