from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace

from extractor import Entry
from free_online import TranslationCache
from human_memory import HumanMemory, build_memory, catalog, import_folder, read_xml
from workbench import Unit


class HumanMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.memory=HumanMemory(self.root/'cache.sqlite3');self.addCleanup(self.memory.close)

    def unit(self,text='Ghost Tool',scope='1234567890',key='entityname.ghost'):
        return Unit('one',text,occurrences=[Entry('e','fixture',1,1,'游戏内显示','literal',text,
                    location={'mod_id':scope,'native_key':key})])

    def row(self,source='Ghost Tool',translation='幽灵工具',scope='1234567890',provider='2861028841',key='entityname.ghost'):
        return (scope,key,source,'Simplified Chinese',translation,provider,'source-sha','target-sha')

    def put(self,*rows):return self.memory.replace(rows,{})

    def package(self,id,language,text,key='entityname.ghost',filename='text.xml'):
        root=self.root/id;root.mkdir(exist_ok=True)
        (root/'filelist.xml').write_text(f'<contentpackage steamworkshopid="{id}"><Text file="%ModDir%/{filename}"/></contentpackage>')
        (root/filename).write_text(f'<infotexts language="{language}"><{key}>{text}</{key}></infotexts>',encoding='utf-8')
        return root

    def test_exact_scoped_lookup_preserves_outer_whitespace_and_origin(self):
        self.put(self.row());result=self.memory.lookup(self.unit(' Ghost Tool '),'Simplified Chinese')['one']
        self.assertEqual(result['translation'],' 幽灵工具 ');self.assertIn('2861028841',result['origin'])

    def test_changed_source_and_other_mod_never_reuse(self):
        self.put(self.row())
        self.assertIsNone(self.memory.lookup(self.unit('New Ghost Tool'),'Simplified Chinese'))
        self.assertIsNone(self.memory.lookup(self.unit(scope='9999999999'),'Simplified Chinese'))

    def test_other_key_does_not_reuse(self):
        self.put(self.row());self.assertIsNone(self.memory.lookup(self.unit(key='entityname.other'),'Simplified Chinese'))

    def test_conflicting_providers_fall_back_instead_of_guessing(self):
        self.put(self.row(),self.row(translation='鬼工具',provider='8888888888'))
        self.assertIsNone(self.memory.lookup(self.unit(),'Simplified Chinese'))

    def test_identical_providers_agree(self):
        self.put(self.row(),self.row(provider='8888888888'))
        self.assertIsNotNone(self.memory.lookup(self.unit(),'Simplified Chinese'))

    def test_short_unscoped_labels_never_guess(self):
        self.put(self.row());self.assertIsNone(self.memory.lookup(self.unit(scope='',key=''),'Simplified Chinese'))

    def test_placeholder_damage_never_reused_even_from_database(self):
        self.put(self.row(source='Ghost [name] Tool'));self.assertIsNone(self.memory.lookup(self.unit('Ghost [name] Tool'),'Simplified Chinese'))

    def test_language_pair_isolation(self):
        self.put(self.row());u=self.unit()
        self.assertIsNone(self.memory.lookup(u,'Traditional Chinese'));u.source_language='French'
        self.assertIsNone(self.memory.lookup(u,'Simplified Chinese'))

    def test_rebuild_refreshes_existing_open_reader_and_removes_stale_rows(self):
        self.put(self.row());self.memory.lookup(self.unit(),'Simplified Chinese')
        self.put(self.row(translation='新幽灵工具'))
        self.assertEqual(self.memory.lookup(self.unit(),'Simplified Chinese')['one']['translation'],'新幽灵工具')
        self.put();self.assertIsNone(self.memory.lookup(self.unit(),'Simplified Chinese'))

    def test_transaction_failure_preserves_existing_cache(self):
        self.put(self.row())
        with self.assertRaises(sqlite3.Error):self.put(('bad',))
        self.assertIsNotNone(self.memory.lookup(self.unit(),'Simplified Chinese'))

    def test_human_precedes_stale_machine_cache_and_forbids_network(self):
        self.put(self.row());cache=TranslationCache(self.root/'online.json',human_memory=self.memory);unit=self.unit()
        cache.remember(cache.key(unit,'Simplified Chinese'),'旧机器译文')
        def forbidden(*a,**k):raise AssertionError('human match made HTTP request')
        result=cache.translate(unit,'Simplified Chinese',forbidden)
        self.assertEqual(result['one']['translation'],'幽灵工具');self.assertEqual(cache.metrics['requests'],0)

    def test_name_batch_excludes_human_hits_without_network(self):
        self.put(self.row(),self.row('Phantom Wrench','幻影扳手',key='entityname.wrench'))
        cache=TranslationCache(self.root/'online.json',human_memory=self.memory)
        work=[(self.unit(),{}),(self.unit('Phantom Wrench',key='entityname.wrench'),{})]
        def forbidden(*a,**k):raise AssertionError('batch leaked human text to HTTP')
        result=cache.translate_names(work,'Simplified Chinese',forbidden)
        self.assertEqual(len(result),2);self.assertTrue(all(error is None for _,_,error in result));self.assertEqual(cache.metrics['human_hits'],2)

    def test_explicit_user_term_wins(self):
        self.put(self.row());cache=TranslationCache(self.root/'online.json',human_memory=self.memory)
        result=cache.translate(self.unit(),'Simplified Chinese',glossary={'Ghost Tool':'自定工具'})
        self.assertEqual(result['one']['translation'],'自定工具')

    def test_join_requires_exact_native_key(self):
        source=self.package('1234567890','English','Ghost Tool')
        target=self.package('2861028841','Simplified Chinese','幽灵工具')
        report=build_memory([source,target],self.memory,[{'provider':'2861028841','targets':['1234567890']}])
        self.assertEqual(report['records'],1);self.assertIsNotNone(self.memory.lookup(self.unit(),'Simplified Chinese'))
        with closing(sqlite3.connect(self.memory.path)) as connection:
            stored=json.loads(connection.execute('SELECT value FROM metadata').fetchone()[0])
        self.assertEqual(stored['records'],1)

    def test_changed_ambiguous_keys_and_broken_placeholders_excluded(self):
        source=self.package('1234567890','English','Ghost [name] Tool')
        target=self.package('2861028841','Simplified Chinese','幽灵工具')
        rules=[{'provider':'2861028841','targets':['1234567890']}]
        self.assertEqual(build_memory([source,target],self.memory,rules)['rejected_quality'],1)
        (source/'text.xml').write_text('<infotexts language="English"><entityname.ghost>A</entityname.ghost><entityname.ghost>B</entityname.ghost></infotexts>')
        self.assertEqual(build_memory([source,target],self.memory,rules)['ambiguous_keys'],1)

    def test_selected_route_cannot_leak_other_mod_files(self):
        source=self.package('1234567890','English','Ghost Tool')
        target=self.package('2861028841','Simplified Chinese','错误译文')
        (target/'correct.xml').write_text('<infotexts language="Simplified Chinese"><entityname.ghost>幽灵工具</entityname.ghost></infotexts>',encoding='utf-8')
        report=build_memory([source,target],self.memory,[{'provider':'2861028841','targets':['1234567890'],'files':['correct.xml']}])
        self.assertEqual(report['records'],1);self.assertEqual(self.memory.lookup(self.unit(),'Simplified Chinese')['one']['translation'],'幽灵工具')

    def test_dtd_rejected_even_utf16(self):
        path=self.root/'bad.xml';path.write_bytes('<!DOCTYPE x [<!ENTITY a "bad">]><x>&a;</x>'.encode('utf-16'))
        with self.assertRaisesRegex(ValueError,'DTD'):read_xml(path)

    def test_path_traversal_is_not_read(self):
        source=self.package('1234567890','English','Ghost Tool',filename='../secret.xml')
        (self.root/'secret.xml').write_text('<infotexts language="English"><entityname.ghost>Secret</entityname.ghost></infotexts>')
        self.assertFalse(catalog(source,'English')[0])

    def test_symlink_source_refused(self):
        path=self.root/'real.xml';path.write_text('<x/>');link=self.root/'link.xml'
        try:link.symlink_to(path)
        except OSError as error:self.skipTest('OS symbolic-link privilege unavailable: '+str(error))
        with self.assertRaises(ValueError):read_xml(link)

    def test_import_folder_never_writes_into_mod_library(self):
        with self.assertRaisesRegex(ValueError,'模组目录外'):import_folder(self.root,HumanMemory(self.root/'inside.sqlite3'))

    def test_missing_bank_does_not_create_file(self):
        self.assertIsNone(self.memory.lookup(self.unit(),'Simplified Chinese'));self.assertFalse(self.memory.path.exists())

    def test_corrupt_bank_falls_back(self):
        self.memory.path.write_text('not sqlite');self.memory.available=True
        self.assertIsNone(self.memory.lookup(self.unit(),'Simplified Chinese'))

    def test_override_container_is_not_treated_as_a_translation_key(self):
        root=self.package('1234567890','English','Ghost Tool')
        (root/'text.xml').write_text('<infotexts language="English"><Override><entityname.ghost>Ghost Tool</entityname.ghost></Override></infotexts>')
        rows,_,_=catalog(root,'English')
        self.assertEqual(rows,{'entityname.ghost':{'Ghost Tool'}})
