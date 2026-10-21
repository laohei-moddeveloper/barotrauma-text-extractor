import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from extractor import Entry, Report
from languages import canonical_language, detect_language
from workbench import Project, native_xml
from live_bridge import LiveBridge
from ui_i18n import tr


def record(text,language,key='greeting'):
    return Entry(text, 'texts.xml', 1, 1, '语言表', 'literal', text,key=key,language=language)

class LanguageTests(unittest.TestCase):
    def test_exact_boundary_whitespace(self):
        from workbench import quality
        self.assertIn("首尾空白发生变化",quality(" Hello ","  你好 "))

    def test_aliases(self):
        self.assertEqual(canonical_language('zh-cn'),'Simplified Chinese')
        self.assertEqual(canonical_language('ja'),'Japanese')

    def test_metadata_detection_and_existing_target(self):
        project=Project(Report('/nonexistent',[record('こんにちは','Japanese'),record('你好','Simplified Chinese')]),source_language='Auto')
        self.assertEqual(project.source_language,'Japanese')
        self.assertEqual(len(project.units),1)
        self.assertEqual(project.units[0].translation,'你好')

    def test_language_pairs_isolate_memory_and_review(self):
        report=Report('/nonexistent',[record('Hello','English')])
        chinese=Project(report)
        chinese.update(chinese.units[0].id,'你好','已校对')
        french=Project(report,chinese,target_language='French')
        self.assertEqual(french.units[0].translation,'')
        self.assertFalse(french.memory)
        french.update(french.units[0].id,'Bonjour','已校对')
        xml,_,_=native_xml(french)
        self.assertEqual(ET.fromstring(xml).attrib['language'],'French')
        self.assertNotIn('nowhitespace',ET.fromstring(xml).attrib)

    def test_detection_admits_latin_ambiguity(self):
        language,reason=detect_language([record('Bonjour','')],'Japanese')
        self.assertEqual(language,'English')
        self.assertIn('手动选择',reason)

    def test_pair_save_load_and_csv_validation_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            project=Project(Report(str(Path(temp)/'source'),[record('こんにちは','Japanese')]),source_language='ja',target_language='French')
            path=Path(temp)/'project.json';project.save(path)
            loaded=Project.load(path)
            self.assertEqual((loaded.source_language,loaded.target_language),('Japanese','French'))
            csv=Path(temp)/'import.csv'
            csv.write_text('source,translation,target_language\nこんにちは,Bonjour,French\nOther,Wrong,German\n',encoding='utf-8')
            with self.assertRaises(ValueError):loaded.import_table(csv)
            self.assertFalse(loaded.memory)
            self.assertFalse(loaded.units[0].translation)

    def test_unicode_game_request_and_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'filelist.xml').write_text('<contentpackage name="AbyssTextLive"/>')
            bridge=LiveBridge(root);bridge.configure('en','ja','fr')
            self.assertEqual(json.loads((root/'Live/settings.json').read_text())['target_language'],'French')
            (root/'Live/requests.json').write_text(json.dumps({'protocol':1,'source_language':'Japanese','records':[{'text':'こんにちは'}]}))
            report,_,_=bridge.read_request()
            self.assertEqual(report.entries[0].language,'Japanese')
            self.assertEqual(Project(report,source_language='Auto',target_language='French').source_language,'Japanese')

    def test_ui_language_preserves_unknown_source(self):
        self.assertEqual(tr('识别语言','en'),'Source language')
        self.assertEqual(tr('目标译文','en'),'Target translation')
        self.assertEqual(tr('你好，captain!','en'),'你好，captain!')

class CompanionTests(unittest.TestCase):
    def test_install_new_only_without_runtime_data(self):
        from companion import install_companion
        with tempfile.TemporaryDirectory() as temp:
            target=install_companion(temp)
            self.assertTrue((target/'Live/Translations.xml').is_file())
            self.assertFalse((target/'Live/settings.json').exists())
            with self.assertRaises(ValueError):install_companion(temp)
