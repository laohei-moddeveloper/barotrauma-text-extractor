"""Cold structured-name throughput, isolation and priority regressions."""
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from free_online import TranslationCache
from online_worker import LiveFeed, run_online


def name(uid,text=None,priority=2,context='ItemPrefab.Name'):
    return SimpleNamespace(id=str(uid),source=text or f'Ceramic Device {uid}',source_language='English',keys=[],
        occurrences=[SimpleNamespace(context=context,file='<游戏内>',location={'live_priority':priority})])


def reply(text):
    return io.BytesIO(json.dumps({'responseStatus':200,'responseData':{'translatedText':text}}).encode())


class NameBatchTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.cache=TranslationCache(Path(self.directory.name)/'cache.json')

    def test_four_cold_names_one_request_then_cached_without_network(self):
        units=[name(i) for i in range(4)];queries=[]
        def opener(request,timeout):
            query=parse_qs(urlparse(request.full_url).query)['q'][0];queries.append(query)
            return reply(query.replace('Ceramic Device','陶瓷设备').replace('__ABYSSROW_','__ ABYSSROW_'))
        result=self.cache.translate_names([(u,None) for u in units],'Simplified Chinese',opener)
        self.assertEqual(len(queries),1);self.assertLessEqual(len(queries[0].encode()),480)
        self.assertEqual([r[u.id]['translation'] for u,r,e in result],[f'陶瓷设备 {i}' for i in range(4)])
        self.assertTrue(all(e is None for _,_,e in result))
        for unit in units:
            self.cache.translate(unit,'Simplified Chinese',lambda *a,**k:self.fail('cache missed'))
        self.assertEqual(self.cache.metrics['requests'],1)

    def test_missing_duplicate_or_reordered_boundaries_retranslate_all_rows(self):
        for bad in ['__ABYSSROW_0__ 甲\n乙','__ABYSSROW_0__ 甲 __ABYSSROW_0__ 乙',
                    '__ABYSSROW_1__ 乙 __ABYSSROW_0__ 甲']:
            with self.subTest(bad=bad):
                self.cache=TranslationCache(Path(self.directory.name)/'cache.json');calls=[]
                def opener(request,timeout):
                    q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
                    return reply(bad if '__ABYSSROW_' in q else '独立译文')
                result=self.cache.translate_names([(name(i),None) for i in range(2)],'Simplified Chinese',opener)
                self.assertEqual(len(calls),3)
                self.assertEqual([r[u.id]['translation'] for u,r,e in result],['独立译文']*2)

    def test_one_empty_row_retries_only_that_row(self):
        calls=[]
        def opener(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            return reply('__ABYSSROW_0__ 陶瓷设备\n__ABYSSROW_1__ ' if '__ABYSSROW_' in q else '第二设备')
        result=self.cache.translate_names([(name(i),None) for i in range(2)],'Simplified Chinese',opener)
        self.assertEqual(len(calls),2)
        self.assertEqual([r[u.id]['translation'] for u,r,e in result],['陶瓷设备','第二设备'])

    def test_transport_limit_does_not_multiply_requests(self):
        calls=[]
        def opener(*args,**kwargs):calls.append(1);raise HTTPError('https://example.invalid',429,'limit',{},None)
        result=self.cache.translate_names([(name(i),None) for i in range(4)],'Simplified Chinese',opener)
        self.assertEqual(len(calls),1);self.assertEqual(len(result),4)
        self.assertTrue(all(r is None and e.retry_after==3600 for _,r,e in result))
        self.assertFalse(self.cache.rows)

    def test_names_with_domain_terms_glossary_formats_or_prose_are_not_batched(self):
        for unit,terms in [(name(1,'Mudraptor Trophy'),None),(name(2,'Plasma Vent'),{'Plasma':'等离子'}),
                           (name(3,'Device [id]'),None),(name(4,context='ItemPrefab.Description'),None),
                           (name(5,context='MissionPrefab.Name'),None)]:
            self.assertFalse(self.cache.can_batch_name(unit,'Simplified Chinese',terms))
        self.assertTrue(self.cache.can_batch_name(name(6),'Simplified Chinese'))
        self.assertFalse(self.cache.can_batch_name(name(6),'French'))

    def test_cache_local_terms_and_outer_spaces_still_work(self):
        first=name(1,' Ceramic Device ');second=name(2,'Other Device');known=name(3,'Mudraptor')
        self.cache.remember(self.cache.key(second,'Simplified Chinese'),'其他设备')
        calls=[]
        def opener(request,timeout):calls.append(1);return reply('陶瓷设备')
        result=self.cache.translate_names([(first,None),(second,None),(known,None)],'Simplified Chinese',opener)
        values={u.id:r[u.id]['translation'] for u,r,e in result}
        self.assertEqual(values,{'1':' 陶瓷设备 ','2':'其他设备','3':'泥偶迅猛龙'})
        self.assertEqual(len(calls),1)

    def test_scheduler_uses_groups_without_losing_following_description(self):
        units=[name(i) for i in range(9)]+[name(10,context='ItemPrefab.Description')]
        calls=[];results=[];active=peak=0;lock=threading.Lock()
        def fetch(text,*args,**kwargs):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active);calls.append(text)
            with lock:active-=1
            return text.replace('Ceramic Device','陶瓷设备')
        with patch('free_online.fetch_text',side_effect=fetch):
            run_online(units,'Simplified Chinese',self.cache,lambda:False,results.append,lambda u,e:self.fail(str(e)))
        self.assertEqual({uid for r in results for uid in r},{u.id for u in units})
        self.assertEqual(len(calls),4);self.assertLessEqual(peak,2)

    def test_feed_never_batches_visible_with_background_or_prose(self):
        feed=LiveFeed()
        for unit in [name(1,priority=0),name(2,priority=2),name(3,priority=2)]:feed.submit(unit)
        eligible=lambda u,g:self.cache.can_batch_name(u,'Simplified Chinese',g)
        self.assertEqual(len(feed.pop_names(feed.pop(),eligible)),1)
        self.assertEqual(len(feed.pop_names(feed.pop(),eligible)),2)
        self.assertEqual(feed.pending(),0)

    def test_cancelled_group_sends_nothing_and_never_caches(self):
        result=self.cache.translate_names([(name(i),None) for i in range(4)],'Simplified Chinese',
            lambda *a,**k:self.fail('cancelled request'),cancelled=lambda:True)
        self.assertEqual(result,[]);self.assertFalse(self.cache.rows)
