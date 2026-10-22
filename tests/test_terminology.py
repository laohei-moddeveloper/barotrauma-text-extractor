import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse

from extractor import Entry
from free_online import TranslationCache,translate_unit
from terminology import exact_term,relevant_terms


def unit(text,keys=(),context=''):
    return SimpleNamespace(id='unit',source=text,source_language='English',keys=keys,
        occurrences=[Entry('entry','fixture.xml',1,1,'物品','literal',text,context=context)])


def reply(text):return io.BytesIO(json.dumps({'responseStatus':200,'responseData':{'translatedText':text}}).encode())


class TerminologyTests(unittest.TestCase):
    def forbidden(self,*a,**k):raise AssertionError('Local term unexpectedly used the network')

    def test_official_terms_are_instant_without_network(self):
        samples={'Coilgun':'电磁枪','Railgun':'轨道炮','Husk infection':'画皮寄生虫感染',
            'Mudraptor':'泥偶迅猛龙','Crawler':'藻鬃爬行者','Thalamus':'丘脑','Welding Fuel Tank':'焊接油箱'}
        for source,target in samples.items():
            with self.subTest(source=source):
                result=translate_unit(unit(source),'Simplified Chinese',self.forbidden)['unit']
                self.assertEqual(result['translation'],target);self.assertFalse(result['issues'])

    def test_affliction_and_game_title_are_not_confused(self):
        self.assertIsNone(exact_term(unit('Barotrauma'),'Simplified Chinese'))
        self.assertEqual(exact_term(unit('Barotrauma',['afflictionname.pressure']),'Simplified Chinese'),'恶性水压创伤')
        self.assertEqual(exact_term(unit('Burn',context='AfflictionPrefab.Name'),'Simplified Chinese'),'烧伤')
        self.assertIsNone(exact_term(unit('Burn!',context='dialogue'),'Simplified Chinese'))

    def test_user_glossary_wins_and_target_pairs_remain_separate(self):
        glossary={'coilgun':'自定义电磁炮'}
        self.assertEqual(exact_term(unit('  COILGUN '),'Simplified Chinese',glossary),'  自定义电磁炮 ')
        self.assertIsNone(exact_term(unit('Coilgun'),'French'))
        self.assertEqual(exact_term(unit('Coilgun'),'French',{'Coilgun':'Canon spécial'}),'Canon spécial')

    def test_domain_terms_and_format_keep_sentence_context_in_one_request(self):
        calls=[]
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            self.assertNotIn('Coilgun',q);self.assertNotIn('[target]',q)
            return reply(q.replace('Reload','重新装填').replace('for','给'))
        result=translate_unit(unit('‖color:1,2,3‖Reload Coilgun for [target]‖color:end‖'),'Simplified Chinese',network)['unit']
        self.assertEqual(len(calls),1);self.assertFalse(result['issues'])
        self.assertIn('电磁枪',result['translation']);self.assertIn('[target]',result['translation'])

    def test_missing_or_reordered_format_tokens_fall_back_safely(self):
        calls=[]
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            return reply('坏格式' if '__ABYSSTEXT_' in q else {'Alert':'警告','for':'给'}.get(q,q))
        result=translate_unit(unit('Alert Coilgun for [target]'),'Simplified Chinese',network)['unit']
        self.assertEqual(result['translation'],'警告电磁枪给 [target]');self.assertFalse(result['issues'])
        self.assertEqual(len(calls),3)

    def test_term_does_not_replace_part_of_an_identifier(self):
        terms=relevant_terms(unit('mycoilgunidentifier'),'Simplified Chinese')
        from terminology import term_pattern
        self.assertIsNone(term_pattern(tuple(terms)).search('mycoilgunidentifier'))

    def test_cache_context_and_glossary_changes_do_not_reuse_wrong_meaning(self):
        with tempfile.TemporaryDirectory() as temp:
            cache=TranslationCache(Path(temp)/'cache.json')
            a=cache.translate(unit('Coilgun'),'Simplified Chinese',self.forbidden)
            b=cache.translate(unit('Coilgun'),'Simplified Chinese',self.forbidden,glossary={'Coilgun':'自定义名称'})
            self.assertNotEqual(a['unit']['translation'],b['unit']['translation'])
            self.assertNotEqual(cache.key(unit('Barotrauma'),'Simplified Chinese'),cache.key(unit('Barotrauma',['afflictionname.pressure']),'Simplified Chinese'))

    def test_fragment_cache_reuses_templates_with_different_placeholders(self):
        calls=[]
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            return reply(q.replace('Alert','警告'))
        with tempfile.TemporaryDirectory() as temp:
            cache=TranslationCache(Path(temp)/'cache.json')
            for source in ['Alert [captain]','Alert [mechanic]']:
                result=cache.translate(unit(source),'Simplified Chinese',network)['unit']
                self.assertEqual(result['translation'],source.replace('Alert','警告'))
            self.assertEqual(len(calls),1)

    def test_concurrent_identical_fragments_share_one_request(self):
        calls=[];started=threading.Event();release=threading.Event()
        def network(request,timeout):
            calls.append(request.full_url);started.set();self.assertTrue(release.wait(2))
            q=parse_qs(urlparse(request.full_url).query)['q'][0];return reply(q.replace('Alert','警告'))
        with tempfile.TemporaryDirectory() as temp,ThreadPoolExecutor(max_workers=2) as pool:
            cache=TranslationCache(Path(temp)/'cache.json')
            a=pool.submit(cache.translate,unit('Alert [one]'),'Simplified Chinese',network)
            self.assertTrue(started.wait(2))
            b=pool.submit(cache.translate,unit('Alert [two]'),'Simplified Chinese',network)
            release.set()
            self.assertFalse(a.result()['unit']['issues']);self.assertFalse(b.result()['unit']['issues'])
            self.assertEqual(len(calls),1)

    def test_cancelled_waiter_and_failed_owner_release_flight(self):
        started=threading.Event();release=threading.Event();cancel=threading.Event()
        def network(*a,**k):started.set();release.wait(2);raise TimeoutError('fixture')
        with tempfile.TemporaryDirectory() as temp,ThreadPoolExecutor(max_workers=2) as pool:
            cache=TranslationCache(Path(temp)/'cache.json')
            owner=pool.submit(cache.translate,unit('Alert [one]'),'Simplified Chinese',network)
            self.assertTrue(started.wait(2));cancel.set()
            waiter=pool.submit(cache.translate,unit('Alert [two]'),'Simplified Chinese',network,cancel.is_set)
            with self.assertRaisesRegex(ValueError,'取消'):waiter.result()
            release.set()
            with self.assertRaises(ValueError):owner.result()
            self.assertFalse(cache.flights)

    def test_google_channel_uses_direct_google_endpoint_without_key(self):
        def network(request,timeout):
            parsed=urlparse(request.full_url);self.assertEqual(parsed.hostname,'translate.googleapis.com')
            query=parse_qs(parsed.query);self.assertEqual(query['client'],['gtx']);self.assertEqual(query['tl'],['zh-CN'])
            self.assertNotIn('Authorization',request.headers)
            return io.BytesIO(json.dumps([[['打开舱门','Open hatch',None,None]],None,'en']).encode())
        result=translate_unit(unit('Open hatch'),'Simplified Chinese',network,channel='google')['unit']
        self.assertEqual(result['translation'],'打开舱门');self.assertFalse(result['issues'])

    def test_channel_switch_does_not_reuse_another_channels_translation(self):
        calls=[]
        def network(request,timeout):
            host=urlparse(request.full_url).hostname;calls.append(host)
            if host=='translate.googleapis.com':return io.BytesIO(json.dumps([[['第二种译文','Open hatch']]]).encode())
            return reply('第一种译文')
        with tempfile.TemporaryDirectory() as temp:
            cache=TranslationCache(Path(temp)/'cache.json')
            first=cache.translate(unit('Open hatch'),'Simplified Chinese',network)
            second=cache.translate(unit('Open hatch'),'Simplified Chinese',network,channel='google')
            self.assertNotEqual(first['unit']['translation'],second['unit']['translation']);self.assertEqual(len(calls),2)

    def test_google_errors_never_silently_forward_to_another_service(self):
        calls=[]
        def network(request,timeout):calls.append(urlparse(request.full_url).hostname);return io.BytesIO(b'{}')
        with self.assertRaisesRegex(ValueError,'Google'):
            translate_unit(unit('Open hatch'),'Simplified Chinese',network,channel='google')
        self.assertEqual(calls,['translate.googleapis.com'])

    def test_mymemory_spaced_markers_are_restored_without_extra_requests(self):
        calls=[]
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            return reply(q.replace('Use','使用').replace('__ABYSSTEXT_0__','__ ABYSSTEXT_0 __'))
        result=translate_unit(unit('Use Coilgun'),'Simplified Chinese',network)['unit']
        self.assertEqual(len(calls),1);self.assertFalse(result['issues']);self.assertEqual(result['translation'],'使用电磁枪')

    def test_medical_template_is_whole_instruction_and_never_noun_treat(self):
        result=translate_unit(unit('Treat opiate overdose with Naloxone.'),'Simplified Chinese',self.forbidden)['unit']
        self.assertEqual(result['translation'],'使用纳洛酮治疗阿片类药物中毒。')
        from terminology import medical_template
        self.assertIsNone(medical_template(unit('Treat the guest with respect.'),'Simplified Chinese'))
        self.assertIsNone(medical_template(unit('Treat unknown illness with unknown drug.'),'Simplified Chinese'))

    def test_chinese_spacing_cleanup_does_not_edit_placeholder_or_boundary_whitespace(self):
        from free_online import chinese_spacing
        self.assertEqual(chinese_spacing('  装填 电磁枪 [专 有 名]\\n','Simplified Chinese'),'  装填电磁枪 [专 有 名]\\n')

    def test_user_term_internal_spacing_is_preserved_in_sentences(self):
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];return reply(q.replace('Reload','装填'))
        result=translate_unit(unit('Reload Coilgun'),'Simplified Chinese',network,glossary={'Coilgun':'电 磁 炮'})['unit']
        self.assertIn('电 磁 炮',result['translation']);self.assertFalse(result['issues'])

    def test_game_actions_follow_object_context_instead_of_web_verb_meaning(self):
        game=relevant_terms(unit('Reload the Coilgun before docking.'),'Simplified Chinese')
        self.assertEqual(game.get('Reload'),'装填')
        web=relevant_terms(unit('Reload the webpage to read the Coilgun guide.'),'Simplified Chinese')
        self.assertNotIn('Reload',web)
        breach=relevant_terms(unit('Seal the hull breach.'),'Simplified Chinese')
        self.assertEqual(breach.get('Seal'),'封堵')
        self.assertNotIn('Seal',relevant_terms(unit('Seal of approval.'),'Simplified Chinese'))
        override=relevant_terms(unit('Reload the Coilgun.'),'Simplified Chinese',{'Reload':'自定动作'})
        self.assertEqual(override.get('Reload'),'自定动作')

    def test_medical_template_handles_known_condition_without_prior_health_key(self):
        result=translate_unit(unit('Treat bleeding with Bandage.'),'Simplified Chinese',self.forbidden)['unit']
        self.assertEqual(result['translation'],'使用绷带治疗出血。');self.assertFalse(result['issues'])

    def test_weapon_verb_keeps_sentence_grammar_then_repairs_only_wrong_sense(self):
        import re
        calls=[]
        def network(request,timeout):
            q=parse_qs(urlparse(request.full_url).query)['q'][0];calls.append(q)
            self.assertIn('Reload',q)
            markers=re.findall(r'__ABYSSTEXT_\d+__',q)
            return reply('在 '+markers[1]+' 到达气闸之前重新加载 '+markers[0]+'。')
        result=translate_unit(unit('Reload the Coilgun before the Mudraptor reaches the airlock.'),'Simplified Chinese',network)['unit']
        self.assertEqual(len(calls),1);self.assertEqual(result['translation'],'在泥偶迅猛龙到达气闸之前装填电磁枪。')
        self.assertFalse(result['issues'])

    def test_software_and_explicit_user_action_terms_are_not_postcorrected(self):
        from terminology import repair_game_actions
        self.assertEqual(repair_game_actions(unit('Reload the Coilgun guide.'),'重新加载网页','Simplified Chinese'),'重新加载网页')
        self.assertEqual(repair_game_actions(unit('Reload the Coilgun.'),'自定重新加载','Simplified Chinese',{'Reload':'自定重新加载'}),'自定重新加载')

    def test_submarine_crew_and_plural_creature_names_keep_game_meaning(self):
        terms=relevant_terms(unit('Crew members saw two Crawlers.'),'Simplified Chinese')
        self.assertEqual(terms['crew members'],'船员');self.assertEqual(terms['Crawlers'],'藻鬃爬行者')
        self.assertEqual(translate_unit(unit('Mudraptors'),'Simplified Chinese',self.forbidden)['unit']['translation'],'泥偶迅猛龙')

    def test_creature_motion_does_not_add_vehicle_meaning(self):
        from terminology import repair_game_actions
        self.assertEqual(repair_game_actions(unit('The Crawler is moving toward the nest.'),'正在驶向巢穴','Simplified Chinese'),'正在移向巢穴')
        self.assertEqual(repair_game_actions(unit('The submarine is moving toward the outpost.'),'正驶向前哨站','Simplified Chinese'),'正驶向前哨站')
        self.assertEqual(repair_game_actions(unit('The Crawler is moving toward the nest.'),'正在驶向巢穴','Simplified Chinese',{'moving':'驶向'}),'正在驶向巢穴')
