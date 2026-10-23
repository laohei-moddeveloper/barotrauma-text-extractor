"""Local, attributed human translations. No network and no third-party execution."""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import xml.etree.ElementTree as ET

from languages import canonical_language
from workbench import quality

MAX_FILE=16*1024*1024


def read_xml(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE:raise ValueError('XML is missing, linked or too large')
    with path.open('rb') as stream:raw=stream.read(MAX_FILE+1)
    if len(raw)>MAX_FILE:raise ValueError('XML is too large')
    # Decode before checking: UTF-16 declarations must not bypass the DTD guard.
    from extractor import decode
    text=decode(raw)
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',text,re.I):raise ValueError('DTD/entities are not supported')
    return ET.fromstring(text),hashlib.sha256(raw).hexdigest()


def language_entries(pack):
    # Barotrauma's <Override> contains normal text keys, not one large string.
    for node in pack:
        if str(node.tag).casefold()=='override':yield from language_entries(node)
        elif isinstance(node.tag,str):yield node


def package_info(root):
    root=Path(root)
    if root.is_symlink():raise ValueError('Linked package directory')
    tree,digest=read_xml(root/'filelist.xml')
    return {'id':tree.get('steamworkshopid','') or (root.name if root.name.isdigit() else ''),
            'name':tree.get('name',''),'version':tree.get('modversion',''),'digest':digest}


def catalog(root,language):
    """Read listed XML only; native language keys and literal prefab fields."""
    root=Path(root).resolve();manifest,_=read_xml(root/'filelist.xml')
    files={str(p.relative_to(root)).replace('\\','/').casefold():p for p in root.rglob('*.xml') if not p.is_symlink()}
    if len(files)>10000:raise ValueError('单个模组 XML 文件过多')
    rows=defaultdict(set);hashes=[];issues=[]
    def add(key,text):
        if not key or not text:return
        text=text.replace('\\n','\n').strip()
        if text and len(text)<=20000:rows[key.casefold()].add(text)
    for entry in manifest:
        relative=entry.get('file','').replace('\\','/')
        if relative.startswith('%ModDir%/'):relative=relative[len('%ModDir%/'):]
        if '%' in relative or Path(relative).is_absolute() or '..' in Path(relative).parts:continue
        path=files.get(relative.casefold())
        if path is None or root not in path.resolve().parents:continue
        if any(parent.is_symlink() for parent in path.parents if parent!=root and root in parent.parents):continue
        try:tree,digest=read_xml(path)
        except (OSError,ValueError,ET.ParseError) as error:issues.append({'file':relative,'error':str(error)});continue
        hashes.append((relative,digest))
        packs=[n for n in tree.iter() if n.tag.casefold() in {'infotexts','infotext'}]
        if packs:
            for pack in packs:
                if canonical_language(pack.get('language',''))!=language:continue
                for node in language_entries(pack):
                    if isinstance(node.tag,str):add(node.tag,''.join(node.itertext()))
        elif language=='English':
            for node in tree.iter():
                tag=node.tag.casefold() if isinstance(node.tag,str) else ''
                identity=node.get('identifier') or node.get('speciesname')
                if not identity:continue
                prefixes={'item':('entityname.','entitydescription.'),'character':('entityname.','entitydescription.'),
                          'affliction':('afflictionname.','afflictiondescription.'),'job':('jobname.','jobdescription.')}
                if tag in prefixes:
                    for field,prefix in zip(('name','description'),prefixes[tag]):
                        text=node.get(field,'')
                        if text and re.search('[A-Za-z]',text) and not re.search('[\u3400-\u9fff]',text):
                            key_id=node.get(field+'identifier') or identity
                            add(prefix+key_id,text)
                            if tag=='character' and field=='name':add('character.'+identity,text)
    return rows,hashes,issues


class HumanMemory:
    def __init__(self,path=None):
        self.path=Path(path) if path else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'AbyssText'/'human-memory.sqlite3'
        self.lock=threading.RLock();self.connection=None;self.available=self.path.is_file() and not self.path.is_symlink()

    def close(self):
        with self.lock:
            if self.connection is not None:self.connection.close();self.connection=None

    def lookup(self,unit,target):
        if not self.available or unit.source_language!='English' or target not in {'Simplified Chinese','Traditional Chinese'}:return None
        scopes=set()
        for e in getattr(unit,'occurrences',[]):
            # A malformed explicit owner must not broaden a scoped lookup.
            if e.location.get('mod_scope_invalid'):return None
            scope=e.location.get('mod_id','')
            if isinstance(scope,str) and scope:scopes.add(scope)
            parts=str(e.file).replace('\\','/').split('/')
            scopes.update(part for part in parts if part.isdigit() and len(part)>=8)
        keys=tuple(getattr(unit,'keys',[]) or [])[:8]
        # No unscoped single-word guessing. Long complete prose may be reused
        # only if every indexed match agrees; short labels need a key or owner.
        if not scopes and not keys and len(unit.source.strip())<24:return None
        sql='SELECT translation,provider FROM pairs WHERE source=? AND language=?'
        values=[unit.source.strip(),target]
        if scopes:
            sql+=' AND scope IN ('+','.join('?' for _ in scopes)+')';values+=sorted(scopes)
        if keys:
            sql+=' AND key IN ('+','.join('?' for _ in keys)+')';values +=[k.casefold() for k in keys]
        sql+=' GROUP BY translation LIMIT 2'
        try:
            with self.lock:
                if self.path.is_symlink():return None
                if self.connection is None:self.connection=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,check_same_thread=False)
                rows=self.connection.execute(sql,values).fetchall()
        except (OSError,sqlite3.Error):return None
        if len(rows)!=1:return None
        text,provider=rows[0]
        text=unit.source[:len(unit.source)-len(unit.source.lstrip())]+text+unit.source[len(unit.source.rstrip()):]
        if quality(unit.source,text):return None
        return {unit.id:{'translation':text,'issues':[],'origin':'本地人工汉化缓存 · 工坊 '+provider}}

    def replace(self,records,report):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.is_symlink():raise ValueError('Human cache cannot be a symbolic link')
        with self.lock:
            self.close()
            connection=sqlite3.connect(self.path)
            try:
                connection.executescript('CREATE TABLE IF NOT EXISTS pairs(scope TEXT,key TEXT,source TEXT,language TEXT,translation TEXT,provider TEXT,source_hash TEXT,target_hash TEXT,PRIMARY KEY(scope,key,source,language,translation,provider)); CREATE INDEX IF NOT EXISTS source_lookup ON pairs(source,language,scope,key); CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);')
                with connection:
                    connection.execute('DELETE FROM pairs')
                    connection.executemany('INSERT OR IGNORE INTO pairs VALUES(?,?,?,?,?,?,?,?)',records)
                    report['records']=connection.execute('SELECT COUNT(*) FROM pairs').fetchone()[0]
                    connection.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('import',json.dumps(report,ensure_ascii=False)))
                count=connection.execute('SELECT COUNT(*) FROM pairs').fetchone()[0]
            finally:connection.close()
            self.available=True
        return count


