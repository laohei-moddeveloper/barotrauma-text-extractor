"""User-selected local file bridge; no HTTP listener and no source mod rewriting."""
import hashlib
from dataclasses import replace
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from languages import canonical_language
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

    def configure(self, ui_language, source_language, target_language):
        path=self.data/"settings.json"
        if path.is_symlink():raise ValueError("桥接输出不允许符号链接")
        atomic_write(path,json.dumps({"ui_language":ui_language,"source_language":canonical_language(source_language),
            "target_language":canonical_language(target_language)},ensure_ascii=False))

    def read_request(self):
        path = self.data/"requests.json"
        if not path.exists(): return None
        if path.is_symlink() or path.stat().st_size>8*1024*1024: raise ValueError("无效或过大的游戏内请求")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest==self.seen: return None
        data = json.loads(raw)
        if not isinstance(data,dict) or data.get("protocol")!=1 or not isinstance(data.get("records"),list): raise ValueError("不支持的桥接协议")
        if len(data["records"])>10000: raise ValueError("单次游戏内请求超过 10000 条")
        report = Report(str(self.root))
        if not isinstance(data.get("source_language","English"),str) or not isinstance(data.get("request_id",""),str):raise ValueError("无效的游戏内请求元数据")
        for index,record in enumerate(data["records"]):
            if not isinstance(record,dict):raise ValueError("无效的游戏内文字记录")
            text, key = record.get("text"), record.get("key","")
            if not isinstance(text,str) or not isinstance(key,str) or len(text)>20000: raise ValueError("无效的游戏内文字记录")
            if not text.strip() or not any(c.isalpha() for c in text): continue
            report.entries.append(Entry(source_id(text)+str(index),"<游戏内>",index+1,1,"游戏内显示","literal",text,
                key=key,language=canonical_language(data.get("source_language","English")),context="当前已加载语言键" if key else "当前原生 GUI 控件文字",
                evidence="LuaCs 客户端采集；动态文字只代表此次观察值",location={"native_key":key} if key else {}))
        self.seen = digest
        return report, bool(data.get("translate")), data.get("request_id",digest)

    def publish(self, project, request_id, drafts=False, complete=True):
        from types import SimpleNamespace
        observed = [replace(u,occurrences=[e for e in u.occurrences if e.file=="<游戏内>"])
                    for u in project.units if any(e.file=="<游戏内>" for e in u.occurrences)]
        content, reasons, count = native_xml(SimpleNamespace(units=observed,target_language=project.target_language),include_drafts=drafts)
        # Hardcoded native controls consume literal translations, never an overlay.
        literals = {}
        for unit in observed:
            if not unit.translation or unit.state=="忽略" or quality(unit.source,unit.translation): continue
            if unit.state!="已校对" and not drafts: continue
            literals[unit.source] = unit.translation
        for name in ["Translations.xml","response.json"]:
            if (self.data/name).is_symlink(): raise ValueError("桥接输出不允许符号链接")
        atomic_write(self.data/"Translations.xml",content)
        atomic_write(self.data/"response.json",json.dumps({"protocol":1,"request_id":request_id,
            "revision":hashlib.sha256((content+json.dumps(literals,ensure_ascii=False)).encode()).hexdigest(),
            "translations":literals,"keys":count,"drafts":drafts,"complete":complete},ensure_ascii=False))
        return count,len(literals),reasons
