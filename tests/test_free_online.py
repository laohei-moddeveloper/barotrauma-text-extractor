import io
import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from free_online import translate_unit, TranslationCache


class FreeOnlineTests(unittest.TestCase):
    def test_existing_chinese_never_calls_network(self):
        def forbidden(*args,**kwargs):raise AssertionError('Chinese entered network queue')
        for text in ['已有中文','已有中文 English [name]']:
            self.assertEqual(translate_unit(self.unit(text),'Simplified Chinese',forbidden)['one']['translation'],text)

    def test_persistent_cache_reuses_only_the_matching_language_pair(self):
        calls=[]
        def opener(request,timeout):
            calls.append(request.full_url)
            return io.BytesIO(b'{"responseStatus":200,"responseData":{"translatedText":"Bonjour"}}')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'cache.json'
            cache=TranslationCache(path)
            cache.translate(self.unit('Hello'),'French',opener);cache.flush()
            loaded=TranslationCache(path)
            loaded.translate(self.unit('Hello'),'French',opener)
            self.assertEqual(len(calls),1)
            loaded.translate(self.unit('Hello'),'German',opener)
            self.assertEqual(len(calls),2)

    def unit(self,text):
        return SimpleNamespace(id='one',source=text,source_language='English')

    def test_keyless_translation_preserves_markup_and_whitespace(self):
        requests=[]
        def opener(request,timeout):
            query=parse_qs(urlparse(request.full_url).query)
            requests.append(query)
            self.assertEqual(query['langpair'],['en|zh-CN'])
            self.assertNotIn('Authorization',request.headers)
            return io.BytesIO(json.dumps({'responseStatus':200,'responseData':{'translatedText':'警告'}}).encode())
        result=translate_unit(self.unit(' ‖color:1,2,3‖Warning‖color:end‖ [name] {0}\n'),'Simplified Chinese',opener)
        self.assertEqual(result['one']['translation'],' ‖color:1,2,3‖警告‖color:end‖ [name] {0}\n')
        self.assertFalse(result['one']['issues'])
        self.assertEqual(len(requests),1)

    def test_quota_is_an_error_not_a_translation(self):
        def opener(*args,**kwargs):
            return io.BytesIO(b'{"responseStatus":403,"quotaFinished":true}')
        with self.assertRaisesRegex(ValueError,'额度'):
            translate_unit(self.unit('Warning'),'Simplified Chinese',opener)

    def test_cancellation_never_sends(self):
        def opener(*args,**kwargs):raise AssertionError('unexpected network')
        with self.assertRaisesRegex(ValueError,'取消'):
            translate_unit(self.unit('Warning'),'French',opener,lambda:True)

    def test_multibyte_request_limit(self):
        def opener(request,timeout):
            text=parse_qs(urlparse(request.full_url).query)['q'][0]
            self.assertLessEqual(len(text.encode()),480)
            return io.BytesIO(json.dumps({'responseStatus':200,'responseData':{'translatedText':text}}).encode())
        source='こんにちは'*100
        result=translate_unit(self.unit(source),'French',opener)
        self.assertEqual(result['one']['translation'],source)