def build_memory(roots,memory,rules):
    """Join exact keys inside explicit mod routes; conflicting variants stay out."""
    packages={};report={'packages':[],'routes':[],'issues':[],'rejected_quality':0,'ambiguous_keys':0}
    for root in roots:
        root=Path(root)
        if root.is_symlink():continue
        try:info=package_info(root)
        except (OSError,ValueError,ET.ParseError):continue
        if info['id']:packages[info['id']]=(root,info);report['packages'].append(info)
    english={};records=[];chinese={}
    for rule in rules:
        provider=packages.get(rule['provider'])
        if provider is None:continue
        p_root,p_info=provider
        for language in ('Simplified Chinese','Traditional Chinese'):
            for scope in rule.get('targets',[]):
                source=packages.get(scope)
                if source is None:continue
                s_root,s_info=source
                if scope not in english:english[scope]=catalog(s_root,'English')
                sources,s_hash,s_issues=english[scope]
                # A route can name one or more translation files, rather than
                # leaking a whole multi-mod bundle into each target mod.
                selected=tuple(rule.get('files',[]))
                cache_key=(rule['provider'],language,selected)
                if cache_key not in chinese:
                    if selected:
                        tables=defaultdict(set);hashes=[];issues=[]
                        for filename in selected:
                            path=p_root/filename
                            if Path(filename).is_absolute() or '..' in Path(filename).parts or p_root.resolve() not in path.resolve().parents:continue
                            if any(parent.is_symlink() for parent in path.parents if parent!=p_root and p_root in parent.parents):continue
                            try:tree,digest=read_xml(path)
                            except (OSError,ValueError,ET.ParseError) as error:issues.append({'file':filename,'error':str(error)});continue
                            hashes.append((filename,digest))
                            for pack in tree.iter():
                                if str(pack.tag).casefold() in {'infotexts','infotext'} and canonical_language(pack.get('language',''))==language:
                                    for node in language_entries(pack):
                                        text=''.join(node.itertext()).replace('\\n','\n').strip()
                                        if text and len(text)<=20000:tables[node.tag.casefold()].add(text)
                        chinese[cache_key]=(tables,hashes,issues)
                    else:chinese[cache_key]=catalog(p_root,language)
                targets,t_hash,t_issues=chinese[cache_key]
                sh=hashlib.sha256(json.dumps(s_hash,sort_keys=True).encode()).hexdigest()
                th=hashlib.sha256(json.dumps(t_hash,sort_keys=True).encode()).hexdigest()
                matched=0
                for key in sorted(sources.keys() & targets.keys()):
                    left,right=sources[key],targets[key]
                    if len(left)!=1 or len(right)!=1:report['ambiguous_keys']+=1;continue
                    original=next(iter(left));translated=next(iter(right))
                    if language=='Simplified Chinese' and not re.search('[\u3400-\u9fff]',translated):continue
                    if quality(original,translated):report['rejected_quality']+=1;continue
                    if len(records)>=200000:raise ValueError('缓存超过 20 万条，请缩小导入范围')
                    records.append((scope,key,original,language,translated,rule['provider'],sh,th));matched+=1
                report['routes'].append({'provider':rule['provider'],'scope':scope,'language':language,'matched':matched})
                report['issues'].extend({'provider':scope,**issue} for issue in s_issues)
                report['issues'].extend({'provider':rule['provider'],**issue} for issue in t_issues)
    report['records']=memory.replace(records,report) if records else 0
    return report


def source_registry():
    import sys
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return json.loads((root/'assets'/'human-translation-sources.json').read_text(encoding='utf-8'))


def import_folder(folder,memory):
    """Read a mod library's immediate packages, never execute its contents."""
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir():raise ValueError('请选择本地模组库目录')
    roots=[folder] if (folder/'filelist.xml').is_file() else sorted(
        (p for p in folder.iterdir() if p.is_dir() and not p.is_symlink()),key=lambda p:p.name)
    if len(roots)>2000:raise ValueError('模组目录超过 2000 个，请缩小范围')
    if memory.path.resolve().is_relative_to(folder.resolve()):raise ValueError('缓存必须保存在模组目录外')
    report=build_memory(roots,memory,source_registry()['rules'])
    if not report['records']:raise ValueError('未找到可靠双语配对；请把原模组和汉化包放在同一模组库，原缓存已保留')
    return report
