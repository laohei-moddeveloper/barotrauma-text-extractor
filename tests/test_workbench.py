import csv
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from extractor import Entry, Report, scan
from live_bridge import LiveBridge
from translation_api import Settings, batches, translate
from workbench import Project, Unit, export_copy, export_csv, export_native, native_xml, quality


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.root=self.base/"source";self.root.mkdir()

    def write(self,name,content):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content if isinstance(content,bytes) else content.encode("utf-8"))
        return path

    def project(self):return Project(scan(self.root))

    def keyed(self):
        self.write("English.xml",'<infotexts language="English"><entityname.a>Medkit</entityname.a><entityname.b>Medkit</entityname.b><event.a>Hello [name]!</event.a></infotexts>')
        return self.project()

    def test_exact_duplicates_group_all_occurrences_and_keys(self):
        project=self.keyed()
        self.assertEqual(len(project.units),2)
        unit=next(u for u in project.units if u.source=="Medkit")
        self.assertEqual(len(unit.occurrences),2)
        self.assertEqual(unit.keys,["entityname.a","entityname.b"])

    def test_significant_whitespace_not_deduplicated(self):
        self.write("a.lua",'GUI.Button(parent,"Start"); GUI.Button(parent," Start")')
        self.assertEqual(len(self.project().units),2)

    def test_references_are_resolved_not_translated_as_identifiers(self):
        project=self.keyed()
        self.write("events.xml",'<Events><ConversationAction text="event.a"/><Item identifier="unknown"/></Events>')
        project=self.project()
        self.assertEqual(len(project.units),2)
        self.assertEqual(len(next(u for u in project.units if "Hello" in u.source).occurrences),2)
        self.assertEqual(project.unresolved[0].key,"entityname.unknown")

    def test_existing_chinese_reused_as_draft(self):
        self.keyed()
        self.write("Translations.xml",'<infotexts language="Simplified Chinese"><entityname.a>医疗包</entityname.a></infotexts>')
        unit=next(u for u in self.project().units if u.source=="Medkit")
        self.assertEqual((unit.translation,unit.state),("医疗包","草稿"))

    def test_conflicting_existing_translations_do_not_pick_arbitrary_one(self):
        self.keyed()
        self.write("Translations.xml",'<infotexts language="Simplified Chinese"><entityname.a>医疗包</entityname.a><entityname.b>医药箱</entityname.b></infotexts>')
        unit=next(u for u in self.project().units if u.source=="Medkit")
        self.assertEqual(unit.translation,"")
        self.assertIn("多个",unit.notes)

    def test_internal_paths_and_labels_are_hidden_by_default(self):
        self.write("a.lua",'Hook.Add("roundStart","internal_id",function() GUI.Button(parent,"Start") end)')
        self.write("b.xml",'<Root><Label name="internal"/></Root>')
        project=self.project()
        self.assertEqual([u.source for u in project.filtered()],["Start"])
        self.assertEqual(len(project.filtered(candidates=True)),4)

    def test_search_matches_translation_key_and_file(self):
        project=self.keyed();unit=project.units[0]
        project.update(unit.id,"医疗包")
        self.assertEqual(project.filtered("医疗包 english.xml"),[unit])
        self.assertEqual(project.filtered("entityname.a"),[unit])
        self.assertEqual(project.filtered(category_name="物品 / 生物"),[unit])

    def test_format_quality_blocks_bad_review_and_export(self):
        project=self.keyed();unit=next(u for u in project.units if "Hello" in u.source)
        project.update(unit.id,"你好！")
        self.assertIn("占位符",unit.issues[0])
        with self.assertRaises(ValueError):project.update(unit.id,unit.translation,state="已校对")
        project.update(unit.id,"你好 [name]！",state="已校对")
        self.assertFalse(unit.issues)

    def test_quality_counts_repeated_tokens_and_markers(self):
        self.assertTrue(quality("[x] [x] ‖color:1,2,3‖{0}‖color:end‖","[x] ‖color:1,2,3‖{0}‖color:end‖"))
        self.assertFalse(quality("DNA","DNA"))
        self.assertTrue(quality("Text","文\x00字"))

    def test_save_reopen_preserves_progress_notes_and_no_key(self):
        project=self.keyed();unit=project.units[0]
        project.update(unit.id,"医疗包",state="已校对",notes="术语已确认")
        output=self.base/"project.json";project.save(output)
        loaded=Project.load(output)
        self.assertEqual(loaded.by_id[unit.id].notes,"术语已确认")
        self.assertEqual(loaded.memory[unit.source],"医疗包")
        self.assertNotIn("api",json.loads(output.read_text(encoding='utf-8')))
        self.assertFalse(loaded.dirty)

    def test_split_homonyms_survives_rescan(self):
        project=self.keyed();unit=project.units[0]
        self.assertTrue(project.split_context(unit.id))
        parts=[u for u in project.units if u.source=="Medkit"]
        self.assertEqual(len(parts),2)
        project.update(parts[0].id,"医疗包",state="已校对")
        project.update(parts[1].id,"医药箱",state="已校对")
        rescanned=Project(scan(self.root),project)
        self.assertEqual({u.translation for u in rescanned.units if u.source=="Medkit"},{"医疗包","医药箱"})

    def test_csv_roundtrip_formula_and_apostrophe(self):
        self.write("a.xml",'<infotexts language="English"><a>=Start</a><b>\'Quoted</b></infotexts>')
        project=self.project()
        for u in project.units:project.update(u.id,"译文"+u.source)
        output=self.base/"out.csv";export_csv(project,output)
        fresh=self.project();fresh.import_table(output)
        self.assertEqual([u.translation for u in fresh.units],[u.translation for u in project.units])
        with output.open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
        self.assertTrue(rows[0]["source"].startswith("'="))

    def test_native_export_uses_real_keys_and_reviewed_only(self):
        project=self.keyed();unit=project.units[0]
        project.update(unit.id,"医疗包",state="已校对")
        other=project.units[1];project.update(other.id,"你好 [name]！")
        target=self.base/"native"
        count,notes=export_native(project,target)
        self.assertEqual(count,2)
        xml=ET.parse(target/"Translations.xml").getroot()
        self.assertEqual(xml.attrib["language"],"Simplified Chinese")
        self.assertEqual(len(xml.find("Override")),2)
        self.assertNotIn("event.a",[e.tag for e in xml.find("Override")])

    def test_native_conflicting_same_key_is_rejected(self):
        e1=Entry("a","a.xml",1,1,"语言表","literal","First",key="same",language="English")
        e2=replace(e1,id="b",text="Other")
        project=Project(Report(str(self.root),[e1,e2]))
        project.update(project.units[0].id,"第一",state="已校对")
        project.update(project.units[1].id,"第二",state="已校对")
        with self.assertRaisesRegex(ValueError,"冲突"):native_xml(project)

    def test_source_export_xml_and_lua_preserve_original_and_unrelated_bytes(self):
        before=b'\xef\xbb\xbf<Items>\r\n<!-- keep -->\r\n<Item identifier="a" name="Medkit" description="Safe &amp; sound" custom="keep"/>\r\n</Items>'
        path=self.write("items.xml",before)
        lua=self.write("ui.lua",b'-- keep\r\nGUI.Button(parent, "Launch" .. " now")\r\n')
        project=self.project()
        for unit in project.units:
            target={"Medkit":"医疗包","Safe & sound":"安全 & 完好","Launch now":'立即 "出发"'}[unit.source]
            project.update(unit.id,target,state="已校对")
        output=self.base/"copy"
        changed,_=export_copy(project,output)
        self.assertEqual(changed,2)
        data=(output/"items.xml").read_bytes()
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'<!-- keep -->\r\n',data)
        self.assertIn(b'custom="keep"',data)
        ET.fromstring(data)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(lua.read_bytes(),b'-- keep\r\nGUI.Button(parent, "Launch" .. " now")\r\n')
        self.assertIn('立即 \\"出发\\"',(output/"ui.lua").read_text(encoding='utf-8'))

    def test_source_export_preserves_utf16(self):
        self.write("a.xml",'<Items><Item name="Kit"/></Items>'.encode("utf-16"))
        project=self.project();project.update(project.units[0].id,"药箱",state="已校对")
        export_copy(project,self.base/"copy")
        data=(self.base/"copy/a.xml").read_bytes()
        self.assertTrue(data.startswith(b'\xff\xfe'))
        self.assertEqual(ET.fromstring(data)[0].attrib["name"],"药箱")

    def test_source_changes_block_export_without_partial_output(self):
        self.keyed();project=self.project();project.update(project.units[0].id,"医疗包",state="已校对")
        self.write("English.xml",'<infotexts language="English"/>')
        output=self.base/"copy"
        with self.assertRaisesRegex(ValueError,"变化"):export_copy(project,output)
        self.assertFalse(output.exists())

    def test_outputs_cannot_touch_source_or_existing_directory(self):
        project=self.keyed();project.update(project.units[0].id,"医疗包",state="已校对")
        for fn,path in [(export_csv,self.root/"x.csv"),(export_native,self.root/"native"),(export_copy,self.root/"copy")]:
            with self.assertRaises(ValueError):fn(project,path)
        with self.assertRaises(ValueError):export_native(project,self.base)
        with self.assertRaises(ValueError):project.save(self.root/"project.json")

    def test_project_path_traversal_is_rejected(self):
        project=self.keyed();project.update(project.units[0].id,"医疗包",state="已校对")
        entry=project.units[0].occurrences[0]
        entry.file="../source/English.xml"
        with self.assertRaisesRegex(ValueError,"非法"):export_copy(project,self.base/"copy")

    def test_scan_cache_invalidation_and_resolution_do_not_mutate_cache(self):
        self.keyed();cache={}
        first=scan(self.root,cache=cache);second=scan(self.root,cache=cache)
        self.assertEqual(first.entries,second.entries)
        self.write("English.xml",'<infotexts language="English"><a>Changed</a></infotexts>')
        self.assertEqual(scan(self.root,cache=cache).entries[0].text,"Changed")

    def test_item_name_matching_arbitrary_key_remains_literal(self):
        self.write("a.xml",'<infotexts language="English"><start>Go</start></infotexts>')
        self.write("b.xml",'<Items><Item identifier="x" name="start" nameidentifier="shared"/></Items>')
        report=scan(self.root)
        name=next(e for e in report.entries if e.text=="start")
        self.assertEqual(name.kind,"literal")
        self.assertEqual(name.location["native_key"],"entityname.shared")
        reference=next(e for e in report.entries if e.text=="shared")
        self.assertEqual(reference.key,"entityname.shared")

    def test_affliction_translation_override_and_language_override_wrapper(self):
        self.write("a.xml",'<Afflictions><Affliction identifier="a" translationoverride="shared" name="Ache" description="Pain"/></Afflictions>')
        self.write("English.xml",'<infotexts language="English"><Override><afflictionname.shared>Ache</afflictionname.shared></Override></infotexts>')
        project=self.project()
        self.assertIn("afflictionname.shared",project.units[0].keys)
        self.assertFalse(any(u.source=="Override" for u in project.units))

    def test_constant_concat_and_simple_display_flow(self):
        self.write("a.lua",'local warning="Hull " .. "breach!"\nGUI.TextBlock(parent,warning)')
        project=self.project()
        self.assertEqual([u.source for u in project.filtered()],["Hull breach!"])
        self.assertEqual(project.units[0].occurrences[0].category,"脚本显示流向")

    def test_registered_xml_scope_avoids_unused_backup_text(self):
        self.write("filelist.xml",'<contentpackage><Item file="%ModDir%/items.xml"/></contentpackage>')
        self.write("items.xml",'<Items><Item identifier="a" name="Visible"/></Items>')
        self.write("backup.xml",'<Items><Item name="Unused backup"/></Items>')
        report=scan(self.root,registered_only=True)
        self.assertIn("Visible",[e.text for e in report.entries])
        self.assertNotIn("Unused backup",[e.text for e in report.entries])

    def test_mixed_internal_identifier_not_rewritten_with_visible_duplicate(self):
        self.write("a.lua",'Hook.Add("Start","hook",function() GUI.Button(parent,"Start") end)')
        project=self.project();unit=next(u for u in project.units if u.source=="Start")
        project.update(unit.id,"开始",state="已校对")
        target=self.base/"copy";count,notes=export_copy(project,target)
        self.assertIn('Hook.Add("Start"',(target/"a.lua").read_text(encoding='utf-8'))
        self.assertIn('GUI.Button(parent,"开始")',(target/"a.lua").read_text(encoding='utf-8'))
        self.assertTrue(notes)


