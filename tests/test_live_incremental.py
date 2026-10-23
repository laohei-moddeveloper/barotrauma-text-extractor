import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from extractor import Entry,Report
from live_bridge import LiveBridge
from workbench import Project


def entry(text,key='',priority=2,context='Visible GUI'):
    return Entry(text,'<游戏内>',1,1,'游戏内显示','literal',text,key=key,language='English',context=context,
        location={'native_key':key,'live_priority':priority})


class IncrementalBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'filelist.xml').write_text('<contentpackage name="AbyssTextLive"/>',encoding='utf-8')
        self.bridge=LiveBridge(self.root)

    def test_mod_scope_is_validated_and_preserved(self):
        packet={'protocol':1,'session_id':'scope','request_id':'1','records':[{'text':'Ghost Tool','mod_id':'1234567890'}]}
        path=self.root/'Live/requests.json';path.write_text(json.dumps(packet))
        report,_,_=self.bridge.read_request()
        self.assertEqual(report.entries[0].location['mod_id'],'1234567890')
        packet['records'][0]['mod_id']='../bad';packet['request_id']='2';path.write_text(json.dumps(packet))
        report,_,_=self.bridge.read_request()
        self.assertEqual(report.entries[0].location['mod_id'],'')
        self.assertTrue(report.entries[0].location['mod_scope_invalid'])

    def test_optional_owner_null_numeric_and_malformed_do_not_drop_batch(self):
        values=[None,'',1234567890,{},'../bad','１２３４５６７８９０',True,12345678901234567890]
        packet={'protocol':1,'session_id':'owners','request_id':'1','records':[
            {'text':'Ghost Tool '+str(i),'mod_id':value} for i,value in enumerate(values)]}
        path=self.root/'Live/requests.json';path.write_text(json.dumps(packet))
        report,_,_=self.bridge.read_request()
        self.assertEqual(len(report.entries),8)
        self.assertEqual([e.location['mod_id'] for e in report.entries],['','','1234567890','','','','',''])
        self.assertFalse(report.entries[0].location['mod_scope_invalid'])
        self.assertTrue(all(e.location['mod_scope_invalid'] for e in report.entries[3:]))

    def test_truncated_status_never_acknowledges_or_drops_pending_delta(self):
        self.request();project=self.project(12);self.bridge.publish(project,'one',True)
        first=self.response();path=self.root/'Live/status.json'
        for raw in [b'',b'   ',b'{"protocol":1,',b'\xff']:
            path.write_bytes(raw)
            self.assertIsNone(self.bridge.status(fresh=True))
            self.bridge.publish(project,'one',True)
            self.assertEqual(self.response(),first)
            self.assertEqual(self.bridge._pending['sequence'],1)
        self.ack(first);self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['sequence'],2)

    def test_truncated_request_is_retried_without_advancing_session_or_stamp(self):
        path=self.root/'Live/requests.json'
        for raw in [b'',b'{"protocol":1,"records":[',b'not json']:
            path.write_bytes(raw)
            self.assertIsNone(self.bridge.read_request())
            self.assertEqual(self.bridge.session_id,'');self.assertIsNone(self.bridge._request_stamp)
        packet={'protocol':1,'session_id':'repaired','request_id':'next','records':[{'text':'Recovered tool'}]}
        path.write_text(json.dumps(packet))
        report,_,_=self.bridge.read_request()
        self.assertEqual(report.entries[0].text,'Recovered tool');self.assertEqual(self.bridge.session_id,'repaired')

    def test_same_size_same_timestamp_request_still_detects_session_restart(self):
        self.request('one');path=self.root/'Live/requests.json';before=path.stat()
        self.request('two')
        # Recreate the Windows metadata collision independently of filesystem
        # clock precision. New content must win over a cached metadata stamp.
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.bridge.session_id='one';self.bridge._request_stamp=(before.st_mtime_ns,before.st_size,before.st_ino)
        self.bridge.seen=__import__('hashlib').sha256(path.read_bytes().replace(b'two',b'one')).hexdigest()
        self.assertIsNotNone(self.bridge.read_request());self.assertEqual(self.bridge.session_id,'two')

    def test_permanent_invalid_json_has_named_warning_and_clears_on_repair(self):
        path=self.root/'Live/status.json';path.write_bytes(b'')
        with patch('live_bridge.time.monotonic',return_value=10):self.assertIsNone(self.bridge.status(fresh=True))
        with patch('live_bridge.time.monotonic',return_value=14):self.assertIn('status.json',self.bridge.read_warning)
        path.write_text(json.dumps({'protocol':1,'active':True}))
        self.assertTrue(self.bridge.status(fresh=True)['active']);self.assertEqual(self.bridge.read_warning,'')

    def test_utf8_bom_status_and_transient_read_lock_recover(self):
        path=self.root/'Live/status.json';path.write_bytes(b'\xef\xbb\xbf'+b'{"protocol":1,"active":true}')
        with patch.object(Path,'open',side_effect=PermissionError('sharing violation')):
            self.assertIsNone(self.bridge.status(fresh=True))
        self.assertTrue(self.bridge.status(fresh=True)['active'])

    def test_valid_json_with_wrong_protocol_still_rejected(self):
        path=self.root/'Live/status.json';path.write_text('{"protocol":9}')
        with self.assertRaisesRegex(ValueError,'status.json'):self.bridge.status(fresh=True)

    def test_capture_mode_defaults_to_native_and_can_opt_into_compatibility(self):
        self.bridge.configure('zh','English','Simplified Chinese')
        data=json.loads((self.root/'Live/settings.json').read_text())
        self.assertFalse(data['compatibility_capture'])
        self.bridge.configure('zh','English','Simplified Chinese',compatibility_capture=True)
        self.assertTrue(json.loads((self.root/'Live/settings.json').read_text())['compatibility_capture'])

    def test_repaired_same_metadata_status_clears_prior_read_warning(self):
        path=self.root/'Live/status.json';valid=b'{"protocol":1,"active":true}'
        path.write_bytes(valid);self.bridge.status();original=path.stat()
        path.write_bytes(b'')
        with patch('live_bridge.time.monotonic',return_value=10):self.assertIsNone(self.bridge.status())
        path.write_bytes(valid);os.utime(path,ns=(original.st_atime_ns,original.st_mtime_ns))
        with patch('live_bridge.time.monotonic',return_value=14):self.assertIn('status.json',self.bridge.read_warning)
        self.assertTrue(self.bridge.status()['active']);self.assertEqual(self.bridge.read_warning,'')

    def project(self,n):
        project=Project(Report('fixture',[entry('Unseen item '+str(i)) for i in range(n)]))
        for unit in project.units:project.update(unit.id,'物品 '+unit.source.split()[-1])
        return project

    def request(self,session='one'):
        (self.root/'Live/requests.json').write_text(json.dumps({'protocol':1,'session_id':session,'request_id':session,
            'source_language':'English','target_language':'Simplified Chinese','response_mode':'delta-v1','records':[]}),encoding='utf-8')
        self.bridge.read_request()

    def response(self):return json.loads((self.root/'Live/response.json').read_text(encoding='utf-8'))

    def ack(self,packet,session='one'):
        (self.root/'Live/status.json').write_text(json.dumps({'protocol':1,'session_id':session,'applied_sequence':packet['sequence']}),encoding='utf-8')

    def test_idle_publish_does_not_rebuild_xml_or_write_files(self):
        project=self.project(2000);self.bridge.publish(project,'one',True)
        with patch('live_bridge.atomic_write') as write,patch('workbench.native_xml',side_effect=AssertionError('idle XML rebuilt')):
            for _ in range(50):self.bridge.publish(project,'one',True)
        write.assert_not_called()

    def test_large_backlog_selects_same_priority_order_with_bounded_top_k(self):
        self.request();project=self.project(2000)
        self.bridge._sync(project,True)
        for index,source in enumerate(self.bridge._literals):self.bridge._priorities[source]=index%4
        expected=sorted(self.bridge._literals,key=lambda source:(self.bridge._priorities[source],source))
        received=[]
        for _ in range(3):
            self.bridge.publish(project,'one',True);packet=self.response()
            received.extend(packet['translations']);self.ack(packet)
        self.assertEqual(received,expected[:24])

    def test_eight_removals_do_not_hide_waiting_translation(self):
        self.request();project=self.project(8);self.bridge.publish(project,'one',True)
        packet=self.response();self.ack(packet)
        for unit in project.units:project.update(unit.id,'')
        project.merge_live(Report('isolated',[entry('Brand new tool')]))
        unit=next(u for u in project.units if u.source=='Brand new tool');project.update(unit.id,'全新工具')
        self.bridge.publish(project,'one',True);packet=self.response()
        self.assertEqual(len(packet['removed']),8);self.assertFalse(packet['complete']);self.ack(packet)
        self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['translations'],{'Brand new tool':'全新工具'})

    def test_unacknowledged_delta_is_not_overwritten_and_all_chunks_arrive(self):
        self.request();project=self.project(25);received={}
        self.bridge.publish(project,'one',True)
        first=self.response();self.assertEqual(len(first['translations']),8)
        project.update(project.units[20].id,'更新物品')
        self.bridge.publish(project,'one',True);self.assertEqual(self.response(),first)
        packet=first
        for _ in range(8):
            self.assertLessEqual(len(packet['translations'])+len(packet['removed']),8)
            received.update(packet['translations']);self.ack(packet)
            self.bridge.publish(project,'one',True);next_packet=self.response()
            if next_packet['sequence']==packet['sequence']:break
            self.assertEqual(next_packet['base_sequence'],packet['sequence']);packet=next_packet
        self.assertEqual(received,{u.source:u.translation for u in project.units})

    def test_wrong_session_ack_does_not_unlock_delta(self):
        self.request();project=self.project(20);self.bridge.publish(project,'one',True)
        first=self.response();self.ack(first,'stale')
        self.bridge.publish(project,'two',True);self.assertEqual(self.response(),first)

    def test_same_metadata_in_place_ack_cannot_stall_next_packet(self):
        self.request();project=self.project(20);self.bridge.publish(project,'one',True)
        status=self.root/'Live/status.json';fixed=1_700_000_000_000_000_000
        first=self.response();self.ack(first);os.utime(status,ns=(fixed,fixed))
        self.bridge.publish(project,'one',True);second=self.response()
        self.assertEqual(second['sequence'],2)
        stamp=(status.stat().st_mtime_ns,status.stat().st_size,status.stat().st_ino)
        self.ack(second);os.utime(status,ns=(fixed,fixed))
        self.assertEqual((status.stat().st_mtime_ns,status.stat().st_size,status.stat().st_ino),stamp)
        self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['sequence'],3)
        self.assertEqual(len(self.response()['translations']),4)

    def test_restart_resets_delta_sequence_and_replays_cache(self):
        self.request();project=self.project(10);self.bridge.publish(project,'one',True)
        first=self.response();self.ack(first);self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['sequence'],2)
        self.request('new');self.bridge.publish(project,'new',True)
        latest=self.response();self.assertEqual(latest['sequence'],1);self.assertTrue(latest['reset'])
        self.assertEqual(len(latest['translations']),8)

    def test_manual_removal_is_transmitted_and_empty_project_clears_legacy(self):
        self.request();project=self.project(1);self.bridge.publish(project,'one',True)
        self.ack(self.response());project.update(project.units[0].id,'',state='忽略')
        self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['removed'],[project.units[0].source])
        legacy=LiveBridge(self.root);project=self.project(1)
        legacy.publish(project,'one',True);legacy.publish(Project(Report('empty')),'one',True)
        self.assertFalse(self.response()['translations'])

    def test_merged_live_import_preserves_edits_and_reports_only_touched_ids(self):
        project=self.project(1000);old_revision=project.revision;old=project.units[0]
        touched=project.merge_live(Report('fixture',[entry(old.source,priority=0),entry('Brand new item')]))
        self.assertIs(project.by_id[old.id],old);self.assertTrue(old.translation)
        self.assertEqual(len(project.units),1001);self.assertEqual(len(touched),2)
        self.assertEqual(project.changes_since(old_revision),touched)
        project.merge_live(Report('fixture',[entry('Brand new item')]))
        self.assertEqual(len(project.units),1001)

    def test_journal_overflow_falls_back_to_full_sync_without_losing_edits(self):
        project=self.project(2);self.bridge.publish(project,'one',True)
        for i in range(2100):project.update(project.units[0].id,'物品 '+str(i))
        self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['translations'][project.units[0].source],'物品 2099')

    def test_conflicting_homonyms_are_not_applied_as_global_literal(self):
        a=entry('Same term',key='entityname.a');b=entry('Same term',key='entityname.b')
        project=Project(Report('fixture',[a,b]));project.split_context(project.units[0].id)
        for unit,target in zip(project.units,['第一义','第二义']):project.update(unit.id,target)
        self.bridge.publish(project,'one',True)
        self.assertNotIn('Same term',self.response()['translations'])

    def test_barotrauma_affliction_does_not_globally_rename_game_title(self):
        project=Project(Report('fixture',[entry('Barotrauma','afflictionname.pressure')]))
        project.update(project.units[0].id,'恶性水压创伤')
        self.bridge.publish(project,'one',True)
        self.assertEqual(self.response()['keys'],1);self.assertNotIn('Barotrauma',self.response()['translations'])
