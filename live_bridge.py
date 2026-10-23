"""User-selected local file bridge; no HTTP listener and no source mod rewriting."""
import hashlib
import heapq
from dataclasses import replace
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

from languages import canonical_language, already_target_chinese
from extractor import Entry, Report
from workbench import atomic_write, native_xml, source_id, quality


class LiveBridge:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        metadata = self.root/"filelist.xml"
        if metadata.is_symlink() or not metadata.is_file(): raise ValueError("请选择安装后的 AbyssTextLive 插件目录")
        if "abysstextlive" not in metadata.read_text(encoding="utf-8-sig").casefold():
            raise ValueError("目录不是 AbyssTextLive 插件，拒绝写入")
        self.data = self.root/"Live"
        if self.data.is_symlink(): raise ValueError("桥接目录不能是符号链接")
        self.data.mkdir(exist_ok=True)
        self.seen = ""
        self.session_id = ""
        self.source_language = "English"
        self.target_language = "Simplified Chinese"
        self._request_stamp=None;self._status_stamp=None;self._status=None
        self._read_issues={}
        self.delta_mode=False;self._sequence=0;self._pending=None;self._delivered={};self._last_meta=None
        self._project=None;self._project_revision=-1;self._snapshot_version=0
        self._observed={};self._sources={};self._literals={};self._priorities={};self._keyed={}
        self._xml_dirty=True;self._xml_content='';self._xml_hash='';self._xml_count=0;self._notes=[];self._xml_at=0
        self._legacy_signature=None
        self._last_sent_snapshot=-1;self._delta_remaining=False

    def configure(self, ui_language, source_language, target_language, compatibility_capture=False):
        path=self.data/"settings.json"
        if path.is_symlink():raise ValueError("桥接输出不允许符号链接")
        atomic_write(path,json.dumps({"ui_language":ui_language,"source_language":canonical_language(source_language),
            "target_language":canonical_language(target_language),"compatibility_capture":bool(compatibility_capture)},ensure_ascii=False))

    @property
    def read_warning(self):
        # Normal Lua File.Write briefly truncates the mailbox. Do not turn
        # a normal racing read into a modal error; sustained damage stays visible.
        now=time.monotonic()
        names=[name for name,(since,_) in self._read_issues.items() if now-since>=3]
        return '等待游戏桥接文件写入完整：'+', '.join(sorted(names)) if names else ''

    def _snapshot(self,path,limit):
        """One bounded, nonblocking attempt. No ACK/cache advances on failure."""
        try:
            if path.is_symlink():raise ValueError('桥接输入不允许符号链接：'+path.name)
            before=path.stat()
            if before.st_size>limit:raise ValueError('游戏桥接文件过大：'+path.name)
            with path.open('rb') as stream:raw=stream.read(limit+1)
            after=path.stat()
            if len(raw)>limit:raise ValueError('游戏桥接文件过大：'+path.name)
            stamp=lambda st:(st.st_mtime_ns,st.st_size,st.st_ino)
            if stamp(before)!=stamp(after) or len(raw)!=after.st_size:raise json.JSONDecodeError('文件正在更新','',0)
            data=json.loads(raw)
        except (OSError,UnicodeError,json.JSONDecodeError):
            self._read_issues.setdefault(path.name,(time.monotonic(),'incomplete'))
            return None
        self._read_issues.pop(path.name,None)
        return data,stamp(after),hashlib.sha256(raw).hexdigest()

    def status(self, fresh=False):
        path=self.data/'status.json'
        if not path.exists():return None
        if path.is_symlink() or path.stat().st_size>16384:raise ValueError('无效的游戏桥接状态文件：status.json')
        stamp=(path.stat().st_mtime_ns,path.stat().st_size,path.stat().st_ino)
        if not fresh and stamp==self._status_stamp and path.name not in self._read_issues:return self._status
        snapshot=self._snapshot(path,16384)
        if snapshot is None:return None
        data,stamp,_=snapshot
        if not isinstance(data,dict) or data.get('protocol')!=1:raise ValueError('不支持的游戏桥接状态协议：status.json')
        self._status_stamp,self._status=stamp,data
        return data

    def read_request(self):
        path = self.data/"requests.json"
        if not path.exists(): return None
        if path.is_symlink() or path.stat().st_size>1024*1024: raise ValueError("无效或过大的游戏内请求")
        stat=path.stat();stamp=(stat.st_mtime_ns,stat.st_size,stat.st_ino)
        if stamp==self._request_stamp and path.name not in self._read_issues:return None
        snapshot=self._snapshot(path,1024*1024)
        if snapshot is None:return None
        data,stamp,digest=snapshot
        if digest==self.seen:self._request_stamp=stamp;return None
        if not isinstance(data,dict) or data.get("protocol")!=1 or not isinstance(data.get("records"),list): raise ValueError("不支持的桥接协议")
        if len(data["records"])>8: raise ValueError("单次游戏内请求最多 8 条；请使用配套版本插件")
        report = Report(str(self.root))
        if any(not isinstance(data.get(k,default),str) or len(data.get(k,default))>256 for k,default in
               [('source_language','English'),('target_language','Simplified Chinese'),('request_id',''),('session_id','')]):
            raise ValueError("无效的游戏内请求元数据")
        for index,record in enumerate(data["records"]):
            if not isinstance(record,dict):raise ValueError("无效的游戏内文字记录")
            text, key = record.get("text"), record.get("key","")
            if not isinstance(text,str) or not isinstance(key,str) or len(text)>20000 or len(key)>256: raise ValueError("无效的游戏内文字记录")
            if not text.strip() or not any(c.isalpha() for c in text): continue
            if already_target_chinese(text,data.get('source_language','English'),data.get('target_language','Simplified Chinese')):continue
            context=record.get('context','当前已加载语言键' if key else '当前原生 GUI 控件文字')
            if not isinstance(context,str) or len(context)>120:raise ValueError('无效的游戏内语境')
            # Owner metadata is optional. Native GUI text has no owning mod;
            # some LuaCs JSON serializers emit null for that missing value.
            # Never reject otherwise valid text because provenance is absent.
            raw_mod_id=record.get('mod_id')
            mod_id='' if raw_mod_id is None else raw_mod_id
            if type(mod_id) is int and 10000000<=mod_id<=9007199254740991:mod_id=str(mod_id)
            invalid_scope=not isinstance(mod_id,str) or bool(mod_id and (not mod_id.isascii() or not mod_id.isdigit() or not 8<=len(mod_id)<=20))
            if invalid_scope:mod_id=''
            priority=record.get('priority',2 if key else 1)
            if not isinstance(priority,int) or priority not in range(4):priority=2
            report.entries.append(Entry(source_id(text)+str(index),"<游戏内>",index+1,1,"游戏内显示","literal",text,
                key=key,language=canonical_language(data.get("source_language","English")),context=context,
                evidence="LuaCs 客户端采集；动态文字只代表此次观察值",location={"native_key":key,"live_priority":priority,"mod_id":mod_id,"mod_scope_invalid":invalid_scope}))
        delta_mode=data.get('response_mode')=='delta-v1'
        pair=(canonical_language(data.get('source_language','English')),canonical_language(data.get('target_language','Simplified Chinese')))
        if (self.session_id,self.source_language,self.target_language,self.delta_mode)!=(data.get('session_id',''),*pair,delta_mode):
            self._sequence=0;self._pending=None;self._delivered={};self._last_meta=None;self._legacy_signature=None
        self.delta_mode=delta_mode
        self._request_stamp=stamp
        self.seen = digest
        self.session_id=str(data.get('session_id',''))
        self.source_language=canonical_language(data.get('source_language','English'))
        self.target_language=canonical_language(data.get('target_language','Simplified Chinese'))
        return report, bool(data.get("translate")), data.get("request_id",digest)

    def _sync(self, project, drafts):
        changed=project.changes_since(self._project_revision) if self._project is project and getattr(self,'_drafts',None)==drafts else None
        full=changed is None
        if full:
            self._observed={};self._sources={};self._literals={};self._priorities={};self._keyed={};self._xml_dirty=True
            changed={u.id for u in project.units}
        for uid in changed:
            old=self._observed.pop(uid,None)
            if old:
                candidates=self._sources.get(old.source,{})
                candidates.pop(uid,None)
                self._literals.pop(old.source,None)
                if len(set(candidates.values()))==1:self._literals[old.source]=next(iter(candidates.values()))
            previous_keyed=self._keyed.pop(uid,None)
            unit=project.by_id.get(uid)
            observed=replace(unit,occurrences=[e for e in unit.occurrences if e.file=='<游戏内>']) if unit else None
            if observed and observed.occurrences:
                self._observed[uid]=observed
                self._priorities[unit.source]=min(e.location.get('live_priority',2) for e in observed.occurrences)
                if observed.keys:self._keyed[uid]=observed
                candidates=self._sources.setdefault(unit.source,{})
                if unit.source.casefold()!='barotrauma' and unit.translation and unit.state!='忽略' and not quality(unit.source,unit.translation) and (drafts or unit.state=='已校对'):
                    candidates[uid]=unit.translation
                self._literals.pop(unit.source,None)
                if len(set(candidates.values()))==1:self._literals[unit.source]=next(iter(candidates.values()))
            if previous_keyed is not None or uid in self._keyed:self._xml_dirty=True
        if full or changed:self._snapshot_version+=1
        self._project=project;self._project_revision=project.revision;self._drafts=drafts

    def _xml(self, project):
        from types import SimpleNamespace
        if self._xml_dirty and (not self.delta_mode or not self._xml_content or time.monotonic()-self._xml_at>=2):
            content,notes,count=native_xml(SimpleNamespace(units=list(self._keyed.values()),target_language=project.target_language),include_drafts=self._drafts)
            self._xml_content=content;self._xml_hash=hashlib.sha256(content.encode()).hexdigest()
            self._xml_count=count;self._notes=notes;self._xml_dirty=False;self._xml_at=time.monotonic()

    def _write(self, packet):
        for name in ['Translations.xml','response.json']:
            if (self.data/name).is_symlink():raise ValueError('桥接输出不允许符号链接')
        if getattr(self,'written_language_revision',None)!=self._xml_hash:
            atomic_write(self.data/'Translations.xml',self._xml_content)
            self.written_language_revision=self._xml_hash
        atomic_write(self.data/'response.json',json.dumps(packet,ensure_ascii=False))

    def publish(self, project, request_id, drafts=False, complete=True, progress=None):
        self._sync(project,drafts)
        result=lambda:(self._xml_count,len(self._literals),self._notes)
        progress=progress or {}
        if self.delta_mode and self._pending:
            # Lua writes status in place. Same-size ACKs may share a timestamp
            # on Windows; metadata alone must never suppress a protocol ACK.
            status=self.status(fresh=True) or {}
            if status.get('session_id')!=self.session_id or type(status.get('applied_sequence')) is not int or status['applied_sequence']!=self._pending['sequence']:
                return result() # Never overwrite an unacknowledged delta.
            self._delivered.update(self._pending['translations'])
            for source in self._pending['removed']:self._delivered.pop(source,None)
            self._pending=None
        self._xml(project)
        packet={'protocol':1,'request_id':request_id,'session_id':self.session_id,
            'source_language':project.source_language,'target_language':project.target_language,
            'keys':self._xml_count,'drafts':drafts,'complete':complete,
            'language_revision':self._xml_hash,'progress':progress}
        if self.delta_mode:
            wanted_meta=(request_id,complete and not self._xml_dirty,self._xml_hash,json.dumps(progress,sort_keys=True),drafts)
            if self._last_sent_snapshot==self._snapshot_version and not self._delta_remaining and wanted_meta==self._last_meta:return result()
            removed=[source for source in self._delivered if source not in self._literals][:8]
            # Only eight records can enter a packet. Keep at most eight
            # candidates instead of sorting/allocating the entire backlog.
            changed_count=0
            def changes():
                nonlocal changed_count
                for source,target in self._literals.items():
                    if self._delivered.get(source)!=target:
                        changed_count+=1;yield source
            changed=heapq.nsmallest(8-len(removed),changes(),key=lambda source:(self._priorities.get(source,2),source))
            translated={source:self._literals[source] for source in changed}
            # nsmallest(0) does not consume its iterator. Removals fill this
            # packet; conservatively continue if any literals remain changed.
            remaining=(changed_count>len(translated) if len(removed)<8 else
                any(self._delivered.get(source)!=target for source,target in self._literals.items())) or any(source not in self._literals and source not in removed for source in self._delivered)
            packet['complete']=complete and not remaining and not self._xml_dirty
            meta=(request_id,packet['complete'],self._xml_hash,json.dumps(progress,sort_keys=True),drafts)
            if not translated and not removed and meta==self._last_meta:return result()
            sequence=self._sequence+1
            packet.update(delta=True,sequence=sequence,base_sequence=self._sequence,reset=sequence==1,
                revision=str(sequence),translations=translated,removed=removed)
            self._write(packet)
            self._sequence=sequence;self._pending=packet;self._last_meta=meta
            self._last_sent_snapshot=self._snapshot_version;self._delta_remaining=remaining
        else:
            signature=(self._snapshot_version,request_id,complete,self._xml_hash,json.dumps(progress,sort_keys=True),drafts)
            if signature==self._legacy_signature:return result()
            packet.update(translations=self._literals,revision=hashlib.sha256((self._xml_hash+json.dumps(self._literals,ensure_ascii=False)).encode()).hexdigest())
            self._write(packet);self._legacy_signature=signature
        return result()