class APITests(unittest.TestCase):
    def unit(self):return Unit("one","Hello [name]!",occurrences=[])
    def opener(self,payload,seen):
        def call(request,timeout):
            seen.append(request)
            return io.BytesIO(json.dumps({"choices":[{"message":{"content":json.dumps(payload)}}]}).encode())
        return call

    def test_mock_api_roundtrip_and_secret_in_header_only(self):
        seen=[]
        result=translate(Settings(key="test-secret"),[self.unit()],opener=self.opener({"translations":[{"id":"one","translation":"你好 [name]！"}]},seen))
        self.assertEqual(result["one"]["issues"],[])
        self.assertNotIn(b"test-secret",seen[0].data)
        self.assertEqual(seen[0].get_header("Authorization"),"Bearer test-secret")

    def test_missing_duplicate_and_unknown_ids_fail_entire_batch(self):
        for records in [[],[{"id":"unknown","translation":"x"}],[{"id":"one","translation":"x"},{"id":"one","translation":"y"}]]:
            with self.assertRaises(ValueError):translate(Settings(),[self.unit()],opener=self.opener({"translations":records},[]))

    def test_bad_placeholders_remain_flagged_drafts(self):
        result=translate(Settings(),[self.unit()],opener=self.opener({"translations":[{"id":"one","translation":"你好"}]},[]))
        self.assertTrue(result["one"]["issues"])

    def test_invalid_url_never_calls_provider(self):
        for endpoint in ["file:///tmp/test","https://user:password@example.com/v1","https://example.com/v1?secret=a"]:
            with self.assertRaises(ValueError):translate(Settings(endpoint=endpoint),[self.unit()],opener=lambda *a,**kw:self.fail("unexpected network"))

    def test_batches_are_bounded(self):
        units=[Unit(str(i),"hello"*100) for i in range(60)]
        groups=list(batches(units,max_items=10,max_chars=3000))
        self.assertEqual(sum(map(len,groups)),60)
        self.assertTrue(all(len(group)<=6 for group in groups))
        for limit in (8,1000):
            groups=list(batches([Unit(str(i),'short') for i in range(19)],max_items=limit))
            self.assertEqual([len(group) for group in groups],[8,8,3])


class LiveBridgeTests(unittest.TestCase):
    def test_chinese_filtered_and_session_priority_retained(self):
        payload={'protocol':1,'request_id':'new','session_id':'session-two','translate':True,
            'records':[{'text':'已有中文'},{'text':'中文 English'},{'text':'Spineling Head','priority':0}]}
        (self.root/'Live/requests.json').write_text(json.dumps(payload),encoding='utf-8')
        report,_,request=self.bridge.read_request()
        self.assertEqual([e.text for e in report.entries],['Spineling Head'])
        self.assertEqual(report.entries[0].location['live_priority'],0)
        self.assertEqual((request,self.bridge.session_id),('new','session-two'))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"AbyssTextLive";self.root.mkdir()
        (self.root/"filelist.xml").write_text('<contentpackage name="AbyssTextLive"/>', encoding='utf-8')
        self.bridge=LiveBridge(self.root)

    def request(self):
        (self.root/"Live/requests.json").write_text(json.dumps({"protocol":1,"request_id":"one","translate":True,"records":[{"key":"entityname.a","text":"Medkit"},{"key":"","text":"Open hatch"}]}), encoding='utf-8')
        return self.bridge.read_request()

    def test_request_deduplication_and_native_response(self):
        report,generate,request_id=self.request()
        self.assertTrue(generate);self.assertIsNone(self.bridge.read_request())
        project=Project(report)
        for u in project.units:project.update(u.id,{"Medkit":"医疗包","Open hatch":"打开舱门"}[u.source])
        count,literals,_=self.bridge.publish(project,request_id,drafts=True,complete=False)
        self.assertEqual((count,literals),(1,2))
        response=json.loads((self.root/"Live/response.json").read_text(encoding='utf-8'))
        self.assertFalse(response["complete"])
        self.assertEqual(response["translations"]["Open hatch"],"打开舱门")
        ET.parse(self.root/"Live/Translations.xml")

    def test_mailbox_rejects_oversize_batch_and_bad_metadata_without_accepting(self):
        path=self.root/'Live/requests.json'
        for data in [dict(records=[{'text':'Tool'}]*9),dict(records=[],session_id=[]),dict(records=[],target_language='x'*257)]:
            path.write_text(json.dumps({'protocol':1,**data}), encoding='utf-8')
            with self.assertRaises(ValueError):self.bridge.read_request()
            self.assertEqual(self.bridge.seen,'')
        self.assertIsNotNone(self.request())

    def test_reply_retains_canonical_pair_and_session_for_client_validation(self):
        path=self.root/'Live/requests.json'
        path.write_text(json.dumps({'protocol':1,'session_id':'current','request_id':'one',
            'source_language':'en','target_language':'zh-cn','records':[{'text':'Tool'}]}), encoding='utf-8')
        report,_,request=self.bridge.read_request()
        project=Project(report,source_language='English',target_language='Simplified Chinese')
        self.bridge.publish(project,request)
        response=json.loads((self.root/'Live/response.json').read_text(encoding='utf-8'))
        self.assertEqual((response['session_id'],response['source_language'],response['target_language']),
            ('current','English','Simplified Chinese'))

    def test_bad_format_never_sent_to_game(self):
        report,_,request_id=self.request();project=Project(report)
        u=next(u for u in project.units if u.keys)
        project.update(u.id,"医疗包\x00")
        count,literals,_=self.bridge.publish(project,request_id,drafts=True)
        self.assertEqual((count,literals),(0,0))

    def test_unrelated_project_keys_not_injected(self):
        report,_,request_id=self.request()
        report.entries.append(Entry("other","else.xml",1,1,"语言表","literal","Medkit",key="unrelated",language="English"))
        project=Project(report);u=next(u for u in project.units if u.source=="Medkit")
        project.update(u.id,"医疗包",state="已校对")
        self.bridge.publish(project,request_id)
        self.assertNotIn("unrelated",(self.root/"Live/Translations.xml").read_text(encoding='utf-8'))

    def test_non_bridge_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):LiveBridge(directory)


if __name__=="__main__":unittest.main()
